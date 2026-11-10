---
title: Rust refresher
description: The handful of Rust ideas you will meet in almost every line of GPUI code, taught through GPUI snippets.
sidebar:
  order: 2
  label: Rust refresher
---

GPUI is a Rust library, so you will read and write Rust. This page covers only the parts of Rust that GPUI code leans on, each shown with a small snippet you will see again in the tutorials.

:::tip[This page is optional]
If you already write Rust comfortably, skip to [Installation](/start/installation/). You can always come back here when a line of GPUI code looks odd. For the full story on any topic, read [The Rust Programming Language](https://doc.rust-lang.org/book/).
:::

**What you'll learn**

- Structs and `impl` blocks, which hold your data and your methods.
- Traits, closures and `move`, which GPUI uses for views and event handlers.
- Why GPUI methods take `&mut self` and `&mut Context<Self>`.
- Small things that show up everywhere: `Option`, `impl IntoElement`, `use`, and `SharedString`.

## Structs and `impl`

A **struct** groups named fields. An `impl` block attaches methods to it.

```rust
struct Counter {
    count: i32,
}

impl Counter {
    fn reset(&mut self) {
        self.count = 0;
    }
}
```

*Why GPUI looks this way:* your app's data is a plain struct. There is no special state container. A GPUI view is a struct like this one with a `Render` implementation added.

You will also see `..Default::default()` at the end of a struct literal. It fills every field you did not write with its default value:

```rust
WindowOptions {
    window_bounds: Some(WindowBounds::Windowed(bounds)),
    ..Default::default()
}
```

*Why:* `WindowOptions` has many fields, and you usually care about one or two.

## Traits

A **trait** is a named set of methods that a type can promise to provide. It is like an interface in TypeScript. You write `impl Trait for Type` to make the promise.

```rust
impl Render for Counter {
    fn render(&mut self, _window: &mut Window, _cx: &mut Context<Self>) -> impl IntoElement {
        div().child(format!("Count: {}", self.count))
    }
}
```

*Why GPUI looks this way:* a view is any struct that implements `Render`. GPUI calls your `render` method whenever it needs to draw the view. You never call `render` yourself.

Traits also explain a common surprise. Methods like `.flex()` and `.child()` only exist when the right trait is in scope. That is why almost every GPUI file starts with `use gpui::prelude::*;` (see [`use` and the prelude](#use-and-the-prelude)).

## Method chaining (the builder pattern)

Many GPUI methods take `self` by value and return it, so you can chain calls one after another:

```rust
div()
    .flex()
    .gap_3()
    .bg(rgb(0x505050))
    .child("Hello")
```

*Why:* it reads like a list of CSS classes, and each call adds one property. The whole chain is one expression, which is what `render` returns. There are no semicolons between the calls, because it is one long statement.

## Closures and `move`

A **closure** is an inline function. The parameters go between `|pipes|`, and the body follows.

```rust
|this, _event, _window, cx| {
    this.count += 1;
    cx.notify();
}
```

*Why:* GPUI handles events by taking a closure ("run this when the user clicks"). Parameters you do not use start with an underscore, like `_event`, so the compiler does not warn about them.

A closure can use variables from the code around it. This is called *capturing*. By default it borrows them. The `move` keyword makes the closure take ownership instead, which you need when the closure outlives the code that created it:

```rust
for id in 0..3 {
    div().id(id).on_click(move |_event, _window, _cx| {
        println!("clicked row {id}");
    });
}
```

*Why:* event handlers are stored and called later, after the loop has moved on. `move` gives each handler its own copy of `id`. You will also see `async move` for background tasks, covered in the [async guide](/guides/async-and-executors/).

## `&mut self` and `&mut Context<Self>`

Rust makes you say whether a function reads or changes something. `&self` means "read only". `&mut self` means "I may change this". A `&mut` reference to something is exclusive: nobody else can touch it at the same time.

```rust
impl Counter {
    fn increment(&mut self, cx: &mut Context<Self>) {
        self.count += 1; // change my data
        cx.notify();     // tell GPUI I changed
    }
}
```

*Why GPUI looks this way:* `&mut self` is your view's data. `cx: &mut Context<Self>` is the toolbox GPUI hands you for things that are not your data: telling GPUI to redraw, creating new state, registering handlers. `Self` here means "this very type" (`Counter`), so `Context<Self>` is "the toolbox for a `Counter`". Rust's exclusive borrow is what stops two pieces of code from changing the same state at once. [Thinking in GPUI](/start/thinking-in-gpui/) explains `cx` in more detail.

## `Option` and `Some`

Rust has no `null`. A value that might be missing is an `Option`: either `Some(value)` or `None`.

```rust
WindowOptions {
    window_bounds: Some(WindowBounds::Windowed(bounds)), // "yes, use these bounds"
    ..Default::default()                                  // other fields: None or default
}
```

*Why:* many window settings are optional. Writing `Some(...)` means you chose a value. Leaving a field alone keeps GPUI's default.

A related type is `Result`, which is either `Ok(value)` or `Err(error)`. When you see `.unwrap()` after `open_window(...)`, it means "stop the program if this failed". Hello World does that to stay short.

## `impl IntoElement`

A function can return "some type that implements this trait" without naming the type. That is `impl Trait` in return position:

```rust
fn swatch(color: gpui::Hsla) -> impl IntoElement {
    div().size_8().bg(color)
}
```

*Why:* the real return type of a long `div()` chain is a long, nested type nobody wants to write. `impl IntoElement` says "something GPUI can draw" and lets the compiler fill in the rest. `render` returns the same thing.

## `use` and the prelude

`use` brings names into scope so you can write `div` instead of `gpui::div`.

```rust
use gpui::{App, Context, Window, div, prelude::*, px, rgb};
```

The `prelude::*` part is a glob import: it pulls in a bundle of the traits GPUI code needs everywhere (`Render`, `IntoElement`, `Styled`, `ParentElement`, and more).

*Why:* without those traits in scope, `div().flex()` fails with "no method named `flex`". If you see that error, check that `prelude::*` is imported first.

## `SharedString` and `String`

A `String` owns its text, and cloning it copies every byte. GPUI has its own `SharedString`: an immutable string that is cheap to clone.

```rust
struct HelloWorld {
    text: SharedString,
}

// "World" is a &str; .into() turns it into a SharedString.
let view = HelloWorld { text: "World".into() };
```

*Why:* GPUI clones text around a lot (into elements, into background tasks), so it uses a string type that makes that cheap. You can pass a `&'static str`, a `String` or a `SharedString` to `.child(...)` and it works. Use `SharedString` in your view's fields when the text is shown on screen and rarely edited. Use `String` when you build or edit text yourself.

## Next steps

- [Installation](/start/installation/): set up your machine and a project.
- [Hello World](/start/hello-world/): see all of these ideas in one real program.
- [The Rust Book](https://doc.rust-lang.org/book/): the full tour, especially the chapters on ownership, traits and closures.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/prelude.rs`
- `crates/gpui/src/element.rs` (`Render`, `IntoElement`)
- `crates/gpui/src/app/context.rs` (`Context<T>`)
- `crates/gpui_shared_string/gpui_shared_string.rs`
- `crates/gpui/src/platform.rs` (`WindowOptions`)
</details>
