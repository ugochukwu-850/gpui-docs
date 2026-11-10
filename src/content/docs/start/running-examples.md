---
title: Run the examples
description: Run GPUI's official examples, find the ones worth reading first, and learn how to read them.
sidebar:
  order: 6
  label: Run the examples
---

The `gpui` crate ships more than forty runnable examples. They are compiled as part of the Zed repository, so unlike prose they cannot quietly drift out of date. Running a few is the fastest way to see what GPUI can do.

**What you'll learn**

- How to run any official example with one command.
- Which examples to read first, and what each one teaches.
- How to read an example effectively.

## Run an example

Clone the Zed repository, go to the revision these docs describe, and run an example by name:

```sh
git clone https://github.com/zed-industries/zed
cd zed
git checkout b5cd310b3b54dfc659fcc06453e6358843dfe216   # the revision these docs describe
cargo run -p gpui --example hello_world
```

You should see the same kind of window as in [Hello World](/start/hello-world/). The first build compiles a lot of code and takes a while. Later runs are quick.

The example name is the file name without `.rs`. Try `cargo run -p gpui --example input` or `--example uniform_list`. A few examples live in subfolders (`image/image.rs`, `svg/svg.rs`, `view_example/view_example_main.rs`), but you still run them by the short names `image`, `svg` and `view_example`.

Examples need the same system libraries as your own app, so finish [Installation](/start/installation/) first. Add `--release` when you care about speed, for example with the list examples.

:::note[Why clone the whole repository?]
Cloning only `crates/gpui` is not enough. GPUI depends on other crates in the Zed workspace (`gpui_platform`, `gpui_linux`, `collections` and more), and not all of them are published to crates.io. Building from a full checkout is the supported route.
:::

## Which example to read first

Read them roughly in this order. Each row says what the example is good for.

| Example | What you will learn |
| --- | --- |
| `hello_world` | The shape of every app: `Application`, a window, a root view, `div`. Covered in [Hello World](/start/hello-world/). |
| `testing` | A small interactive counter, plus how to write tests with `#[gpui::test]`. |
| `uniform_list` | The simplest long, scrolling list. See [Long lists](/tutorials/long-lists/). |
| `input` | A real single-line text input with focus, key bindings and a custom element. See the [text input tutorial](/tutorials/text-input/). |
| `view_example` | Builds a text input out of smaller views that share state. A good second read after `input`. |
| `data_table` | A table of 10,000 rows with a hand-built scrollbar. |
| `text`, `text_layout`, `text_wrapper` | Styled text, alignment, wrapping and truncation. |
| `grid_layout` | CSS-grid-style layout. |
| `popover`, `drag_drop`, `scrollable` | Floating layers, dragging and dropping, scrolling. |
| `animation` | Animations, including animated SVG transforms. |
| `image`, `svg`, `gradient`, `painting` | Images, SVG, gradients and custom drawing. |
| `window`, `set_menus` | Different kinds of windows, and application menus. |

To run the tests in `testing`, use `cargo test -p gpui --example testing --features test-support`.

The examples folder holds more than this list. `list_example` is the best small demo of a list whose rows have different heights. A few others (`active_state_bug`, `toggle_headless`, `layer_shell`, `paths_bench`, `tree` and `ownership_post`) mostly help people working on GPUI itself.

## Read the source on GitHub

You do not need to clone anything only to read. Every example is a single file you can browse at the revision these docs use:

<https://github.com/zed-industries/zed/tree/b5cd310b3b54dfc659fcc06453e6358843dfe216/crates/gpui/examples>

## How to read an example

1. Start at `main` (or a function it calls, often `run_example`) and find the root view being created with `cx.new`.
2. Read that view's `render` method. It shows the structure of the UI.
3. Search for `cx.listener`, `cx.notify()` and `on_action`. These show how a click or key press changes data.
4. Search the examples for the API you need. From the Zed repo root:

   ```sh
   grep -rn "cx.listener" crates/gpui/examples
   ```

Most examples have the same shape, which is also the shape of your own `main.rs`:

```rust
use gpui::{App, Bounds, Context, Window, WindowBounds, WindowOptions, div, prelude::*, px, size};
use gpui_platform::application;

fn run_example() {
    application().run(|cx: &mut App| {
        let bounds = Bounds::centered(None, size(px(500.), px(500.0)), cx);
        cx.open_window(
            WindowOptions {
                window_bounds: Some(WindowBounds::Windowed(bounds)),
                ..Default::default()
            },
            |_, cx| cx.new(|_| /* your root view */),
        )
        .unwrap();
        cx.activate(true);
    });
}
```

:::tip[Ignore the browser support code]
Some examples have `#[cfg(target_family = "wasm")]` blocks, a `#[path = "example_support/fonts.rs"] mod example_support;` line and a call to `example_support::load_fonts(cx)`. They let the same examples run in a web browser. On desktop, `load_fonts` returns `true`, so you can leave all of it out when you copy code into your own project.
:::

## Run examples in the browser

A few examples (`hello-world`, `text`, `text-layout`, `text-wrapper`, `input`, `dynamic-fonts` and `prime-sieve`) are also served by a web gallery. This is optional:

```sh
cd crates/gpui_web/examples/hello_web
trunk serve
```

Then open <http://localhost:8080/>. You need [Trunk](https://trunk-rs.github.io/trunk/), the nightly Rust toolchain with the WASM target (the gallery's toolchain file selects it), and a browser with WebGPU or WebGL2.

## Next steps

- [Thinking in GPUI](/start/thinking-in-gpui/): the mental model behind the code you just ran.
- [Counter tutorial](/tutorials/counter/): build your first interactive app.
- [Examples index](/reference/examples-index/): the full list of examples.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/examples/README.md`
- `crates/gpui/Cargo.toml` (`[[example]]` entries)
- `crates/gpui/examples/example_support/fonts.rs`
- `crates/gpui/examples/view_example/view_example_main.rs`
- `crates/gpui_web/examples/hello_web`
</details>
