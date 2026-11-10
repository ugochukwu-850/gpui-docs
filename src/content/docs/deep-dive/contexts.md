---
title: "Contexts: which cx do I have?"
description: What App, Context<T>, Window, AsyncApp and the test contexts are, how they relate, and which methods live on which.
sidebar:
  order: 3
  label: Contexts
---

:::note[Advanced]
This page is for readers who have finished the beginner path and keep wondering why GPUI has so many kinds of `cx`. Read [Thinking in GPUI](/start/thinking-in-gpui/) and [State and views](/guides/state-and-views/) first.
:::

Almost every GPUI function takes a *context parameter*, conventionally named `cx`. A **context** is the object that lets your code reach the app: create entities, read state, schedule work. There are several kinds, and the type tells you where you are and what you may do. This page is the map.

`crates/gpui/docs/contexts.md` summarises them in one line each. This page expands that with what the source shows.

:::tip[In short]
- `App` is the world. Every other context is `App` plus a little extra information, or a way to reach `App` later.
- `Context<T>` is what you get inside an entity. It is an `App` that also knows which entity is acting, so it adds `notify`, `emit`, `observe` and `spawn`.
- `Window` is not a context. It is passed next to one. Async code uses owned versions (`AsyncApp`) that return `Result`, because the app or window may be gone.
:::

## The family tree

```text
 sync, borrowed (&mut)                    async, owned ('static, Clone)
 ---------------------                    -----------------------------
 App                        --to_async--> AsyncApp
  ^ Deref                                   ^ Deref
 Context<'a, T>   (App + "I am entity T")  AsyncWindowContext (AsyncApp + window)

 Window  (not a context; passed next to one)

 tests:   TestAppContext  (like AsyncApp, panics instead of Result)
          VisualTestContext (TestAppContext + a window)
```

"Deref" here is the Rust feature that lets one type act like another. Because `Context<T>` derefs to `App`, any function that takes `&mut App` also accepts `&mut Context<T>`.

The *sync* contexts on the left are plain borrows. They exist only while your function runs, so they cannot be kept across an `await`. The *async* contexts on the right are owned and cloneable, so they can.

## Which one do I have?

The context type tells you where you are. Closure signatures in the API follow a small number of patterns.

| You are in... | You receive |
| --- | --- |
| `Application::run(...)` | `cx: &mut App` |
| The build closure of `cx.open_window(..)` | `window: &mut Window, cx: &mut App` |
| `cx.new(\|cx\| ...)` or `entity.update(cx, \|this, cx\| ...)` | `this: &mut T, cx: &mut Context<T>` |
| `Render::render` | `window: &mut Window, cx: &mut Context<Self>` |
| `RenderOnce::render` | `window: &mut Window, cx: &mut App` |
| `Element::request_layout` / `prepaint` / `paint` | `window: &mut Window, cx: &mut App` |
| Event handlers on elements (`on_click`, `on_mouse_down`, ...) | `event: &E, window: &mut Window, cx: &mut App` |
| `cx.listener(\|this, event, window, cx\| ...)` | `this: &mut T, &E, window: &mut Window, cx: &mut Context<T>` |
| `cx.spawn(async move \|this, cx\| ...)` | `this: WeakEntity<T>, cx: &mut AsyncApp` |
| `cx.spawn_in(window, async move \|this, cx\| ...)` | `this: WeakEntity<T>, cx: &mut AsyncWindowContext` |
| `#[gpui::test] fn t(cx: &mut TestAppContext)` | `TestAppContext` |

## `App`: the world

`App` is the root context. It owns all entity data, the windows, globals, the keymap and the platform. If a function takes `&mut App`, you can call it with a `Context<T>` too, because `Context<T>` derefs to `App`.

`Application::run` creates the `App` for you. You never construct one yourself.

Here are representative things that live on `App`:

- **Entities:** `cx.new(...)` and the rest of the `AppContext` trait (covered below), plus `observe`, `subscribe`, `observe_new` and `observe_release`.
- **Windows:** `open_window`, `windows`, `active_window`, `refresh_windows`, `activate` and `quit`.
- **Globals:** `set_global`, `global`, `try_global`, `global_mut`, `default_global`, `has_global`, `remove_global` and `observe_global`. See [Globals](/deep-dive/globals-and-state-patterns/).
- **Input:** `bind_keys`, `on_action`, `observe_keystrokes` and `dispatch_action`.
- **Async:** `spawn`, `to_async`, `background_executor`, `foreground_executor` and `defer`.
- **Platform:** `read_from_clipboard`, `write_to_clipboard`, `open_url`, `set_menus`, `prompt_for_paths`, `displays`, `window_appearance` and `http_client`.

## `Context<'a, T>`: the world, plus "I am entity T"

`Context<T>` is the context you get inside an entity update. Structurally it is just this:

```rust
pub struct Context<'a, T> {
    app: &'a mut App,
    entity_state: WeakEntity<T>,
}
```

It implements `Deref` and `DerefMut` to `App`. What it adds is everything that needs to know *which entity is acting*.

| Method | Purpose |
| --- | --- |
| `entity_id()`, `entity()`, `weak_entity()` | Identify the current entity or get a handle to it. `entity()` panics if the entity is dead, which cannot happen while you hold its context. |
| `notify()` | Tell observers and the windows displaying this entity that it changed. |
| `emit(event)` | Emit a typed event (`T: EventEmitter<Evt>`). It is delivered after the update. |
| `observe(&other, cb)`, `observe_self(cb)` | Call back when another entity notifies. |
| `subscribe(&other, cb)`, `subscribe_self(cb)` | Call back for events of a given type. |
| `observe_global::<G>(cb)` | Call back when a global changes. |
| `on_release(cb)`, `observe_release(&other, cb)`, `on_drop(..)` | Run code when an entity (or a guard) is released. |
| `spawn(async move \|this, cx\| ...)` | Run a foreground future with a weak handle to this entity. |
| `listener(\|this, event, window, cx\| ...)` | Turn a method on this entity into an event-handler closure that elements can use. |
| `processor(..)` | Like `listener`, but returns a value. |
| `defer_in(window, f)`, `on_next_frame(window, f)` | Run code later, with `&mut T`. |
| `focus_handle()`, `focus_self(window)`, `focus_view(&view, window)` | Focus helpers. |
| `on_action(type_id, window, cb)` | Register an action handler for this entity. |

Some methods come in an `_in` form that takes a `&Window`: `observe_in`, `subscribe_in`, `on_release_in`, `observe_global_in`, `spawn_in`, `on_focus`, `on_blur`, `observe_window_bounds`, `observe_window_activation`, `observe_keystrokes` and others. The plain versions have no window. The `_in` versions give the callback a `&mut Window` as well, and tie the subscription to that window.

## `Window`: one OS window, never a context

`Window` holds the state of one OS window: the root view, focus, size and scale, text style, element state, hit testing, and every painting primitive (`paint_quad`, `paint_glyph`, `paint_svg` and so on).

It is **not** a context. You always get it as a separate `window: &mut Window` argument next to a `cx`. Use `cx` for entity operations and `window` for window operations.

Typical methods:

- **Lifecycle and drawing:** `refresh()`, `request_animation_frame()`, `on_next_frame(..)`, `defer(cx, ..)` and `remove_window()`.
- **Content:** `root::<E>()`, `replace_root(cx, build)` and `set_window_title(..)`.
- **Focus and input:** `focus(&handle, cx)`, `focused(cx)` and `dispatch_action(..)`.
- **Geometry:** `bounds()`, `viewport_size()`, `rem_size()` and `text_style()`.
- **State tied to elements:** `use_state(cx, init)`, `use_keyed_state(key, cx, init)` and `with_element_state(..)`.
- **Async:** `spawn(cx, async move |cx| ...)` gives you an `AsyncWindowContext`, and `to_async(cx)` creates one.
- **Entity observation scoped to this window:** `observe(&entity, cx, cb)` and `subscribe(&entity, cx, cb)`.

To get a `Window` outside an event handler, use a `WindowHandle<V>` and call `handle.update(cx, |root: &mut V, window, cx| ...)`. It returns a `Result`, because the window may have been closed.

## `AppContext`: one trait for "can act on entities"

`App`, `Context<T>`, `AsyncApp`, `AsyncWindowContext`, `TestAppContext` and `VisualTestContext` all implement the `AppContext` trait. This trait is why `entity.update(cx, ...)`, `entity.read_with(cx, ...)` and `cx.new(...)` accept any of them.

```rust
pub trait AppContext {
    fn new<T: 'static>(&mut self, build_entity: impl FnOnce(&mut Context<T>) -> T) -> Entity<T>;
    fn reserve_entity<T: 'static>(&mut self) -> Reservation<T>;
    fn insert_entity<T: 'static>(&mut self, reservation: Reservation<T>, build_entity: impl FnOnce(&mut Context<T>) -> T) -> Entity<T>;
    fn update_entity<T, R>(&mut self, handle: &Entity<T>, update: impl FnOnce(&mut T, &mut Context<T>) -> R) -> R where T: 'static;
    fn read_entity<T, R>(&self, handle: &Entity<T>, read: impl FnOnce(&T, &App) -> R) -> R where T: 'static;
    fn update_window<T, F>(&mut self, window: AnyWindowHandle, f: F) -> Result<T> where F: FnOnce(AnyView, &mut Window, &mut App) -> T;
    fn background_spawn<R>(&self, future: impl Future<Output = R> + Send + 'static) -> Task<R> where R: Send + 'static;
    fn read_global<G, R>(&self, callback: impl FnOnce(&G, &App) -> R) -> R where G: Global;
    // plus: as_mut, with_window, read_window
}
```

The signatures above are abbreviated. `use gpui::prelude::*` imports the trait as `AppContext as _`, which is why `cx.new(..)` works without a named import.

`BorrowAppContext` is a sibling trait. It is implemented for anything that can `BorrowMut<App>`, which includes `App` and `Context<T>`. It provides `set_global`, `update_global` and `update_default_global`.

## `VisualContext`: entities plus a window

`VisualContext: AppContext` is for contexts that have a window in hand. It adds `window_handle()`, `update_window_entity(..)`, `new_window_entity(..)`, `replace_root_view(..)` and `focus(..)`, plus an associated `type Result<T>`. `AsyncWindowContext` implements it (with `Result<T> = anyhow::Result<T>`), and so do `VisualTestContext` and the bench context.

In ordinary synchronous code you do not need it, because you already hold a `window: &mut Window`. Its practical use is `Entity::update_in(cx, |this, window, cx| ...)` from async code:

```rust
cx.spawn_in(window, async move |this, cx| {
    // cx: &mut AsyncWindowContext
    this.update_in(cx, |this, window, cx| {
        this.focus_handle.focus(window, cx);
    })
    .ok();
})
.detach();
```

`WeakEntity::update_in` is also available on any `AppContext`. It looks up the entity's *current window* (the last window that rendered it) and returns an error if there is none.

## `AsyncApp` and `AsyncWindowContext`: contexts you can keep

The sync contexts are references. They cannot live across an `await`, because the borrow would have to last for as long as the future does. Calling `to_async()` (on `App`, `Context<T>`, or `Window::to_async(cx)`) produces a cloneable owned handle instead.

- **`AsyncApp`** holds the app *weakly*, plus both executors. Its docs say: "Methods will panic if the app has been dropped, but this should not happen in practice when using foreground tasks spawned via `cx.spawn()`." It implements `AppContext`, so `entity.update(&mut async_cx, ...)` works and returns the value directly. It also has `update(|app| ...)`, `refresh()`, `open_window`, `spawn`, `read_global` and `update_global`, `has_global`, and the executors.
- **`AsyncWindowContext`** is an `AsyncApp` (it derefs to one) plus a window. Its `update(|window, app| ...)` returns a `Result`, because the window might have closed. It also provides `update_root`, `on_next_frame`, `prompt` and global helpers, and it implements `VisualContext`.

The thing to remember is that these can fail. The `WeakEntity` you receive in `cx.spawn` closures returns a `Result` from `update` and `read_with`. Handle it, usually with `.ok()` or by returning early.

```rust
fn reload(&self, cx: &mut Context<Self>) {
    cx.spawn(async move |this, cx| {
        let data = cx.background_spawn(async { expensive() }).await;
        this.update(cx, |this, cx| {
            this.data = data;
            cx.notify();
        })
        .ok();
    })
    .detach();
}
```

See [Async and executors](/guides/async-and-executors/) for how the executors work.

## `TestAppContext`: contexts for tests

`#[gpui::test]` gives your test a `TestAppContext`. It is a cloneable handle like `AsyncApp`, but it implements `AppContext` with panics instead of `Result`, and it runs on a deterministic scheduler (so test runs repeat exactly). It adds test-only helpers: `run_until_parked()`, `update(|app| ..)`, `read(|app| ..)`, `open_window(..)`, `add_window(..)`, `simulate_keystrokes(..)`, `simulate_input(..)`, `dispatch_action(..)`, `executor()`, `set_global`, and clipboard and prompt simulation.

To involve a window, wrap the context in a `VisualTestContext`. This example is from `crates/gpui/examples/testing.rs`:

```rust
#[gpui::test]
fn test_counter_in_window(cx: &mut TestAppContext) {
    let window = cx.update(|cx| {
        cx.open_window(Default::default(), |_, cx| cx.new(|cx| Counter::new(cx)))
            .unwrap()
    });

    let mut cx = VisualTestContext::from_window(window.into(), cx);
    let counter = window.root(&mut cx).unwrap();

    let focus_handle = counter.read_with(&cx, |counter, _| counter.focus_handle.clone());
    cx.update(|window, cx| {
        focus_handle.dispatch_action(&Increment, window, cx);
    });

    assert_eq!(counter.read_with(&cx, |counter, _| counter.count), 1);
}
```

Side effects (observers, events) run when each `update*` call completes, and the window is redrawn after every update, so assertions about rendered output work. Async work does not make progress until you `await` or call `cx.run_until_parked()`. The [Testing guide](/guides/testing/) shows more.

## Common mistakes

- **Trying to use `Window` as a context.** `window.new(...)` does not exist. Pass `cx` for entity operations and `window` for window operations.
- **Holding `cx` across `await`.** You cannot keep `&mut App` or `&mut Context<T>` across an await. Use `cx.spawn(...)` and work with the `AsyncApp` it gives you.
- **Capturing a strong `Entity<T>` in a spawned future** when the `WeakEntity` argument would do. The strong handle keeps the entity alive for as long as the future runs.
- **Ignoring the `Result`** from `WeakEntity::update` or `AsyncWindowContext::update`. A closed window or a released entity is a normal event, not a bug.
- **Using `read(cx)` with a test context.** `TestAppContext` is not a `&App`. Use `read_with(cx, |x, _| ...)` instead. The testing example calls this out.

## Next steps

- [Entities](/deep-dive/entities/): create, read, update and observe, using the contexts above.
- [Views and render](/deep-dive/views-and-render/): what `Render::render` receives and why.
- [Testing](/guides/testing/): `TestAppContext` in practice.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/docs/contexts.md`
- `crates/gpui/src/gpui.rs` (`AppContext`, `VisualContext`, `BorrowAppContext`, `EventEmitter`)
- `crates/gpui/src/app.rs` (`App`)
- `crates/gpui/src/app/context.rs` (`Context<T>`)
- `crates/gpui/src/app/async_context.rs` (`AsyncApp`, `AsyncWindowContext`)
- `crates/gpui/src/app/test_context.rs` (`TestAppContext`, `VisualTestContext`)
- `crates/gpui/src/window.rs` (`Window`, `WindowHandle`)
- `crates/gpui/examples/testing.rs`
</details>
