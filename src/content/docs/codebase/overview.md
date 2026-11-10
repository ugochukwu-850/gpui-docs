---
title: "Start here: a tour of the GPUI source"
description: A map of the GPUI crates in the Zed repository, a suggested three-day reading route through this tour, and how to download only the GPUI part of the repository.
sidebar:
  order: 1
  label: Start here
---

This tour teaches you to read the GPUI source code, so you can answer "how does that actually work?" yourself. This page gives you the map, a reading route, and the commands to download the code.

All facts in the tour were read from commit `b5cd310b` of the Zed repository. Paths are relative to the repository root.

:::note[Advanced]
The Codebase tour is for readers who have already built something with GPUI and now want to look inside it. You do not need to know Rust macros or graphics APIs. You do need to be comfortable reading Rust: traits, generics, `Rc` and `RefCell`.
:::

## What you'll learn

- Which crates make up GPUI and how they depend on each other.
- The order to read the tour pages, and which source files to open on each day.
- How to download only the GPUI part of the Zed repository.
- How to run an example from a full checkout.

:::tip[In short]
1. GPUI is a set of crates inside the Zed repository. The framework lives in `crates/gpui`. Everything OS-specific lives in separate backend crates.
2. Read in this order: how to read the source, the file map, one frame (the most important page), state, input, backends, macros, then the `ui` crate.
3. You can read GPUI without downloading all of Zed, but you need a full checkout to build it.
:::

## Before you start

Finish these first. The tour assumes you have met the words *view*, *entity* and `cx.notify()`.

1. [Installation](/start/installation/) and [Hello World](/start/hello-world/), so you have seen a GPUI window run.
2. At least the [Counter tutorial](/tutorials/counter/). The page [How a frame is drawn](/codebase/frame-lifecycle/) follows a click on that counter through the whole framework.
3. Optional but helpful: [The big picture](/deep-dive/big-picture/) in the Deep Dive, which explains the same ideas without file names.

## What is in the repository

GPUI lives inside the Zed monorepo at `github.com/zed-industries/zed`. The most important thing to know about the current layout: **`crates/gpui` contains no OS-specific windowing or rendering code.**

`gpui` defines the framework plus a set of *traits* (Rust's version of interfaces) such as `Platform` and `PlatformWindow`, in `crates/gpui/src/platform.rs`. Each operating system is implemented by a separate *backend crate*. A thin crate called `gpui_platform` picks the right backend when your program is compiled.

```text
+------------------------------------------------------------------+
|  Your app  (or Zed itself)                                       |
+---------------------------------+--------------------------------+
|  gpui   THE FRAMEWORK           |  ui   Zed's component library  |
|  state (entities), views,       |  (Button, Label, ...) built    |
|  elements, layout, input, text, |  ON gpui; not part of GPUI     |
|  drawing, async executors       |  itself                        |
|                                 |                                |
|  helpers: gpui_macros, gpui_util, gpui_shared_string,            |
|           gpui_tokio (optional)                                  |
+---------------------------------+--------------------------------+
|        The boundary: traits only (Platform, PlatformWindow, ...) |
+------------------------------------------------------------------+
|  gpui_platform   chooses ONE backend at compile time             |
+----------+-----------+-----------+-----------+-------------------+
| gpui_    | gpui_     | gpui_     | gpui_web  | gpui_ios          |
| linux    | macos     | windows   | (browser) | (iPhone, iPad)    |
+----------+-----------+-----------+-----------+-------------------+
   draws with:                         draws with:
   gpui_wgpu (Linux and web)           Metal (gpui_apple: macOS, iOS)
                                       Direct3D 11 (inside gpui_windows)
```

Read the diagram from the top: your app uses `gpui`, and `gpui` talks to the operating system only through the traits. The backend crates fill in those traits.

## The crates

Line counts are `wc -l` over every `.rs` file in the crate (tests, benches, examples and build scripts included). They give you a sense of scale, not a precise figure.

| Crate | Path | Rust lines | Role |
| --- | --- | ---: | --- |
| `gpui` | `crates/gpui` | 104,045 (src 92,839, examples 10,963) | The framework: `App`, entities, `Window`, elements, layout (taffy), styling, input dispatch, keymap, actions, text layout, the `Scene`, executors, test support, and the platform traits. |
| `gpui_platform` | `crates/gpui_platform` | 2,764 (src 231, rest benches) | Convenience entry point. `application()`, `headless()` and `current_platform()` return the backend for the target OS. Its Cargo features forward to the backend crates. |
| `gpui_linux` | `crates/gpui_linux` | 17,545 | Linux and FreeBSD backend: Wayland client, X11 client, a headless mode, a `calloop` event loop, XDG desktop portals. |
| `gpui_macos` | `crates/gpui_macos` | 10,014 | macOS backend on AppKit: windows, events, menus, pasteboard, display links. Rendering and text come from `gpui_apple` (see below). |
| `gpui_windows` | `crates/gpui_windows` | 13,383 | Windows backend: Win32 window procedure, DirectX 11 renderer, DirectWrite text system, HLSL shaders. |
| `gpui_wgpu` | `crates/gpui_wgpu` | 6,353 (plus ~1,700 lines of WGSL) | A shared [wgpu](https://wgpu.rs) renderer (`WgpuRenderer`), the wgpu atlas, device selection, and `CosmicTextSystem` (cosmic-text based text shaping and rasterisation). Used by Linux and the web. |
| `gpui_web` | `crates/gpui_web` | 7,887 | Browser backend (`wasm32`): one canvas, one window, WebGPU with WebGL2 fallback, DOM event translation, IME mirror, `fetch`-based HTTP client. |
| `gpui_ios` | `crates/gpui_ios` | 3,706 | iOS backend on UIKit: application lifecycle, `CAMetalLayer` view, touch input, native text input. |
| `gpui_macros` | `crates/gpui_macros` | 3,631 | Procedural macros: `#[derive(Action)]`, `#[derive(IntoElement)]`, `#[gpui::test]`, style helper generators, and more. See [How the macros work](/codebase/macros/). |
| `gpui_util` | `crates/gpui_util` | 834 | Small shared helpers: `ArcCow`, `ResultExt` (`.log_err()`), `TryFutureExt`, `defer`, `measure`, `post_inc`, and a few Windows shell/process helpers. |
| `gpui_tokio` | `crates/gpui_tokio` | 100 | Optional bridge that runs Tokio futures from GPUI (`gpui_tokio::init`, `Tokio::spawn`). |
| `gpui_shared_string` | `crates/gpui_shared_string` | 210 | `SharedString`, a cheaply clonable immutable string backed by `smol_str::SmolStr`. |
| `ui` | `crates/ui` | 31,669 | Zed's component library (Button, Label, ListItem, ContextMenu, ...) built on GPUI. Not part of GPUI itself; see [A real component library](/codebase/reading-zed-ui-crate/). |

If you only have time for one crate, make it `gpui`. About 93,000 of its lines are in `src/`, and one file, `window.rs`, holds more than 10,000 of them. The next page, [How to read the source](/codebase/how-to-read-the-source/), shows how to cope with that.

:::note[What is not in this checkout]
Several workspace crates that GPUI depends on were not part of the slice this documentation was written from, so their code was not read:

- `gpui_apple` is listed in the root `Cargo.toml` and is depended on by `gpui_macos` and `gpui_ios`. `crates/gpui_macos/src/gpui_macos.rs` does `use gpui_apple::metal_renderer as renderer;`, so the Metal renderer, `AppleTextSystem`, `AppleDispatcher` and the Metal display link live there.
- `collections`, `http_client`, `refineable` (and `derive_refineable`), `scheduler` and `sum_tree` are depended on by `gpui`. `Task`, `Priority`, `BackgroundExecutor`'s inner scheduler and the test scheduler come from `scheduler`; the `Refineable` derive used by `Style` comes from `refineable`.
- `ui` additionally depends on `theme`, `component`, `icons`, `menu`, `ui_macros` and `documented`.
:::

## Which crate depends on which

Arrows mean "depends on". The facts come from each crate's `Cargo.toml`. You do not need to memorise this. Come back to it when a `use` line puzzles you.

```text
                       your application
                      /        |         \
                     v         v          v
              gpui_platform   ui        gpui_tokio (optional)
                   |           |            |
   cfg(target_os / target_family)           |
                   |           |            |
  +--------+-------+---+-------+-----+      |
  v        v       v       v         v      |
gpui_linux gpui_macos gpui_windows gpui_ios gpui_web
  |  |        |            |          |       |
  |  |        +-----+------+          |       |
  |  |              v                 |       |
  |  |         gpui_apple  <----------+       |
  |  |       (Metal, CoreText;                |
  |  |        not in checkout)                |
  |  v                                        v
  | gpui_wgpu  <------------------------------+
  |  (wgpu + WGSL + cosmic-text; optional on Linux: only with wayland/x11)
  |                                           |
  +---------------------+---------------------+
                        v
                      gpui  <---  gpui_macros, gpui_shared_string, gpui_util
                        ^
                        |
         (ui also depends on gpui, gpui_macros, gpui_util
          and on crates outside the checkout: theme, component, ...)
```

Four details are worth knowing:

- `gpui_windows` does **not** use `gpui_wgpu`. Windows has its own DirectX 11 renderer (`crates/gpui_windows/src/directx_renderer.rs`) and DirectWrite text system (`direct_write.rs`).
- `gpui_linux` depends on `gpui_wgpu` only through its `wayland` and `x11` features. With neither enabled it can only run headless.
- `gpui` itself has a dev-dependency on `gpui_platform`. That is how `crates/gpui/examples/*` can call `gpui_platform::application()` even though `gpui_platform` depends on `gpui`.
- `gpui_platform`'s `Cargo.toml` selects the backend with `[target.'cfg(...)'.dependencies]` tables. `crates/gpui_platform/src/gpui_platform.rs` then uses `cfg_select!` in `current_platform()` to construct it.

## Your reading route

Here is a route that goes from "what is where" to "how does it work". Each page builds on the one before. The times are a suggestion for a relaxed pace, not a promise.

### Day 1: get your bearings

1. **This page**, then [How to read the source](/codebase/how-to-read-the-source/). You learn the search commands and the naming habits that make a 10,000-line file readable.
2. [Where everything lives](/codebase/gpui-crate-map/). A map of every file in `crates/gpui/src`.
3. Open `crates/gpui/examples/hello_world.rs` next to the map and find each type it uses.

Files to open: `crates/gpui/README.md` (section "The Big Picture"), `crates/gpui/src/_ownership_and_data_flow.rs`, `crates/gpui/src/gpui.rs`.

### Day 2: the two engines

4. [How a frame is drawn](/codebase/frame-lifecycle/). This is the most important page. It follows one click on the counter from the mouse to the pixels.
5. [How state is stored and updated](/codebase/app-and-entity-internals/). The first half of that story: where entities live and why updates are queued.

Files to open: `crates/gpui/src/element.rs`, `crates/gpui/src/elements/div.rs`, `crates/gpui/src/app.rs`, `crates/gpui/src/app/entity_map.rs`, and `Window::draw` in `crates/gpui/src/window.rs`.

### Day 3: the edges

6. [How input finds your code](/codebase/input-and-dispatch-internals/). Mouse, keyboard, focus and actions.
7. [How GPUI talks to your OS](/codebase/platform-backends/). The traits and the backend for your operating system.
8. [How the macros work](/codebase/macros/). What `#[derive(IntoElement)]` and the `px_2()` style methods really are.
9. [A real component library: the ui crate](/codebase/reading-zed-ui-crate/). How Zed builds a button on top of everything you have read.

Files to open: `crates/gpui/src/key_dispatch.rs`, `crates/gpui_platform/src/gpui_platform.rs` (231 lines), the `Platform` trait in `crates/gpui/src/platform.rs`, `crates/ui/src/components/button/button.rs`.

:::tip
You do not have to read every page. If you only care about one question, the table "Where to start for a given question" in [How to read the source](/codebase/how-to-read-the-source/) sends you to the right page.
:::

## Download only GPUI

You can read GPUI without downloading all of Zed. Git's *partial clone* skips file contents until you need them, and a *sparse checkout* puts only the folders you name on disk.

```sh
git clone --filter=blob:none --sparse https://github.com/zed-industries/zed.git
cd zed
git checkout b5cd310b   # the commit this tour was written from
git sparse-checkout set \
  crates/gpui crates/gpui_platform crates/gpui_macros \
  crates/gpui_util crates/gpui_shared_string crates/gpui_tokio \
  crates/gpui_linux crates/gpui_macos crates/gpui_windows \
  crates/gpui_wgpu crates/gpui_web crates/gpui_ios crates/gpui_apple \
  crates/ui
```

What the flags do:

- `--filter=blob:none` downloads the commit history but not the file contents. Git fetches a file's contents the first time you check it out.
- `--sparse` starts with only the files in the repository root (such as `Cargo.toml`).
- `git checkout b5cd310b` makes line numbers and names match this tour. Skip it if you prefer the newest code, and expect some names to have moved.
- `git sparse-checkout set ...` lists the folders to put on disk.

A shallower and smaller download is possible by adding `--depth 1` to the clone. That gives you only the newest commit, so you cannot check out `b5cd310b`.

`crates/gpui_apple` is not in the set used to write these pages, but it is worth adding if you want to read the Metal renderer.

:::caution[Reading is not building]
This is enough to **read** the code with an editor, `rg` (ripgrep) and `find`. It is not enough to **build** it. The root `Cargo.toml` lists every workspace member, and `gpui` depends on workspace crates such as `collections`, `http_client`, `refineable`, `scheduler` and `sum_tree` that a minimal sparse checkout does not contain. To compile and run examples, do a full blobless clone (leave out `--sparse` and the `sparse-checkout` command), or add the missing crates to the sparse set. The exact minimal set is not documented here because those crates' manifests were not available when this page was written. The git commands above are standard, but they were not run while writing this page.
:::

:::tip
If you only want to *use* GPUI in your own project, you do not need the Zed repository at all. `crates/gpui/Cargo.toml` declares `version = "0.2.2"` and `publish = true`, and `crates/gpui/README.md` shows adding `gpui` and `gpui_platform` as dependencies.
:::

## Build and run an example

From the root of a full checkout (this is what `crates/gpui/examples/README.md` says):

```sh
cargo run -p gpui --example hello_world
```

Notes taken from the source:

- `rust-toolchain.toml` at the repository root pins `channel = "1.98.1"` and lists extra targets including `wasm32-unknown-unknown` ("gpui on the web").
- The workspace uses Rust edition 2024 (`[workspace.package] edition = "2024"`).
- All examples are listed in the [examples index](/reference/examples-index/). Cargo features that affect them are in [Cargo features and environment variables](/reference/cargo-features/).
- On macOS, `crates/gpui/README.md` says you need Xcode and the Xcode command line tools to use Metal. The README does not list Linux system packages, and none were verified for this page.

## Try it yourself

These are reading exercises. They do not change the repository.

1. In `Cargo.toml` at the repository root, find the `[workspace] members` list and look for the entries that start with `crates/gpui`. You should find 13: the 12 `gpui*` crates in the table plus `crates/gpui_apple`.
2. Open `crates/gpui_platform/Cargo.toml` and find the `[target.'cfg(...)'.dependencies]` tables. Which backend crate is chosen for `target_os = "windows"`?
3. Open `crates/gpui_platform/src/gpui_platform.rs` and read `current_platform`. Name the five `cfg_select!` branches.
4. Run `wc -l crates/gpui/src/window.rs`. Does it match the 10,680 lines quoted in [Where everything lives](/codebase/gpui-crate-map/)? A different number means your checkout is on a different commit.

## Next steps

- [How to read the source](/codebase/how-to-read-the-source/): search commands, naming habits, and a question-to-file table.
- [Where everything lives](/codebase/gpui-crate-map/): every file in `crates/gpui/src`, grouped by job.
- [How a frame is drawn](/codebase/frame-lifecycle/): the most important page in the tour.

<details>
<summary>Where this lives in the source</summary>

- `Cargo.toml` (workspace members) and `rust-toolchain.toml` at the repository root
- `crates/gpui/README.md`, `crates/gpui/Cargo.toml`, `crates/gpui/examples/README.md`
- `crates/gpui/src/platform.rs` (the platform traits)
- `crates/gpui_platform/Cargo.toml` and `crates/gpui_platform/src/gpui_platform.rs`
- each crate's `Cargo.toml` for the dependency arrows
</details>
