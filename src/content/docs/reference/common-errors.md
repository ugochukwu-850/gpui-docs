---
title: Common errors
description: Look up the compile errors, panics and silent failures newcomers hit most often with GPUI, each as symptom, cause and fix.
sidebar:
  order: 4
---

:::note[Reference]
This is a lookup page. Come here when something breaks. To avoid many of these problems in the first place, read [Thinking in GPUI](/start/thinking-in-gpui/) and [State and views](/guides/state-and-views/).
:::

GPUI has a few classic mistakes. Some show up as compile errors, some as panics (the program crashes with a message), and some as nothing at all: the code runs and the screen just does not change. This page lists them all in the same shape: what you **see**, why it **happens**, and how to **fix** it.

:::tip[In short]
- Find your problem in one of five groups: [compile errors](#compile-errors), [panics about state and ownership](#panics-about-state-and-ownership), [panics about drawing and elements](#panics-about-drawing-and-elements), [startup and platform problems](#startup-and-platform-problems), or [things that fail silently](#things-that-fail-silently).
- If the UI does not update, jump to "State changed, UI didn't". The most common cause is a forgotten `cx.notify()`.
- Panic and error strings in quotation marks are copied from the source at commit `b5cd310b`, so you can search for them with `rg`.
:::

Compiler messages are described rather than quoted, because they come from `rustc` and not from GPUI.

## Compile errors

### `on_click`, `on_hover`, `tooltip` or `overflow_scroll` is "not found" on a `div()`

**Symptom.** The compiler says there is no method named `on_click` (or `on_hover`, `tooltip`, `overflow_scroll`) on `Div`.

**Cause.** Those methods belong to `StatefulInteractiveElement`, and that trait is only implemented for `Stateful<E>`. `Stateful<E>` is the wrapper you get from `.id(...)`, whose doc says "Assign this element an ID, so that it can be used with interactivity". A bare `Div` has `InteractiveElement` (mouse down, up and move listeners, `on_action`, `track_focus`, `key_context`) but not click, hover, tooltip or scrolling. The source is `crates/gpui/src/elements/div.rs` (`impl<E> StatefulInteractiveElement for Stateful<E>`).

**Fix.** Give the element an id first.

```rust
div().on_click(|_, _, _| {})                // error: no method named `on_click`
div().id("save").on_click(|_, _, _| {})     // ok
```

Also check that `use gpui::prelude::*;` is in scope. It imports `InteractiveElement` and `StatefulInteractiveElement` (`crates/gpui/src/prelude.rs`). A missing trait import gives the same "method not found" error.

### "the trait bound ... `IntoElement` is not satisfied" when you call `.child(MyComponent)`

**Symptom.** The compiler complains that `MyComponent` does not implement `IntoElement`.

**Cause.** `ParentElement::child` takes `impl IntoElement`. A struct that implements `RenderOnce` is not automatically an element.

**Fix.** Add `#[derive(IntoElement)]` (`gpui_macros/src/derive_into_element.rs`). It implements `IntoElement` using `ViewElement<Self>`. For a view entity, pass the `Entity<V>` itself, not the struct. `impl IntoElement for Entity<V: Render>` is in `view.rs`.

One more thing to know: `RenderOnce` is declared `pub trait RenderOnce: 'static`. A component that borrows data (`struct Row<'a>`) therefore cannot implement it. Clone or move the data into the component instead.

### Mismatched types from `impl IntoElement` (an `if`/`else` or `match` that returns different elements)

**Symptom.** The compiler reports mismatched types for the return value of `render`, where two branches build different elements.

**Cause.** `Render::render` and `RenderOnce::render` return `impl IntoElement`, which means one concrete type. Two branches that build different element types have different types. For example, a `Div` and a `Stateful<Div>`, or a `Label` and an `Img`.

**Fix.** Call `.into_any_element()` on each branch. It returns an `AnyElement`. Or restructure with `FluentBuilder::when`, `when_else` or `when_some`, so both paths give the same type (`crates/gpui/src/util.rs`). Components in `ui` that need a different return type use `#[allow(refining_impl_trait)]`. For example, `Button::render` returns `ButtonLike` (see [Reading the ui crate](/codebase/reading-zed-ui-crate/)).

### Using `self` or `cx` inside a listener closure ("closure may outlive the current function", wrong `cx` type)

**Symptom.** You write an `on_click` closure that uses `self` or `cx`, and the compiler says the closure may outlive the current function, or that `cx` has the wrong type.

**Cause.** Listeners such as `on_click` take `impl Fn(&ClickEvent, &mut Window, &mut App) + 'static`. The context is a plain `&mut App`, not your entity's `Context<Self>`, and the closure cannot borrow `self`.

**Fix.** Wrap the handler with `cx.listener(...)` (`Context::listener` in `crates/gpui/src/app/context.rs`). It captures a *weak* handle to the current entity and calls your closure as `|this: &mut Self, event, window, cx: &mut Context<Self>|`.

```rust
div().id("inc").on_click(cx.listener(|this, _event, _window, cx| {
    this.count += 1;
    cx.notify();
}))
```

### Borrow-checker errors around `Context<T>`

**Symptom.** `rustc` reports a borrow error where you use `cx` and a field, or two entities, in the same function.

**Cause.** These are all consequences of how contexts work (see [App internals](/codebase/app-and-entity-internals/)). There are four typical shapes.

- **Using `cx` while holding a borrow of a field of the entity.** `Context<T>` derefs to `App`, and `self` is the leased entity. So `let item = &self.items[0]; cx.notify(); use(item)` is fine, but `let item = &self.items[0]; self.entity.update(cx, ...)` is not.
- **Updating another entity from inside an update.** `other.update(cx, |other, cx| ...)` takes `cx` mutably for its whole duration. You cannot touch `self`'s fields from that closure unless you pass copies in.
- **Passing `&mut Context<Self>` where `&mut App` is expected, or the reverse.** `&mut Context<T>` derefs to `&mut App` automatically in most places. Going the other way is impossible, because `Context` carries the entity.
- **Returning a reference to data inside `entity.read(cx)`.** The returned `&T` borrows `cx`.

**Fix.** For the first, clone the data out before the call. For the second, read what you need before the call. For the fourth, use `read_with(cx, |this, _| this.value.clone())`.

### `#[derive(Action)]` fails to compile

**Symptom.** The derive reports an error about missing traits or about an unknown argument.

**Cause.** `#[derive(Action)]` requires `Clone` and `PartialEq` on the type. It also needs `serde::Deserialize` and `schemars::JsonSchema`, unless you specify `#[action(no_json)]` (documented on the `Action` trait). Unknown `#[action(...)]` arguments fail with "'..' argument not recognized, expected 'namespace', 'no_json', 'no_register, 'deprecated_aliases', or 'deprecated'".

**Fix.** Derive the missing traits, add `#[action(no_json)]`, or correct the argument name.

## Panics about state and ownership

### "cannot update `T` while it is already being updated" / "cannot read `T` while it is already being updated"

**Symptom.** The program crashes with a message like this (from `double_lease_panic` in `crates/gpui/src/app/entity_map.rs`):

```text
cannot update my_crate::MyView while it is already being updated
cannot read my_crate::MyView while it is already being updated
```

**Cause.** `Entity::update` removes the entity's value from the `EntityMap` for as long as the closure runs. This is called a *lease*. A second `update`, `read`, `read_with` or `as_mut` on the same entity before the first one finishes finds nothing there, and panics. The common routes are:

- An entity's `update` closure calls a method that does `self_entity.read(cx)`, because the handle was stored in a field.
- Two entities update each other synchronously (A updates B, whose code updates A).
- Rendering. `Render::render` for an entity runs inside that entity's update. Calling `entity.read(cx)` or `entity.update(cx, ..)` on *itself* from `render`, or from helper code it calls, panics.
- An `observe` or `subscribe` callback runs through a lease on the observer. If the callback updates the observed entity while it is leased (for example, when observing yourself), it panics.

**Fix.** Pass values instead of handles. Or restructure so one side returns data and the other applies it afterwards. Or move the work to the end of the effect cycle with `cx.defer(...)` or `Context::defer_in(window, ...)`. These push `Effect::Defer`, "allowing entities that are currently on the stack to be returned to the app". The [ownership page](/deep-dive/ownership-and-data-flow/#reentrancy-rules) explains the rules.

There are related, quieter variants. `WeakEntity::update` returns a `Result` with the context message "entity released" if the entity is gone. `App::update_window` returns `Err("window not found")` if the window is absent **or is currently being updated** (the window is taken out of its slot with `Option::take` during the update). Handle the `Result` with `.ok()`, `?` or `.log_err()`.

### "RefCell already borrowed: attempted mutable App borrow at ..."

**Symptom.** The program crashes with this message (the `Display` text of `AppBorrowError` in `crates/gpui/src/app.rs`):

```text
RefCell already borrowed: attempted mutable App borrow at src/foo.rs:10:5; existing mutable borrow group began at src/bar.rs:22:9
```

**Cause.** Something entered the `App` through `AppCell::borrow_mut` (a platform callback, or `AsyncApp::update`) while an outer `&mut App` was still alive further up the stack. GPUI allows only one borrow at a time. An example is calling `async_cx.update(...)` synchronously from inside a callback that already has `cx`. It also happens when a native callback runs re-entrantly (the Windows frame-request guard in `Window::new` exists to avoid this).

**Fix.** Use the `cx` you already have. Or spawn (`cx.spawn(async move |this, cx| ...)`), so the update happens after the current call returns. The two locations in the message tell you where the first borrow began. Build with `TRACK_THREAD_BORROWS` set for even more output.

### "app was released before async operation completed"

**Symptom.** A panic with this message, usually during shutdown or in code running on a plain thread.

**Cause.** `AsyncApp::app()` does `self.app.upgrade().expect(...)`. You kept an `AsyncApp`, or used one from a plain thread, after the `App` was dropped. The executor checks foreground tasks spawned with `cx.spawn` before running them. It does not check arbitrary threads.

**Fix.** Do not pass `AsyncApp` to code that outlives the application. Use `WeakEntity` and handle the `Result`. Or use `BackgroundExecutor::spawn` and send results back through a foreground task.

### "no state of type X exists" / "no global added for X"

**Symptom.** A panic naming a global type.

**Cause.** You called `cx.global::<G>()`, `global_mut` or `remove_global` before `cx.set_global(..)` (`crates/gpui/src/app.rs`). A second cause: you read global `G` from inside `update_global::<G>`. The global is leased out of `globals_by_type` for that time, so it looks missing. (`lease_global` itself panics with "no global registered of type {}" if the global is absent.)

**Fix.** Set the global during startup. Or use `cx.try_global::<G>()`, `cx.has_global::<G>()` or `cx.default_global::<G>()`.

### "Action with name `X` already registered"

**Symptom.** The app panics at startup with this message (from `ActionRegistry::insert_action`, `crates/gpui/src/action.rs`):

```text
Action with name `editor::Undo` already registered (might be registered in `#[action(deprecated_aliases = [...])]`.
```

**Cause.** Two action types resolve to the same `namespace::Name`. A typical case is `actions!(editor, [Undo])` in two crates or modules. Another is an alias that equals another action's name. The panic happens when the `App` is created, not when the duplicate is used.

**Fix.** Rename one of them, or change its `namespace` or `name`. Remember that `#[action(name = ..)]` must not contain `::`. The derive reports a compile-time panic for that: "in #[action] attribute: `name = \"..\"` must not contain `::`, also specify `namespace` instead".

### "Leases must be ended with EntityMap::end_lease" / "Exited with leaked handles"

**Symptom.** One of these two messages.

**Cause.** The first is an internal check (`LeaseInner::drop`). It points to a bug in code that holds a lease across an early return. The second comes from the entity leak detector. It runs in tests, and in builds with `GPUI_LEAK_DETECTION` or the `leak-detection` feature. It fires when `Entity` handles are still alive at shutdown. That is usually a strong reference cycle: A owns `Entity<B>` and B owns `Entity<A>`, or a `Task` or `Subscription` closure captures a strong handle to its own owner.

**Fix.** Capture a `WeakEntity` instead (`cx.spawn` already gives you one). Set `LEAK_BACKTRACE=1` to get allocation backtraces. See [Cargo features](/reference/cargo-features/) for the leak-detection switches.

## Panics about drawing and elements

### "this method can only be called during paint" / "...during request_layout, or prepaint"

**Symptom.** A debug build panics with one of these messages.

**Cause.** These are `debug_assert!`s in `WindowInvalidator` (`window.rs`). Painting calls (`paint_quad`, `paint_glyph`, `on_mouse_event`, `set_key_context`, `handle_input` and others) are only legal in `paint`. `insert_hitbox`, `request_layout`, `compute_layout` and `set_focus_handle` are only legal in `request_layout` or `prepaint`. Some, such as `with_element_state`, work in prepaint or paint. A typical trigger is writing a custom `Element` and putting a call in the wrong method, or calling a `Window` API from a render function.

**Fix.** Move the call into the right phase. See [Elements](/deep-dive/elements/#three-phases-per-frame).

### "must call request_layout only once" / "must call request_layout before prepaint" / "must call prepaint before paint" / "cannot measure after painting"

**Symptom.** A panic about phases being called twice or out of order.

**Cause.** The `Drawable` state machine in `crates/gpui/src/element.rs` rejects phases that come out of order. In custom elements, this means calling `request_layout` on the same `AnyElement` twice, or calling `paint` without `prepaint`.

**Fix.** Rebuild the `AnyElement` each frame. Elements are meant to be used once. Do not keep an `AnyElement` across frames.

### "attempted to dereference an ArenaRef after its Arena was cleared"

**Symptom.** A panic with this message.

**Cause.** An `AnyElement` (which lives in the per-frame arena) outlived the frame that created it (`crates/gpui/src/arena.rs`).

**Fix.** Do not store elements in entities or statics. Store the data, and build the element again in `render`.

### "Exceeded maximum (10) deferred depth"

**Symptom.** A panic with this message while drawing overlays.

**Cause.** `prepaint_deferred_draws` loops over rounds of `deferred(...)` elements that create deferred children of their own, and asserts a depth of 10 (`window.rs`). This happens with popovers inside popovers inside popovers, or with an element that always defers a new deferred child.

**Fix.** Flatten the nesting, or stop the element from creating a new deferred child on every pass.

### "you must return some state when you pass some element id" / "you must not return an element state when passing None for the global id"

**Symptom.** A panic with one of these messages in a custom element.

**Cause.** You misused `Window::with_optional_element_state`. If the element has an id you must return `Some(state)`. If it has none you must return `None` (`window.rs`).

**Fix.** Make the returned value match whether `id()` returned `Some` or `None`.

### "failed to resolve font 'X' or any of the fallbacks: ..."

**Symptom.** A panic with this message, preceded by a warning: `failed to load font {font:?}: {error:#}`.

**Cause.** `TextSystem::font_id` (`crates/gpui/src/text_system.rs`) did not find the requested family, or any entry in the fallback stack. On the web there are no system fonts: `WebTextSystem` is built with `CosmicTextSystem::new_without_system_fonts`.

**Fix.** Register fonts first with `cx.text_system().add_fonts(...)`. The examples' `example_support::load_fonts` does this for IBM Plex Sans and Lilex.

## Startup and platform problems

### The window never appears on Linux

**Symptom.** The program runs without errors, but no window is drawn. Or it panics at startup.

**Cause.** There are five things to check, in this order (all in `gpui_linux/src/linux/`).

1. **Features.** `gpui_platform` must be built with `wayland` and/or `x11` (see [Cargo features](/reference/cargo-features/)). Without them, `gpui_linux` has no display backend. `select_backend` returns `None`, and the platform starts headless. Windows open as `HeadlessWindow`, which "lay out and handle input but draw nothing".
2. **Environment.** `select_backend` prefers Wayland when `WAYLAND_DISPLAY` is non-empty, else X11 when `DISPLAY` is non-empty, else headless. Under SSH, or in a service without those variables, you get headless again. Setting `ZED_HEADLESS` to anything forces headless.
3. **Allowed modes.** If you built with `gpui_platform::linux(modes)`, and `HEADLESS` is excluded while no display server is available, startup panics with "{modes:?} does not allow starting headless, and no allowed display server was given".
4. **Connection errors.** If GPUI selected a display server but connecting fails, `connect_initially` panics with the error text (`unwrap_or_else(|error| panic!("{error:#}"))`).
5. **Invalid X11 DPI override.** A `GPUI_X11_SCALE_FACTOR` other than `randr` or a positive number panics with "`GPUI_X11_SCALE_FACTOR` must be a positive normal number or `randr`. Got `...`".

The `wgpu` renderer also needs a Vulkan or GL adapter. `WgpuContext` errors with "No GPU adapters found" or "No GPU adapter found that can configure the display surface". `ZED_DEVICE_ID` can select among adapters.

**Fix.** Enable the right features, and run with a display server available. Fix whichever of the five items above matches your message.

### The window opens but there is no text

**Symptom.** The window and its shapes appear, but all text is missing.

**Cause.** One of these:

- **macOS:** the app was built without `gpui_platform/font-kit`. The log line is "gpui_macos was compiled without the `font-kit` feature, so no text will be rendered." and the text system is `NoopTextSystem`.
- **Web:** no fonts are registered (see the font error above).
- **Headless platforms** (`headless()`, Windows headless) use `NoopTextSystem`, which lays out nothing real.
- **Missing glyphs for a script:** no loaded font has the characters.

**Fix.** On macOS, enable `font-kit`. On the web, register fonts. For a missing script, register a font and listen with `App::on_missing_glyphs` (see `examples/README.md`, "Dynamic font loading").

### "Mac platform not created on main thread" / "failed to initialize Windows platform" / "App is already running"

**Symptom.** A panic with one of these messages at startup.

**Cause.** `MacPlatform::new` expects the main thread (`main_thread_marker().expect(..)`). `current_platform` panics with the Windows error if platform setup fails. `LinuxPlatform::run` can only be called once (`.expect("App is already running")`).

**Fix.** Create and run the application once, from `main`.

### Web: the second window fails

**Symptom.** Opening a second window, or reopening one after closing, returns a `WebWindowError`.

**Cause.** `gpui_web` supports one top-level window (module doc in `gpui_web.rs`). With the default `multithreaded` feature, the page must also be cross-origin isolated (`SharedArrayBuffer` and `Atomics`).

**Fix.** Use a single window on the web, and serve the page with the needed isolation headers (`crates/gpui/examples/README.md` documents them).

### Calling `spawn` after quit

**Symptom.** A debug build panics with "Can't spawn on main thread after on_app_quit". A release build only logs an error.

**Cause.** `App::spawn` on the main thread after `on_app_quit` has run hits `debug_panic!`.

**Fix.** Do not start new foreground work once the app is quitting.

## Things that fail silently

These produce no panic, which makes them harder to find.

### State changed, UI didn't

**Symptom.** You changed data, but the window still shows the old value.

**Cause.** There are four common reasons.

- **You never called `cx.notify()`.** `Entity::update` does not notify automatically. (`as_mut` does: `GpuiBorrow::drop` calls `app.notify`.) `Window::focus`, `blur` and input modality changes call `refresh()` on their own.
- **The state is not in an entity.** You changed a field of a plain struct held in `Rc<RefCell<..>>`, or a static. Redraw tracking works by recording which entities were *read during the last draw* (`EntityMap::read_inner` and `lease_inner`, then `Window::record_entities_accessed`). State outside entities never invalidates anything.
- **You notified an entity the window did not read while rendering.** `App::notify` only invalidates windows that are tracking the entity. Otherwise it just queues observers.
- **A cached view did not notice.** A **cached** view (`.cached(style)`) is reused unless its own entity is in `window.dirty_views`, its cache key (bounds, content mask, text style, opacity) changed, or the window is `refreshing`. `Window::mark_view_dirty` marks a notified entity and its ancestor *views*. It walks `DispatchTree::view_path_reversed`, which only knows entities that were rendered as views. So notifying a plain model entity that a cached view read will redraw the window, but, as far as this code reads, will not by itself re-render the cached view. (Derived from reading `view.rs::prepaint_view` and `window.rs::mark_view_dirty`. Not tested.)

**Fix.** Call `cx.notify()` on the entity whose state changed, and keep state in entities. For a cached view that reads a model, have the view `cx.observe(&model, |_, _, cx| cx.notify())`, or notify the view's own entity. See [Views and render](/deep-dive/views-and-render/#how-notify-reaches-the-screen).

### A `Subscription` or `Task` was dropped

**Symptom.** A callback never runs, or background work stops early.

**Cause.** You dropped a handle that was keeping it alive.

- `Subscription` is `#[must_use]` and "When dropped, the subscription is cancelled and the callback will no longer be invoked" (`subscription.rs`). `cx.observe(...);` as a statement warns, and then does nothing useful.
- `Task<T>`: `Context::spawn` documents "The returned task must be held or detached." A dropped task is cancelled. `gpui_tokio` documents the same ("the Tokio task will be cancelled if the GPUI task is dropped").

**Fix.** Store the `Subscription` in a field (`_subscription: Subscription`) or call `.detach()`, which keeps the callback alive as long as the observed entity lives. `Subscription::join(a, b)` combines several. For a `Task`, store it in a field, call `.detach()`, or for `Task<Result<..>>` call `.detach_and_log_err(cx)` (`TaskExt` in `executor.rs`).

### An observer or listener didn't fire

**Symptom.** You registered an observer, subscriber or action handler and it never runs.

**Cause.** One of these:

- A new observer only becomes active after the current effect cycle (`insert_pending` plus `defer(activate)`). An observer registered during a `notify` does not see that same notification.
- `cx.subscribe` only receives events of the exact type emitted. The emitter must implement `EventEmitter<E>`, and `emit` queues the event, which is delivered at the end of the update.
- Action handlers only run when the focused node is at or below the element that registers them.
- An action handler consumes the action unless it calls `cx.propagate()`. Mouse handlers propagate unless they call `cx.stop_propagation()` (see the `App::stop_propagation` and `propagate` docs).

**Fix.** For actions, give the element `track_focus(&focus_handle)` and focus it (`window.focus(&handle, cx)`). Also set a `key_context(..)` that your keybinding's context predicate matches. For events, check the event type and the `EventEmitter` impl.

### Elements mix up their state or scroll position

**Symptom.** Two list items share a scroll position, or hover and active state leaks between siblings.

**Cause.** Elements with an id keep persistent state (scroll offsets, hover, `use_state`-style values), keyed by the **path** of `ElementId`s. `Element::id` documents: "This id must be unique among children of the first containing element with an id." Two siblings with the same id share state. `View::entity_id` adds a related rule: two views keyed on the same entity "must not be rendered at the same position in the element tree (e.g. as siblings under the same parent): their internal element state ... would silently collide".

**Fix.** Generate ids from stable data, such as `ElementId::NamedInteger(name, index)` via `ElementId::named_usize("row", ix)`. Do not use random values.

### A cached view is zero-sized or never grows

**Symptom.** A view wrapped in `.cached(style)` shows up with no size, or stays the same size as its content changes.

**Cause.** `Entity::cached(style)` states: "Caching requires a definite size: a cached view is laid out from `style` and is *not* measured from its contents."

**Fix.** Give the `StyleRefinement` an explicit `size`, `w` or `h`, or do not cache the view.

### Hover or click goes to the element behind

**Symptom.** You put an overlay on top of something, but the element underneath still reports hover and receives clicks.

**Cause.** GPUI only inserts a hitbox when needed, and an overlay that should block the mouse has to say so. Otherwise elements behind it still report `is_hovered`.

**Fix.** Call `.occlude()`, which sets `HitboxBehavior::BlockMouse`. The scroll-friendly variant is `.block_mouse_except_scroll()`. See [input internals](/codebase/input-and-dispatch-internals/).

## Next steps

- [Cargo features and environment variables](/reference/cargo-features/): the switches behind many startup problems.
- [Debugging and performance](/guides/debugging-and-performance/): tools for tracking down a problem yourself.
- [How GPUI owns your data](/deep-dive/ownership-and-data-flow/): the reasoning behind the ownership panics.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/app/entity_map.rs` (`double_lease_panic`, leases, leak detection)
- `crates/gpui/src/app.rs` (`AppBorrowError`, globals, `update_window`)
- `crates/gpui/src/elements/div.rs` (`StatefulInteractiveElement for Stateful<E>`)
- `crates/gpui/src/element.rs` (`Drawable`), `crates/gpui/src/arena.rs`
- `crates/gpui/src/window.rs` (`WindowInvalidator`, `prepaint_deferred_draws`, `with_optional_element_state`, `mark_view_dirty`)
- `crates/gpui/src/action.rs`, `crates/gpui/src/text_system.rs`, `crates/gpui/src/subscription.rs`, `crates/gpui/src/view.rs`
- `crates/gpui_linux/src/linux/` (backend selection)
</details>
