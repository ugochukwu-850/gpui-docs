---
title: Test your app
description: Write fast, repeatable tests for your GPUI views, async code, clicks and key presses without opening a real window.
sidebar:
  order: 12
  label: Testing
---

Can you test a UI without clicking around by hand? Yes. GPUI has a test mode that runs your views against a fake platform. No window opens, tests run in milliseconds, and the same test gives the same result every time.

## What you'll learn

- How to turn on GPUI's test support
- How to write your first test, step by step
- How to test code that waits on timers or background tasks
- How to click and type in a test
- How to catch memory leaks

## Set up

Turn on the `test-support` feature of `gpui` for tests only. Put it in `[dev-dependencies]`:

```toml title="Cargo.toml"
[dev-dependencies]
gpui = { version = "...", features = ["test-support"] }
```

Use the same `version` or `git` source as your normal `gpui` dependency. Tests use `#[gpui::test]` instead of `#[test]`. It works with `cargo test`.

## Your first test, step by step

We will test a small counter.

### Step 1: the code to test

```rust title="src/main.rs"
use gpui::{Context, prelude::*};

pub struct Counter {
    pub count: i32,
}

impl Counter {
    pub fn increment(&mut self, cx: &mut Context<Self>) {
        self.count += 1;
        cx.notify();
    }
}
```

### Step 2: write the test

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use gpui::TestAppContext;

    #[gpui::test]
    fn increment_adds_one(cx: &mut TestAppContext) {
        // Create a Counter, the way your app would
        let counter = cx.new(|_| Counter { count: 0 });

        // Call a method on it
        counter.update(cx, |counter, cx| counter.increment(cx));

        // Read the state back and check it
        let count = counter.read_with(cx, |counter, _| counter.count);
        assert_eq!(count, 1);
    }
}
```

### Step 3: run it

```sh
cargo test
```

You should see `increment_adds_one ... ok`.

### How it works

- `#[gpui::test]` sees that the function asks for a `TestAppContext` and builds one for you. It is a fake app with no real windows.
- `cx.new(...)` creates a view, just like it does in your app. You get an `Entity<Counter>` back.
- `counter.update(cx, ...)` lets you change the view. Observers and subscriptions run right after it, as they do in a real app.
- `counter.read_with(cx, ...)` reads it. A `TestAppContext` has no `read(cx)`, so use `read_with`.

## Test code that waits

In a test, nothing runs in the background by itself. Time is fake, and tasks wait until you tell them to run. That makes tests fast and exact.

Say `Counter` loads a value after a delay:

```rust
impl Counter {
    pub fn load_later(&mut self, cx: &mut Context<Self>) {
        cx.spawn(async move |this, cx| {
            cx.background_executor().timer(Duration::from_secs(5)).await;
            this.update(cx, |counter, cx| {
                counter.count = 100;
                cx.notify();
            })
            .ok();
        })
        .detach();
    }
}
```

The test moves the clock forward and runs the task. It does not wait five real seconds:

```rust
#[gpui::test]
fn load_later_sets_count(cx: &mut TestAppContext) {
    let counter = cx.new(|_| Counter { count: 0 });
    counter.update(cx, |counter, cx| counter.load_later(cx));

    // Not yet: the task has not run
    assert_eq!(counter.read_with(cx, |c, _| c.count), 0);

    cx.executor().advance_clock(Duration::from_secs(5)); // move time forward
    cx.run_until_parked(); // run every task that is ready

    assert_eq!(counter.read_with(cx, |c, _| c.count), 100);
}
```

`run_until_parked()` means "run tasks until nothing is left to do". Call it before you check results that come from tasks, `cx.defer`, or timers. Tests can also be `async fn`, and you can `.await` a task directly (see `crates/gpui/examples/testing.rs`).

:::caution[Common mistake]
Awaiting something GPUI does not control, like a real file read, a network call or a thread, makes the test panic with a "parked" error. This is on purpose, because it finds deadlocks. Replace the real thing with a fake. If you must wait on a real thread, call `cx.executor().allow_parking()` at the start of the test.
:::

## Test with a window: clicks and keys

A view that draws things needs a window, even a fake one. Use `add_window_view`. It gives you the view and a test context that can click and type:

```rust
use gpui::{Modifiers, TestAppContext};

#[gpui::test]
fn clicking_the_button_counts(cx: &mut TestAppContext) {
    let (view, cx) = cx.add_window_view(|_, _| CounterView { count: 0 });

    // Find the button by the name we gave it in render
    let position = cx.debug_bounds("increment").expect("button was drawn").center();
    cx.simulate_click(position, Modifiers::default());

    assert_eq!(cx.update(|_, cx| view.read(cx).count), 1);
}
```

The view marks the button with `debug_selector`, which gives it a name the test can look up:

```rust
div()
    .id("increment")
    .debug_selector(|| "increment".into())  // a name for tests
    .on_click(cx.listener(|this, _, _, cx| {
        this.count += 1;
        cx.notify();
    }))
    .child("+1")
```

This follows the test at the bottom of `crates/gpui/examples/animation.rs`. Selectors are only recorded in debug builds, which `cargo test` uses by default.

More things you can do on the test context:

```rust
cx.simulate_keystrokes("up up enter"); // press keys, space-separated
cx.simulate_input("hello");            // type text
cx.simulate_mouse_move(position, None, Modifiers::default());
cx.simulate_resize(size(px(300.), px(300.)));
```

Key presses only trigger actions if the key bindings exist. A test starts with no bindings, so register them first: `cx.update(|_, cx| cx.bind_keys([...]))`. A good habit is to put your `bind_keys` calls in an `init(cx)` function that both `main` and your tests call.

To send an action directly, as `crates/gpui/examples/testing.rs` does, call `dispatch_action` on a focus handle:

```rust
focus_handle.dispatch_action(&Increment, window, cx);
```

See [Actions and keybindings](/guides/actions-and-keybindings/) and [Focus](/guides/focus/).

## Fake the operating system

The `TestAppContext` records what your code asks the OS to do, so you can check it. These are methods of the `cx` in the test's signature, so use them in tests that do not shadow it with a window context:

- `cx.opened_url()` returns the last URL passed to `open_url`
- `cx.read_from_clipboard()` returns what your code copied
- `cx.has_pending_prompt()` and `cx.simulate_prompt_answer("Delete")` let you answer a confirmation dialog
- `cx.shown_system_notifications()` lists notifications

See [Windows, menus and the OS](/guides/windows-and-platform/) for the code that produces these.

## Run a test many times in different orders

Real apps have tasks that finish in different orders. GPUI can shuffle the order for you. Ask for several runs, and each run uses a different random seed:

```rust
#[gpui::test(iterations = 10)]
fn survives_any_order(cx: &mut TestAppContext, mut rng: StdRng) {
    // use `rng` to make choices, so each run explores something different
}
```

`StdRng` comes from the `rand` crate, so add `rand` to `[dev-dependencies]` if you use it. If run number 7 fails, repeat just that one:

```sh
SEED=7 cargo test survives_any_order
```

## Catch memory leaks

A leak happens when two things hold on to each other forever (for example, a view that stores a task that holds the view). To check that a view really goes away:

```rust
let entity = cx.new(|_| Counter { count: 0 });
let weak = entity.downgrade();
drop(entity);
cx.run_until_parked();
weak.assert_released(); // panics if something still holds the view
```

To find out *who* holds on, build with leak detection and ask for backtraces:

```sh
GPUI_LEAK_DETECTION=1 LEAK_BACKTRACE=1 cargo test my_test
```

## Common mistakes

- **Forgetting `run_until_parked()`.** Tasks, timers and `cx.defer` do not run on their own. Call it before you check the result.
- **Forgetting to move the clock.** A task waiting on a timer never finishes until you call `advance_clock`.
- **Awaiting real I/O.** The test panics. Fake it, or call `allow_parking()`.
- **Calling `read(cx)` on `TestAppContext`.** Use `read_with`.
- **Expecting key bindings from `main`.** Register them in the test.
- **Using `std::thread::sleep` in code you test.** Use the executor's timer, so the test controls time.
- **Trusting one passing run.** For code with several tasks, use `iterations = 10` or more.

## Next steps

- [Run work in the background](/guides/async-and-executors/) for the tasks you are now testing
- [Debug and speed up your app](/guides/debugging-and-performance/) when a test finds a leak or a slow frame
- Want the why? [Contexts](/deep-dive/contexts/) explains `App`, `Context` and `Window`

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/app/test_context.rs` (`TestAppContext`, `VisualTestContext`)
- `crates/gpui/src/executor.rs` (`advance_clock`, `run_until_parked`, `allow_parking`)
- `crates/gpui/src/app/entity_map.rs` (`assert_released`)
- `crates/gpui/src/seeds.rs` (`SEED`, `ITERATIONS`)
- `crates/gpui_macros/src/test.rs`
- `crates/gpui/examples/testing.rs`, `animation.rs`
</details>
