---
title: Thinking in GPUI
description: The mental model behind every GPUI app, explained with one loop and a React comparison.
sidebar:
  order: 5
  label: Thinking in GPUI
---

Every GPUI app, from a counter to a code editor, runs on the same simple loop. Once you see it, the rest of the framework falls into place. This page explains the loop and the handful of words you need to talk about it.

**What you'll learn**

- The loop: data, render, draw, event, change, notify.
- What a view, an element, `cx`, a window and an entity are.
- How GPUI compares to React.

## The loop

Here is the whole idea in one picture:

```text
  1. Your data (fields on a struct)
        │
        ▼
  2. render() describes the UI (a tree of div()s) <────┤
        │                                              │
        ▼                                              │
  3. GPUI draws it on screen                           │
        │                                              │
        ▼                                              │
  4. The user clicks or types                          │
        │                                              │
        ▼                                              │
  5. Your handler changes the data                     │
        │                                              │
        ▼                                              │
  6. cx.notify() tells GPUI "this changed" ────────────┘
```

In words:

1. You keep your app's data in a struct.
2. GPUI calls `render`, which reads that data and returns a description of the UI.
3. GPUI draws the description.
4. The user does something, like click a button.
5. Your event handler changes the data.
6. Your handler calls `cx.notify()`, and GPUI calls `render` again with the new data.

You never reach into the screen and change a label. You change the data, and the screen follows.

## The loop in code

This is the counter from the [counter tutorial](/tutorials/counter/), cut down to the parts of the loop:

```rust
struct Counter {
    count: i32,                       // 1. your data
}

impl Render for Counter {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        div()                         // 2. describe the UI from the data
            .id("counter")
            .child(format!("Count: {}", self.count))
            .on_click(cx.listener(|this, _event, _window, cx| {   // 4. user clicks
                this.count += 1;      // 5. change the data
                cx.notify();          // 6. tell GPUI it changed
            }))
    }
}
```

Step 3, drawing, is GPUI's job. You do not write any code for it.

:::caution[Common mistake]
Forgetting `cx.notify()`. GPUI does not watch your fields. It redraws only when you tell it the data changed. If you change a value and the screen stays the same, this is the first thing to check.
:::

## The words you need

### View

A **view** is a struct that knows how to draw itself. You make a struct a view by implementing the `Render` trait for it. A view usually holds the data it shows. It is GPUI's version of a React component that has state.

### Element

An **element** is one box in the description that `render` returns. `div()` makes the most common one. You style it with methods (`.flex()`, `.bg(...)`) and put things inside it with `.child(...)`. Elements are short-lived. They describe the screen for the current data and are rebuilt the next time `render` runs.

### `cx`: the toolbox GPUI hands you

Almost every GPUI function receives a `cx`, short for *context*. Think of it as the toolbox GPUI gives you for talking to the framework. Your data is yours, and `cx` is how you ask GPUI to do things: redraw (`cx.notify()`), create new state (`cx.new(...)`), turn a closure into an event handler (`cx.listener(...)`), open windows, and more.

The type of `cx` tells you where you are. In `main`, you get an `App`, the root toolbox that owns the whole application. Inside a view's methods, you get `Context<Self>`, a toolbox for that one view. It does everything `App` does and adds view-specific things like `cx.notify()`. You do not need to memorise the difference. If a method you need is missing, check that you have the right `cx`.

### Window

A **window** is one native OS window. GPUI passes a `&mut Window` to `render` and most handlers. It carries the window's own state, such as its size and which element has keyboard focus. Each window has one **root view** that fills it.

### Entity

When you call `cx.new(|_| HelloWorld { ... })`, GPUI takes ownership of your struct and gives you back a handle: an `Entity<HelloWorld>`. An **entity** is a piece of state that GPUI owns, and the handle is how you refer to it. You can copy the handle cheaply and hand it to other parts of your app. To read or change the data inside, you go through the handle together with a `cx`.

Views are entities, which is why a window's root view is an `Entity`. You can also make entities for plain data that several views share. You do not need entities for a first app. The [counter tutorial](/tutorials/counter/) uses none beyond the root view. When you are ready for shared state, read [Share state between views](/guides/state-and-views/) and then the [Entities](/deep-dive/entities/) deep dive.

## React vs GPUI

If you know React, this table maps the ideas. Where the match is not exact, the right column says so.

| React | GPUI | Notes |
| --- | --- | --- |
| Component with state | A struct that implements `Render` (a *view*) | State is plain fields on the struct. |
| Stateless component | A component built with `RenderOnce` | See [Views and render](/deep-dive/views-and-render/). |
| JSX | A chain of `div()` calls | It is Rust code, not markup. |
| CSS classes or Tailwind | Style methods like `.flex()`, `.gap_3()`, `.bg(...)` | The names follow Tailwind. |
| Props | Fields and constructor arguments | A parent passes data when it creates the child. |
| `useState` and a setter | A field, plus `cx.notify()` after you change it | There is no hook. You change the field directly. |
| `onClick={() => ...}` | `.on_click(cx.listener(\|this, event, window, cx\| ...))` | `cx.listener` gives your closure access to the view. |
| Re-render happens automatically after `setState` | You call `cx.notify()` | GPUI does not watch your data. |
| Shared state (context, stores) | An `Entity` handed to several views | See [Share state between views](/guides/state-and-views/). |

:::note[Coming from React?]
The biggest habit to change: in React you ask for a re-render by calling a setter. In GPUI you change the data yourself and then say so with `cx.notify()`. The upside is that your state is plain Rust data, with no special wrapper.
:::

## Next steps

- [Counter tutorial](/tutorials/counter/): build this loop for real, with buttons.
- [Share state between views](/guides/state-and-views/): split a UI into views that share data.
- [Views and render](/deep-dive/views-and-render/) and [Entities](/deep-dive/entities/): the details, once you want them.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/element.rs` (`Render`, `IntoElement`)
- `crates/gpui/src/app/context.rs` (`Context<T>`, `notify`, `listener`)
- `crates/gpui/src/app/entity_map.rs` (`Entity`)
- `crates/gpui/src/window.rs` (`Window`)
- `crates/gpui/src/_ownership_and_data_flow.rs`
</details>
