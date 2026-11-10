---
title: Examples index
description: Find the shipped GPUI example that shows the feature you want, and the command to run it.
sidebar:
  order: 1
---

:::note[Reference]
This is a lookup page for readers who have finished the beginner path. If you have not run an example yet, start with [Running the examples](/start/running-examples/). To understand the code you find here, read [Thinking in GPUI](/start/thinking-in-gpui/) and [State and views](/guides/state-and-views/) first.
:::

The GPUI repository ships dozens of small, runnable programs. They are the best way to see one feature in isolation. This page lists every one, grouped by topic, with a plain description of what it shows.

:::tip[In short]
- Run any example from the root of the Zed repository with `cargo run -p gpui --example <name>`.
- Scan the topic tables below for the feature you want, then open that file in `crates/gpui/examples/`.
- Start with `hello_world`, then `input`, `uniform_list`, `testing`, `ownership_post` and `view_example`.
:::

## How to use this page

All examples live in `crates/gpui/examples/`. Run one from the root of the Zed repository, replacing `<name>` with the name in the first column:

```sh
cargo run -p gpui --example <name>
```

For example, `cargo run -p gpui --example hello_world` opens a small window with a greeting. Cargo builds GPUI the first time, so expect a long first compile.

The descriptions come from the `//!` docs in each file, the examples' `README.md`, and the APIs each file actually uses. All of this was checked by reading the files at commit `b5cd310b`.

### How examples are declared

`crates/gpui/Cargo.toml` has explicit `[[example]]` entries for some files. They are marked **reg.** (registered) in the tables. For examples that live in a directory, the entry is how the name maps to the path. For instance, `image` maps to `examples/image/image.rs`.

Cargo finds the remaining files through its normal example auto-discovery (the manifest only sets `autobenches = false`). The `example_support/fonts.rs` file is shared support code (`load_fonts(cx)`). On non-wasm targets it just returns `true`. On wasm it registers the bundled IBM Plex Sans and Lilex fonts.

### The common skeleton

Most examples share one skeleton, so once you have read one you can read them all:

```rust
gpui_platform::application().run(|cx: &mut App| {
    // ...
    cx.open_window(WindowOptions { .. }, |_, cx| cx.new(|_| MyView));
    // ...
    cx.activate(true);
});
```

Many examples also have `#![cfg_attr(target_family = "wasm", no_main)]` and a `#[wasm_bindgen(start)]` entry, so they can run in the browser too.

## Start here

| Example | What it shows |
| --- | --- |
| `hello_world` (reg.) | The minimal app: `application().run`, `Bounds::centered`, `open_window`, and a root view implementing `Render` that returns a styled `div` with a child. |
| `input` (reg.) | A complete single-line text field: focus, `EntityInputHandler` and `ElementInputHandler`, selections, clipboard, keyboard actions bound with `KeyBinding`, custom painting with `paint_quad`, plus `#[gpui::test]` tests. |
| `uniform_list` (reg.) | `uniform_list` with `cx.processor(...)`: a virtualised list of 50 uniform rows. |
| `testing` | The testing infrastructure. It is an interactive counter window, and the file's tests use `#[gpui::test]`, `TestAppContext`, actions, focus and `open_window`. The file's header gives the test command: `cargo test -p gpui --example testing --features test-support`. |
| `ownership_post` | Entities, `cx.subscribe` and `EventEmitter` with a counter and a subscriber. It supports the `_ownership_and_data_flow` documentation, so read it alongside [How GPUI owns your data](/deep-dive/ownership-and-data-flow/). |
| `view_example` (reg.) | Composing a text input from the `View` primitives: an `Editor` entity (cursor, blink, focus, keyboard), and `Input` and `TextArea` shaping layers. The files are `view_example_main.rs`, `example_editor.rs`, `example_input.rs`, `example_text_area.rs` and `example_tests.rs`. The tests need `--features test-support`. |

## Layout and styling

| Example | What it shows |
| --- | --- |
| `grid_layout` (reg.) | CSS-grid style layout: `.grid().grid_cols(5).grid_rows(5)` and grid placement of children. |
| `opacity` (reg.) | `opacity(...)` on images, SVG and elements with shadows. Also an `AssetSource` for the SVG and image files, and a `list`. |
| `pattern` (reg.) | Patterned backgrounds with `pattern_slash(...)` and `linear_gradient`. |
| `shadow` (reg.) | Box shadows: many `BoxShadow` configurations that vary `blur_radius` and `spread_radius`. |
| `text` (reg.) | A typography showcase (the window is titled "GPUI Typography"): text size, line height and font family styling, and a `set_menus` call. |
| `text_layout` | Text alignment (left, center, right), underline and strikethrough decorations, font weights and styles, and `StyledText` with highlights. |
| `text_wrapper` (reg.) | Wrapping and truncation: `truncate`, `text_ellipsis` and `line_clamp`. |
| `gradient` | `linear_gradient` fills in different `ColorSpace`s, painted both on `div`s and with `canvas` + `PathBuilder` + `paint_path`. |
| `tree` (reg.) | A very deep tree of nested `div`s (default depth 50, overridable with `GPUI_TREE_DEPTH`), to exercise deep hierarchies. |

## Interaction and focus

| Example | What it shows |
| --- | --- |
| `anchor` | `anchored()` with each `Anchor` corner and edge, inside `deferred(...)`, so the popup chooses the side of the button it opens on. |
| `popover` | Floating layers composed from `deferred` and `anchored`. |
| `data_table` | A virtualised table: `uniform_list` with `UniformListScrollHandle`, random stock-style rows, truncating cells, and a custom scrollbar drawn with `canvas`. |
| `drag_drop` | `on_drag` (with a drag payload type and a drag preview view) and `on_drop` targets with opacity feedback. |
| `focus_visible` | Keyboard-only focus styling with `focus_visible(...)`, `track_focus`, `tab_index` and `tab_stop`, key bindings and actions. |
| `tab_stop` (reg.) | Tab-order navigation: `FocusHandle::tab_index(n).tab_stop(true)`. The `Tab` and `TabPrev` actions call `window.focus_next(cx)` and `window.focus_prev(cx)`. |
| `scrollable` | Nested scrolling containers with `overflow_scroll()` ("two way scroll in nested layout"). |
| `list_example` (reg.) | `list(...)` with `ListState::new(count, ListAlignment::Bottom, ..)`: bottom-aligned list state and scrollbar behaviour. |
| `mouse_pressure` (reg.) | `on_mouse_pressure` and `MousePressureEvent` (`PressureStage` and amount), where the hardware supports it (macOS trackpads). |
| `active_state_bug` | A reproduction of a bug: the `.active()` background on a button getting stuck on every other click. Useful when working on GPUI itself. |
| `a11y` (reg.) | AccessKit accessibility: `role(...)`, `aria_label`, `tab_stop`, `track_focus` and actions. On Linux, the file notes `cargo run -p gpui --features gpui_platform/wayland,gpui_platform/x11 --example a11y`. |

## Images, drawing and animation

| Example | What it shows |
| --- | --- |
| `animation` | `with_animation` and `Animation::new(duration).with_easing(bounce(ease_in_out))`, `Transformation::rotate` on an SVG, and `SpringAnimation` with `SpringConfig`. It also contains a `#[gpui::test]`. |
| `gif_viewer` | `img(path)` showing an animated GIF (`examples/image/black-cat-typing.gif`). |
| `image` (reg.) | Loading images from local files, URLs (including a GitHub Actions badge) and embedded sources through `ImageSource`. Also `AssetSource` setup, `set_menus` and key bindings. |
| `image_gallery` | Image caching with `RetainAllImageCache` as an `ImageCacheProvider`, remote images, menus and key bindings. |
| `image_loading` | Loading and fallback elements for `img(...)`, an intentionally failing image, `ImageCache`, and a custom `AssetSource`. |
| `painting` | Custom drawing in a `canvas` element: building `Path`s with `PathBuilder` (lines, curves), `paint_path`, `paint_quad` and `linear_gradient`. |
| `paths_bench` | A path-rendering benchmark window titled "Vulkan". Specialised, for GPUI development. |
| `svg` (reg.) | `svg().path(...)` rendering with an `AssetSource` rooted at `examples/` (it uses `svg/dragon.svg`, `image/color.svg` and `image/arrow_circle.svg`). |

## Windows and application behaviour

| Example | What it shows |
| --- | --- |
| `window` | Opening normal, `WindowKind::Dialog`, `PopUp` and `Floating` windows, nested dialogs, windows with `is_movable: false`, and custom titlebars. |
| `window_positioning` | Placing windows on specific displays. It iterates `cx.displays()` and passes `display_id`, `WindowBounds::Windowed`, `WindowKind` and `WindowBackgroundAppearance`. |
| `window_shadow` (reg.) | Client-side window decorations: `Decorations::Client`, `window.set_client_inset`, a painted shadow, resize-edge hit testing and `cx.observe`. A comment in the file says shadow rendering needs significant improvement. |
| `window_movable` (reg.) | The `is_movable` window option, with a window for each setting. |
| `move_entity_between_windows` (reg.) | An entity registers callbacks with the `_in` API family and is re-hosted in a new window. The callbacks keep targeting the entity's current window. |
| `on_window_close_quit` (reg.) | Quitting the application when a window closes, using `cx.on_window_closed` and `cx.quit()`, with a `cmd-w` `CloseWindow` key binding. |
| `set_menus` (reg.) | Application menu setup with `cx.set_menus(...)` and `on_action` handlers. |
| `system_notifications` (reg.) | Posting, replacing, dismissing and responding to OS notifications through `show_system_notification`. |
| `layer_shell` | Wayland layer-shell surfaces (`gpui::layer_shell::*`), for panels and overlays. It requires Linux and the `wayland` feature. Otherwise the program panics with "This example requires the `wayland` feature and a linux system." |
| `toggle_headless` (reg.) | Linux only. It starts headless and attaches to or detaches from Wayland or X11 at runtime, while preserving the app and its entities. It reads commands from stdin: `ls`, `create [message]`, `open`, `close`, `quit`. Use `open DISPLAY=:1` or `WAYLAND_DISPLAY=… XDG_RUNTIME_DIR=…` to target another display server. |

## The browser gallery

`crates/gpui_web/examples/hello_web` builds several of the examples above for the browser with [Trunk](https://trunk-rs.github.io/trunk/):

```sh
cd crates/gpui_web/examples/hello_web
trunk serve        # then open http://localhost:8080/
```

Its `Cargo.toml` declares binaries that point at the original sources: `hello-world` (`hello_world.rs`), `text`, `text-layout`, `text-wrapper` and `input`. It also has gallery-only binaries: `dynamic-fonts`, `font-fallback-test`, `queue-test`, `http-client-test`, and `hello-web` (`main.rs`, which includes the `/prime-sieve` background-task demo).

`crates/gpui/examples/README.md` documents the gallery, the cross-origin isolation headers needed for shared memory, and the dynamic font loading demo (`App::on_missing_glyphs`).

## Other places with runnable code

| Location | What it is |
| --- | --- |
| `crates/gpui_ios/examples/ios.rs` and `crates/gpui_ios/examples/ios/` | An iOS sample app (Info.plist, `build-simulator.sh`). |
| `crates/gpui_platform/benches/` | Criterion benchmarks (`primitives`, `atlas_upload`, `inspector_render`, `randomized_element_tree`), with `required-features = ["bench-support"]`. |
| `crates/gpui/benches/focus_cleanup.rs` | Registered as a bench of `gpui_platform` (`path = "../gpui/benches/focus_cleanup.rs"`). |
| `crates/gpui_wgpu/benches/layout_line.rs` | A text layout benchmark. |

## Next steps

- [Running the examples](/start/running-examples/): setup and troubleshooting for your first run.
- [Cargo features and environment variables](/reference/cargo-features/): flags some examples need, such as `test-support`.
- [How to read the source](/codebase/how-to-read-the-source/): find your way around the crates behind these examples.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/examples/` and `crates/gpui/examples/README.md`
- `crates/gpui/Cargo.toml` (the `[[example]]` entries)
- `crates/gpui/examples/example_support/fonts.rs`
- `crates/gpui_web/examples/hello_web/`
</details>
