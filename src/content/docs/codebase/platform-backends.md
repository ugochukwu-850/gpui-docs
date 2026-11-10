---
title: How GPUI talks to your OS
description: The platform traits GPUI defines, how gpui_platform picks a backend, and a guide to the Linux, macOS, Windows, web and iOS backends.
sidebar:
  order: 7
  label: How GPUI talks to your OS
---

GPUI's core never calls an operating system function. It talks to a handful of traits, and a *backend* crate implements them for each OS. This page maps those traits, then walks through each backend. It was read from commit `b5cd310b`.

## What you'll learn

- The handful of traits that make up the boundary between GPUI and an OS.
- How `gpui_platform` picks the backend at compile time, and how Linux picks Wayland or X11 at run time.
- Which renderer, text system and frame source each OS uses.
- Where to start reading if you want to understand (or write) a backend.

:::note[Advanced]
This page is for readers who want to see how the same GPUI program runs on five platforms, or who plan to debug an OS-specific problem. You do not need to know Win32, AppKit or Wayland. It names the entry point to read for each.
:::

:::tip[In short]
1. `crates/gpui/src/platform.rs` defines the traits (`Platform`, `PlatformWindow`, `PlatformDispatcher`, `PlatformTextSystem`, `PlatformAtlas`). Backends implement them. The core never imports an OS API.
2. The only drawing data that crosses the boundary is a `Scene`, handed over by `PlatformWindow::draw(&Scene)`. Input comes back as `PlatformInput`.
3. The backend is chosen when you compile (`cfg_select!` in `gpui_platform`). On Linux, Wayland versus X11 versus headless is chosen when you run.
:::

## The idea in one picture

```text
   gpui (the framework)                          a backend crate (one per OS)
 +-------------------------------+            +-----------------------------------+
 | Window::draw builds a Scene   | --draw---> | PlatformWindow::draw(&Scene)      |
 |                               |            |   -> renderer -> GPU -> screen    |
 | Window::dispatch_event        | <--input-- | on_input(PlatformInput)           |
 | Window::draw runs when asked  | <--frame-- | on_request_frame(...) each refresh|
 | async tasks are spawned       | --run----> | PlatformDispatcher                |
 | text needs shaping            | --glyphs-> | PlatformTextSystem + PlatformAtlas|
 +-------------------------------+            +-----------------------------------+
   knows only the traits                        talks to Win32, AppKit, Wayland,
                                                X11, the browser or UIKit
```

:::note[How thoroughly each crate was read]
**Read closely**: the traits in `gpui/src/platform.rs`, `gpui_platform`, the entry points and draw/frame paths of `gpui_linux`, `gpui_windows`, `gpui_wgpu`, and the frame-pacing and event entry points of `gpui_macos`, `gpui_web`, `gpui_ios`.
**Only skimmed**: the bodies of Wayland protocol handlers, X11 clipboard/XIM code, Win32 message handlers beyond the ones named, DirectWrite, the WGSL shader bodies, IME code, accessibility adapters, and menu/clipboard/notification implementations.
**Not in the checkout**: `gpui_apple` (Metal renderer, Apple text system, Apple dispatcher). Statements about Metal are limited to how `gpui_macos` and `gpui_ios` call into it.
:::

## The traits (`crates/gpui/src/platform.rs`)

| Trait | Responsibility | Representative methods |
| --- | --- | --- |
| `Platform` | The process-wide OS integration: event loop, executors, windows, displays, clipboard, menus, URLs, credentials, notifications, keyboard layout. | `run(on_finish_launching)`, `quit`, `background_executor`, `foreground_executor`, `text_system`, `open_window(handle, WindowParams) -> Box<dyn PlatformWindow>`, `displays`, `read_from_clipboard`, `set_menus`, `keyboard_layout`, `set_initial_windowing`, `request_windowing` |
| `PlatformWindow` (also `HasWindowHandle + HasDisplayHandle`) | One native window and its swap chain. | `bounds`, `scale_factor`, `on_request_frame`, `on_input`, `on_resize`, `on_close`, **`draw(&self, scene: &Scene)`**, `schedule_frame`, `frame_waker`, `sprite_atlas`, `set_input_handler`, `gpu_specs`, `a11y_*`, many platform-specific defaults |
| `PlatformDisplay` | A monitor. | `id`, `bounds`, `visible_bounds`, ... |
| `PlatformDispatcher` (`Send + Sync`) | Where runnables execute: a main thread plus a pool, with priorities and timers. | `dispatch(runnable, priority)`, `dispatch_on_main_thread`, `dispatch_after`, `spawn_realtime`, `is_main_thread` |
| `PlatformTextSystem` (`Send + Sync`) | Font loading, shaping and glyph rasterisation. | `add_fonts`, `font_id`, `font_metrics`, `layout_line`, `glyph_raster_bounds`, `rasterize_glyph`, `recommended_rendering_mode` |
| `PlatformAtlas` | GPU texture atlas for glyphs, SVGs, images. | `get_or_insert_with(key, build) -> Option<AtlasTile>`, `remove` |
| `PlatformInputHandler` / `InputHandler` | Text input and IME bridge (see [input internals](/codebase/input-and-dispatch-internals/)). | `replace_text_in_range`, `marked_text_range`, `bounds_for_range`, ... |
| `PlatformKeyboardLayout`, `PlatformKeyboardMapper` | Keyboard layout identity and mapping of key equivalents. | `id`, `name`, `map_key_equivalent` |
| `PlatformHeadlessRenderer` (test/bench only) | Render a `Scene` to an `RgbaImage` without a window. | `render_scene_to_image`, `render_scene` |

Glue types: `WindowParams`/`WindowOptions`, `RequestFrameOptions { require_presentation, force_render, signal_at, signal_source }`, `FrameRequestSource { NativeCallback, LocalSchedule }`, `DispatchEventResult`, `WindowVisibility`, `PlatformInfo { os, target }`, and, for runtime mode switching, `WindowingRequest { Headless, Windowed(GraphicalEnvironment) }` plus (Linux) `WindowingModes` bitflags.

Runtime flow across the boundary (full version in [How a frame is drawn](/codebase/frame-lifecycle/)):

```text
Platform::run(on_finish_launching)      blocks (or returns, on wasm) running the OS loop
  -> your callback gets &mut App
Platform::open_window  -> PlatformWindow
Window::new registers callbacks on the PlatformWindow:
    on_request_frame -> Window::draw + present      (PlatformWindow::draw(&Scene))
    on_input         -> Window::dispatch_event
    on_resize / on_active_status_change / on_close / ...
```

## Choosing a backend: `gpui_platform`

`crates/gpui_platform/src/gpui_platform.rs` is 231 lines:

```rust
pub fn application() -> gpui::Application { gpui::Application::with_platform(current_platform(false)) }
pub fn headless()    -> gpui::Application { gpui::Application::with_platform(current_platform(true)) }

pub fn current_platform(headless: bool) -> Rc<dyn Platform> {
    cfg_select! {
        target_os = "ios"     => gpui_ios::current_platform(headless),
        target_os = "macos"   => Rc::new(gpui_macos::MacPlatform::new(headless)),
        target_os = "windows" => Rc::new(gpui_windows::WindowsPlatform::new(headless).expect(..)),
        all(any(target_os = "linux", target_os = "freebsd"), not(target_env = "ohos"))
                              => gpui_linux::current_platform(headless),
        target_family = "wasm" => { Rc::new(gpui_web::WebPlatform::new_with_backend(true, WebBackendPreference::Auto)) },
    }
}
```

Other entry points: `linux(WindowingModes)`, `application_with_web_backend(..)`, `single_threaded_web()`, `web_init()` (panic hook and logging), and with `bench-support` / `test-support`, `bench_text_system()` and `current_headless_renderer()` (Metal headless renderer on macOS, `WgpuHeadlessRenderer` on Linux, `None` elsewhere).

Backend selection is by compile-time `cfg`, not runtime. On Linux the *display server* is chosen at runtime (below). The backend crates that get compiled are selected by `[target.'cfg(...)'.dependencies]` tables in `gpui_platform/Cargo.toml`; features `wayland`, `x11` forward to `gpui_linux`; `font-kit` and `runtime_shaders` forward to the Apple crates.

:::caution[Linux: `gpui_platform` defaults enable neither Wayland nor X11]
`gpui_platform`'s `default = ["multithreaded"]`, and the workspace declares `gpui_linux` with `default-features = false`. `gpui_linux`'s own `default = ["wayland", "x11"]` therefore does not apply when it is pulled in through `gpui_platform`. `crates/gpui/README.md` tells Linux users to enable `wayland`, `x11` or both on `gpui_platform`. Without them, `gpui_linux` can only run headless. See [Cargo features](/reference/cargo-features/).
:::

## `gpui_linux`

About 17.5k lines. **Start reading at** `LinuxPlatform::run` in `crates/gpui_linux/src/linux/platform.rs`, then the `PlatformWindow::draw` of the window type for your display server. Layout under `crates/gpui_linux/src/linux/`:

| Path | Role |
| --- | --- |
| `platform.rs` (2,211) | `LinuxPlatform`, `LinuxCommon` (executors, text system, appearance, callbacks, `calloop` `LoopSignal`), `impl Platform for LinuxPlatform`, mode switching (`request_windowing`, `apply_pending_mode`), file pickers, credentials via `oo7`. |
| `display_connection.rs` | `Backend { Wayland, X11 }`, `select_backend(modes, &GraphicalEnvironment)`, and the `DisplayConnection { Headless, Wayland, X11 }` enum with a `dispatch!` macro forwarding every operation. |
| `wayland/` (`client.rs` 3,506, `window.rs` 2,601, `clipboard.rs`, `cursor.rs`, `serial.rs`, `display.rs`, `layer_shell.rs`, `popup.rs`) | A Wayland client built on `wayland-client` with `calloop-wayland-source`. `client.rs` has dozens of `impl Dispatch<..> for WaylandClientStatePtr` (seat, keyboard, pointer, text-input-v3, xdg surfaces, data devices, fractional scale, pointer gestures, layer shell, xdg-activation, primary selection). |
| `x11/` (`client.rs` 3,215, `window.rs` 2,067, `clipboard.rs` 1,288, `xim_handler.rs`, `event.rs`, `display.rs`) | An X11 client on `x11rb` (xcb) with XIM input methods (`zed-xim`), XInput2, RandR, DRI3. |
| `headless.rs`, `headless/window.rs` | `HeadlessConnection` and `HeadlessWindow`: "lay out and handle input but draw nothing". |
| `dispatcher.rs` | `LinuxDispatcher`: N worker threads (at least 2, `available_parallelism`) draining a `PriorityQueueReceiver`, one timer thread, and a `calloop` channel for the main thread queue. |
| `text_system.rs` | One line: `pub(crate) use gpui_wgpu::CosmicTextSystem;`. |
| `xdg_desktop_portal.rs`, `system_notifications.rs`, `power.rs`, `keyboard.rs` | Portals (`ashpd`), notifications (`notify-rust`), power state, `xkbcommon` keyboard layouts. |

### Event loop: calloop

`LinuxPlatform::run(on_finish_launching)`:

```rust
self.connect_initially();
on_finish_launching();
let mut event_loop = self.event_loop.borrow_mut().take().expect("App is already running");
event_loop.run(None, &mut (), |_| self.apply_pending_mode()).log_err();
// then fire the quit callback
```

Everything is a calloop event source: the foreground executor's channel, timers, the Wayland connection (`calloop-wayland-source`) or X11 connection, the power listener, portal results. `Platform::quit` calls `common.signal.stop()` on the `LoopSignal`.

### Wayland vs X11 vs headless

`connect_initially` takes the initial `WindowingRequest` (default `Windowed(GraphicalEnvironment::detect())`) and calls `select_backend(allowed_modes, environment)`:

1. Wayland if the `wayland` feature is compiled, `WindowingModes::WAYLAND` is allowed and `WAYLAND_DISPLAY` is set and non-empty;
2. else X11 if `x11` is compiled, allowed and `DISPLAY` is set and non-empty;
3. else no connection: it `assert!`s that `HEADLESS` is allowed (message: `"{:?} does not allow starting headless, and no allowed display server was given"`) and starts headless.

So with neither env var set (or neither feature), a windowed app silently becomes headless: windows open but nothing is drawn. `current_platform(headless)` uses `WindowingModes::HEADLESS` when `headless` is true or when the `ZED_HEADLESS` env var exists, and `WindowingModes::all()` otherwise. `App::request_windowing` / `Application::with_windowing` can switch modes at runtime; the platform refuses to switch while a window is open (see the comment block on `DisplayConnection`).

### Rendering and pacing

Both Wayland and X11 windows own a `gpui_wgpu::WgpuRenderer`. `PlatformWindow::draw` first recovers from a lost device (`renderer.device_lost()` -> `renderer.recover(&raw_window)`), then (Wayland) arms `surface.frame(...)` and calls `renderer.draw(scene)`. The Wayland window has a small state machine (`FrameLoop::{Ticking, AwaitingCallback, Parked, RetryScheduled, PresentationFailed, RescheduleRequested, Scheduled}`) so that frame callbacks are never stalled (`frame`, `complete_frame`, `frame_callback_fired`, `scheduled_frame_fired` in `wayland/window.rs`).

### Environment variables read here

`WAYLAND_DISPLAY`, `DISPLAY`, `XDG_RUNTIME_DIR` (`GraphicalEnvironment::detect` in `gpui/src/platform.rs`), `ZED_HEADLESS`, `XDG_ACTIVATION_TOKEN` and `WAYLAND_SOCKET` (Wayland client, both removed from the environment after reading), `GPUI_X11_SCALE_FACTOR` (X11 DPI override), `XCURSOR_PATH`, `LC_CTYPE`, and `GPUI_LINUX_DISPLAY_MODE_SCENARIO` (test scaffolding). Details in [Cargo features and environment variables](/reference/cargo-features/).

## `gpui_wgpu`

About 6.3k lines of Rust plus WGSL (the shader language wgpu uses). It is used by Linux and the web. **Start reading at** `WgpuRenderer::draw` in `wgpu_renderer.rs`.

| File | Role |
| --- | --- |
| `wgpu_renderer.rs` (2,959) | `WgpuRenderer`, `WgpuSurfaceConfig`, `GpuContext`, `WgpuHeadlessRenderer`. `draw(&Scene) -> bool`, `update_drawable_size`, `recover`, `replace_surface`, `unconfigure_surface`. Internals: `WgpuPipelines`, `WgpuBindGroupLayouts`, instance buffers per primitive kind, path rasterisation with MSAA to an intermediate texture then composite, `render_frame` iterating `scene.batches()`. |
| `wgpu_context.rs` (832) | `WgpuContext` (instance, adapter, device, queue, dual-source blending detection), adapter ranking, device-lost and uncaptured-error handlers (`DeviceErrorState`). Web-only `WebBackendPreference { Auto, WebGpu, WebGl }`. |
| `wgpu_atlas.rs` (568) | `WgpuAtlas`: `PlatformAtlas` over wgpu textures with `etagere` rectangle packing. |
| `cosmic_text_system.rs` (1,875) | `CosmicTextSystem`: `PlatformTextSystem` using `cosmic-text` and `swash`; optional `font-kit` feature changes how the best matching face for a `Font` is found. |
| `shaders.wgsl` (1,362), `shaders_subpixel.wgsl`, `shaders_storage.wgsl`, `shaders_webgl.wgsl` | Vertex/fragment pairs: `vs_quad/fs_quad`, `vs_shadow/fs_shadow`, `vs_path_rasterization`, `vs_path`, `vs_underline`, `vs_mono_sprite`, `vs_poly_sprite`, `vs_surface`; the WebGL variant reads instance data from a `texture_2d<u32>` instead of storage buffers. |

Device selection (`WgpuContext`): the adapter list is sorted by (1) a `ZED_DEVICE_ID` PCI id match, (2) the GPU the compositor is using, (3) device type with `Discrete > Integrated > Other > Virtual > Cpu`. Gamma and contrast for text are read from `ZED_FONTS_GAMMA` (default 1.8, clamped to 1.0..2.2), `ZED_FONTS_GRAYSCALE_ENHANCED_CONTRAST` (default 1.0) and `ZED_FONTS_SUBPIXEL_ENHANCED_CONTRAST` (default 0.5) in `RenderingParameters::new`. On Linux the wgpu features enabled are `std, metal, gles, vulkan, wgsl, webgpu`; on wasm `webgl`.

`WgpuRenderer::draw` returns `false` for transient surface states (`Suboptimal`, `Lost`, `Outdated`, `Timeout`, `Occluded`, validation errors) after reconfiguring the surface where appropriate, so the window knows presentation did not happen and can retry. After more than ten consecutive GPU errors it panics with `"Too many consecutive GPU errors. Last error: {error}"`.

## `gpui_windows`

About 13.4k lines. No wgpu: Windows has its own stack. **Start reading at** `window_procedure` in `window.rs` (where Win32 messages arrive) and `WindowsPlatform::run` in `platform.rs`.

| File | Role |
| --- | --- |
| `platform.rs` (2,026) | `WindowsPlatform`. `run` connects (`connect_initially`), calls `on_finish_launching`, then runs the classic `GetMessageW` / `TranslateMessage` / `DispatchMessageW` loop, finally firing the quit callback. A hidden top-level window (not message-only) receives system broadcasts like `WM_DISPLAYCHANGE`. |
| `window.rs` (1,742), `events.rs` (1,836) | `WindowsWindow` and `window_procedure`; `handle_msg` translates `WM_*` messages into `PlatformInput`, resize, DPI, IME, focus, close, hit-testing for window controls. |
| `directx_renderer.rs` (2,058), `directx_devices.rs`, `directx_atlas.rs` | `DirectXRenderer` on Direct3D 11 with DXGI swap chains (optionally via DirectComposition; disable with `GPUI_DISABLE_DIRECT_COMPOSITION=true` or `1`); path rendering through a 4x MSAA intermediate texture; device-lost recovery with `skip_draws`. |
| `direct_write.rs` (2,076) | `DirectWriteTextSystem`. Headless platforms use `gpui::NoopTextSystem`. |
| `shaders.hlsl` (1,268), `alpha_correction.hlsl`, `build.rs` | HLSL for each primitive. In release builds (`not(debug_assertions)`) `build.rs` compiles modules `quad`, `shadow`, `path_rasterization`, `path_sprite`, `underline`, `monochrome_sprite`, `subpixel_sprite`, `polychrome_sprite` with `fxc.exe` into `OUT_DIR/shaders_bytes.rs`. `fxc` is located via `GPUI_FXC_PATH`, `where.exe fxc.exe`, or the Windows SDK; it panics `"Failed to find fxc.exe"` otherwise. |
| `dispatcher.rs`, `vsync.rs`, `direct_manipulation.rs`, `clipboard.rs`, `dialog.rs`, `destination_list.rs`, `system_settings.rs`, `keyboard.rs`, `display.rs`, `system_notifications.rs`, `util.rs`, `wrapper.rs` | Thread-pool dispatcher posting `WM_GPUI_TASK_DISPATCHED_ON_MAIN_THREAD` to the platform window; a DWM-timing vsync provider; precision touchpad via DirectManipulation; clipboard, file dialogs, jump lists, system settings, keyboard layout, monitors, toast notifications. |

Data flow: Win32 message -> `window_procedure` -> `handle_msg` -> `PlatformInput` -> callback -> `Window::dispatch_event`. Frames: `vsync.rs` produces `FrameRequestSource::NativeCallback` or `LocalSchedule` requests. A subtle point documented in the `Window::new` frame callback: Windows can pump messages during a draw, so the frame callback checks `draw_in_progress()`.

## `gpui_macos`

About 10k lines of AppKit glue using `objc2`. **Start reading at** `MacPlatform::run` in `platform.rs` and `platform_input_from_native` in `events.rs`.

| File | Role |
| --- | --- |
| `platform.rs` (1,632) | `MacPlatform::new(headless)` (panics `"Mac platform not created on main thread"` if not on the main thread). `run` sets up `NSApplication` with a delegate class and activation policy; headless mode runs `CFRunLoopRun`. Menus, dock menu, URLs, keychain credentials. |
| `window.rs` (4,151) | `MacWindow` / `MacWindowState`: `NSWindow` + a native view, tabbing, fullscreen, titlebar, IME (`NSTextInputClient`), drag and drop. Owns the renderer (`renderer::Renderer`), whose `draw(scene)` is called from `PlatformWindow::draw`. |
| `events.rs` (579) | `platform_input_from_native`: `NSEvent` -> `PlatformInput`. |
| `display_link.rs` (690) | Frame pacing: `CAMetalDisplayLink` on macOS 14+, otherwise a registry of immortal `CVDisplayLink`s shared by windows. |
| `keyboard.rs` (1,508), `pasteboard.rs`, `display.rs`, `window_appearance.rs`, `system_notifications.rs`, `screen_capture.rs` | Text Input Sources layout, `NSPasteboard` including the find pasteboard, displays, light/dark, `UNUserNotificationCenter`, ScreenCaptureKit (feature `screen-capture`). |

Text: `MacPlatform::new` uses `gpui_apple::AppleTextSystem::new()` under `feature = "font-kit"`, and otherwise logs `"gpui_macos was compiled without the `font-kit` feature, so no text will be rendered."` and installs `gpui::NoopTextSystem`.

Everything Metal (renderer, atlas, `AppleDispatcher`, `main_thread_marker`) is imported from the `gpui_apple` crate (`use gpui_apple::metal_renderer as renderer;`, `pub(crate) use gpui_apple::{AppleActivity, AppleDispatcher, main_thread_marker};`), which was not available for this documentation.

## `gpui_web`

About 7.9k lines (including a `hello_web` example gallery). Only compiles its modules for `target_family = "wasm"`. **Start reading at** the module doc in `gpui_web.rs`, then `WebPlatform::run` in `platform.rs`.

- Documented limits (module doc in `gpui_web.rs`): "one document-owned canvas and supports one top-level window"; WebGPU preferred with automatic WebGL2 fallback; `WebBackendPreference` forces either; a second window, or reopening after closing, returns `WebWindowError`.
- `platform.rs`: `WebPlatform`. `run` spawns an async task that calls `initialize_graphics` (creating the canvas, a `WgpuContext` and a surface), then invokes `on_finish_launching`; on failure it shows an unavailable message in the page.
- `window.rs`: `WebWindow` drives frames with `requestAnimationFrame` and renders with `gpui_wgpu::WgpuRenderer`.
- `events.rs`, `ime_mirror.rs`, `keyboard.rs`, `viewport.rs`: DOM events to `PlatformInput`, an off-screen text mirror for IME, the browser keyboard layout, visual viewport tracking.
- `dispatcher.rs`: `WebDispatcher`. With the `multithreaded` feature (default) it uses `wasm_thread` workers and requires `SharedArrayBuffer`/`Atomics` (the page must be cross-origin isolated); the function `shared_memory_supported()` checks this. The `gpui_platform::single_threaded_web()` constructor builds a single-threaded platform.
- `text_system.rs`: `WebTextSystem` wraps `CosmicTextSystem::new_without_system_fonts(..)` and adds a Canvas-based fallback for missing CJK and emoji graphemes (`canvas_fallback.rs`, `canvas_text.rs`, `glyph_cache.rs`, `run_replacements.rs`). Fonts must be added with `add_fonts` (the examples bundle IBM Plex Sans; `examples/example_support/fonts.rs`).
- `http_client.rs`: `FetchHttpClient` for `http_client::HttpClient` on top of `fetch`.

## `gpui_ios`

About 3.7k lines of UIKit glue. **Start reading at** `ios/application.rs`. The crate is compiled only for `target_os = "ios"` (`crate-type = ["staticlib", "rlib"]`). The crate-level doc: "connects GPUI to UIKit, CoreText, and Metal through the shared Apple renderer".

- `ios/application.rs`: `run`, app delegate, `CADisplayLink` (`render_frame`), lifecycle phases.
- `ios/platform.rs`: `IosPlatform`. `quit` and `restart` log warnings ("iOS apps cannot programmatically quit"). Mobile-only trait methods in `Platform` (`on_app_lifecycle`, `on_memory_warning`, `gestures`) are implemented for it.
- `ios/window.rs`: a `GPUIMetalView` whose layer class is `CAMetalLayer`; `PlatformWindow::draw` is `self.renderer.lock().draw(scene)` using the Metal renderer from `gpui_apple`; safe-area and keyboard insets; `set_status_bar_style`.
- `ios/text_input.rs`, `events.rs`: native text input, raw touch delivery (`PlatformInput::Touch`, recognised into gestures by `gestures.rs` in `gpui`).
- `examples/ios.rs` plus `examples/ios/` (Info.plist, `build-simulator.sh`).

## The backends at a glance

| | Linux | macOS | Windows | Web | iOS |
| --- | --- | --- | --- | --- | --- |
| Crate | `gpui_linux` | `gpui_macos` (+ `gpui_apple`) | `gpui_windows` | `gpui_web` | `gpui_ios` (+ `gpui_apple`) |
| Event loop | `calloop` | `NSApplication` run loop | Win32 message loop | browser | UIKit |
| Renderer | `gpui_wgpu` (Vulkan/GL) | Metal (`gpui_apple`) | Direct3D 11 | `gpui_wgpu` (WebGPU/WebGL2) | Metal (`gpui_apple`) |
| Text system | `CosmicTextSystem` | `AppleTextSystem` (needs `font-kit`) | `DirectWriteTextSystem` | `WebTextSystem` over cosmic-text | Apple (via `gpui_apple`) |
| Frame source | `wl_surface.frame` / timers | `CAMetalDisplayLink` / `CVDisplayLink` | vsync thread (DWM timing) | `requestAnimationFrame` | `CADisplayLink` |
| Windows | many | many | many | one | UIKit window |
| Headless | yes (`HeadlessWindow`) | yes (`CFRunLoopRun`) | yes (`NoopTextSystem`) | n/a | `current_platform(_headless)` ignores the flag |

## Try it yourself

These are reading exercises. None changes the repository.

1. Open `crates/gpui_platform/src/gpui_platform.rs` (231 lines) and read `current_platform`. Which `cfg_select!` branch would your machine take?
2. In `crates/gpui/src/platform.rs`, list the methods of the `Platform` trait that have no default body. That is the minimum a new backend must write.
3. Find `impl PlatformWindow for` in the backend for your OS (`rg "impl PlatformWindow for" crates`). Locate its `draw` method and see what it hands to the renderer.
4. Find the frame source for your OS in the table in [How a frame is drawn](/codebase/frame-lifecycle/) (step 6). Open that file and find where it calls the `on_request_frame` callback.
5. On Linux, read `select_backend` in `gpui_linux/src/linux/display_connection.rs`. Which two environment variables decide between Wayland and X11?

## Next steps

- [How a frame is drawn](/codebase/frame-lifecycle/): how `PlatformWindow::draw` and `on_request_frame` fit into one frame.
- [How input finds your code](/codebase/input-and-dispatch-internals/): what happens after a backend produces `PlatformInput`.
- [Windows and platform](/guides/windows-and-platform/): the user-facing guide to opening windows on each OS.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/platform.rs` (all the platform traits)
- `crates/gpui_platform/src/gpui_platform.rs`, `crates/gpui_platform/Cargo.toml`
- `crates/gpui_linux/src/linux/` (`platform.rs`, `display_connection.rs`, `wayland/`, `x11/`, `headless.rs`, `dispatcher.rs`)
- `crates/gpui_wgpu/src/` (`wgpu_renderer.rs`, `wgpu_context.rs`, `wgpu_atlas.rs`, `cosmic_text_system.rs`, `shaders.wgsl`)
- `crates/gpui_windows/src/` (`platform.rs`, `window.rs`, `events.rs`, `directx_renderer.rs`, `direct_write.rs`, `vsync.rs`)
- `crates/gpui_macos/src/` (`platform.rs`, `window.rs`, `events.rs`, `display_link.rs`)
- `crates/gpui_web/src/`, `crates/gpui_ios/src/ios/`
</details>
