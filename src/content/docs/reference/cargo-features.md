---
title: Cargo features and environment variables
description: Which Cargo features your GPUI app needs on each operating system, what every feature does, and which environment variables GPUI reads.
sidebar:
  order: 2
  label: Cargo features and env vars
---

:::note[Advanced]
This page is for readers who have finished the beginner path and need to pick Cargo features, debug a platform problem, or find out what an environment variable does. Read [Installation](/start/installation/) and [Thinking in GPUI](/start/thinking-in-gpui/) first.
:::

A Cargo **feature** is a switch in `Cargo.toml` that turns optional code on or off at build time. GPUI has many of them, spread over several crates. This page tells you which ones your app needs, then lists every one with what it does in the code.

:::tip[In short]
- Most apps only need `gpui` plus `gpui_platform` with `font-kit` (macOS) or `wayland` and `x11` (Linux). Windows needs nothing.
- If a Linux window opens but nothing is drawn, or a macOS window has no text, the cause is almost always a missing feature. See the first two sections below.
- Everything after "Picking features" is a reference. Jump to the crate or variable you need.
:::

## How to use this page

1. Read **Picking features for your app** to choose features for your platform.
2. If something is not working, check [Common errors](/reference/common-errors/) too. It links back here.
3. Use the per-crate tables as a dictionary. Each row says what the feature enables in the code.
4. Use the **Environment variables** tables to find a variable by name. They are grouped by when GPUI reads them: build time, runtime in the framework, runtime on Linux, and runtime rendering.

Everything on this page was read from the `Cargo.toml` files and the `#[cfg(...)]` and `env::var` sites in the source at commit `b5cd310b`. A feature that only forwards to another crate is described as such.

## Picking features for your app

`crates/gpui/README.md` recommends adding two dependencies:

```toml
gpui = { version = "*" }
gpui_platform = { version = "*", features = ["font-kit", "wayland", "x11"] }
```

The rules from the README, which the backend source confirms, are these.

- **macOS**: Metal rendering is always available, but you need `gpui_platform/font-kit` for glyphs. Without it `MacPlatform::new` logs `"gpui_macos was compiled without the `font-kit` feature, so no text will be rendered."` and installs `NoopTextSystem`.
- **Linux / FreeBSD**: enable `wayland`, `x11` or both on `gpui_platform`. They also bring in the renderer and text system, so no text feature is needed.
- **Windows**: nothing to enable.

:::caution[Why `gpui_platform` defaults matter on Linux]
`gpui_platform` has `default = ["multithreaded"]`, which only affects the browser build. The workspace declares `gpui_linux = { path = "crates/gpui_linux", default-features = false }`. So a Linux app that depends on `gpui_platform` without `wayland`/`x11` gets a `gpui_linux` with neither compiled in, and `LinuxPlatform` can only start headless. "Headless" means running without a display: windows are created but nothing is drawn. See [Common errors](/reference/common-errors/).
:::

## `gpui` features (`crates/gpui/Cargo.toml`)

These are the switches on the main crate. Several are markers or forwarders, and the "Effect in the code" column says exactly what each one gates.

`default = ["font-kit", "wayland", "x11", "windows-manifest"]`

| Feature | Enables | Effect in the code |
| --- | --- | --- |
| `font-kit` | nothing (`font-kit = []`) | No `cfg(feature = "font-kit")` exists inside `gpui/src`. It is a marker that consumers/`dev-dependencies` can name. The real switch is `gpui_platform/font-kit` -> `gpui_macos/font-kit` -> `gpui_apple/font-kit`, and `gpui_wgpu/font-kit`. |
| `wayland` | nothing (`wayland = []`) | Gates Linux-specific API: the `platform::layer_shell` module, `PlatformWindow::set_exclusive_edge`, and the `GraphicalEnvironment::guess_compositor` branch (`cfg!(feature = "wayland")`). It does **not** compile the Wayland client; that is `gpui_linux/wayland`. |
| `x11` | `scap?/x11` | Same idea: `guess_compositor` uses `cfg!(feature = "x11")`; also enables X11 support in `scap` when `screen-capture` is on. |
| `windows-manifest` | `dep:embed-resource` | `build.rs` embeds `resources/windows/gpui.manifest.xml` and `gpui.rc` into Windows binaries (`embed_resource::compile(..).manifest_required().unwrap()`). `gpui_platform` turns it on for Windows via `gpui = { features = ["windows-manifest"] }`. |
| `screen-capture` | `scap` | Compiles `platform/scap_screen_capture.rs` (Windows, Linux, FreeBSD) and the `Platform` screen-capture methods. On macOS the frame type is a CoreVideo `CVImageBuffer`. The default `Platform::screen_capture_sources` implementation returns the error "gpui was compiled without the screen-capture feature". |
| `profiler` | `dep:hdrhistogram` | The task/frame profiler: `profiler::journal`, `profiler::hang`, per-window `WindowProfiler`, the debug frame overlay (`debug_overlay.rs`), `App::foreground_journal`, `App::start_hang_monitor`. About 170 `cfg` sites, mostly in `window.rs` and `app.rs`. |
| `inspector` | `gpui_macros/inspector` | Compiles the in-app inspector (`Inspector` entity, `InspectorElementPath`, element registry) and `#[derive_inspector_reflection]`. These are also enabled automatically by `debug_assertions`, so debug builds always include them (`cfg(any(feature = "inspector", debug_assertions))`). |
| `stacker` | `dep:stacksafe` | Wraps Taffy layout (`TaffyLayoutEngine::compute_layout`, the node measure closure) in `stacksafe` so very deep trees do not overflow the stack. |
| `leak-detection` | none | Makes `build.rs` set `cfg(gpui_leak_detection)`: entity handle leak tracking (see below). `GPUI_LEAK_DETECTION` does the same. |
| `hot-reload` | `async-tungstenite`, `dioxus-cli-config`, `dioxus-devtools-types`, `smol`, `subsecond` | With `build.rs` conditions below sets `cfg(gpui_hot_reload)`: compiles `hot_reload.rs` (a client for the Dioxus devserver, using `subsecond` jump tables) and `View::render` for `AnyView` goes through `subsecond::HotFn`. |
| `test-support` | `bench_metrics?/test-support`, `collections/test-support`, `http_client/test-support`, `wayland`, `x11`, `proptest`, `futures-concurrency`, `postage`, `web-time` | Compiles the test platform and contexts: `TestAppContext`, `TestApp`, `HeadlessAppContext`, `VisualTestAppContext`, `TestDispatcher`, `ThreadedDispatcher`, `gpui::test` module, `PlatformWindow::render_to_image`, debug-bounds recording, `calculate_seeds`. Also re-exports `proptest`. |
| `bench-support` | `profiler`, `dep:criterion`, `dep:bench_metrics` | Compiles `BenchAppContext`, `randomized_element_tree`, the Criterion integration (`BenchMeasurement`, `#[gpui::bench]` runtime). |
| `bench` | `bench-support` | A compatibility alias: the manifest comment says "Preserve the published feature name while consumers migrate to `bench-support`." `#[gpui::bench]`'s docs still say to enable `bench`. |

Dependencies are also selected by target in `gpui/Cargo.toml` (not features): `pollster` on non-wasm, `scap` optional on Linux/FreeBSD/Windows, `objc2-*`/CoreFoundation on Apple, `windows` features on Windows, `wasm-bindgen`-related dev-dependencies on wasm.

### `gpui/build.rs`

1. Registers `cfg(gles)`, `cfg(gpui_leak_detection)`, `cfg(gpui_hot_reload)` with `rustc-check-cfg`.
2. `println!("cargo::rerun-if-env-changed=GPUI_LEAK_DETECTION")`. If the variable is set and non-empty, **or** the `leak-detection` feature is on (`CARGO_FEATURE_LEAK_DETECTION`), emits `cargo::rustc-cfg=gpui_leak_detection`. The comment explains why `test-support` does not enable it: it does bookkeeping on every entity handle and test-support must stay cheap. CI sets the env var.
3. Emits `cargo::rustc-cfg=gpui_hot_reload` only if `hot-reload` is enabled **and** the build has debug assertions **and** the target OS is `macos`, `linux`, `windows` or `ios`: "Hot reloading is limited to debug builds so the feature can't ship in release binaries".
4. On Windows with `windows-manifest`, compiles the resource file.

## `gpui_platform` features (`crates/gpui_platform/Cargo.toml`)

`gpui_platform` is the crate your app depends on to get a working backend. Its features mostly forward to the backend crates. This is where you usually turn things on.

`default = ["multithreaded"]`

| Feature | Forwards to | Notes |
| --- | --- | --- |
| `multithreaded` | `gpui_web/multithreaded` | Browser builds use threads (`wasm_thread`); needs a nightly toolchain and a cross-origin-isolated page. Manifest comment: "Off, gpui_web builds on stable." |
| `wayland` | `gpui_linux/wayland` | Compile the Wayland backend. |
| `x11` | `gpui_linux/x11` | Compile the X11 backend. |
| `font-kit` | `gpui_macos/font-kit` | Required on macOS for text rendering. |
| `screen-capture` | `gpui/screen-capture`, `gpui_macos/screen-capture`, `gpui_windows/screen-capture`, `gpui_linux/screen-capture` | Turns on screen capture in `gpui` and in each backend. |
| `inspector` | `gpui/inspector` | Turns on the in-app inspector in `gpui`. |
| `runtime_shaders` | `gpui_macos/runtime_shaders`, `gpui_ios/runtime_shaders` | Forwarded again to `gpui_apple/runtime_shaders`. That crate was not available for reading, so what it changes is not documented here. |
| `test-support` | `gpui/test-support`, `gpui_macos/test-support`, `gpui_windows/test-support`, `gpui_wgpu/test-support` | Also enables `current_headless_renderer()` in `gpui_platform`. |
| `bench-support` | `gpui/bench-support`, `gpui_macos/bench-support`, `gpui_wgpu/bench-support` | Enables the benches (each declares `required-features = ["bench-support"]`) and `bench_text_system()`. |

## Backend crate features

You rarely set these directly, because `gpui_platform` forwards to them. They are listed so you can see what each forwarded feature finally pulls in.

| Crate | Features | Meaning |
| --- | --- | --- |
| `gpui_linux` | `default = ["wayland", "x11"]`, `test-support`, `screen-capture` | `wayland` pulls in `accesskit_unix`, `gpui_wgpu`, `ashpd/wayland`, `calloop-wayland-source`, `wayland-backend`, `wayland-client`, `wayland-cursor`, `wayland-protocols` (+ `-plasma`, `-wlr`), `filedescriptor`, `xkbcommon/wayland`, `open`, `gpui/wayland`, `uuid/v5`. `x11` pulls in `accesskit_unix`, `gpui_wgpu`, `ashpd`, `as-raw-xcb-connection`, `x11rb`, `xkbcommon/x11`, `xim`, `filedescriptor`, `open`, `scap?/x11`. Without both, only `HeadlessConnection` exists. |
| `gpui_macos` | `default = ["gpui/default"]`, `bench-support`, `test-support`, `runtime_shaders`, `font-kit`, `screen-capture` | `font-kit` -> `gpui_apple/font-kit` (selects `AppleTextSystem`). `screen-capture` adds `objc2-core-media` and `objc2-screen-capture-kit`. |
| `gpui_windows` | `default = ["gpui/default"]`, `test-support`, `screen-capture` | `test-support` also compiles `render_to_image`. |
| `gpui_wgpu` | `default = []`, `bench-support`, `test-support`, `font-kit` | `font-kit` (`dep:font-kit`) changes `find_best_match` in `cosmic_text_system.rs` to use `font_kit::matching::find_best_match` for choosing a face; without it a simpler path is used. `bench-support` and `test-support` add `dep:image` and enable `WgpuHeadlessRenderer` on non-wasm. `gpui_linux` depends on `gpui_wgpu` with `features = ["font-kit"]`. |
| `gpui_web` | `default = ["multithreaded"]`, `multithreaded` | `multithreaded = ["dep:wasm_thread", "scheduler/wasm-threads"]`. |
| `gpui_ios` | `runtime_shaders` | Forwarded to `gpui_apple`. |
| `gpui_macros` | `inspector` | Compiles `derive_inspector_reflection`. |
| `ui` | `default = []` | No features. |

## Environment variables

Some variables are read when you **build** GPUI, and some when your app **runs**. Check the group heading before you set one.

### Build time

| Variable | Read in | Effect |
| --- | --- | --- |
| `GPUI_LEAK_DETECTION` | `gpui/build.rs` | If non-empty, sets `cfg(gpui_leak_detection)`. Re-checked via `rerun-if-env-changed`. |
| `GPUI_FXC_PATH` | `gpui_windows/build.rs` | Path to `fxc.exe` for compiling HLSL in release builds. If unset or missing, tries `where.exe fxc.exe`, then the Windows SDK; panics `"Failed to find fxc.exe"` otherwise. |
| `TRACK_THREAD_BORROWS` | `gpui/src/app.rs` via `option_env!` | Compile-time. When set at build, `AppCell` prints a line on every borrow and drop. |

### Runtime: framework and tests

| Variable | Read in | Effect |
| --- | --- | --- |
| `SEED` | `gpui/src/seeds.rs`, `app/headless_app_context.rs`, `app/visual_test_context.rs` | Starting seed for `#[gpui::test]` / `#[gpui::bench]`; with it set, runs `SEED..SEED + iterations` and ignores explicit seeds. |
| `ITERATIONS` | `gpui/src/seeds.rs` | Overrides the `iterations` argument. Invalid values panic with `"invalid ITERATIONS variable"` / `"invalid SEED variable as integer"`. |
| `LEAK_BACKTRACE` | `app/entity_map.rs` | Non-empty: capture backtraces when entity handles are created (leak detection builds). |
| `GPUI_RUN_UNTIL_PARKED_LOG` | `gpui/src/executor.rs` | `1`: logs a warning when `allow_parking` is called in tests. |
| `BENCH_MEASUREMENT` | `gpui/src/bench.rs` (documented) | Selects what Criterion analyses: default wall time with counters printed; `instructions`; `foreground-instructions`; `wall-time` disables counters. |
| `GPUI_BENCH_SCENE_STATS` | `gpui_platform/benches/*` | `1`: print scene statistics from the benches. |
| `ZED_MEASUREMENTS` | `gpui_util::measure` | `1` or `true`: print elapsed time for measured blocks (the per-window frame callback measures `"frame duration"`) to stderr. |
| `GPUI_TREE_DEPTH` | `examples/tree.rs` | Nesting depth for the tree example (default 50). |

### Runtime: platform (Linux)

| Variable | Read in | Effect |
| --- | --- | --- |
| `WAYLAND_DISPLAY`, `DISPLAY`, `XDG_RUNTIME_DIR` | `GraphicalEnvironment::detect` (`gpui/src/platform.rs`) | Decide Wayland vs X11 vs headless (Wayland first). Non-empty values count as set. |
| `ZED_HEADLESS` | `gpui::guess_compositor`, `gpui_linux::current_platform` | Any value: report/start headless. |
| `XDG_ACTIVATION_TOKEN` | `wayland/client.rs` | Taken at startup (and removed from the environment) so the first window can take focus. |
| `WAYLAND_SOCKET` | `wayland/client.rs` | An already-open compositor socket inherited from the parent process; removed after reading. |
| `GPUI_X11_SCALE_FACTOR` | `x11/client.rs` | `randr`, or a positive number, or empty (not set). Other values panic: ``"`GPUI_X11_SCALE_FACTOR` must be a positive normal number or `randr`. Got `...`"``. |
| `XCURSOR_PATH`, `LC_CTYPE` | `linux/platform.rs` | `XCURSOR_PATH` is only read to enrich the warning logged when a cursor icon fails to load. `LC_CTYPE` (then `C`) picks the locale for the xkb compose table used for dead keys and compose sequences. |
| `GPUI_LINUX_DISPLAY_MODE_SCENARIO` | `linux/platform.rs` (test module) | Test harness only. |

### Runtime: rendering

| Variable | Read in | Effect |
| --- | --- | --- |
| `ZED_DEVICE_ID` | `gpui_wgpu/src/wgpu_context.rs` | Four hex digits (optional `0x`) of the PCI device id to prefer when choosing a GPU adapter. Invalid values are logged and ignored. |
| `ZED_FONTS_GAMMA` | `gpui_wgpu/src/wgpu_renderer.rs` | Text gamma, default `1.8`, clamped to `1.0..=2.2`. |
| `ZED_FONTS_GRAYSCALE_ENHANCED_CONTRAST` | same | Default `1.0` (min 0). |
| `ZED_FONTS_SUBPIXEL_ENHANCED_CONTRAST` | same | Default `0.5` (min 0). |
| `GPUI_DISABLE_DIRECT_COMPOSITION` | `gpui_windows/src/directx_renderer.rs`, `platform.rs` | `true` or `1`: create a plain HWND swap chain instead of a DirectComposition one. |
| `ZED_RESTART_PID`, `ZED_RESTART_EXECUTABLE`, `ZED_RESTART_ARGUMENTS` | `gpui_windows/src/platform.rs` | Set by the Windows restart helper script for the new process; not meant to be set by hand. |

`gpui_util` also reads Windows variables (`ProgramFiles`, `LOCALAPPDATA`, `SCOOP`, `USERPROFILE`, `SystemRoot`, ...) to locate PowerShell; this is not GPUI behaviour. GPUI logs through the `log` crate and does not initialise a logger in the library; examples that want output call `env_logger` themselves (for example `image_loading.rs` and `a11y.rs`).

## Next steps

- [Common errors](/reference/common-errors/): symptoms such as "the window never appears on Linux" and their fixes.
- [Platform backends](/codebase/platform-backends/): how the backend crates behind these features fit together.
- [Testing](/guides/testing/): when you need the `test-support` feature.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/Cargo.toml` and `crates/gpui/build.rs`
- `crates/gpui_platform/Cargo.toml`
- `crates/gpui_linux/Cargo.toml`, `crates/gpui_macos/Cargo.toml`, `crates/gpui_windows/Cargo.toml`, `crates/gpui_wgpu/Cargo.toml`, `crates/gpui_web/Cargo.toml`, `crates/gpui_ios/Cargo.toml`, `crates/gpui_macros/Cargo.toml`, `crates/ui/Cargo.toml`
- `crates/gpui/README.md` (feature recommendations)
</details>
