---
title: "Tutorial: Build long lists"
description: Show 100,000 rows smoothly with uniform_list, and a chat-style list of variable-height messages with list.
sidebar:
  order: 3
  label: Long lists
---

If you draw 100,000 rows as ordinary children, GPUI has to build, measure and paint every one of them. This tutorial shows the fix, called *virtualization*, and uses it to build two scrolling lists side by side.

*Virtualization* means the list only creates the rows that are on screen right now. When you scroll, it builds the rows that come into view and forgets the ones that left.

## What you'll build

An 800 by 560 window with a white background, split into two halves.

On the left, a column 320 pixels wide:

- three buttons: **Top**, **Row 50,000** and **Bottom**, which jump around the list
- a list of 100,000 rows ("Row 1", "Row 2", ...). Hovering a row highlights it, and clicking selects it in light blue.

On the right:

- a header showing "20 messages" and an **Add message** button
- a chat-style list of messages with different lengths and heights. It starts scrolled to the bottom and stays there as you add messages, unless you scroll up.

## What you'll learn

- When to use `uniform_list` and when to use `list`
- How `cx.processor` gives your row-building code access to the view
- How to scroll a list from code with a scroll handle
- How to tell a `list` when its data changed

## Which list should I use?

GPUI has two virtualized lists. The deciding question is whether all rows have the same height.

| | `uniform_list` | `list` |
| --- | --- | --- |
| Row heights | All identical | May differ |
| How it positions rows | Measures the first row, then does arithmetic | Measures rows as they are drawn and remembers the heights |
| State you keep | `UniformListScrollHandle` (optional) | `ListState` (required) |
| Typical use | Tables, file trees, pickers | Chat logs, feeds, documents |

We use both. Each step shows an excerpt of the final program. The complete file is at the end.

## Step 1: The state

The view stores what both lists need.

```rust
const ROW_COUNT: usize = 100_000;

struct LongLists {
    selected_row: Option<usize>,
    scroll_handle: UniformListScrollHandle,
    messages: Vec<SharedString>,
    message_state: ListState,
}
```

- `selected_row` is the row you clicked, if any.
- `scroll_handle` lets the code scroll the left list.
- `messages` is the chat data, and `message_state` is what the right list uses to remember its layout.

There is no `Vec` of 100,000 rows. The left list only needs a count, and it draws row text on demand.

## Step 2: A list of identical rows

Here is the left list, built with `uniform_list`:

```rust
uniform_list(
    "rows",
    ROW_COUNT,
    cx.processor(|this, range: Range<usize>, _window, cx| {
        range
            .map(|ix| {
                div()
                    .id(ix)
                    .px_2()
                    .py_1()
                    .cursor_pointer()
                    .when(this.selected_row == Some(ix), |row| {
                        row.bg(rgb(0xcfe3ff))
                    })
                    .hover(|style| style.bg(rgb(0xeeeeee)))
                    .on_click(cx.listener(
                        move |this, _event, _window, cx| {
                            this.selected_row = Some(ix);
                            cx.notify();
                        },
                    ))
                    .child(format!("Row {}", ix + 1))
            })
            .collect::<Vec<_>>()
    }),
)
.track_scroll(&self.scroll_handle)
.flex_1(),
```

`uniform_list` takes three arguments:

1. An element id, `"rows"`.
2. The **total** number of rows, `ROW_COUNT`.
3. A function that receives a range, such as `12..30`, and returns elements for only those rows.

When you scroll, GPUI calls your function again with the new range. It can run many times per second, so keep it light. Notice that it does not loop over 100,000 rows. It loops over `range`, which holds only a screenful.

The rows are ordinary `div`s. Each has an id (`.id(ix)`), because it handles clicks and hover. A plain number works as an id.

### Why `cx.processor`

The function `uniform_list` wants has no access to your view. `cx.processor(...)` fixes that, in the same way `cx.listener` does for clicks. It wraps your closure so the first argument, `this`, is your `LongLists`. That is how the closure can read `this.selected_row`, and how it can call `cx.listener(...)` to attach a click handler to each row.

### Rules for `uniform_list`

- **Give it a bounded height.** Here `.flex_1()` makes it fill the space under the buttons. Without a height limit, the list grows to fit all 100,000 rows, and virtualization does nothing.
- **Every row must have the same height.** The list measures only the first row and assumes the others match. If your rows vary, use `list` instead.
- **Give clickable rows an id.** As in the [todo list](/tutorials/todo-list/), ids let GPUI keep per-row state.

## Step 3: Scroll from code

The three buttons above the list move it. To do this you keep a `UniformListScrollHandle` in the view and attach it to the list with `.track_scroll(&self.scroll_handle)` (you saw that line above). Then a button can call methods on the handle:

```rust
.child(button("middle", "Row 50,000").on_click(cx.listener(
    |this, _event, _window, cx| {
        this.scroll_handle
            .scroll_to_item(ROW_COUNT / 2, ScrollStrategy::Center);
        cx.notify();
    },
)))
```

`scroll_to_item(index, strategy)` scrolls so that row `index` is visible. The strategy picks where it lands: `Top`, `Center`, `Bottom`, or `Nearest`. The **Top** button uses `ScrollStrategy::Top`, and the **Bottom** button calls `scroll_to_bottom()`.

The handle stores your request, and the list carries it out the next time it lays itself out. That is why the handler calls `cx.notify()`: it makes sure a new frame happens. When you click **Row 50,000**, you will see the list jump to the middle, with row 50,000 centered.

## Step 4: A list with different heights

The right-hand list holds chat messages. Some are one line and some are four, so `uniform_list` would not work. We use `list`:

```rust
list(
    self.message_state.clone(),
    cx.processor(|this, index: usize, _window, _cx| {
        let text = this
            .messages
            .get(index)
            .cloned()
            .unwrap_or_else(|| "".into());
        div()
            .w_full()
            .px_3()
            .py_2()
            .border_b_1()
            .border_color(rgb(0xeeeeee))
            .child(text)
            .into_any_element()
    }),
)
.flex_1(),
```

`list` takes a `ListState` and a function from a row index to one element. The function builds one row at a time, and it must end with `.into_any_element()`.

The `ListState` is stored in your view and cloned into the element on each draw (`self.message_state.clone()`). Cloning is cheap. The state remembers each row's measured height, so it has to live longer than a single frame. Here is how it is created:

```rust
let messages: Vec<SharedString> = (0..20).map(Self::message_text).collect();
let message_state = ListState::new(messages.len(), ListAlignment::Bottom, px(200.));
message_state.set_follow_mode(FollowMode::Tail);
```

`ListState::new(count, alignment, overdraw)` takes three arguments:

- `count`: how many rows there are now.
- `alignment`: `ListAlignment::Top` behaves like a normal list. `ListAlignment::Bottom` anchors to the bottom, like a chat log, so it starts scrolled to the end.
- `overdraw`: extra space above and below the window that is drawn and measured ahead of time, so rows do not pop in while you scroll.

The last line turns on `FollowMode::Tail`. While you are at the bottom, new messages scroll into view automatically. If you scroll up, the list stops following. It resumes when you come back to the bottom.

## Step 5: Tell the list when data changes

Because a `list` remembers row heights, it has to know when your data changes. Here is the method behind the **Add message** button:

```rust
fn add_message(&mut self, cx: &mut Context<Self>) {
    let index = self.messages.len();
    self.messages.push(Self::message_text(index));
    self.message_state.splice(index..index, 1);
    cx.notify();
}
```

The `splice` call is the important one. `splice(old_range, count)` means "the rows in `old_range` were replaced by `count` new rows". Adding one row at the end is `index..index` with `1`. Removing the row at `i` would be `i..i + 1` with `0`.

When you click **Add message**, you will see the count in the header go up and a new message appear at the bottom. Scroll up and add another, and the list stays where you put it.

:::caution[Common mistake]
Changing the data without calling `splice` (or `reset`). The saved heights no longer match the data, so positions and the scrollbar drift. Call `message_state.reset(count)` to throw everything away, or `remeasure()` to keep the rows but measure them again.
:::

## Put it together

The remaining code is layout: two columns inside one `div`, a `button` helper like the one in earlier tutorials, and `main`. Here is the complete program.

<details>
<summary>Complete src/main.rs</summary>

```rust title="src/main.rs"
use std::ops::Range;

use gpui::{
    App, Bounds, Context, Div, FollowMode, ListAlignment, ListState, ScrollStrategy, SharedString,
    Stateful, UniformListScrollHandle, Window, WindowBounds, WindowOptions, div, list, prelude::*,
    px, rgb, size, uniform_list,
};
use gpui_platform::application;

const ROW_COUNT: usize = 100_000;

struct LongLists {
    selected_row: Option<usize>,
    scroll_handle: UniformListScrollHandle,
    messages: Vec<SharedString>,
    message_state: ListState,
}

impl LongLists {
    fn new() -> Self {
        let messages: Vec<SharedString> = (0..20).map(Self::message_text).collect();
        let message_state = ListState::new(messages.len(), ListAlignment::Bottom, px(200.));
        message_state.set_follow_mode(FollowMode::Tail);
        Self {
            selected_row: None,
            scroll_handle: UniformListScrollHandle::new(),
            messages,
            message_state,
        }
    }

    fn message_text(index: usize) -> SharedString {
        let sentence = "The quick brown fox jumps over the lazy dog. ";
        format!("Message {index}: {}", sentence.repeat(1 + index % 4)).into()
    }

    fn add_message(&mut self, cx: &mut Context<Self>) {
        let index = self.messages.len();
        self.messages.push(Self::message_text(index));
        self.message_state.splice(index..index, 1);
        cx.notify();
    }
}

fn button(id: &'static str, label: &'static str) -> Stateful<Div> {
    div()
        .id(id)
        .px_3()
        .py_1()
        .rounded_md()
        .bg(rgb(0xe4e4ea))
        .cursor_pointer()
        .hover(|style| style.bg(rgb(0xd4d4dc)))
        .active(|style| style.bg(rgb(0xc4c4ce)))
        .child(label)
}

impl Render for LongLists {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        div()
            .flex()
            .size_full()
            .bg(rgb(0xffffff))
            .text_color(rgb(0x1e1e2e))
            .child(
                div()
                    .flex()
                    .flex_col()
                    .w(px(320.))
                    .h_full()
                    .border_r_1()
                    .border_color(rgb(0xdddddd))
                    .child(
                        div()
                            .flex()
                            .gap_2()
                            .p_2()
                            .child(button("top", "Top").on_click(cx.listener(
                                |this, _event, _window, cx| {
                                    this.scroll_handle.scroll_to_item(0, ScrollStrategy::Top);
                                    cx.notify();
                                },
                            )))
                            .child(button("middle", "Row 50,000").on_click(cx.listener(
                                |this, _event, _window, cx| {
                                    this.scroll_handle
                                        .scroll_to_item(ROW_COUNT / 2, ScrollStrategy::Center);
                                    cx.notify();
                                },
                            )))
                            .child(button("bottom", "Bottom").on_click(cx.listener(
                                |this, _event, _window, cx| {
                                    this.scroll_handle.scroll_to_bottom();
                                    cx.notify();
                                },
                            ))),
                    )
                    .child(
                        uniform_list(
                            "rows",
                            ROW_COUNT,
                            cx.processor(|this, range: Range<usize>, _window, cx| {
                                range
                                    .map(|ix| {
                                        div()
                                            .id(ix)
                                            .px_2()
                                            .py_1()
                                            .cursor_pointer()
                                            .when(this.selected_row == Some(ix), |row| {
                                                row.bg(rgb(0xcfe3ff))
                                            })
                                            .hover(|style| style.bg(rgb(0xeeeeee)))
                                            .on_click(cx.listener(
                                                move |this, _event, _window, cx| {
                                                    this.selected_row = Some(ix);
                                                    cx.notify();
                                                },
                                            ))
                                            .child(format!("Row {}", ix + 1))
                                    })
                                    .collect::<Vec<_>>()
                            }),
                        )
                        .track_scroll(&self.scroll_handle)
                        .flex_1(),
                    ),
            )
            .child(
                div()
                    .flex()
                    .flex_col()
                    .flex_1()
                    .h_full()
                    .child(
                        div()
                            .flex()
                            .items_center()
                            .justify_between()
                            .p_2()
                            .child(format!("{} messages", self.messages.len()))
                            .child(button("add", "Add message").on_click(cx.listener(
                                |this, _event, _window, cx| this.add_message(cx),
                            ))),
                    )
                    .child(
                        div().flex_1().flex().overflow_hidden().child(
                            list(
                                self.message_state.clone(),
                                cx.processor(|this, index: usize, _window, _cx| {
                                    let text = this
                                        .messages
                                        .get(index)
                                        .cloned()
                                        .unwrap_or_else(|| "".into());
                                    div()
                                        .w_full()
                                        .px_3()
                                        .py_2()
                                        .border_b_1()
                                        .border_color(rgb(0xeeeeee))
                                        .child(text)
                                        .into_any_element()
                                }),
                            )
                            .flex_1(),
                        ),
                    ),
            )
    }
}

fn main() {
    application().run(|cx: &mut App| {
        let bounds = Bounds::centered(None, size(px(800.), px(560.)), cx);
        cx.open_window(
            WindowOptions {
                window_bounds: Some(WindowBounds::Windowed(bounds)),
                ..Default::default()
            },
            |_, cx| cx.new(|_| LongLists::new()),
        )
        .unwrap();
        cx.activate(true);
    });
}
```
</details>

Run it with `cargo run`. Use the mouse wheel to move through 100,000 rows. Use the buttons to jump around, click **Add message** a few times, and scroll up in the right list to see that it does not pull you back down.

## Common mistakes

- **No height on the list.** A `uniform_list` in an unconstrained parent grows to fit all rows, which defeats virtualization. Constrain it with `h_full()`, `flex_1()` or a fixed height.
- **Different heights in a `uniform_list`.** Rows get misplaced or clipped. Use `list` instead.
- **Capturing a row index for data that can change.** If rows can be reordered or removed, capture a stable id and look the item up again in the click handler, as in the todo list.
- **Slow work in the row function.** It runs for every visible row each time the list draws. Prepare data ahead of time in your view. The `data_table` example shares its rows as `Rc<Quote>`, so building a row clones a pointer rather than the data.

## Try it yourself

- Add a **Remove last** button for the right list. Remember `splice`.
- Make the left list select a row on hover instead of on click.
- Read `crates/gpui/examples/data_table.rs`. It draws 10,000 rows by 24 columns with a `uniform_list` and a custom scrollbar.

## Next steps

- [Tutorial: Text input](/tutorials/text-input/) is the advanced tutorial: it builds a real text field.
- [Layout](/guides/layout/) explains the `flex` and size methods used to split the window.
- [Events and interaction](/guides/events-and-interaction/) covers scrolling and mouse events.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/examples/uniform_list.rs`
- `crates/gpui/examples/list_example.rs`
- `crates/gpui/examples/data_table.rs`
- `crates/gpui/src/elements/uniform_list.rs` (`uniform_list`, `UniformListScrollHandle`, `ScrollStrategy`)
- `crates/gpui/src/elements/list.rs` (`list`, `ListState`, `ListAlignment`, `FollowMode`)
- `crates/gpui/src/app/context.rs` (`Context::processor`, `Context::listener`)
</details>
