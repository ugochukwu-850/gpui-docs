---
title: App-wide state and design patterns
description: How to store state that exists once per app with the Global trait, when to pick a global over an entity, and the architecture patterns the GPUI examples and the ui crate use.
sidebar:
  order: 7
  label: Globals and patterns
---

:::note[Advanced]
This page is for readers who have finished the beginner path and are deciding where a piece of state should live. Read [Thinking in GPUI](/start/thinking-in-gpui/) and [State and views](/guides/state-and-views/) first. [Entities](/deep-dive/entities/) will also help.
:::

Entities hold state that has an identity: *this* document, *that* panel. Some state is naturally one-per-app: the theme, the settings, a registry, the asset source. GPUI stores that as **globals**, one value per Rust type, kept on the `App`.

If you know React, a global is a little like a context provider at the root of the app, or a module-level singleton. The difference is that the `App` owns it and you read it through `cx`.

:::tip[In short]
- A global is one value per Rust type. Mark the type with `impl Global for T {}`, store it with `cx.set_global`, and read it with `cx.global::<T>()`.
- Reading a global in `render` does **not** make the view redraw when it changes. You must `observe_global` (and `cx.notify()`), or refresh the window yourself.
- Use a global for "the one" of something. Use an entity for anything with several instances, a lifetime, or events.
:::

```text
 App
 +-- globals:  TypeId -> value        "the theme", "the settings"   (one per type)
 +-- entities: EntityId -> value      "this editor", "that panel"   (many per type)
```

## The `Global` trait

`Global` is a marker trait. A marker trait has no methods. It just labels a type as allowed.

```rust
pub trait Global: 'static {}
```

Implement it on a type to allow storing it. The accessor methods are bounded by it, so trying to store a random type is a compile error.

```rust
struct AppState {
    view_mode: ViewMode,
}
impl Global for AppState {}
```

### Accessors on `App` (and anything that derefs to it)

| Method | Behaviour |
| --- | --- |
| `cx.set_global(value)` | Inserts or replaces the global of that type. |
| `cx.global::<G>() -> &G` | Reads. **Panics** with `no state of type G exists` if unset. |
| `cx.try_global::<G>() -> Option<&G>` | Reads without panicking. |
| `cx.has_global::<G>() -> bool` | Presence check. |
| `cx.global_mut::<G>() -> &mut G` | Mutable access. Panics if unset. |
| `cx.default_global::<G>() -> &mut G` | Mutable access. Inserts `G::default()` first if missing (needs `G: Default`). |
| `cx.update_global::<G, R>(\|g, cx\| ...)` | Runs a closure with `&mut G` **and** `&mut cx` at the same time (from `BorrowAppContext`). |
| `cx.update_default_global::<G, R>(..)` | The same, creating a default first. |
| `cx.remove_global::<G>() -> G` | Removes and returns it. Panics if unset. |

Two convenience traits are implemented for every `Global`:

- `ReadGlobal::global(cx: &App) -> &Self`, so you can write `AppState::global(cx)`.
- `UpdateGlobal::update_global(cx, |this, cx| ...)` and `UpdateGlobal::set_global(cx, value)`.

Async contexts have their own helpers. `AsyncApp` has `read_global`, `try_read_global`, `read_default_global`, `update_global` and `has_global`. `AsyncWindowContext` forwards `read_global` and `update_global`.

### The mutable-access trap

Why does `update_global` exist when `global_mut` does the same job? Because `cx.global_mut::<G>()` holds `&mut cx` for as long as the reference lives. You cannot use `cx` for anything else in that time.

`update_global` solves this by *leasing* the value out of the map for the duration of the closure, just as `Entity::update` does. In plain words, it takes the value out, runs your closure, and puts it back.

```rust
cx.update_global::<AppState, _>(|state, cx| {
    state.view_mode.toggle();
    set_app_menus_from(state, cx);   // free to use cx here
});
```

The flip side is the same as for entities. Inside the closure the global is **not in the map**. Calling `cx.global::<AppState>()` (or `update_global` again) from within panics, because the lease helper reports `no global registered of type ...`.

## Observing globals

Every function that changes a global queues a `NotifyGlobalObservers` effect for that type. These are `set_global`, `global_mut`, `default_global`, `update_global` and (despite its doc comment saying otherwise) `remove_global`. Register interest with `observe_global`:

```rust
// On App:
let sub = cx.observe_global::<Theme>(|cx: &mut App| { /* ... */ });

// On Context<T>: callback gets &mut T and the entity's context.
let sub = cx.observe_global::<Theme>(|this: &mut Self, cx: &mut Context<Self>| {
    this.rebuild_styles(cx);
    cx.notify();
});

// With a window:
let sub = cx.observe_global_in::<Theme>(window, |this, window, cx| { /* ... */ });
```

Rules to remember:

- **Reading a global in `render` does not subscribe the view to it.** GPUI tracks dependencies for entities only. A view that displays a global must `observe_global` (and call `cx.notify()`). Otherwise you refresh the windows yourself with `cx.refresh_windows()` or `window.refresh()`. `ui::KeyBinding::set_default_visibility` does the latter after `set_global`.
- **`global_mut` notifies even if you only read through it.** The effect is queued when you call it. Use `global::<G>()` for reads.
- **Subscriptions cancel when dropped.** Like all subscriptions, the returned `Subscription` stops when you drop it, so `.detach()` it or store it. `Context::observe_global` observers remove themselves once the observing entity is gone.
- **Observers run later.** They run when the outermost update finishes (see [Effects are deferred to the end of the update](/deep-dive/ownership-and-data-flow/#effects-are-deferred-to-the-end-of-the-update)). GPUI merges duplicate notifications for the same type while one is pending.

## A settings-like pattern

Put plain data in a global. Wrap it for convenience. Observe it from the views that care.

```rust
#[derive(Clone)]
struct Settings {
    font_size: f32,
    show_line_numbers: bool,
}
impl Global for Settings {}

// Startup
cx.set_global(Settings { font_size: 14.0, show_line_numbers: true });

// Anywhere with &App
let size = cx.global::<Settings>().font_size;

// Change it. All observers run after this returns.
cx.update_global::<Settings, _>(|s, _| s.show_line_numbers = false);

// A view that depends on it
impl Editor {
    fn new(cx: &mut Context<Self>) -> Self {
        let sub = cx.observe_global::<Settings>(|_this, cx| cx.notify());
        Self { _settings_sub: sub }
    }
}
```

GPUI itself uses a stricter form of the same idea for colours (`crates/gpui/src/colors.rs`). It has a `GlobalColors(Arc<Colors>)` newtype (a struct that wraps one value), a `Colors::get_global(cx)` helper, and a `DefaultColors` extension trait on `App`. You call `cx.init_colors()` to install the default.

The `text` example copies that shape for its own `GlobalTextContext`. It is a newtype around `Arc<TextContext>`, with a `get_global` helper and an `ActiveTextContext` trait, so views can write `cx.text_context()`.

### Restricting access

The `Global` docs suggest using visibility: keep the stored type private and expose only functions. `ui::KeyBinding` does exactly this:

```rust
struct VimStyle(bool);                 // private
impl Global for VimStyle {}

impl KeyBinding {
    pub fn set_vim_mode(cx: &mut App, enabled: bool) { cx.set_global(VimStyle(enabled)); }
    pub fn is_vim_mode(cx: &App) -> bool { cx.try_global::<VimStyle>().is_some_and(|g| g.0) }
}
```

Note the use of `try_global` with a default. A global that may not have been installed should never be read with `global::<G>()`.

### Registries and extension traits

`ui::utils::retained_focus` hides a `#[derive(Default)] struct RetainedFocusRegistry` global behind an *extension trait* on `App`. An extension trait is a trait you write only to add methods to a type you do not own.

```rust
pub trait RetainedFocusExt {
    fn retained_focus_handle(&mut self) -> FocusHandle;
}
impl RetainedFocusExt for App {
    fn retained_focus_handle(&mut self) -> FocusHandle {
        let focus_handle = self.focus_handle();
        let registry = self.default_global::<RetainedFocusRegistry>();
        registry.handles.retain(|handle| handle.upgrade().is_some());
        registry.handles.push(focus_handle.downgrade());
        focus_handle
    }
}
```

`default_global` removes any "is it initialised yet?" ceremony. Because `Context<T>` derefs to `App`, `cx.retained_focus_handle()` works inside any entity.

## Globals versus entities

| | Global | Entity |
| --- | --- | --- |
| Instances | Exactly one per Rust type | Any number |
| Addressing | By type: `cx.global::<G>()` | By handle: `Entity<T>` |
| Change notification | `observe_global`, coarse (the whole value) | `observe` / `subscribe`, per entity, with typed events |
| Rendering dependency | **Not tracked.** Observe explicitly. | **Tracked** for the window when read during a draw |
| Lifetime | Until removed or the app exits | Until the last handle drops |
| Can emit events | No | Yes (`EventEmitter`) |
| Access inside its own update | Leased out: not available | Leased out: not available |

Use a global for configuration, the theme, keymap-like registries, a shared HTTP client wrapper, a feature flag set, or anything that is conceptually "the" one.

Use an entity for anything whose lifetime is tied to part of the UI, anything with more than one instance, anything that emits events, and state that views render from and need to be redrawn for.

A common bridge between the two is a global *holding an entity handle*:

```rust
struct GlobalStore(Entity<Store>);
impl Global for GlobalStore {}

cx.set_global(GlobalStore(cx.new(|_| Store::default())));
let store = cx.global::<GlobalStore>().0.clone();   // clone the handle, then use it normally
```

This gives you global reachability and entity notification, at the cost of one extra step.

## Assets and other app-level services

Not every app-wide dependency is a global. Some are configured on `Application` before it runs.

```rust
gpui_platform::application()
    .with_assets(Assets { base })       // impl AssetSource
    .with_http_client(client)
    .run(|cx: &mut App| { /* ... */ });
```

`AssetSource` is a two-method trait for embedded or on-disk resources. `svg().path(..)` uses it, and so does image loading of relative paths:

```rust
pub trait AssetSource: 'static + Send + Sync {
    fn load(&self, path: &str) -> Result<Option<Cow<'static, [u8]>>>;
    fn list(&self, path: &str) -> Result<Vec<SharedString>>;
}
```

The `svg` example implements it over a directory:

```rust
impl AssetSource for Assets {
    fn load(&self, path: &str) -> Result<Option<std::borrow::Cow<'static, [u8]>>> {
        fs::read(self.base.join(path))
            .map(|data| Some(std::borrow::Cow::Owned(data)))
            .map_err(|err| err.into())
    }
    fn list(&self, path: &str) -> Result<Vec<SharedString>> { /* read_dir */ }
}
```

The default source (`()`) loads nothing. Retrieve the configured one with `cx.asset_source()`, and fetch the HTTP client with `cx.http_client()`. Other `Application` builder methods are `with_quit_mode`, `with_windowing` and `with_restart_arguments`.

## Architecture patterns seen in the source

These patterns come from reading the examples and the `ui` crate. None of them is a rule. They are habits that fit GPUI's ownership model.

**1. Parent owns children and their subscriptions.** `ui::ContextMenu` builds a submenu entity and a subscription to its `DismissEvent` together, and returns both so the parent can store them:

```rust
let submenu = Self::build_submenu(builder, parent_entity, parent_depth, window, cx);
let dismiss_subscription = cx.subscribe(&submenu, |this, submenu, _: &DismissEvent, cx| {
    let should_dismiss_parent = submenu.read(cx).clicked;
    this.close_submenu(false, cx);
    if should_dismiss_parent {
        cx.emit(DismissEvent);
    }
});
(submenu, dismiss_subscription)
```

The child talks up through an event. The parent decides what to do, and passes the message further up if needed. Dropping the stored pair tears the wiring down.

**2. Managed views (`DismissEvent`).** A view that is `Focusable + EventEmitter<DismissEvent> + Render` can be hosted by a popover, modal or menu holder. The holder subscribes to `DismissEvent` to know when to remove it. `ui::PopoverMenu` and `ui::ContextMenu` use this pattern. It is the closest thing GPUI has to a convention for transient UI.

**3. Model, observer view.** A model entity owns the data. Each view stores the model handle, observes it, and calls `cx.notify()` on itself. No shared mutable state exists outside entities. (See [Models versus views](/deep-dive/entities/#models-versus-views).)

**4. A shared data plane.** `view_example` keeps its text in an `Entity<String>` that both an `Editor` view and a `CursorReadout` component read. The editor observes the string and notifies itself, so that its `.cached(..)` subtree redraws.

**5. Props down, events up with stateless components.** Components (`RenderOnce`) take `Entity<_>` handles and plain values. Interaction goes back through `cx.listener(..)` closures defined in the owning view's `render`.

**6. Tasks owned by state.** The `Editor` stores `_blink_task: Task<()>`. It replaces the task to restart the blink and assigns `Task::ready(())` to stop it, because dropping a task cancels it. Spawned futures receive a `WeakEntity` so they do not extend the view's life.

**7. Lazy per-element state.** `window.use_state(cx, init)` and `use_keyed_state(key, cx, init)` hold an `Entity<S>` in element state for as long as that element keeps being rendered. The `ui` scrollbar uses it to keep a `ScrollbarState` per scrollable element.

**8. Extension traits for convenience.** Examples are `RetainedFocusExt for App`, `DefaultColors for App`, and `ActiveTextContext` in the examples. They add methods to `App` or `Context<T>` without wrapping them.

**9. Actions and key contexts for input.** Instead of one closure per key, define actions (`actions!(counter, [Increment, Decrement])`), bind them with `cx.bind_keys(..)`, and attach `.key_context("Counter").on_action(cx.listener(Self::increment))` to the focused element. See [Actions and keybindings](/guides/actions-and-keybindings/), `examples/testing.rs` and `crates/gpui/docs/key_dispatch.md`.

## Common mistakes

- **Reading `cx.global::<G>()` before it is set.** It panics. Install defaults at startup, or use `try_global` or `default_global`.
- **Expecting a view to re-render when a global changes** without calling `observe_global`.
- **Using `global_mut` for reads.** It triggers observers needlessly.
- **Putting per-instance state in a global** because it is "easy to reach". Two windows or two documents will then fight over it.
- **Calling `cx.global::<G>()` inside `update_global::<G>`** for the same `G`. The global is leased out.
- **Storing an `Entity<_>` inside a global and never releasing it.** It lives until you replace or remove the global.

## Next steps

- [Entities](/deep-dive/entities/): the other half of app state.
- [Actions and keybindings](/guides/actions-and-keybindings/): the action pattern in practice.
- [Images, SVG and assets](/guides/images-svg-and-assets/): `AssetSource` in context.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/global.rs` (`Global`, `ReadGlobal`, `UpdateGlobal`)
- `crates/gpui/src/gpui.rs` (`BorrowAppContext`)
- `crates/gpui/src/app.rs` (`global`, `set_global`, `global_mut`, `default_global`, `remove_global`, `observe_global`, `lease_global`, `Application::with_assets`)
- `crates/gpui/src/app/context.rs` (`Context::observe_global`, `observe_global_in`)
- `crates/gpui/src/app/async_context.rs` (global helpers on `AsyncApp`)
- `crates/gpui/src/colors.rs`, `crates/gpui/src/assets.rs`
- `crates/gpui/examples/set_menus.rs`, `crates/gpui/examples/text.rs`, `crates/gpui/examples/svg/svg.rs`
- `crates/ui/src/components/keybinding.rs`, `crates/ui/src/utils/retained_focus.rs`, `crates/ui/src/components/context_menu.rs`, `crates/ui/src/components/popover_menu.rs`
</details>
