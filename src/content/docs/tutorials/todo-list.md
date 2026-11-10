---
title: "Tutorial: Build a todo list"
description: Show a list of items, give each one a stable id, toggle items done and remove them.
sidebar:
  order: 2
  label: Todo list
---

The [counter](/tutorials/counter/) kept one number. Real apps show collections of things. In this tutorial you will build a todo list that draws a `Vec` of items, lets you tick them off, and lets you remove them.

## What you'll build

A 420 by 520 window with a dark background and:

- a **Todo** heading, with a count such as "1 of 3 done" on the right
- two buttons: **Add task** and **Clear completed**
- a list of tasks. Each row has a small checkbox, the task title, and a red **Remove** button.
- done tasks with a filled checkbox and struck-through gray text
- a list that scrolls with the mouse wheel when it gets taller than the window

To keep the focus on lists, **Add task** creates titles like "Task 3" instead of reading text you type. Text entry is a topic of its own, covered in the [text input tutorial](/tutorials/text-input/).

## What you'll learn

- How to draw every item of a `Vec` with `.children(...)`
- Why each item needs its own stable id
- How to style something only when a condition is true, with `.when(...)`
- How to make a container scroll

## Before you start

You should have finished the [counter tutorial](/tutorials/counter/). The project setup is the same. As before, the pieces below are excerpts, and the complete file is at the end of the page.

## Step 1: Describe your data

Start with the data. Each todo has a title and a done flag. It also has an `id`, which we explain in a moment.

```rust
struct TodoItem {
    id: u64,
    title: SharedString,
    done: bool,
}

struct TodoList {
    items: Vec<TodoItem>,
    next_id: u64,
}
```

`SharedString` is GPUI's cheap-to-copy string type. Cloning one does not copy the text, so it is a good fit for titles that you draw every frame.

`TodoList` is our view. It holds the list of items and `next_id`, a counter we use to give each new item a fresh id.

Why not use an item's position in the `Vec` as its identity? Because positions shift when you remove something. A click handler that remembered "item number 2" could end up acting on a different item by the time it runs. A number that never changes, like `id`, always points at the right item.

## Step 2: Add and remove items

Next, give the view some starting data and a method to add an item.

```rust
impl TodoList {
    fn new() -> Self {
        let titles = ["Read the GPUI docs", "Build a counter", "Build a todo list"];
        let items = titles
            .into_iter()
            .enumerate()
            .map(|(index, title)| TodoItem {
                id: index as u64,
                title: title.into(),
                done: index == 0,
            })
            .collect();
        Self {
            items,
            next_id: titles.len() as u64,
        }
    }

    fn add_item(&mut self, cx: &mut Context<Self>) {
        let id = self.next_id;
        self.next_id += 1;
        self.items.push(TodoItem {
            id,
            title: format!("Task {id}").into(),
            done: false,
        });
        cx.notify();
    }
}
```

`new` creates three tasks, with the first one already done. `add_item` takes the next id, adds a new item and calls `cx.notify()`. As in the counter, `notify` tells GPUI to redraw.

## Step 3: Draw the list

Now draw the items. `.children(...)` accepts any iterator of things that can become elements, so you can map your `Vec` straight into rows. Here is the list container, with the row contents left out for now:

```rust
div()
    .id("items")
    .flex()
    .flex_col()
    .gap_1()
    .flex_1()
    .overflow_y_scroll()
    .when(self.items.is_empty(), |list| list.child("Nothing to do."))
    .children(self.items.iter().map(|item| {
        let id = item.id;
        div()
            .id(("todo", id))
            // ... the rest of the row
```

Notice that `render` walks `self.items` each time it runs. You do not compare the old list to the new one or patch anything. Change the data, call `cx.notify()`, and GPUI draws what the data says.

Three details in this snippet:

- `.when(condition, |el| ...)` applies the closure only if the condition is true. Here it shows "Nothing to do." when the list is empty. It keeps the chain of calls unbroken, which is neater than building the element in a mutable variable.
- `.overflow_y_scroll()` makes the container scroll vertically. It needs an id (`"items"`), because GPUI has to remember the scroll position between frames. It also needs a bounded height, which `flex_1()` gives it by filling the space left in the window.
- `.id(("todo", id))` gives each row its own id.

### Why every row needs an id

An id is how GPUI recognises "the same element as last frame", so it can keep that element's hover state, click state or scroll position. Siblings must have different ids. An id can be a string, a number, or a pair such as `("todo", id)`. The pair gives you a readable name plus a per-item number.

If ids are unstable (for example, taken from the row's position in a list that can reorder), GPUI can attach one item's hover or scroll state to a different item.

## Step 4: Make rows interactive

Each row has two parts: a toggle area (checkbox plus title) and a **Remove** button. We make them two separate, side-by-side clickable elements.

Why not make the whole row clickable and put the Remove button inside it? Because a click on the inner button is also a click inside the outer row. Both handlers would run, and the row would toggle as it was removed. Keeping the two targets as siblings avoids the problem. (If you do need nested clickable elements, call `cx.stop_propagation()` in the inner handler.)

Here is the toggle area:

```rust
div()
    .id(("toggle", id))
    .flex()
    .items_center()
    .gap_2()
    .flex_1()
    .cursor_pointer()
    .child(
        div()
            .size_4()
            .rounded_sm()
            .border_1()
            .border_color(rgb(0x89b4fa))
            .when(item.done, |checkbox| {
                checkbox.bg(rgb(0x89b4fa))
            }),
    )
    .child(div().child(item.title.clone()).when(
        item.done,
        |title| title.line_through().text_color(rgb(0x6c7086)),
    ))
    .on_click(cx.listener(move |this, _event, _window, cx| {
        if let Some(item) =
            this.items.iter_mut().find(|item| item.id == id)
        {
            item.done = !item.done;
        }
        cx.notify();
    })),
```

Read it from the top:

- The small `div` with `size_4()` is the checkbox. It is a bordered square. The `.when(item.done, ...)` call fills it in when the item is done.
- The title gets a line through it and a gray color, again with `.when(item.done, ...)`.
- The click handler finds the item by `id`, flips `done`, and calls `cx.notify()`.

The **Remove** button follows the same pattern:

```rust
div()
    .id(("remove", id))
    .px_2()
    .rounded_md()
    .cursor_pointer()
    .text_color(rgb(0xf38ba8))
    .hover(|style| style.bg(rgb(0x45475a)))
    .active(|style| style.bg(rgb(0x585b70)))
    .child("Remove")
    .on_click(cx.listener(move |this, _event, _window, cx| {
        this.items.retain(|item| item.id != id);
        cx.notify();
    })),
```

`retain` keeps every item except the one with this id. Because it is looked up by id, it removes the right one even if the list changed since the row was drawn.

### Why the closures say `move`

Both handlers are written `move |this, ...|`. The closure has to outlive the call to `render` that created it, so it cannot borrow `item` or any local variable. Instead, `move` copies the small `id` number into the closure. Inside the handler, you look the item up again in `this`, which is the current data at click time.

:::caution[Common mistake]
Capturing a reference to an item, or its index in the `Vec`, in a click handler. Capture a small copyable value such as the `id`, and find the item again inside the handler.
:::

## Step 5: The header and buttons

The heading and the two buttons are plain `div`s, much like the counter. Two things are worth noting:

```rust
let total = self.items.len();
let done_count = self.items.iter().filter(|item| item.done).count();
```

These two lines at the top of `render` compute the numbers for "1 of 3 done" fresh on every draw, so they are always correct. You never need to update a separate counter.

```rust
.child(button("clear", "Clear completed").on_click(cx.listener(
    |this, _event, _window, cx| {
        this.items.retain(|item| !item.done);
        cx.notify();
    },
)))
```

**Clear completed** uses `retain` again, this time keeping only the items that are not done.

## Put it together

Here is the full program. Run it with `cargo run`, add enough tasks to overflow the window, and scroll with the mouse wheel.

<details>
<summary>Complete src/main.rs</summary>

```rust title="src/main.rs"
use gpui::{
    App, Bounds, Context, Div, SharedString, Stateful, Window, WindowBounds, WindowOptions, div,
    prelude::*, px, rgb, size,
};
use gpui_platform::application;

struct TodoItem {
    id: u64,
    title: SharedString,
    done: bool,
}

struct TodoList {
    items: Vec<TodoItem>,
    next_id: u64,
}

impl TodoList {
    fn new() -> Self {
        let titles = ["Read the GPUI docs", "Build a counter", "Build a todo list"];
        let items = titles
            .into_iter()
            .enumerate()
            .map(|(index, title)| TodoItem {
                id: index as u64,
                title: title.into(),
                done: index == 0,
            })
            .collect();
        Self {
            items,
            next_id: titles.len() as u64,
        }
    }

    fn add_item(&mut self, cx: &mut Context<Self>) {
        let id = self.next_id;
        self.next_id += 1;
        self.items.push(TodoItem {
            id,
            title: format!("Task {id}").into(),
            done: false,
        });
        cx.notify();
    }
}

fn button(id: &'static str, label: &'static str) -> Stateful<Div> {
    div()
        .id(id)
        .px_3()
        .py_1()
        .rounded_md()
        .bg(rgb(0x313244))
        .cursor_pointer()
        .hover(|style| style.bg(rgb(0x45475a)))
        .active(|style| style.bg(rgb(0x585b70)))
        .child(label)
}

impl Render for TodoList {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        let total = self.items.len();
        let done_count = self.items.iter().filter(|item| item.done).count();

        div()
            .flex()
            .flex_col()
            .gap_3()
            .size_full()
            .p_4()
            .bg(rgb(0x1e1e2e))
            .text_color(rgb(0xcdd6f4))
            .child(
                div()
                    .flex()
                    .items_center()
                    .justify_between()
                    .child(div().text_xl().child("Todo"))
                    .child(
                        div()
                            .text_sm()
                            .text_color(rgb(0x9399b2))
                            .child(format!("{done_count} of {total} done")),
                    ),
            )
            .child(
                div()
                    .flex()
                    .gap_2()
                    .child(
                        button("add", "Add task")
                            .on_click(cx.listener(|this, _event, _window, cx| this.add_item(cx))),
                    )
                    .child(button("clear", "Clear completed").on_click(cx.listener(
                        |this, _event, _window, cx| {
                            this.items.retain(|item| !item.done);
                            cx.notify();
                        },
                    ))),
            )
            .child(
                div()
                    .id("items")
                    .flex()
                    .flex_col()
                    .gap_1()
                    .flex_1()
                    .overflow_y_scroll()
                    .when(self.items.is_empty(), |list| list.child("Nothing to do."))
                    .children(self.items.iter().map(|item| {
                        let id = item.id;
                        div()
                            .id(("todo", id))
                            .flex()
                            .items_center()
                            .gap_2()
                            .px_3()
                            .py_2()
                            .rounded_md()
                            .bg(rgb(0x313244))
                            .hover(|style| style.bg(rgb(0x3b3d52)))
                            .child(
                                div()
                                    .id(("toggle", id))
                                    .flex()
                                    .items_center()
                                    .gap_2()
                                    .flex_1()
                                    .cursor_pointer()
                                    .child(
                                        div()
                                            .size_4()
                                            .rounded_sm()
                                            .border_1()
                                            .border_color(rgb(0x89b4fa))
                                            .when(item.done, |checkbox| {
                                                checkbox.bg(rgb(0x89b4fa))
                                            }),
                                    )
                                    .child(div().child(item.title.clone()).when(
                                        item.done,
                                        |title| title.line_through().text_color(rgb(0x6c7086)),
                                    ))
                                    .on_click(cx.listener(move |this, _event, _window, cx| {
                                        if let Some(item) =
                                            this.items.iter_mut().find(|item| item.id == id)
                                        {
                                            item.done = !item.done;
                                        }
                                        cx.notify();
                                    })),
                            )
                            .child(
                                div()
                                    .id(("remove", id))
                                    .px_2()
                                    .rounded_md()
                                    .cursor_pointer()
                                    .text_color(rgb(0xf38ba8))
                                    .hover(|style| style.bg(rgb(0x45475a)))
                                    .active(|style| style.bg(rgb(0x585b70)))
                                    .child("Remove")
                                    .on_click(cx.listener(move |this, _event, _window, cx| {
                                        this.items.retain(|item| item.id != id);
                                        cx.notify();
                                    })),
                            )
                    })),
            )
    }
}

fn main() {
    application().run(|cx: &mut App| {
        let bounds = Bounds::centered(None, size(px(420.), px(520.)), cx);
        cx.open_window(
            WindowOptions {
                window_bounds: Some(WindowBounds::Windowed(bounds)),
                ..Default::default()
            },
            |_, cx| cx.new(|_| TodoList::new()),
        )
        .unwrap();
        cx.activate(true);
    });
}
```
</details>

## Try it yourself

- Add a filter (All, Active, Done) as a field on `TodoList`, and filter the items in `render` before `.children(...)`.
- Insert new items at the top of the list instead of the end.
- Save the list to disk when it changes, and load it in `TodoList::new`.

## Next steps

- [Tutorial: Long lists](/tutorials/long-lists/) shows how to handle lists with thousands of rows.
- [Tutorial: Text input](/tutorials/text-input/) builds the text field this todo list is missing.
- [Events and interaction](/guides/events-and-interaction/) explains ids, clicks and hover in detail.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/examples/tab_stop.rs` (ids, `when`, `hover`, `on_click` with `cx.listener`)
- `crates/gpui/src/element.rs` (`ParentElement::children`)
- `crates/gpui/src/elements/div.rs` (`id`, `hover`, `active`, `overflow_y_scroll`, `on_click`)
- `crates/gpui/src/window.rs` (`ElementId` conversions)
- `crates/gpui/src/util.rs` (`when`, `when_some`)
- `crates/gpui/src/styled.rs` (`line_through`)
</details>
