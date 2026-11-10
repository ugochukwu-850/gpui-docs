---
title: Hello World
description: Build and run your first GPUI window, with every line of the program explained.
sidebar:
  order: 4
---

In this page you will open your first GPUI window and learn what each line of the program does. The program is adapted from `crates/gpui/examples/hello_world.rs`, with the web and font-loading support code removed.

**What you'll learn**

- How a GPUI program starts, and what `Application` and `cx` are.
- How to open a window and choose its size.
- What a view is, and how `Render` and `div()` draw something.
- How to style and nest elements.

## What you'll see

A 500 by 500 window opens in the middle of your screen. It has a dark gray background, a thin blue border and a soft shadow. Inside, the text "Hello, World!" is centred in white, with a row of four small squares (red, green, blue and yellow, each with a dashed white outline) underneath it.

## The whole program

First, set up your project as described in [Installation](/start/installation/). Then replace `src/main.rs` with this and run `cargo run`:

<details>
<summary>Complete src/main.rs</summary>

```rust
use gpui::{
    App, Bounds, Context, SharedString, Window, WindowBounds, WindowOptions, div, prelude::*, px,
    rgb, size,
};
use gpui_platform::application;

struct HelloWorld {
    text: SharedString,
}

impl Render for HelloWorld {
    fn render(&mut self, _window: &mut Window, _cx: &mut Context<Self>) -> impl IntoElement {
        div()
            .flex()
            .flex_col()
            .gap_3()
            .bg(rgb(0x505050))
            .size(px(500.0))
            .justify_center()
            .items_center()
            .shadow_lg()
            .border_1()
            .border_color(rgb(0x0000ff))
            .text_xl()
            .text_color(rgb(0xffffff))
            .child(format!("Hello, {}!", self.text))
            .child(
                div()
                    .flex()
                    .gap_2()
                    .child(swatch(gpui::red()))
                    .child(swatch(gpui::green()))
                    .child(swatch(gpui::blue()))
                    .child(swatch(gpui::yellow())),
            )
    }
}

fn swatch(color: gpui::Hsla) -> impl IntoElement {
    div()
        .size_8()
        .bg(color)
        .border_1()
        .border_dashed()
        .rounded_md()
        .border_color(gpui::white())
}

fn main() {
    application().run(|cx: &mut App| {
        let bounds = Bounds::centered(None, size(px(500.), px(500.0)), cx);
        cx.open_window(
            WindowOptions {
                window_bounds: Some(WindowBounds::Windowed(bounds)),
                ..Default::default()
            },
            |_, cx| {
                cx.new(|_| HelloWorld {
                    text: "World".into(),
                })
            },
        )
        .unwrap();
        cx.activate(true);
    });
}
```

</details>

The only change from the upstream example is the `swatch` helper, which replaces six copies of the same `div` chain.

:::tip[Closing the window on macOS]
On macOS, GPUI's default is to keep the process alive after the last window closes. Quit with Ctrl-C in the terminal. See the `on_window_close_quit` example to quit when the window closes. (In the source, `QuitMode::Default` means `Explicit` on macOS and `LastWindowClosed` elsewhere.)
:::

## How it works

The program has four parts: imports, a view (your data plus a `render` method), a small helper, and `main`. We will go through them in that order, and then follow `main` from start to finish.

### Imports

```rust
use gpui::{ ..., prelude::*, ... };
use gpui_platform::application;
```

The first line brings in the types the program uses. The `prelude::*` part is important. It imports a group of traits that give elements their methods: `Styled` (for `.bg()` and friends), `ParentElement` (for `.child()`), and a few more. Without it, `div().flex()` fails to compile, because those methods live on traits. If you are not sure why, the [Rust refresher](/start/rust-refresher/#use-and-the-prelude) explains.

The second line imports `application()`, the function that starts your app.

### The view: a struct plus `Render`

```rust
struct HelloWorld {
    text: SharedString,
}
```

A **view** is a struct that knows how to draw itself. It is GPUI's version of a React component. This one holds a single piece of data, the name to greet. `SharedString` is GPUI's immutable string that is cheap to copy, which is why you see it here instead of `String`.

```rust
impl Render for HelloWorld {
    fn render(&mut self, _window: &mut Window, _cx: &mut Context<Self>) -> impl IntoElement {
```

`Render` is the trait that makes a struct a view. GPUI calls `render` whenever it needs to draw the view, and you return a description of the UI for the current data. Think of it as the body of a React component: it reads your state and returns what to show.

The two arguments are things GPUI hands you:

- `window` is the window this view lives in. You can use it for things like focus and window size. We do not need it here, so the name starts with an underscore.
- `cx` is the **context**, a toolbox for working with this view (for example, `cx.notify()` to request a redraw). Also unused here. [Thinking in GPUI](/start/thinking-in-gpui/) explains it.

The return type, `impl IntoElement`, means "anything GPUI can turn into something to draw". A `div()` qualifies.

### `div()`, styling and children

```rust
div()
    .flex()
    .flex_col()
    .gap_3()
    .bg(rgb(0x505050))
    .size(px(500.0))
    .justify_center()
    .items_center()
    ...
```

`div()` creates an **element**, a box you can style and put things in. It is the GPUI version of an HTML `<div>`.

Each method after it adds one style, and each returns the element so you can keep chaining. If you know Tailwind CSS, the names will feel familiar:

- Layout is flexbox. `.flex()` turns it on, `.flex_col()` stacks children vertically, and `.justify_center()` and `.items_center()` centre them.
- Spacing uses a scale. `.gap_3()` puts space between children.
- Colours come from helpers. `rgb(0x505050)` builds a colour from a hex number, and `gpui::red()` and friends are ready-made colours.
- `px(500.0)` is a length of 500 logical pixels.
- `.border_1()`, `.shadow_lg()` and `.text_xl()` add a border, a shadow and larger text.

Now the children:

```rust
.child(format!("Hello, {}!", self.text))
.child(
    div()
        .flex()
        .gap_2()
        .child(swatch(gpui::red()))
        .child(swatch(gpui::green()))
        ...
)
```

`.child(...)` adds one thing inside the box. A string is a valid child, so text is written as `.child("some text")`. Here we format a greeting from `self.text`. The second child is another `div()` holding the four swatches in a row.

Notice that `render` reads `self.text` directly. There is no binding layer. You read your struct and describe the UI.

### The `swatch` helper

```rust
fn swatch(color: gpui::Hsla) -> impl IntoElement {
    div()
        .size_8()
        .bg(color)
        .border_1()
        .border_dashed()
        .rounded_md()
        .border_color(gpui::white())
}
```

A plain function that returns an element works as a small reusable piece of UI. It takes a colour and returns a styled square. We call it four times instead of repeating the same chain.

### `main`: Application and `cx`

```rust
fn main() {
    application().run(|cx: &mut App| {
```

`application()` creates an `Application` for your operating system. It picks the right backend for you: Metal, DirectX, or Wayland and X11. Calling `.run(...)` starts the app. It does not return until the app quits, and it calls your closure once the app has finished launching.

Your closure receives `cx: &mut App`. `App` is the root context, which is the part of GPUI that owns every window, every piece of state, and services like the clipboard. Anything you do at startup, such as opening windows, happens inside this closure.

### Choosing a size and position

```rust
let bounds = Bounds::centered(None, size(px(500.), px(500.0)), cx);
```

`Bounds` is a rectangle: a position and a size. `Bounds::centered` makes one of the size you ask for, centred on a display. `None` means "the primary display". It needs `cx` because it asks the app about your displays.

### Opening a window

```rust
cx.open_window(
    WindowOptions {
        window_bounds: Some(WindowBounds::Windowed(bounds)),
        ..Default::default()
    },
    |_, cx| {
        cx.new(|_| HelloWorld {
            text: "World".into(),
        })
    },
)
.unwrap();
```

`open_window` creates a **window** and takes two arguments:

1. **Options.** `WindowOptions` has many settings (title bar, focus, and so on). We set only the bounds, as a normal window (`WindowBounds::Windowed`), and `..Default::default()` fills in the rest.
2. **A function that builds the window's root view.** Every window has one root view, which fills the window. The function gets the new window and `cx`, and must return the view.

It returns a `Result`, because opening a window can fail (for example, if there is no display). The example calls `.unwrap()` to stop the program in that case. A real app might show an error instead.

### Creating the root view

```rust
cx.new(|_| HelloWorld { text: "World".into() })
```

`cx.new` takes a function that returns your struct. GPUI takes ownership of that struct and gives you back a handle to it, called an `Entity<HelloWorld>`. We will explain entities in [Thinking in GPUI](/start/thinking-in-gpui/). For now: GPUI holds your view's data, and the handle is how you refer to it. Because `HelloWorld` implements `Render`, the entity is a view and can be a window's root.

### Bringing the app to the front

```rust
cx.activate(true);
```

`activate` asks the operating system to make your app the active one. Passing `true` means "even if another app has focus right now", which is what you want when you launch from a terminal. Without it, the window can open behind other windows on some platforms.

## Try it

- Change `"World"` to your name and run it again.
- Change `rgb(0x505050)` to another hex colour.
- Add a second window with another `cx.open_window(...)` call.
- Give the window a title. `WindowOptions` has a `titlebar` field of type `Option<TitlebarOptions>`.

## Next steps

- [Thinking in GPUI](/start/thinking-in-gpui/): the mental model that makes every later page easier.
- [Counter tutorial](/tutorials/counter/): add state and a button to a view.
- [Styling guide](/guides/styling/): more on the Tailwind-style methods.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/examples/hello_world.rs`
- `crates/gpui/src/app.rs` (`Application::run`, `App::open_window`, `App::activate`, `QuitMode`)
- `crates/gpui/src/element.rs` (`Render`, `IntoElement`)
- `crates/gpui/src/prelude.rs`
- `crates/gpui/src/geometry.rs` (`Bounds::centered`)
- `crates/gpui/src/platform.rs` (`WindowOptions`)
- `crates/gpui_shared_string/gpui_shared_string.rs`
- `crates/gpui_platform/src/gpui_platform.rs` (`application`)
</details>
