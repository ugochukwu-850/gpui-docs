---
title: How to read the GPUI source
description: "Practical advice for navigating the GPUI codebase: where to start for a given question, search commands that work, the naming habits to look for, and twelve reading exercises."
sidebar:
  order: 2
  label: How to read the source
---

GPUI's own README says: "Currently, the best way to learn about these APIs is to read the Zed source code". This page is a field guide for doing that. All paths are relative to the repository root, and all names were checked at commit `b5cd310b`.

## What you'll learn

- A five-minute way to get oriented in the crate.
- Which file to open first for a given question.
- Search commands that find things in a 100,000-line codebase.
- Naming habits (`_in`, `with_`, `pub(crate)`) that tell you what a function does before you read it.

:::note[Advanced]
This page is for readers who have the source on disk (see [Start here](/codebase/overview/)) and want to move around in it quickly. It assumes you can run commands in a terminal.
:::

:::tip[In short]
1. Start with the module list in `crates/gpui/src/gpui.rs` and the doc comments. They are the table of contents.
2. Search for names, not for files. `rg` (ripgrep) plus your editor's "go to symbol" will beat scrolling.
3. Many methods exist twice (on `Window` and on `Context<T>`), and `pub(crate)` items are still where the real work happens.
:::

## Orient yourself in five minutes

1. Open `crates/gpui/src/gpui.rs` (353 lines). The `mod` list is the table of contents. The `pub use` lines tell you what is public. The `AppContext`, `VisualContext` and `EventEmitter` traits are defined here.
2. Read `crates/gpui/README.md`, section "The Big Picture". It describes the three *registers* GPUI works in: entities (shared application state), views (entities that can draw themselves, written as high-level declarative UI), and elements (the low-level building blocks, with full control over layout and painting).
3. Read `crates/gpui/src/_ownership_and_data_flow.rs` and `crates/gpui/docs/contexts.md`. These are the authors' own prose.
4. Keep [Where everything lives](/codebase/gpui-crate-map/) open in another tab to find the file for any concept.

:::note[Two modules you will not see in a normal build]
`_accessibility` and `_ownership_and_data_flow` are declared only under `#[cfg(doc)]` in `gpui.rs`. `#[cfg(doc)]` means "compile this only when generating rustdoc", so the files exist on disk but are not part of a normal build. `gpui.rs` also has `#![warn(missing_docs)]`: public items are expected to carry doc comments, so the comments are usually worth reading before the code.
:::

## Where to start for a given question

| Question | Start in | Then |
| --- | --- | --- |
| How do I make X appear on screen? | `crates/gpui/examples/` (see the [examples index](/reference/examples-index/)) | `elements/div.rs`, `styled.rs` |
| What does this `Styled` method do? | `crates/gpui_macros/src/styles.rs` (methods are generated) | `style.rs` for the fields they set |
| How does a state change cause a redraw? | `app/context.rs::notify` | [How a frame is drawn](/codebase/frame-lifecycle/) |
| Why did this panic with "already being updated"? | `app/entity_map.rs::double_lease_panic` | [How state is stored and updated](/codebase/app-and-entity-internals/) |
| How is layout computed? | `taffy.rs`, `Element::request_layout` in the element you care about | `window.rs::draw_roots` |
| How are things drawn? | `Window::paint_quad` and friends in `window.rs`, `scene.rs` | the backend renderer ([platform backends](/codebase/platform-backends/)) |
| Why does hover or click not reach my element? | `Window::insert_hitbox`, `Frame::hit_test` in `window.rs` | `elements/div.rs::paint_mouse_listeners` |
| How do keybindings resolve? | `key_dispatch.rs`, `keymap.rs` | `keymap/context.rs` |
| What is an action? | `action.rs` | `gpui_macros/src/derive_action.rs` |
| What does `#[derive(IntoElement)]` generate? | `gpui_macros/src/derive_into_element.rs` | `view.rs::ViewElement` |
| How do async tasks run? | `executor.rs`, `platform_scheduler.rs` | the backend's `dispatcher.rs` |
| What does the OS give GPUI? | `platform.rs` traits | `gpui_<os>/src/.../platform.rs` |
| How do I test this? | `test.rs`, `app/test_context.rs`, `examples/testing.rs` | `gpui_macros/src/test.rs` |
| How does Zed build a button? | `crates/ui/src/components/button/` | [A real component library](/codebase/reading-zed-ui-crate/) |

## Search patterns that work

All of these use `rg` ([ripgrep](https://github.com/BurntSushi/ripgrep)), a fast text search tool. Plain `grep -rn` works too. Run them from the repository root.

### Find trait implementations

In Rust, "how does X behave?" is often answered by finding every `impl` of a trait.

```sh
rg "impl Render for" crates/gpui/examples          # views in the examples
rg "impl RenderOnce for" crates/ui/src             # components
rg "impl Element for" crates/gpui/src              # all low-level elements
rg "impl Platform for" crates                      # every backend's Platform
rg "impl PlatformWindow for" crates                # every backend's window
rg "impl PlatformTextSystem for" crates            # text systems
rg "impl PlatformDispatcher for" crates            # executors' backends
rg "impl EventEmitter<" crates/gpui/src crates/ui/src
```

### Find the three phases of an element

Every element draws in three phases (`request_layout`, `prepaint`, `paint`). [How a frame is drawn](/codebase/frame-lifecycle/) explains them.

```sh
rg "fn request_layout" crates/gpui/src
rg "fn prepaint\b" crates/gpui/src
rg "fn paint\b" crates/gpui/src/elements
```

### Find where something is stored or triggered

```sh
rg "Effect::" crates/gpui/src                      # every producer/consumer of the effect queue
rg "fn flush_effects|fn push_effect|fn finish_update" crates/gpui/src/app.rs
rg "set_dirty|invalidate_view|\.refresh\(\)" crates/gpui/src
rg "schedule_frame|on_request_frame|frame_waker" crates   # frame pacing across backends
rg "scene\.insert_primitive|next_frame\.scene" crates/gpui/src/window.rs
rg "insert_hitbox" crates/gpui/src
rg "debug_assert_paint|debug_assert_prepaint" crates/gpui/src   # which API is allowed in which phase
```

### Find panics and error strings

Useful for decoding a message you saw.

```sh
rg "panic!\(|\.expect\(\"" crates/gpui/src --glob '!*test*'
rg "already being updated" crates/gpui/src
rg "can only be called during" crates/gpui/src
```

### Find feature-gated code

```sh
rg 'cfg\(.*feature = "test-support"' crates/gpui/src
rg 'cfg\(.*feature = "profiler"' crates/gpui/src | head
rg 'cfg\(.*target_os' crates/gpui/src/platform.rs
```

### Find where actions and key bindings are declared

```sh
rg "actions!\(" crates                              # unit actions
rg "derive\(.*Action" crates                        # actions with fields
rg "KeyBinding::new\(" crates/gpui/examples
rg "inventory::submit|inventory::collect" crates/gpui crates/gpui_macros
```

## Naming habits that save time

- **Jump by symbol, not by file.** `window.rs` is about 10,000 lines and `app.rs` about 3,900. Use your editor's outline, or `rg -n "^    pub fn|^    fn" crates/gpui/src/window.rs`.
- **Many methods exist in two places.** There is one on `Window` and a wrapper on `Context<T>`. For example `cx.on_next_frame(window, f)` wraps `window.on_next_frame`. Grep for the underlying name.
- **A name ending in `_in` takes a `Window` as well.** Examples are `observe_in`, `subscribe_in`, `defer_in` and `update_in`. The version without the suffix is the window-less variant.
- **A name starting with `with_` takes a closure and pushes and pops state around it.** Examples are `with_content_mask`, `with_element_offset`, `with_id`, `with_element_state` and `with_rendered_view`. The stacks they push to are fields near the top of `Window`.
- **`pub(crate)` means "visible inside the `gpui` crate only".** These items are implementation details, but they are still where the behaviour is. `Effect`, `DispatchTree`, `Frame`, `Arena` and `HitTest` are all `pub(crate)`.

## Read the doc comments first

Because of `#![warn(missing_docs)]`, public APIs mostly have good comments. Some are essential reading:

- `Window::insert_hitbox` and `HitboxBehavior`: how occlusion (one element blocking the mouse from elements behind it) works.
- `Window::on_mouse_event` and `Window::on_key_event`: "should only be called as part of the paint phase".
- `Context::listener` and `Context::processor`: why `cx.listener(...)` exists.
- `App::stop_propagation` and `App::propagate`: opposite defaults for mouse and action handlers.
- `View` in `view.rs`: the model that unifies `Render` and `RenderOnce`, and the caveat that two views keyed on the same entity must not be siblings.
- The module docs at the top of `element.rs`, `key_dispatch.rs`, `elements/div.rs`, `elements/list.rs` and `elements/uniform_list.rs`.
- `DisplayConnection`'s doc comment in `gpui_linux/src/linux/display_connection.rs`: the attach and detach lifecycle of display servers.

If you want generated HTML, `cargo doc -p gpui --open` builds it (this command was not run for this documentation). It includes the `#[cfg(doc)]` modules `_ownership_and_data_flow` and `_accessibility`. Items marked `#[doc(hidden)]` (the `private` module, `style_helpers!`, `MacroActionBuilder`) do not appear.

## Follow an event from the OS to your listener

Here is a worked route you can follow with `rg`. It uses Wayland, but the shape is the same on every backend.

1. Pick a backend. For Wayland, run `rg "fn handle_input" crates/gpui_linux/src/linux/wayland/window.rs`.
2. See who calls `handle_input`. It is the `Dispatch<wl_pointer::WlPointer, ()>` impl in `wayland/client.rs`.
3. `handle_input` calls `callbacks.input`, which is set by `PlatformWindow::on_input`. `rg "on_input" crates/gpui/src/window.rs` lands in `Window::new`.
4. That calls `Window::dispatch_event`, which calls `dispatch_mouse_event` (or `dispatch_key_event`).
5. Listeners were registered in the last paint: `rg "fn on_mouse_event" crates/gpui/src/window.rs`. The callers are in `elements/div.rs::paint_mouse_listeners`.
6. Your closure runs. If it calls `cx.notify()`, continue at [How a frame is drawn](/codebase/frame-lifecycle/).

The reverse route, from state to pixels, is the same page in the other direction: `Context::notify`, then `WindowInvalidator::invalidate_view`, `flush_effects`, `PlatformWindow::schedule_frame`, the backend's frame source, `Window::draw`, and finally `PlatformWindow::draw(&Scene)`.

## A suggested order for reading `window.rs`

The file is long, so read it in layers.

1. The types near the top: `WindowInvalidator` (about line 150), `DispatchPhase` (96), `FocusHandle` (536), `Hitbox` (834), `Frame` (1041), `Window` (1220), `ElementId` (7885).
2. `Window::new`, to see every platform callback being registered.
3. `Window::draw`, `draw_roots` and `present`.
4. The painting section: `paint_quad`, `paint_glyph`, `paint_layer`, `insert_hitbox`, `on_mouse_event`.
5. `dispatch_event`, `dispatch_mouse_event`, `dispatch_key_event` and `dispatch_action_on_node_inner`.
6. The `with_*` scope helpers (`with_element_state`, `with_content_mask`, and so on).

Line numbers are for commit `b5cd310b` and drift. Search for the name.

## Try it yourself

Each exercise has an answer you can verify in the source. They only read; none changes the repository. If you want to watch code run, copy an example into a scratch project outside the checkout and add `println!` calls there.

### Warm-up

1. **Count the frames.** In `examples/hello_world.rs`, which call opens the window, and which function draws the first frame before that call returns? (`App::open_window` calls `Window::draw` once.)
2. **Why is `Effect::Notify` deduplicated?** Find `pending_notifications` in `app.rs` and describe a case that benefits.
3. **Trace a double-lease.** Write down the call stack from `Entity::update` to `double_lease_panic` for an entity that updates itself.
4. **Which phase?** For each of `insert_hitbox`, `paint_quad`, `set_key_context`, `compute_layout`, `on_mouse_event` and `handle_input`, find the `debug_assert_*` call and note the permitted phase. Find the odd one: `set_focus_handle` asserts prepaint while `set_key_context` asserts paint.

### Going deeper

5. **Z-order.** Insert three overlapping rectangles in your head into `BoundsTree::insert`. What `order` does each get? Then add a fourth that overlaps nothing.
6. **Batching.** Given quads with orders `[1,1,2]` and a monochrome sprite with order `1`, what does `Scene::batches()` yield? (Hint: `BatchIterator::next` sorts by `(order, kind)`.)
7. **Keymap precedence.** Read `Keymap::resolve_bindings_for_input`. Explain why a binding in context `Editor` beats a binding with no context for the same keystroke, even if the latter was added later.
8. **Action stops by default.** Find where `cx.propagate_event = false` is assigned in the bubble phase of `dispatch_action_on_node_inner`, and compare with `dispatch_mouse_event`.
9. **A new backend.** List the `Platform` methods without a default implementation. That is the minimum surface a backend must provide. Start from the trait in `platform.rs`.
10. **Compare renderers.** Open `WgpuRenderer::render_frame` and `DirectXRenderer::render` side by side. Both loop over `scene.batches()`. Match each `PrimitiveBatch` variant to its draw function in each.
11. **Design a component on paper.** Read `crates/ui/src/components/label/label.rs`, then sketch a `RenderOnce` `Tag` component with a builder method and `#[derive(IntoElement)]`.
12. **Macro expansion.** Take `actions!(editor, [Undo])` and write out by hand what `derive(Action)` and `register_action` generate. Compare with `derive_action.rs`.

## Next steps

- [Where everything lives](/codebase/gpui-crate-map/): the file-by-file map you will use with every exercise above.
- [How a frame is drawn](/codebase/frame-lifecycle/): the single most useful page when you want to understand GPUI.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/gpui.rs` (module list, `#![warn(missing_docs)]`, `#[cfg(doc)]` modules)
- `crates/gpui/README.md`, `crates/gpui/docs/contexts.md`
- `crates/gpui/src/_ownership_and_data_flow.rs`
- `crates/gpui/src/window.rs`, `crates/gpui/src/app.rs`
- `crates/gpui/src/elements/div.rs`
- `crates/gpui_linux/src/linux/wayland/window.rs`, `wayland/client.rs`, `display_connection.rs`
</details>
