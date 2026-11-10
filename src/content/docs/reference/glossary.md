---
title: Glossary
description: Plain-English definitions of the GPUI terms and types you will meet, in alphabetical order, with the file where each one lives.
sidebar:
  order: 3
---

:::note[Reference]
This is a lookup page. If many of these words are new, read [Thinking in GPUI](/start/thinking-in-gpui/) and [State and views](/guides/state-and-views/) first. They introduce the most important terms with examples.
:::

GPUI has a lot of vocabulary. This page explains each term in one or two plain sentences, so you can find a word you just met and move on. Terms are grouped by their first letter.

:::tip[In short]
- Each entry says what the thing is, in words a beginner can read. It is not a full API description.
- The `file.rs` at the end of an entry is where the type is defined, if you want the real thing.
- Paths are relative to `crates/gpui/src` unless they start with `crates/`.
:::

A few labels you will see:

- *(crate-private)* means you cannot name the type from outside `gpui`, but it explains behaviour you will meet.
- *(hidden)* means the item is not shown in the public docs.
- Everything was read from commit `b5cd310b`.

Some words come up in nearly every entry. A **handle** is a small value that points at something owned elsewhere. A **view** is an entity that can draw itself. An **element** is one piece of the UI tree that is built and drawn each frame.

## A

**Action**: A named command in your app, such as `editor::Undo`. Key bindings connect keystrokes to actions, and elements register listeners that run when an action happens. See [input internals](/codebase/input-and-dispatch-internals/). Defined in `action.rs`; the derive is in `crates/gpui_macros/src/derive_action.rs`.

**ActionRegistry** *(crate-private)*: The table of every action in the program. It is built when the app starts, and is used to create actions from their names or from JSON. `action.rs`.

**Anchored**: An element, made with `anchored()`, that places its child at a chosen point and keeps it inside the window. Popovers and menus use it. `elements/anchored.rs`.

**AnyElement**: An element whose exact type has been hidden, so you can store different kinds of elements together. It lives in a memory pool (an *arena*) that is cleared after each frame. `element.rs`.

**AnyEntity**: An `Entity` whose type has been hidden. You can turn it back into a typed handle with `downcast`. `app/entity_map.rs`.

**AnyView**: A handle to any entity that can render, without naming its type. A window's root view is an `AnyView`. `view.rs`.

**AnyWindowHandle** / **WindowHandle<V>**: Small copyable values that identify a window. The typed `WindowHandle<V>` also remembers the type of the window's root view. `window.rs`.

**App**: The one object that owns all application state: entities, windows, globals, the keymap, the platform, the executors and the effect queue. You pass it around as `&mut App`, usually named `cx`. See [App internals](/codebase/app-and-entity-internals/). `app.rs`.

**AppCell** *(hidden)*: A wrapper around `RefCell<App>` that remembers where a double borrow started, so the panic message can point at it. `app.rs`.

**AppContext**: A trait for anything that can create and update entities and start work. `App`, `Context<T>`, `AsyncApp` and `TestAppContext` all implement it. `gpui.rs`.

**Application**: The app builder you get before the app is running, from `gpui_platform::application()`. You configure it (`with_assets`, `with_http_client`, `with_quit_mode`) and then call `run`. `app.rs`.

**Arena** / **ArenaBox**: A fast memory pool and the box type that lives in it. Elements for one frame, and the payloads of queued `Emit` effects, live in arenas that are cleared after each frame or flush. `arena.rs`.

**Asset**: A resource that loads in the background and is cached by the `App`, such as an image. `asset_cache.rs`. **AssetSource** is a different trait, for bundled bytes: it has `load` and `list`. `assets.rs`.

**AsyncApp** / **AsyncWindowContext**: Owned versions of the context that you can keep across an `await`. They hold only a weak reference to the app, so their methods can fail. `app/async_context.rs`.

**AtlasTile**: A small rectangle inside a big GPU texture (an *atlas*) that holds many sprites. Sprites refer to tiles, and `PlatformAtlas` hands them out. `platform.rs`.

## B

**Background**: A fill for a shape: a solid colour, a linear gradient or a pattern. `color.rs`.

**BackgroundExecutor** / **ForegroundExecutor**: Handles for running a future on the thread pool or on the main thread. Both give you a `Task`. `executor.rs`.

**Bounds<T>**: A rectangle, made of an `origin: Point<T>` and a `size: Size<T>`. `geometry.rs`.

**BoundsTree** *(crate-private)*: A tree of rectangles. For each new rectangle it returns one more than the highest layer order of the rectangles it overlaps. The `Scene` uses it to order drawing. It is not used for hit testing. `bounds_tree.rs`.

## C

**Canvas**: An element, made with `canvas(prepaint, paint)`, that lets your closures use the low-level paint API directly. `elements/canvas.rs`.

**ClickEvent**: The event passed to `on_click` handlers. It can come from the mouse, the keyboard or touch, and `Div` builds it for you. `interactive.rs`.

**ContentMask<P>**: The rectangle that clips painting and hit testing. Anything outside it is not drawn or hit. `with_content_mask` stacks them. `window.rs`.

**Context<'a, T>**: The `&mut App` wrapper you get inside code that runs for an entity. It derefs to `App` and adds `notify`, `emit`, `observe`, `subscribe`, `spawn` and `listener`. See [Contexts](/deep-dive/contexts/). `app/context.rs`.

**Corners<T>** / **Edges<T>**: Types that hold four values: one per corner (for radii), or one per side (for margins, padding and borders). `geometry.rs`.

## D

**DefiniteLength** / **AbsoluteLength** / **Length**: The three kinds of layout length. An absolute length is `Pixels` or `Rems`. A definite length is absolute or a fraction. A `Length` is definite or `auto`. `geometry.rs`.

**Deferred**: An element, made with `deferred(child)`, that is laid out in place but painted after its ancestors, so it appears on top. It is used for overlays and popovers. `elements/deferred.rs`.

**DevicePixels** / **ScaledPixels** / **Pixels** / **Rems**: The units of size. `Pixels` are logical pixels, the ones you write in code. `ScaledPixels` are `Pixels` times the display scale factor, and the `Scene` stores these. `DevicePixels` are whole physical pixels, used for atlas and surface sizes. `Rems` scale with the window's base font size. `geometry.rs`.

**DispatchPhase**: Either `Capture` or `Bubble`. It tells a mouse, key or action listener which pass of event delivery it is in. `window.rs`.

**DispatchTree** *(crate-private)*: A per-frame tree used to send key events and actions. It records key contexts, listeners, focus ids and view ids, and routing starts from the focused node. `key_dispatch.rs`.

**Div**: The all-purpose container element, like an HTML `<div>`. It does flexbox and grid layout, styling, children and interaction. `elements/div.rs`.

**Drawable<E>**: A wrapper that holds an element and tracks which drawing phase it is in. It panics if the phases are called out of order. `element.rs`.

## E

**Effect** *(crate-private)*: A side effect waiting in a queue, such as `Notify`, `Emit`, `RefreshWindows`, `NotifyGlobalObservers`, `Defer` or `EntityCreated`. GPUI runs them in `flush_effects`. See [How GPUI owns your data](/deep-dive/ownership-and-data-flow/). `app.rs`.

**Element**: The low-level trait for things that can be drawn. It has three phases: `request_layout`, `prepaint` and `paint`. See [Elements](/deep-dive/elements/). `element.rs`.

**ElementId**: The name of an element among its siblings. It can be a name, a number, a UUID, a view's entity id, a focus handle, a code location and more. GPUI joins ids into a `GlobalElementId` path. `window.rs`.

**Entity<T>**: A strong handle to a value of type `T` owned by the `App`. It counts references, and it only works together with a context. See [Entities](/deep-dive/entities/). `app/entity_map.rs`.

**EntityId**: The unique number that identifies an entity. `app/entity_map.rs`.

**EntityMap** *(crate-private)*: The storage behind entities. It holds the boxed values by id, plus the shared reference counts, and it supports leasing. `app/entity_map.rs`.

**EventEmitter<E>**: A marker trait that says an entity type can `emit` events of type `E`. `gpui.rs`.

## F

**Focusable**: A trait for views that can hand out their `FocusHandle`. `window.rs`.

**FocusHandle**: A handle that identifies something that can have keyboard focus. You use it with `track_focus`, `Window::focus`, `is_focused` and `tab_index`. `window.rs`.

**Frame** *(crate-private)*: Everything produced by one draw: the `Scene`, hitboxes, mouse listeners, the `DispatchTree`, element state, deferred draws and tab stops. A window keeps `rendered_frame` and `next_frame`. See [Frame lifecycle](/codebase/frame-lifecycle/). `window.rs`.

**FluentBuilder**: A helper trait with `when`, `when_some`, `when_else` and `map`, so you can add conditions to a chain of builder calls. `util.rs`.

## G

**Global**: A marker trait for a value that exists once per app, stored by type. You read it with `cx.global::<T>()`. See [Globals and state patterns](/deep-dive/globals-and-state-patterns/). `global.rs`.

**GlobalElementId**: The full path of `ElementId`s from the root down to one element, plus a hash. GPUI uses it as the key for state that must last between frames. `element.rs`.

**GpuiBorrow**: The guard returned by `as_mut`. It lets you mutate an entity, and it calls `notify` when it is dropped. `app.rs`.

## H

**Hitbox**: An invisible rectangle added during prepaint. GPUI uses hitboxes to find which element the mouse is over, and for hover. It stores an `id`, `bounds`, `content_mask` and `HitboxBehavior`. `window.rs`.

**HitboxBehavior**: How a hitbox treats the mouse: `Normal`, `BlockMouse` (hides everything behind it from the mouse) or `BlockMouseExceptScroll`. `window.rs`.

**Hsla** / **Rgba**: Colour types. `Hsla` is hue, saturation, lightness and alpha. `Rgba` is red, green, blue and alpha, as floats. Most APIs take `Hsla`. `color.rs`.

## I

**Interactivity**: The struct inside `Div` that holds all its listeners and interaction styles. You can reuse it to build your own interactive element. `elements/div.rs`.

**InteractiveElement** / **StatefulInteractiveElement**: Traits that give an element its event methods. The first provides `.on_mouse_down`, `.on_action`, `.track_focus` and `.id`. The second only works on `Stateful<_>` and adds `.on_click`, `.on_hover`, `.tooltip` and `.overflow_scroll`. `elements/div.rs`.

**IntoElement**: A trait for anything that can become an element. Derive it for your `RenderOnce` components. `element.rs`.

## K

**KeyBinding**: A link between a keystroke sequence and an action, with an optional condition on the key context. `keymap/binding.rs`.

**KeyContext**: A set of labels an element declares with `.key_context(...)`. Key bindings can match against it. `keymap/context.rs`. **KeyBindingContextPredicate** is the small expression language for that matching, for example `Editor && mode == full` or `A > B`.

**Keymap**: The ordered list of key bindings, with precedence rules, `NoAction` and `Unbind`. `keymap.rs`.

**Keystroke**: One key press with its modifiers and optional text (`key_char`). You can parse one from a string like `cmd-shift-p`. `platform/keystroke.rs`.

## L

**LayoutId**: A handle to one node in the layout tree for the current frame. `taffy.rs`.

**Lease**: Temporarily taking an entity (or global) out of its map while a closure borrows it mutably. It is the reason re-entrant updates panic. `app/entity_map.rs`.

**ListState**: The shared state of a `list(...)` element, which is a virtualised list of variable-height rows. `elements/list.rs`.

## M

**MacroActionBuilder** *(hidden)*: The record that the action derives register at build time, for the action registry to collect. `action.rs`.

## P

**Path** / **PathBuilder**: A vector path that has been turned into triangles for the `Scene`, and the builder that makes it (using the `lyon` library). `scene.rs`, `path_builder.rs`.

**Platform** / **PlatformWindow** / **PlatformDisplay** / **PlatformDispatcher** / **PlatformTextSystem** / **PlatformAtlas**: The traits that a backend crate implements for each operating system. See [Platform backends](/codebase/platform-backends/). `platform.rs`.

**PlatformInput**: The enum of every input event a backend can produce. `interactive.rs`.

**Primitive** / **PrimitiveBatch**: A primitive is one drawable record in a `Scene`: `Quad`, `Shadow`, `Path`, `Underline`, `MonochromeSprite`, `SubpixelSprite`, `PolychromeSprite` or `PaintSurface`. A batch is a run of the same kind, kept in draw order. `scene.rs`.

## R

**Refineable**: A derive from the `refineable` crate (not in the checkout). It generates a `FooRefinement` struct with optional fields and a `refine` method. `StyleRefinement` is built this way.

**Render**: The trait for views: `fn render(&mut self, window, cx: &mut Context<Self>) -> impl IntoElement`. An `Entity<T: Render>` is a *view*. See [Views and render](/deep-dive/views-and-render/). `element.rs`.

**RenderOnce**: The trait for components that are used up when they render: `fn render(self, window, cx: &mut App) -> impl IntoElement`. Pair it with `#[derive(IntoElement)]`. `element.rs`.

**Reservation<T>**: A claimed entity slot returned by `reserve_entity`. It lets you know the `EntityId` before you insert the value. `gpui.rs`.

## S

**Scene**: The ordered, backend-neutral list of primitives that painting a frame produces. A renderer then draws it. `scene.rs`.

**SharedString**: An immutable string that is cheap to clone. It is backed by `smol_str::SmolStr`. `crates/gpui_shared_string/gpui_shared_string.rs`.

**Size<T>** / **Point<T>**: A width and height pair, and an x and y pair. `geometry.rs`.

**Stateful<E>**: What `.id(...)` returns. It wraps an element and unlocks stateful interactivity: `on_click`, hover, tooltips and scrolling. `elements/div.rs`.

**Style** / **StyleRefinement**: `Style` is the full set of layout and paint properties for an element. `StyleRefinement` is a partly filled-in version, and it is what the `Styled` builder methods write to. `style.rs`.

**Styled**: The trait that gives you the Tailwind-like builder methods (`.flex()`, `.px_2()`, `.bg(..)`). It only needs `fn style(&mut self) -> &mut StyleRefinement`. `styled.rs`.

**SubscriberSet** *(crate-private)*: The registry of callbacks keyed by the emitter's id. Each callback is pending, active or dropped. `subscription.rs`.

**Subscription**: A `#[must_use]` handle for an observer or subscriber. Dropping it cancels the callback, and `detach()` keeps the callback alive. `subscription.rs`.

## T

**TaffyLayoutEngine**: GPUI's wrapper around the Taffy layout library. It creates layout nodes, solves the layout and returns bounds. `taffy.rs`.

**Task<T>**: A handle to a future that is running. It comes from the `scheduler` crate and is re-exported in `executor.rs`. Hold it or call `.detach()`, because dropping it cancels the work. `Context::spawn` documents "The returned task must be held or detached." `TaskExt::detach_and_log_err` helps with `Task<Result<..>>`.

**TestAppContext**: The context given to `#[gpui::test]` tests. It uses a deterministic scheduler and a fake platform, and it panics instead of returning errors. `app/test_context.rs`.

**TextRun** / **Font** / **ShapedLine** / **LineLayout**: A `TextRun` is the styling for one range of text. A `Font` describes a font. A `ShapedLine` is a line of text laid out into glyphs and ready to paint. A `LineLayout` holds its glyph runs. `text_system.rs`, `text_system/line.rs`, `text_system/line_layout.rs`.

**TextSystem** / **WindowTextSystem**: `TextSystem` is the app-wide front end for fonts and glyphs, over a `PlatformTextSystem`. `WindowTextSystem` adds a per-window cache of laid-out lines. `text_system.rs`.

## U

**UniformListScrollHandle**: The handle for controlling scroll in a `uniform_list`, which is a list of same-height rows. `elements/uniform_list.rs`.

## V

**View**: A trait that treats `Render` entities and `RenderOnce` components alike, as things that render into elements. A view can optionally be keyed by an entity id, for caching and invalidation. **ViewElement<V>** is the element that does the work. `view.rs`.

## W

**WeakEntity<T>**: A handle that does not keep its entity alive. `upgrade()` returns an `Option<Entity<T>>`, and `update` returns a `Result`. `app/entity_map.rs`.

**Window**: The state of one window: the platform window, the root view, two frames, the layout engine, focus, input state and the text system. It is not a context. You get it as `&mut Window` next to `cx`. `window.rs`.

**WindowInvalidator** *(crate-private)*: The per-window record of what needs redrawing: a dirty flag, a set of dirty views and the current draw phase. It can wake the platform's frame source. `window.rs`.

**WindowOptions**: The settings you pass to `open_window`: bounds, titlebar, window kind, appearance and more. `platform.rs`.

## Next steps

- [The big picture](/deep-dive/big-picture/): see how the main terms fit together.
- [Common errors](/reference/common-errors/): look up a panic or compile error you are seeing.
- [How to read the source](/codebase/how-to-read-the-source/): follow a term into the code.

<details>
<summary>Where this lives in the source</summary>

- Each entry names its own file. Most are under `crates/gpui/src/`.
- `crates/gpui_macros/src/derive_action.rs`
- `crates/gpui_shared_string/gpui_shared_string.rs`
</details>
