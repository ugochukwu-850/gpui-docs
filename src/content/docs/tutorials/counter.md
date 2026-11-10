---
title: "Tutorial: Build a counter"
description: Build a small window with a number and three buttons, and learn how GPUI redraws when your data changes.
sidebar:
  order: 1
  label: Counter
---

In this tutorial you will build a counter: a number on screen and three buttons that change it. It is small, but it teaches the loop that every GPUI app follows. Your data changes, you tell GPUI, and GPUI draws the window again.

## What you'll build

A small dark window, 300 by 200 pixels, with:

- a large number in the middle, starting at `0`
- a row of three buttons under it: **Decrement**, **Increment** and **Reset**
- buttons that lighten when you hover over them and darken while you press them

## What you'll learn

- How to keep state in a plain Rust struct (a *view*)
- How to build a button out of a `div`
- How to handle a click with `cx.listener`
- Why you call `cx.notify()` after changing state

:::note[Coming from React?]
A GPUI view is close to a React component, and a field like `count` plays the role of `useState`. The big difference is that there is no setter. You change the field directly, then call `cx.notify()` to say "this view changed, draw it again".
:::

## Set up the project

Create a new Rust project and add GPUI to it by following [Installation](/start/installation/). Use `edition = "2024"` in `Cargo.toml`. If you have not run a GPUI window yet, do [Hello World](/start/hello-world/) first, so you know your setup works.

You will put all the code in `src/main.rs`. The tutorial shows the file in small pieces. The complete file is at the end of the page, so you can copy it whenever you like.

## Step 1: Store the count in a struct

A *view* is a struct that knows how to draw itself. It is GPUI's version of a React component. Our view has one field.

```rust
struct Counter {
    count: i32,
}
```

`count` is an ordinary Rust field. There is no special reactive type. Whenever GPUI needs to draw the window, it reads `self.count` and builds the screen from it.

## Step 2: Draw the number and a button

A view becomes drawable when you implement the `Render` trait. Its `render` method returns a tree of elements, much like JSX. Here is the part that draws the number:

```rust
div()
    .flex()
    .flex_col()
    .gap_4()
    .size_full()
    .justify_center()
    .items_center()
    .bg(rgb(0x1e1e2e))
    .text_color(rgb(0xcdd6f4))
    .child(div().text_3xl().child(format!("{}", self.count)))
```

`div()` is a box, like an HTML `<div>`. The methods that follow are styling. They read like Tailwind classes: `flex_col` stacks children in a column, `gap_4` adds space between them, and `size_full` fills the window. `rgb(0x1e1e2e)` is a color written as hex.

The last line adds a child: the count, turned into text with `format!`. With only this, you would see a number centered on a dark background.

Next, the button. GPUI's core crate has no button element, so we make one from a `div`. We wrap it in a small helper function so we can reuse it three times.

```rust
fn button(label: &'static str) -> Stateful<Div> {
    div()
        .id(label)
        .px_4()
        .py_2()
        .rounded_md()
        .bg(rgb(0x313244))
        .text_color(rgb(0xcdd6f4))
        .cursor_pointer()
        .hover(|style| style.bg(rgb(0x45475a)))
        .active(|style| style.bg(rgb(0x585b70)))
        .child(label)
}
```

Two things here need explaining.

**The `.id(label)` call.** GPUI redraws the whole window many times, so it needs a way to recognise "the same element as last frame". It uses this to remember whether the mouse is pressed on a button, for example. An element that needs this memory must have an *id*. Calling `.id(...)` turns a `Div` into a `Stateful<Div>`, and only a `Stateful` element has `on_click` and `active`. Here we use the label as the id, since each button has a different label.

**The `.hover` and `.active` calls.** Each takes a closure that changes the style. GPUI applies the change only while the mouse is over the button (`hover`) or pressing it (`active`). You do not track any hover state yourself.

Notice the return type, `Stateful<Div>`. Returning the concrete type lets the caller keep chaining, which we do in the next step.

## Step 3: React to a click

Now we connect a button to the count. Here is the Increment button:

```rust
.child(button("Increment").on_click(cx.listener(
    |this, _event, _window, cx| {
        this.count += 1;
        cx.notify();
    },
)))
```

`on_click` runs a function when the user clicks. But the function it expects has no access to your `Counter`, because it is not tied to any view. That is what `cx.listener` solves. It wraps your closure so that, at click time, GPUI hands it:

- `this`, a `&mut Counter` you can change
- `cx`, a context for the view, which has `notify`

Inside the closure we add one to `count`, then call `cx.notify()`.

### Why `cx.notify()`

GPUI does not watch your fields. It has no way to know that `count` changed. It only draws again when you tell it the data changed, and `cx.notify()` is how you tell it. After the closure finishes, GPUI calls `render` again, and the new number appears.

When you run the app and click **Increment**, you will see the number go up by one on each click. The Decrement and Reset buttons work the same way. They are in the complete file below.

:::caution[Common mistake]
Forgetting `cx.notify()`. The code compiles and `count` really does change, but the number on screen stays the same until something else causes a redraw. If your UI looks stuck, check that every handler that changes state calls `cx.notify()`.
:::

:::caution[Common mistake]
Forgetting `.id(...)` on something you want to click. `on_click` only exists on elements that have an id, so the compiler tells you there is no method named `on_click`. Add `.id("something-unique")` before it.
:::

## Step 4: Open the window

The last piece is `main`. It starts the app and opens a window that contains a `Counter`.

```rust
fn main() {
    application().run(|cx: &mut App| {
        let bounds = Bounds::centered(None, size(px(300.), px(200.)), cx);
        cx.open_window(
            WindowOptions {
                window_bounds: Some(WindowBounds::Windowed(bounds)),
                ..Default::default()
            },
            |_, cx| cx.new(|_| Counter { count: 0 }),
        )
        .unwrap();
        cx.activate(true);
    });
}
```

`Bounds::centered` makes a 300 by 200 window in the middle of the screen. `cx.new(|_| Counter { count: 0 })` creates the view with the count starting at zero. Run `cargo run` to see it.

## Put it together

Here is the full program. Paste it into `src/main.rs` and run it. Click the buttons, then hover over them and press them to see the style changes.

<details>
<summary>Complete src/main.rs</summary>

```rust title="src/main.rs"
use gpui::{
    App, Bounds, Context, Div, Stateful, Window, WindowBounds, WindowOptions, div, prelude::*, px,
    rgb, size,
};
use gpui_platform::application;

struct Counter {
    count: i32,
}

fn button(label: &'static str) -> Stateful<Div> {
    div()
        .id(label)
        .px_4()
        .py_2()
        .rounded_md()
        .bg(rgb(0x313244))
        .text_color(rgb(0xcdd6f4))
        .cursor_pointer()
        .hover(|style| style.bg(rgb(0x45475a)))
        .active(|style| style.bg(rgb(0x585b70)))
        .child(label)
}

impl Render for Counter {
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
            .child(div().text_3xl().child(format!("{}", self.count)))
            .child(
                div()
                    .flex()
                    .gap_2()
                    .child(button("Decrement").on_click(cx.listener(
                        |this, _event, _window, cx| {
                            this.count -= 1;
                            cx.notify();
                        },
                    )))
                    .child(button("Increment").on_click(cx.listener(
                        |this, _event, _window, cx| {
                            this.count += 1;
                            cx.notify();
                        },
                    )))
                    .child(button("Reset").on_click(cx.listener(
                        |this, _event, _window, cx| {
                            this.count = 0;
                            cx.notify();
                        },
                    ))),
            )
    }
}

fn main() {
    application().run(|cx: &mut App| {
        let bounds = Bounds::centered(None, size(px(300.), px(200.)), cx);
        cx.open_window(
            WindowOptions {
                window_bounds: Some(WindowBounds::Windowed(bounds)),
                ..Default::default()
            },
            |_, cx| cx.new(|_| Counter { count: 0 }),
        )
        .unwrap();
        cx.activate(true);
    });
}
```
</details>

## What happens when you click

1. The window tells GPUI that the mouse went down and up.
2. GPUI checks which element is under the pointer. It finds the Increment button, which has a click listener, so it calls the listener.
3. Your closure runs, adds one to `count` and calls `cx.notify()`.
4. GPUI sees the notification and calls `render` again. The whole element tree is rebuilt from the new `count`, and the window shows the new number.

## Try it yourself

- Add a `step: i32` field to `Counter` and a button that doubles it.
- Make the Decrement button look faded when `count` is `0`. Hint: `.when(condition, |this| this.opacity(0.5))`.
- Change the number's color to red when `count` is negative.

## Next steps

- [Tutorial: Build a todo list](/tutorials/todo-list/) uses these ideas to show a list of items.
- [Events and interaction](/guides/events-and-interaction/) covers clicks, hover, drag and more.
- [Actions and key bindings](/guides/actions-and-keybindings/) shows how to change the counter with keys like the up arrow.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/examples/testing.rs`
- `crates/gpui/src/app/context.rs` (`Context::listener`, `Context::notify`)
- `crates/gpui/src/elements/div.rs` (`on_click`, `hover`, `active`, `id`)
- `crates/gpui/src/util.rs` (`FluentBuilder::when`)
</details>
