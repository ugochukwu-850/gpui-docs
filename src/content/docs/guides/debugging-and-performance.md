---
title: Debug and speed up your app
description: Find out why your UI does not update, why it freezes or stutters, and why memory keeps growing, with the tools GPUI gives you.
sidebar:
  order: 13
  label: Debugging and performance
---

Something is wrong with your app. The screen does not update, the window stutters, or it uses more and more memory. This page gives you a short checklist for each problem and shows the tools that help.

## What you'll learn

- How to see GPUI's log messages
- What to check when the UI does not update
- How to find code that freezes the window
- How to read frame times, and how to inspect elements
- Habits that keep your app fast
- Which environment variables and Cargo features help

## See the log messages

GPUI writes warnings and errors (a failed image load, for example) through the Rust `log` crate. You only see them if your app sets up a logger. The GPUI examples use `env_logger`:

```toml title="Cargo.toml"
[dependencies]
env_logger = "0.11"
```

```rust
fn main() {
    env_logger::init(); // first line of main
    // ...
}
```

Run with a log level:

```sh
RUST_LOG=info cargo run
```

Start here for any "it silently does nothing" problem.

## The UI does not update

This is the most common problem. Go through the list:

1. **Did you call `cx.notify()`?** GPUI does not watch your fields. When you change data, call `cx.notify()` so it redraws the view. This includes changes made from a task or a timer.
2. **Did you notify the right view?** `cx.notify()` redraws the view it is called on. If the data lives in another view, notify that one.
3. **Is the task still alive?** A dropped task is cancelled, and its update never happens. See [Run work in the background](/guides/async-and-executors/).
4. **Is a click handler missing an id?** Handlers like `on_click` need `.id("some-name")` on the element first.
5. **Is the log telling you something?** Turn on logging (above).

## The window freezes or stutters

The UI thread does everything: handling clicks, calling `render`, drawing. If any piece takes too long, the window stalls. The usual cause is slow work done directly in a click handler or in `render`.

The fix is almost always to move that work to the background with `cx.background_spawn`. See [Run work in the background](/guides/async-and-executors/).

To find the culprit, GPUI has a **hang monitor**. It watches the UI thread and reports any piece of work that took too long. It is part of the `profiler` feature:

```toml title="Cargo.toml"
gpui = { version = "...", features = ["profiler"] }
```

```rust
use std::time::Duration;
use gpui::profiler::hang::HangMonitorConfig;

cx.start_hang_monitor(
    HangMonitorConfig {
        threshold: Duration::from_millis(100),   // work longer than this is a hang
        frame_budget: Duration::from_millis(16), // roughly one frame at 60 fps
        interval: Duration::from_secs(1),        // how often to check
    },
    |poll| {
        // runs on the monitor's own thread
        if !poll.incidents.is_empty() {
            eprintln!("UI thread was blocked: {} incident(s)", poll.incidents.len());
        }
    },
)
.expect("hang monitor");
```

It can be started once per app. The report arrives after the slow work finishes, because work that never finishes cannot be measured.

## Look at frame times

The `profiler` feature also adds a small overlay that shows how long each frame takes to draw. Switch it on from any handler that has a `window`:

```rust
window.cycle_debug_frame_overlay_mode(); // Hidden -> Minimal -> Full -> Hidden
```

`Minimal` shows the latest draw time in milliseconds. `Full` adds the worst recent times and a frame counter. A frame needs to finish in about 16 ms to hold 60 frames per second.

The overlay does not cause redraws itself, so if its frame counter keeps climbing while nothing should change, something is redrawing the window nonstop. Look for a `cx.notify()` inside an observer, or a repeating animation.

Always measure a **release build** (`cargo run --release`). Debug builds do extra checks and are much slower.

## Inspect elements

The inspector lets you pick an element in a running window and see its style and layout. GPUI provides the picking. Your app provides the panel that shows the details, so there is no ready-made inspector window.

- `window.toggle_inspector(cx)` turns inspector mode on or off for one window.
- `cx.set_inspector_renderer(...)` is where you draw the panel.

Both exist in debug builds, or when you enable the `inspector` feature. GPUI does not bind a key to the inspector. Hook `toggle_inspector` to an action of your own.

## Find out why memory grows

The most common cause is two things holding on to each other, so neither is ever dropped:

- A view stores a task, and the task holds a strong handle to the same view. Inside `cx.spawn`, use the weak handle you are given (`this`).
- Two views hold `Entity` handles to each other. Make one side a `WeakEntity`.
- A subscription was created but its `Subscription` was never stored or dropped.

You can write a test that proves a view goes away. See [Catch memory leaks](/guides/testing/#catch-memory-leaks).

## Keep your app fast

These habits matter most. Skim them before you reach for tools.

**Notify as little as you can.** `cx.notify()` redraws one view. Put a ticking clock or a progress bar in its own small view, so a change redraws that view and not your whole window.

**Show long lists with `uniform_list`.** It only builds the rows you can see. Never add 10,000 `.child(...)` calls. See the [long lists tutorial](/tutorials/long-lists/).

**Keep `render` cheap.** It runs every time the view changes. Do not sort big collections or format lots of strings inside it. Compute once when the data changes, and store the result as `SharedString`s.

**Do slow work in the background.** Anything over a millisecond or two belongs in `cx.background_spawn`.

**Cache parts that rarely change.** `entity.cached(style)` reuses a child view's drawing until it changes. The catch: a cached view needs a definite size, so you give it one in the `style`:

```rust
use gpui::StyleRefinement;

div().child(
    self.sidebar.clone().cached(StyleRefinement::default().size_full()),
)
```

**Stop animations you cannot see.** A repeating animation redraws every frame. Use `.with_max_fps(..)` or remove it. See [Animate things](/guides/animation/).

**Limit image memory.** Decoded pictures take space. For long galleries see `crates/gpui/examples/image_gallery.rs`. See also [Show images, icons and SVG](/guides/images-svg-and-assets/).

## Cargo features that help

Add these to the `gpui` dependency when you need them:

| Feature | Adds |
|---|---|
| `inspector` | Element inspector support (also on in debug builds) |
| `profiler` | Hang monitor, frame-time overlay, task and frame timing |
| `leak-detection` | Tracks every view handle so tests can list leaks |
| `test-support` | The test tools. See [Test your app](/guides/testing/) |

Leave `profiler` and `inspector` off in your shipping build unless you want them. They add bookkeeping on every frame.

## Environment variables

| Variable | What it does |
|---|---|
| `RUST_LOG` | Chooses which log messages show (needs a logger like `env_logger`) |
| `SEED`, `ITERATIONS` | Repeat or multiply randomized test runs |
| `GPUI_LEAK_DETECTION` | Set **when building** to track view handles |
| `LEAK_BACKTRACE` | With leak detection, records where each handle was made |
| `TRACK_THREAD_BORROWS` | Set **when building** to print every borrow of the app. Helps with "already borrowed" panics |
| `GPUI_RUN_UNTIL_PARKED_LOG=1` | In tests, logs when `allow_parking` is on |
| `ZED_HEADLESS` | Linux: start with no display |
| `GPUI_X11_SCALE_FACTOR` | Linux X11: override the scale factor |
| `ZED_DEVICE_ID` | Linux: choose a graphics card by its PCI id |
| `GPUI_DISABLE_DIRECT_COMPOSITION` | Windows: turn off DirectComposition |

The full list is in [Cargo features and environment variables](/reference/cargo-features/).

## Common mistakes

- **Judging speed from a debug build.** Always measure with `--release`.
- **Forgetting `cx.notify()`.** The most common reason a UI looks stuck.
- **Doing slow work in `render` or a click handler.** Move it to `cx.background_spawn`.
- **Calling `window.cycle_debug_frame_overlay_mode()` without the `profiler` feature.** It does not exist then, so the code will not compile.
- **Starting the hang monitor twice.** The second start fails.

## Next steps

- [Run work in the background](/guides/async-and-executors/) to fix freezes
- [Test your app](/guides/testing/) to reproduce bugs and catch leaks
- Want the why? [Views and render](/deep-dive/views-and-render/) explains what causes a redraw

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/profiler.rs`, `profiler/hang/monitor.rs`
- `crates/gpui/src/debug_overlay.rs`
- `crates/gpui/src/inspector.rs`, `crates/gpui/src/window.rs` (`toggle_inspector`, overlay methods)
- `crates/gpui/src/app.rs` (`start_hang_monitor`, `TRACK_THREAD_BORROWS`)
- `crates/gpui/src/view.rs` (`Entity::cached`)
- `crates/gpui/Cargo.toml` (features)
- `crates/gpui_linux/src/linux.rs`, `crates/gpui_wgpu/src/wgpu_context.rs`, `crates/gpui_windows/src/directx_renderer.rs` (platform variables)
</details>
