---
title: Run work in the background
description: Load files, call servers and wait on timers without freezing your window, then show the result in your view.
sidebar:
  order: 7
  label: Async and background work
---

How do you read a big file, or wait two seconds, without freezing the window? You move the slow part off the UI thread, then hand the result back to your view when it is ready.

## What you'll learn

- Why slow work freezes your window, and how to avoid it
- How to run work in the background with `cx.background_spawn`
- How to update a view when that work finishes with `cx.spawn`
- How tasks are cancelled, detached or stored
- How to wait with a timer, and how to use Tokio-based libraries

## Why a window freezes

Your app has one **UI thread**. It handles clicks, runs `render` and draws every frame. If any of that code takes a second, nothing else happens for a second. The window looks frozen.

So slow work (reading big files, parsing, network calls, `sleep`) must not run on the UI thread. GPUI gives you two places to run async code:

| | Where it runs | Can it touch your views? | Use it for |
|---|---|---|---|
| `cx.spawn` | The UI thread, between other events | Yes | Applying results to your view |
| `cx.background_spawn` | A pool of worker threads | No | The slow part itself |

The pattern you will use almost every time: start on the UI thread with `cx.spawn`, do the slow part with `cx.background_spawn`, then update your view.

:::note[Coming from React?]
This is close to `useEffect` plus `fetch` plus `setState`. The difference: GPUI does not re-run anything for you. You start the work from an event handler, and you call `cx.notify()` when the data changes.
:::

## A first example: load data without freezing

This program has one button. Click it and the app pretends to load something for two seconds. The window stays responsive the whole time. Replace `src/main.rs` (see [Hello World](/start/hello-world/) for the project setup).

```rust title="src/main.rs"
use std::time::Duration;

use gpui::{
    App, Bounds, Context, SharedString, Task, Window, WindowBounds, WindowOptions, div,
    prelude::*, px, rgb, size,
};
use gpui_platform::application;

struct Loader {
    status: SharedString,
    // Keeping the task here keeps the work alive (more on this below).
    _load: Option<Task<()>>,
}

impl Loader {
    fn start_loading(&mut self, cx: &mut Context<Self>) {
        self.status = "Loading...".into();
        cx.notify();

        self._load = Some(cx.spawn(async move |this, cx| {
            // 1. Slow work runs on a worker thread.
            let answer = cx
                .background_spawn(async move {
                    std::thread::sleep(Duration::from_secs(2)); // pretend this is slow I/O
                    42
                })
                .await;

            // 2. Back on the UI thread: store the result and redraw.
            this.update(cx, |this, cx| {
                this.status = format!("The answer is {answer}").into();
                cx.notify();
            })
            .ok();
        }));
    }
}

impl Render for Loader {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        div()
            .flex()
            .flex_col()
            .gap_4()
            .size_full()
            .justify_center()
            .items_center()
            .bg(rgb(0x1e1e2e))
            .text_color(rgb(0xcdd6f4))
            .child(self.status.clone())
            .child(
                div()
                    .id("load")
                    .px_4()
                    .py_2()
                    .rounded_md()
                    .bg(rgb(0x313244))
                    .hover(|s| s.bg(rgb(0x45475a)))
                    .cursor_pointer()
                    .on_click(cx.listener(|this, _, _, cx| this.start_loading(cx)))
                    .child("Load data"),
            )
    }
}

fn main() {
    application().run(|cx: &mut App| {
        let bounds = Bounds::centered(None, size(px(400.), px(240.)), cx);
        cx.open_window(
            WindowOptions {
                window_bounds: Some(WindowBounds::Windowed(bounds)),
                ..Default::default()
            },
            |_, cx| {
                cx.new(|_| Loader {
                    status: "Nothing loaded yet".into(),
                    _load: None,
                })
            },
        )
        .unwrap();
        cx.activate(true);
    });
}
```

Click **Load data**. The text changes to "Loading...", and two seconds later to "The answer is 42". The button still reacts to your mouse while it loads.

## How it works

Take the important lines one at a time.

### Start on the UI thread with `cx.spawn`

```rust
cx.spawn(async move |this, cx| { /* ... */ })
```

`cx.spawn` takes an async closure. GPUI runs it on the UI thread and gives it two things:

- `this` is a `WeakEntity<Loader>`, a handle to your view that does not keep it alive.
- `cx` is an `AsyncApp`, a context you can hold across `.await`.

A long task should not keep your view alive, so you get a weak handle. If the view is gone when the task finishes, `this.update(...)` returns an `Err`.

### Do the slow part with `cx.background_spawn`

```rust
let answer = cx.background_spawn(async move { /* slow */ 42 }).await;
```

This runs the future on a worker thread. The future must be `Send + 'static`, so it cannot borrow `self` or hold a view handle. Move owned data in (a `PathBuf`, a `String`, a clone of what you need) and return owned data out.

While you `.await`, the UI thread is free to handle events. That is the whole trick.

### Hand the result back with `this.update`

```rust
this.update(cx, |this, cx| {
    this.status = format!("The answer is {answer}").into();
    cx.notify();
})
.ok();
```

Now you are back on the UI thread, so you can change your view. `cx.notify()` tells GPUI to redraw it. Without that call the data changes but the screen does not.

## Tasks: drop cancels, detach keeps going

`cx.spawn` and `cx.background_spawn` both return a `Task`. A task is a handle to the running work.

**If you drop a task, the work stops.** That is the most important rule on this page.

```rust
cx.spawn(async move |this, cx| { /* ... */ }); // dropped immediately: never finishes
```

You have three ways to keep it running:

| Do this | When |
|---|---|
| `.detach()` | Fire and forget. It runs to the end and you cannot cancel it |
| Store it in a field | The work should live as long as the view, and be cancellable |
| `.await` it inside another async block | You need its result |

The example stores the task in `_load`. This has a nice side effect. If the user clicks **Load data** twice, the second `Some(...)` replaces the first task, which drops it and cancels it. Only the newest request finishes. That is a simple way to get "latest request wins" and debouncing.

If your task returns a `Result`, use `.detach_and_log_err(cx)`. It runs the task and logs the error if it fails.

## Wait with a timer

Use GPUI's timer instead of `std::thread::sleep` on the UI thread:

```rust
cx.spawn(async move |this, cx| {
    loop {
        cx.background_executor().timer(Duration::from_secs(1)).await;
        let result = this.update(cx, |this, cx| {
            this.seconds += 1;
            cx.notify();
        });
        if result.is_err() {
            break; // the view is gone, so stop ticking
        }
    }
})
.detach();
```

This ticks once a second without blocking anything. Notice the `break`. When the view is closed, `update` returns `Err`. A loop that ignores it would spin forever.

[Tests](/guides/testing/) can move this timer's clock forward instantly.

## Use a library that needs Tokio

GPUI has its own async runtime, not Tokio. Libraries that need a Tokio runtime (`reqwest` is the common one) can panic or hang if you `.await` them inside `cx.spawn`.

The `gpui_tokio` crate (in the Zed repository) bridges the two. Call `init` once at startup, then wrap the Tokio future:

```rust
// once, at startup
gpui_tokio::init(cx);

// later, inside a cx.spawn closure
let response = gpui_tokio::Tokio::spawn(cx, async move {
    client.get(url).send().await
})
.await;
```

The result is a normal GPUI `Task`, and dropping it cancels the Tokio work too.

## Common mistakes

:::caution[The task is dropped]
`cx.spawn(...)` with the result ignored cancels right away. Add `.detach()`, `.detach_and_log_err(cx)`, or store the task in a field.
:::

:::caution[Heavy work inside `cx.spawn`]
`cx.spawn` runs on the UI thread. Parsing a big file there still freezes the window. Move the heavy part into `cx.background_spawn(...)` and `.await` it.
:::

- **Sending views to the background.** An `Entity`, `WeakEntity` or `Rc` cannot cross into `background_spawn`. Clone the plain data you need first.
- **Awaiting inside `update`.** The closure you pass to `update` is not async. Do the awaiting outside, then apply the result inside a new `update`.

## Next steps

- [Test your app](/guides/testing/) to run these tasks deterministically in tests
- [Debug and speed up your app](/guides/debugging-and-performance/) to find code that blocks the UI
- Want the why? [Contexts](/deep-dive/contexts/) and [Entities](/deep-dive/entities/) explain `AsyncApp` and weak handles

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/executor.rs`
- `crates/gpui/src/app/context.rs` (`spawn`, `spawn_in`)
- `crates/gpui/src/app/async_context.rs`
- `crates/gpui_tokio/src/gpui_tokio.rs`
- `crates/gpui/examples/testing.rs`, `move_entity_between_windows.rs`
</details>
