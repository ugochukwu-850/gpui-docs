---
title: Lay out your UI
description: Arrange elements in rows, columns and grids, center them, make them grow or scroll, and float popovers above everything else.
sidebar:
  order: 3
  label: Layout
---

Layout is how you decide where elements go and how big they are. GPUI uses the same ideas as CSS flexbox and CSS grid, so if you have written web layouts, most of this will feel familiar.

## What you'll learn

- How to put elements in a row or a column
- How to center things and space them out
- How to make one element fill the leftover space
- How to build a grid, pin an element in a corner and scroll a long list
- How to show a popover above everything else
- Where GPUI layout differs from CSS

## A starting layout

This is a typical app shell: a sidebar on the left and a content area that fills the rest.

```rust
use gpui::{div, prelude::*, px, rgb};

div()
    .flex()                       // lay children out with flexbox
    .size_full()                  // fill the whole window
    .child(
        div()
            .w(px(200.))          // sidebar: a fixed width
            .bg(rgb(0x313244))
            .p_4()
            .child("Sidebar"),
    )
    .child(
        div()
            .flex_1()             // content: take all the remaining width
            .p_4()
            .child("Content"),
    )
```

You would see a 200 pixel wide dark column on the left and a wide content area next to it. We will go through each idea below.

## Rows and columns

A plain `div()` stacks its children from top to bottom and does not use flexbox. Call `.flex()` to turn on flexbox. Children then sit in a **row** by default. Add `.flex_col()` for a **column**.

```rust
// A row: children sit side by side
div().flex().child("A").child("B").child("C")

// A column: children stack top to bottom
div().flex().flex_col().child("A").child("B").child("C")
```

:::caution[Common mistake]
`.flex_col()`, `.items_center()`, `.justify_center()` and `.gap_2()` only do something inside a flex container. If they seem to be ignored, you probably forgot `.flex()`.
:::

## Space and alignment

Use `gap` for the space between children, and `items_*` and `justify_*` to align them:

```rust
div()
    .flex()
    .gap_2()               // 8 pixels between children
    .items_center()        // line up children across the row (top to bottom)
    .justify_between()     // push the first child left and the last child right
    .child("Title")
    .child("Menu")
```

Which is which? `justify_*` works along the direction of the flex (left to right in a row). `items_*` works across it. This is the same as `justify-content` and `align-items` in CSS.

| Method | What it does |
| --- | --- |
| `justify_start()` / `justify_end()` | Pack children at the start or end |
| `justify_center()` | Center children |
| `justify_between()` | Equal space between children, none at the edges |
| `justify_around()` / `justify_evenly()` | Equal space around or between all children |
| `items_start()` / `items_end()` | Align to the top/bottom of a row |
| `items_center()` | Center across the row |
| `items_stretch()` | Stretch to fill (the default) |

### Center something in the window

```rust
div()
    .size_full()
    .flex()
    .justify_center()
    .items_center()
    .child("I am in the middle")
```

## Growing and shrinking

Flex children can share the leftover room.

```rust
div()
    .flex()
    .child(div().flex_none().child("Fixed"))     // never changes size
    .child(div().flex_1().child("Fills the rest")) // takes the free space
```

- `.flex_1()` makes a child grow to fill the free space (and shrink if there is too little).
- `.flex_none()` stops a child from growing or shrinking.
- `.flex_wrap()` lets children move to the next line when they run out of room.

## Grid

For a table-like layout, use `.grid()`, say how many columns and rows you want, and let children span several cells. This is a classic page layout (header, sidebar, content, footer), adapted from `crates/gpui/examples/grid_layout.rs`. The variables `header`, `sidebar`, `content` and `footer` stand for elements you built earlier:

```rust
div()
    .grid()
    .grid_cols(5)                          // 5 equal columns
    .grid_rows(5)                          // 5 equal rows
    .gap_1()
    .size_full()
    .child(header.row_span(1).col_span_full())   // full-width header
    .child(sidebar.col_span(1).row_span(3))
    .child(content.col_span(3).row_span(3))
    .child(footer.row_span(1).col_span_full())   // full-width footer
```

`col_span(n)` and `row_span(n)` make a child cover `n` cells. `col_span_full()` covers the whole row.

GPUI grids only support "N equal columns". There is no `grid-template-columns: 200px 1fr`. For a layout like that, nest flex containers, as in the sidebar example at the top.

## Size things

```rust
div().w(px(240.)).h_full().max_w(px(640.))
div().size_full()        // as big as the parent
```

Percent sizes (`w_full()`, `w_1_2()`, `relative(0.5)`) are fractions of the parent. They need a parent with a known size. If the parent has no size, the percentage has nothing to measure. A reliable pattern is `.size_full()` on every element from the window root down.

The window's root element always fills the window.

## Pin an element with absolute positioning

`.absolute()` takes an element out of the normal flow. Then place it with `top_*`, `left_*`, `right_*`, `bottom_*` or `inset_*`. Put `.relative()` on the parent so it is clear which box the child is placed in.

```rust
div()
    .relative()
    .size_64()
    .child("Main content")
    // A red badge in the top-right corner
    .child(div().absolute().top_2().right_2().size_4().bg(gpui::red()))
    // A dark overlay covering the whole parent
    .child(div().absolute().inset_0().bg(gpui::black().opacity(0.4)))
```

An absolute child takes no space in its parent. It draws on top of siblings that came before it, but under siblings that come after it (see "How is this different from CSS?" below).

## Scroll a long area

Add `.overflow_y_scroll()` to make an element scroll with the mouse wheel or trackpad. It needs an `.id(...)`, because the scroll position has to be remembered between frames.

```rust
div()
    .id("messages")              // required for scrolling
    .h(px(300.))                 // scrolling needs a limited height
    .overflow_y_scroll()
    .children((0..100).map(|n| div().child(format!("Message {n}"))))
```

Other helpers: `overflow_x_scroll()`, `overflow_scroll()` (both directions) and `overflow_hidden()` (clip without scrolling).

### My scroll area grows instead of scrolling

This happens inside a flex column. A flex child refuses to be smaller than its content unless it can scroll or clip. Mark the scrolling child with `.overflow_y_scroll()` (or add `.min_h_0()`) and it will shrink:

```rust
div().size_full().flex().flex_col()
    .child(div().h_8().flex_none().child("Header"))
    .child(
        div()
            .id("body")
            .flex_1()               // fill the leftover height
            .overflow_y_scroll()    // and scroll instead of growing
            .child(long_content),
    )
```

For lists with thousands of rows, do not put every row in a scrolling `div`. Use a virtual list that draws only the visible rows. See [Long lists](/tutorials/long-lists/).

## Popovers and dropdowns

A popover has two jobs: draw on top of everything else, and stay inside the window. GPUI has one helper for each, and you use them together.

```rust
use gpui::{Anchor, anchored, deferred, px};

button.child(
    deferred(                                  // draw on top of everything
        anchored()                             // keep inside the window
            .anchor(Anchor::TopLeft)           // which corner of the popover touches the anchor point
            .snap_to_window_with_margin(px(8.))
            .child(popover_content),
    )
    .priority(1),
)
```

- `deferred(child)` leaves the child where you wrote it in the tree, but draws it after everything else, so it appears on top.
- `anchored()` places its child next to the anchor point and moves it if it would run off the window. By default the anchor point is where the element sits in its parent. `.position(point)` uses a point in the window instead, such as the mouse position for a context menu.
- `.priority(n)` decides which of two deferred elements is on top. Higher is on top.

To close the popover when the user clicks elsewhere, add `.on_mouse_down_out(...)` to the popover content (see [Handle clicks and mouse input](/guides/events-and-interaction/#click-outside-an-element)). Add `.occlude()` to the content too, so clicks inside it do not reach elements underneath.

A complete, runnable popover lives in `crates/gpui/examples/popover.rs`. `anchor.rs` shows all eight anchor corners.

## How is this different from CSS?

If you know CSS, these are the things to watch for:

- **`div` is block by default, not flex.** You must call `.flex()` or `.grid()` yourself.
- **There is no `z-index`.** Elements draw in tree order: later siblings cover earlier ones. To lift something above everything, use `deferred(...)`.
- **There is no inline layout.** Text is its own element: `.child("some text")` creates one. GPUI has no `display: inline` or `inline-block`.
- **Grid is simpler.** Only "N equal columns" plus spans and explicit line numbers.
- **Some CSS features are missing:** `float`, `order`, `calc()`, CSS variables, `justify-items` and `justify-self`.
- **Lengths are typed.** Padding cannot be `auto`, and border widths and corner radii cannot be percentages.
- **Percentages are written `relative(0.5)`**, a fraction from 0 to 1, not `50%`.

GPUI computes layout with [Taffy](https://github.com/DioxusLabs/taffy), a Rust library that implements the CSS flexbox and grid rules. That is why flex behaves just like on the web.

## Common mistakes

- **Forgetting `.flex()`.** Then `items_center` and `gap_2` seem to do nothing.
- **`size_full()` inside a parent with no size.** Give the chain from the window root a definite size.
- **Scrolling does nothing.** The element needs an `.id(...)` and a limited height.
- **A long list pushes the layout taller.** Add `.overflow_y_scroll()` or `.min_h_0()` to the flexible child.
- **A popover is cut off or hidden behind later elements.** Wrap it in `deferred(anchored()...)`.
- **Clicking a popover also clicks the thing behind it.** Add `.occlude()` to the popover.

## Next steps

- [Style your UI](/guides/styling/) for colors, borders, shadows and text.
- [Handle clicks and mouse input](/guides/events-and-interaction/) to make your layout respond to the user.
- [Elements](/deep-dive/elements/) if you want to know how GPUI measures and places elements each frame.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/taffy.rs` (the layout engine bridge)
- `crates/gpui/src/style.rs` (`Style`, `Display`, `Overflow`, `Position`)
- `crates/gpui/src/styled.rs` (the flex, grid and position methods)
- `crates/gpui/src/elements/anchored.rs`, `deferred.rs`
- `crates/gpui/src/elements/div.rs` (scrolling)
- `crates/gpui/examples/grid_layout.rs`, `popover.rs`, `anchor.rs`, `scrollable.rs`
</details>
