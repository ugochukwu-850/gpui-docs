---
title: Where everything lives
description: A map of crates/gpui/src grouped by job, so you can find the file for any GPUI concept and see how big each one is.
sidebar:
  order: 3
  label: Where everything lives
---

This page is a map of `crates/gpui/src`, the heart of GPUI. Use it to find the file behind any concept, and to know what you are walking into before you open it. It describes commit `b5cd310b`.

## What you'll learn

- The six main groups the files fall into (runtime, UI tree, input, rendering, text, platform glue), plus tooling and docs-only files.
- How the main types own each other (the diagram under "The mental model").
- Which file to open for each concept, and how large it is.

:::note[Advanced]
This page is for readers who are about to read GPUI source files and want to know where to look. Skim the tables first. Come back to them with a question in mind, because they are reference material.
:::

:::tip[In short]
1. `crates/gpui/src/gpui.rs` is the *crate root*. It declares every module and re-exports (`pub use`) nearly everything, so you write `gpui::Foo` instead of `gpui::window::Foo`.
2. Three files are much bigger than the rest: `window.rs` (10,680 lines), `platform.rs` (4,017) and `app.rs` (3,890). Most of the framework's behaviour is in them.
3. One `App` owns everything. Each `Window` owns its frames, and each frame owns the drawing and input data for that moment.
:::

## The mental model

A *module* is a Rust source file (or folder) that groups related code. The *crate root* is the first file Rust reads and the one that lists the modules. For `gpui` it is `src/gpui.rs`, set with `[lib] path` in `Cargo.toml`.

Here is how the main objects own each other at run time. The file that defines each one is on the right.

```text
App                       app.rs            the one owner of everything
 |-- EntityMap            app/entity_map.rs owns every Entity<T> (your state)
 |-- Keymap, ActionRegistry                 keymap.rs, action.rs
 |-- Platform (a trait)   platform.rs       implemented by gpui_linux, gpui_macos, ...
 |-- windows              one Window per open window
      |
      `-- Window          window.rs
           |-- root: AnyView                  view.rs   (the top view)
           |-- rendered_frame, next_frame     the frame on screen / the frame being built
           |      |-- Scene                   scene.rs  (+ bounds_tree.rs)
           |      |-- hitboxes, mouse_listeners
           |      `-- DispatchTree            key_dispatch.rs
           |-- TaffyLayoutEngine              taffy.rs
           |-- WindowTextSystem               text_system.rs
           `-- platform_window: Box<dyn PlatformWindow>   the native window
```

New words in that picture:

- A **frame** is everything GPUI builds to show one picture of your window.
- A **hitbox** is a rectangle that says "the mouse can hit me here".
- A **scene** is the list of shapes and text to draw, before any graphics API sees it.
- The **dispatch tree** records which elements can receive keyboard input.

The pages [How a frame is drawn](/codebase/frame-lifecycle/) and [How input finds your code](/codebase/input-and-dispatch-internals/) explain them in detail. You do not need them yet.

## The groups

```text
crates/gpui/src
 |
 |-- CORE RUNTIME ......... app.rs  app/  global.rs  subscription.rs  arena.rs
 |                          executor.rs  platform_scheduler.rs  asset_cache.rs
 |                          assets.rs  util.rs  queue.rs  shared_uri.rs
 |-- UI TREE .............. element.rs  view.rs  elements/  window.rs  window/
 |                          style.rs  styled.rs  taffy.rs  geometry.rs  color.rs
 |                          colors.rs  spring.rs  tab_stop.rs  prelude.rs
 |-- INPUT ................ interactive.rs  input.rs  key_dispatch.rs  keymap.rs
 |                          keymap/  action.rs  gestures.rs  platform/keystroke.rs
 |-- RENDERING ............ scene.rs  bounds_tree.rs  path_builder.rs
 |                          svg_renderer.rs  debug_overlay.rs
 |-- TEXT ................. text_system.rs  text_system/  elements/text.rs
 |-- PLATFORM GLUE ........ platform.rs  platform/  platform_scheduler.rs
 |-- TOOLING / TEST ....... test.rs  bench.rs  seeds.rs  randomized_element_tree.rs
 |                          profiler.rs  profiler/  inspector.rs  hot_reload.rs
 |                          app/test_*.rs  app/bench_context.rs
 `-- DOCS-ONLY MODULES .... _ownership_and_data_flow.rs  _accessibility.rs
```

Outside `src/`: `examples/` (see the [examples index](/reference/examples-index/)), `docs/contexts.md` and `docs/key_dispatch.md` (short prose guides), `benches/focus_cleanup.rs`, `tests/action_macros.rs`, `build.rs` and `resources/windows/` (the Windows manifest).

Sizes in the tables are line counts of the file or directory. Each description was checked against the head of the file or its doc comment.

## Core runtime

State, ownership, async and the reactive graph.

| Path | Lines | What it is |
| --- | ---: | --- |
| `gpui.rs` | 353 | Crate root. Module list, re-exports, and three central traits: `AppContext` (create/update/read entities, windows, globals, spawn background work), `VisualContext` (the same plus window-scoped operations), `EventEmitter`. Also `BorrowAppContext`, `Reservation`, `GpuSpecs`, and the `#[doc(hidden)] private` module used by macro expansions. |
| `app.rs` | 3,890 | `Application` (builder, `run`), `App` (the owner of everything), `AppCell` (a `RefCell<App>` wrapper that reports where a double borrow started), the private `Effect` enum, `flush_effects`, observers/subscriptions, globals, keymap and action registration on the app, clipboard/menu/URL/notification pass-throughs to the platform. |
| `app/` | 7,496 | `context.rs` (`Context<T>`, the per-entity wrapper around `&mut App`), `entity_map.rs` (`Entity`, `WeakEntity`, `AnyEntity`, `EntityMap`, leasing, reference counts, leak detector), `async_context.rs` (`AsyncApp`, `AsyncWindowContext`). Test-only: `test_context.rs` (`TestAppContext`, `VisualTestContext`), `test_app.rs` (`TestApp`), `headless_app_context.rs`, `visual_test_context.rs` (macOS), `bench_context.rs` (`BenchAppContext`). |
| `global.rs` | 75 | The `Global` marker trait plus `ReadGlobal` / `UpdateGlobal` helpers. |
| `subscription.rs` | 559 | `SubscriberSet`, `SingleSubscriberSet` (callback registries keyed by emitter) and `Subscription` (cancel-on-drop handle). |
| `arena.rs` | 401 | A bump allocator (`Arena`, `ArenaBox`) used for per-frame elements and for `Effect::Emit` payloads. |
| `executor.rs` | 626 | `ForegroundExecutor`, `BackgroundExecutor`, `SendForegroundExecutor`, `TaskExt::detach_and_log_err`. Re-exports `Task`, `Priority` and friends from the external `scheduler` crate. |
| `platform_scheduler.rs` | 457 | `PlatformScheduler`: adapts a `PlatformDispatcher` to the `scheduler::Scheduler` trait. |
| `asset_cache.rs` | 358 | The `Asset` trait (async-loaded, cached resources keyed by a source value), `AssetLogger`, `Resource`. |
| `assets.rs` | 133 | `AssetSource` (where embedded/bundled bytes come from) and `RenderImage`. |
| `util.rs` | 252 | `FluentBuilder` (`.when`, `.when_some`, `.map`), `FutureExt` / `Timeout` helpers for futures. |
| `queue.rs` | 541 | A priority queue with weighted random selection between priorities. Compiled only for Windows, Linux, wasm, tests and test/bench features. |
| `shared_uri.rs` | 25 | `SharedUri`, a `SharedString` newtype for URIs. |

## UI tree

Declaring, laying out and painting the interface.

| Path | Lines | What it is |
| --- | ---: | --- |
| `element.rs` | 1,003 | `Element` (the three-phase trait), `IntoElement`, `Render`, `RenderOnce`, `ParentElement`, `GlobalElementId`, `Drawable<E>` (the per-element phase state machine), `AnyElement`, `Empty`. |
| `view.rs` | 675 | `View` trait, `AnyView`, `AnyWeakView`, `ViewElement<V>`: the element that renders an `Entity<T: Render>` or a `RenderOnce` value and implements view caching (`reuse_prepaint` / `reuse_paint`). |
| `window.rs` | 10,680 | `Window` (per-window state and the whole draw loop), `Frame`, `WindowInvalidator`, `FocusHandle`, `Hitbox`, painting primitives (`paint_quad`, `paint_glyph`, ...), input dispatch (`dispatch_event`, `dispatch_key_event`, `dispatch_mouse_event`), `WindowHandle`, `ElementId`. By far the largest file. |
| `window/` | 1,467 | `a11y.rs` (AccessKit tree building), `a11y/debug.rs`, `prompts.rs` (the built-in fallback prompt dialog). |
| `elements/` | 15,829 | The built-in elements. See table below. |
| `style.rs` | 1,529 | `Style`, `TextStyle`, `Display`, `Overflow`, `Visibility`, `Fill`, and how a `Style` is painted. |
| `styled.rs` | 904 | The `Styled` trait (Tailwind-like builder methods). Most methods are generated by macros from `gpui_macros`. |
| `taffy.rs` | 787 | `TaffyLayoutEngine`, `LayoutId`, `AvailableSpace`, and the conversion from GPUI `Style` to `taffy::style::Style`. |
| `geometry.rs` | 4,088 | `Point`, `Size`, `Bounds`, `Edges`, `Corners`, and the unit types `Pixels`, `ScaledPixels`, `DevicePixels`, `Rems`, plus `Length` / `DefiniteLength` / `AbsoluteLength`. |
| `color.rs` | 1,070 | `Rgba`, `Hsla`, `Background` (solid, gradients, patterns), `linear_gradient`, `pattern_slash`, `checkerboard`. |
| `colors.rs` | 123 | `Colors` / `GlobalColors`: the default palette GPUI itself uses for examples and base components. |
| `spring.rs` | 830 | Spring physics for animation: `SpringConfig`, `SpringAnimation`, `Interpolate`. |
| `tab_stop.rs` | 616 | `TabStopMap`: tab-order bookkeeping for `FocusHandle`s (built on `sum_tree`). |
| `prelude.rs` | 9 | The glob-import set (`use gpui::prelude::*`): `Render`, `RenderOnce`, `IntoElement`, `Styled`, `InteractiveElement`, `ParentElement`, `FluentBuilder`, `VisualContext`, ... |
| `inspector.rs` | 271 | `InspectorElementId` and the reflection support types used by the in-app inspector. Mostly compiled only with the `inspector` feature or `debug_assertions`. |
| `_accessibility.rs`, `_ownership_and_data_flow.rs` | 295, 140 | Prose-only modules, compiled under `#[cfg(doc)]` so they show up in rustdoc. |

### `elements/`

| File | Lines | Element |
| --- | ---: | --- |
| `div.rs` | 5,793 | `Div`, `Stateful<E>`, `Interactivity`, `InteractiveElement`, `StatefulInteractiveElement`, `ScrollHandle`. The "HTML div": layout container plus all mouse, key, focus, drag and hover handling. |
| `list.rs` | 3,892 | `list(...)` and `ListState`: virtualised list of variable-height items. |
| `uniform_list.rs` | 936 | `uniform_list(...)`: virtualised list where all rows have the same height (skips taffy for the rows). |
| `text.rs` | 1,349 | `StyledText`, `TextLayout`, `InteractiveText`: text as an element; measures through the text system during layout. |
| `animation.rs` | 1,028 | `Animation`, `AnimationExt::with_animation`, easing functions. |
| `img.rs` | 918 | `img(...)`: images from files, URLs, embedded bytes, with loading/fallback states. |
| `anchored.rs` | 579 | `anchored()`: places a child at an anchor point and keeps it inside the window. |
| `deferred.rs` | 319 | `deferred(...)`: lays a child out in place but paints it after its ancestors (for popovers). |
| `svg.rs` | 303 | `svg()`: SVG rendering with optional transformation. |
| `image_cache.rs` | 330 | Image cache elements used by `img`. |
| `surface.rs` | 134 | `surface(...)`: paints an externally supplied surface (the source type documented in the file is a CoreVideo image buffer, i.e. macOS). |
| `container_query.rs` | 126 | An element that renders differently depending on the space its parent offers. |
| `canvas.rs` | 95 | `canvas(prepaint, paint)`: low-level drawing without defining a whole element. |
| `mod.rs` | 27 | Re-exports. |

## Input

How platform events and keystrokes become mouse listeners and actions. See [How input finds your code](/codebase/input-and-dispatch-internals/).

| Path | Lines | What it is |
| --- | ---: | --- |
| `interactive.rs` | 998 | `PlatformInput` (the enum every backend produces), the concrete event structs (`KeyDownEvent`, `MouseDownEvent`, `ScrollEvent`, `ClickEvent`, ...), `ExternalPaths`, `FileDropEvent`. |
| `input.rs` | 611 | `EntityInputHandler` and `ElementInputHandler`: bridge from the platform's text-input/IME protocol to your view. |
| `key_dispatch.rs` | 2,216 | `DispatchTree` (nodes, key contexts, action listeners, focus nodes, view nodes), `dispatch_key`, `flush_dispatch`, replay of pending multi-stroke input. |
| `keymap.rs` | 1,143 | `Keymap` and its binding resolution (precedence, `NoAction`, `Unbind`, pending multi-key sequences). |
| `keymap/` | 1,055 | `binding.rs` (`KeyBinding`), `context.rs` (`KeyContext`, `KeyBindingContextPredicate`, the context-matching mini language). |
| `action.rs` | 456 | The `Action` trait, the `actions!` macro, `ActionRegistry` built from `inventory` registrations, `NoAction`, `Unbind`. |
| `gestures.rs` | 2,331 | Touch gesture recognition (tap, pan with momentum, long press, back gesture) and `PlatformGestures`. |
| `platform/keystroke.rs` | 813 | `Keystroke`, `Modifiers`, parsing strings like `"cmd-shift-p"`. |

## Rendering

Turning painted primitives into something a GPU API can draw. See [How a frame is drawn](/codebase/frame-lifecycle/).

| Path | Lines | What it is |
| --- | ---: | --- |
| `scene.rs` | 949 | `Scene` and the primitives: `Quad`, `Shadow`, `Underline`, `Path`, `MonochromeSprite`, `SubpixelSprite`, `PolychromeSprite`, `PaintSurface`; `PrimitiveBatch`; draw ordering. |
| `bounds_tree.rs` | 472 | `BoundsTree`: an R-tree variant used by `Scene` to assign each primitive a z-order (one more than the max of overlapping bounds). Not used for hit testing. |
| `path_builder.rs` | 347 | `PathBuilder`: builds fill/stroke `Path`s with `lyon` tessellation. |
| `svg_renderer.rs` | 525 | `SvgRenderer`: parses SVG with `usvg` and rasterises with `resvg` into atlas-ready bitmaps. |
| `debug_overlay.rs` | 428 | Frame-time overlay painted straight into the `Scene`. Only with the `profiler` feature. |

## Text

| Path | Lines | What it is |
| --- | ---: | --- |
| `text_system.rs` | 1,396 | `TextSystem` (fonts, metrics, glyph rasterisation front end over a `PlatformTextSystem`), `WindowTextSystem` (per-window line layout cache), `Font`, `TextRun`, `RenderGlyphParams`. |
| `text_system/line_layout.rs` | 1,057 | `LineLayout`, `WrappedLineLayout`, `LineLayoutCache`, `FontRun`. |
| `text_system/line.rs` | 1,979 | `ShapedLine`, `WrappedLine`: painting laid-out text (glyph quads, underlines, strikethroughs). |
| `text_system/line_wrapper.rs` | 2,069 | `LineWrapper`: word wrapping and truncation. |
| `text_system/font_features.rs`, `font_fallbacks.rs` | 154, 21 | OpenType feature flags and fallback family lists for a `Font`. |

The actual shaping and rasterisation is done by a backend implementation of `PlatformTextSystem`: `CosmicTextSystem` in `gpui_wgpu`, `DirectWriteTextSystem` in `gpui_windows`, `AppleTextSystem` in `gpui_apple`.

## Platform glue

| Path | Lines | What it is |
| --- | ---: | --- |
| `platform.rs` | 4,017 | The traits a backend implements (`Platform`, `PlatformWindow`, `PlatformDisplay`, `PlatformDispatcher`, `PlatformTextSystem`, `PlatformAtlas`, `PlatformInputHandler`), plus window options, cursor styles, clipboard types, image decoding helpers, and an atlas helper (`AtlasState`). |
| `platform/app_menu.rs` | 426 | `Menu`, `MenuItem`, `OwnedMenu`, `init_app_menus`. |
| `platform/keyboard.rs` | 41 | `PlatformKeyboardLayout`, `PlatformKeyboardMapper`. |
| `platform/platform_info.rs` | 49 | `PlatformInfo`, `OperatingSystem`, `PlatformTarget`. |
| `platform/popup.rs`, `platform/layer_shell.rs` | 134, 83 | Parent-anchored popup window options; Wayland layer-shell options (`layer_shell` only with `wayland` on Linux). |
| `platform/scap_screen_capture.rs` | 325 | Screen capture on Linux and Windows through the `scap` crate (feature `screen-capture`). |
| `platform/threaded_dispatcher.rs` | 744 | A thread-pool `PlatformDispatcher` for tests and benches. |
| `platform/test/`, `platform/test.rs`, `platform/visual_test.rs` | 1,676, 12, 280 | `TestPlatform`, `TestWindow`, `TestDisplay`, `TestDispatcher`; and `VisualTestPlatform` (real rendering plus a test dispatcher, macOS). |
| `hot_reload.rs` | 248 | Subsecond-based hot patching client (feature `hot-reload`, debug builds only). |

## Tooling and test support

| Path | Lines | What it is |
| --- | ---: | --- |
| `test.rs` | 172 | Module docs and helpers for `#[gpui::test]`. Compiled with `test-support`. |
| `bench.rs`, `seeds.rs` | 65, 67 | The Criterion integration for `#[gpui::bench]`, and `calculate_seeds` (reads `SEED` / `ITERATIONS`). |
| `randomized_element_tree.rs` | 2,031 | A seeded, mutable random element tree for rendering benchmarks and tests. |
| `profiler.rs`, `profiler/` | 2,227, 5,740 | Task/frame/thread profiling: journal of foreground work, hang detector (`hang.rs`, `hang/monitor.rs`), action timing. Mostly behind the `profiler` feature. |

## Try it yourself

These are reading exercises. Nothing here changes the repository.

1. Run `wc -l crates/gpui/src/*.rs | sort -n | tail -5` from the repository root. Do the three biggest files match the "In short" box?
2. Open `crates/gpui/src/gpui.rs`. Which `mod` lines have a `#[cfg(...)]` attribute above them? Those modules are compiled only in some builds. Compare with what the tables say about `queue.rs` and `inspector.rs`.
3. Find the `pub use window::*;` line in `gpui.rs`. What would you have to write to name `Window` if that line were not there?
4. Pick one concept from your own app (say `div`, `SharedString`, or `Keystroke`) and find its row in the tables. Open the file and read the first 30 lines.
5. Find `Window` in `window.rs` and locate the fields `rendered_frame` and `next_frame`. They are the two frames the diagram above shows.

## Next steps

- [How a frame is drawn](/codebase/frame-lifecycle/): uses `app.rs`, `window.rs`, `element.rs`, `taffy.rs` and `scene.rs` together.
- [How state is stored and updated](/codebase/app-and-entity-internals/): the "core runtime" group in detail.
- [How input finds your code](/codebase/input-and-dispatch-internals/): the "input" group in detail.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/gpui.rs` (crate root and re-exports)
- every file named in the tables above, under `crates/gpui/src`
- `crates/gpui/Cargo.toml` (`[lib] path`)
</details>
