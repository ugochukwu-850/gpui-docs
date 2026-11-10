---
title: Style your UI
description: Give your GPUI elements colors, spacing, borders, shadows, text styles and hover effects by chaining method calls.
sidebar:
  order: 2
  label: Styling
---

GPUI has no stylesheet. You style an element by chaining method calls on it, and the method names are borrowed from [Tailwind CSS](https://tailwindcss.com/). If you have used Tailwind, you already know most of them. If you have not, this page teaches the ones you will use every day.

## What you'll learn

- How to style an element with chained methods
- How to set colors, sizes, spacing, borders, shadows and text
- How to change styles on hover and while pressed
- How to turn styles on and off with `.when(...)`
- Which GPUI method matches which CSS property

## A styled card

Here is a card. Read it top to bottom. Each line is one style.

```rust
use gpui::{FontWeight, div, prelude::*, px, rgb};

div()
    .flex()
    .flex_col()
    .gap_2()
    .w(px(320.))
    .p_4()
    .bg(rgb(0x1e1e2e))
    .text_color(rgb(0xcdd6f4))
    .border_1()
    .border_color(rgb(0x45475a))
    .rounded_lg()
    .shadow_lg()
    .child(
        div()
            .text_lg()
            .font_weight(FontWeight::SEMIBOLD)
            .child("Weekly report"),
    )
    .child(
        div()
            .text_sm()
            .text_color(rgb(0xa6adc8))
            .child("12 tasks done, 3 left."),
    )
```

You would see a dark, 320 pixel wide card with a thin gray border, rounded corners and a soft shadow. It has a bold title and a smaller, dimmer line under it.

Every method takes the element and gives it back, so you can chain as many as you like. Put this code inside a `render` function, as in [Hello World](/start/hello-world/).

:::caution[Common mistake]
Add `use gpui::prelude::*;` to every file that builds UI. It brings in the traits that hold the styling methods. Without it, the compiler says the methods are "not found".
:::

## Colors

Four helpers cover most needs:

```rust
use gpui::{hsla, rgb, rgba};

rgb(0x2563eb)               // like #2563eb
rgba(0x2563eb80)            // like #2563eb80 (the last two digits are opacity)
hsla(0.6, 0.8, 0.5, 1.0)    // hue, saturation, lightness, opacity
gpui::red()                 // named colors: red, green, blue, yellow, black, white
```

Use them with `.bg(color)` for the background, `.text_color(color)` for text and `.border_color(color)` for borders.

:::caution[Common mistake]
`hsla` takes the hue as a fraction from `0.0` to `1.0`, not degrees. For 210 degrees, write `210. / 360.`.
:::

To make a color see-through, call `.opacity(0.1)` on the color itself. This is handy for hover tints:

```rust
gpui::black().opacity(0.1)   // black at 10% strength
```

## Sizes and spacing

Sizes and spacing come from a scale. At the default settings, each step is 4 pixels, so `p_4()` is 16 pixels of padding and `w_8()` is 32 pixels wide. The scale runs through `0`, `0p5` (2px), `1`, `2`, `3`, `4`, `5`, `6`, `8`, `10`, `12`, `16` and on to `128`.

```rust
div().p_4()            // padding on all sides
div().px_4().py_2()    // padding left and right, then top and bottom
div().gap_2()          // space between children (in a flex container)
div().w_64().h_8()     // width and height from the scale
div().size_8()         // width and height together
div().w_full()         // 100% of the parent
div().size_full()      // 100% wide and 100% tall
```

When the scale is not enough, pass a length yourself:

```rust
div().w(px(320.))          // exactly 320 pixels
div().p(rems(0.75))        // 0.75 times the font size (rems)
div().h(relative(0.5))     // half of the parent
div().max_w(px(640.))      // at most 640 pixels wide
```

`px`, `rems` and `relative` all come from the `gpui` crate. Use `px` when you know the pixel size, `rems` when sizes should grow with the base font size, and `relative` for fractions of the parent.

## Borders and rounded corners

```rust
div()
    .border_1()                          // 1 pixel border on all sides
    .border_color(rgb(0x45475a))
    .rounded_md()                        // rounded corners
```

- Border widths: `border_1()`, `border_2()`, `border_4()` and so on. For one side, use `border_t_1()`, `border_b_1()`, `border_l_1()` or `border_r_1()`.
- Corner sizes: `rounded_sm()`, `rounded_md()`, `rounded_lg()`, `rounded_xl()` and `rounded_full()` for a pill or circle.
- One corner or side only: `rounded_t_lg()` (top corners) or `rounded_tl_lg()` (top-left corner).
- A custom size: `.rounded(px(6.))`.
- A dashed border: `.border_dashed()`.

Borders take up room inside the element, like CSS borders do. Your content is pushed inward by the border width.

## Shadows

```rust
div().shadow_md()       // a medium shadow
div().shadow_none()     // remove shadows
```

The presets run from small to large: `shadow_2xs`, `shadow_xs`, `shadow_sm`, `shadow_md`, `shadow_lg`, `shadow_xl`, `shadow_2xl`. Shadows follow rounded corners, so pair them with `rounded_*`. For a custom shadow, see `crates/gpui/examples/shadow.rs`.

## Text

Text styles set on an element also apply to everything inside it, like inherited properties in CSS. Set `text_color` once on the outer element and every child uses it.

```rust
div()
    .text_color(rgb(0xcdd6f4))            // color for all text inside
    .text_xl()                            // bigger text
    .font_weight(FontWeight::BOLD)        // bold
    .text_center()                        // center the text in its box
    .line_height(relative(1.5))
    .child("Hello")
```

Text sizes: `text_xs()`, `text_sm()`, `text_base()`, `text_lg()`, `text_xl()`, `text_2xl()`, `text_3xl()`. For an exact size, use `text_size(px(13.))`.

To cut off long text, use `.truncate()` (one line ending in `...`) or `.line_clamp(2)` (at most two lines).

For fonts and custom text drawing, see [Text and fonts](/guides/text-and-fonts/).

## Opacity

`div().opacity(0.5)` fades the element and everything inside it. To fade only a background, fade the color instead: `.bg(color.opacity(0.5))`.

## Hover and pressed styles

Use `.hover(...)` and `.active(...)` to change styles while the mouse is over an element or pressing it. Each takes a closure that receives a style and returns it with extra methods applied:

```rust
div()
    .id("save")                               // needed for .active(), see below
    .px_3()
    .py_1()
    .bg(rgb(0x2563eb))
    .rounded_md()
    .cursor_pointer()                         // show the hand cursor
    .hover(|style| style.bg(rgb(0x1d4ed8)))   // darker blue on hover
    .active(|style| style.opacity(0.8))       // slightly faded while pressed
    .child("Save")
```

Only the properties you set in the closure change. Everything else keeps its normal style, so you do not need to repeat the background, padding and so on.

`.hover(...)` works on any `div`. `.active(...)` needs `.id("some-name")` first. Mouse features that remember something between frames, like "is the button pressed?", need an id to attach that memory to. Read more in [Handle clicks and mouse input](/guides/events-and-interaction/#why-do-i-need-id).

### Show a child when the parent is hovered

Give the parent a name with `.group("row")`, then style the child with `.group_hover("row", |s| s.visible())`. A child that starts with `.invisible()` appears when the user hovers anywhere on the row.

Styles for keyboard focus work the same way. See [Manage keyboard focus](/guides/focus/#show-a-focus-ring).

## Change styles with conditions

Sometimes a style depends on your data. `.when(condition, |this| ...)` applies the closure only if the condition is true, without breaking your chain:

```rust
div()
    .id("row")
    .px_3()
    .when(self.selected, |this| this.bg(rgb(0x2457ca)))
    .when_some(self.error.clone(), |this, message| this.child(message))
```

- `.when(cond, f)` runs `f` if `cond` is true.
- `.when_some(option, f)` runs `f` with the value if the `Option` has one.
- There are also `.when_else(..)` and `.when_none(..)`.

:::note[Coming from React?]
This replaces the `condition && <Thing />` and ternary patterns, and the conditional class names you may have built with `clsx`.
:::

To reuse a group of styles, write a small function with the signature `fn selected_style<T: Styled>(this: T) -> T` and pass it to `.when(is_selected, selected_style)`.

## Cheat sheet: GPUI methods and CSS

| CSS | GPUI |
| --- | --- |
| `display: flex` | `.flex()` |
| `flex-direction: column` | `.flex_col()` |
| `display: none` | `.hidden()` |
| `width: 100%` | `.w_full()` |
| `width: 320px` | `.w(px(320.))` |
| `padding: 16px` | `.p_4()` |
| `gap: 8px` | `.gap_2()` |
| `background` | `.bg(color)` |
| `color` | `.text_color(color)` |
| `border: 1px solid` | `.border_1().border_color(color)` |
| `border-radius: 8px` | `.rounded_lg()` |
| `box-shadow` | `.shadow_md()` |
| `opacity` | `.opacity(0.5)` |
| `font-size` | `.text_sm()`, `.text_size(px(13.))` |
| `font-weight: 700` | `.font_weight(FontWeight::BOLD)` |
| `text-overflow: ellipsis` | `.truncate()` |
| `overflow: hidden` | `.overflow_hidden()` |
| `cursor: pointer` | `.cursor_pointer()` |
| `position: absolute` | `.absolute()` |
| `:hover` | `.hover(\|s\| ..)` |
| `:active` | `.active(\|s\| ..)` |
| `:focus` | `.focus(\|s\| ..)` |

Layout methods like `items_center` and `justify_between` are in [Lay out your UI](/guides/layout/).

## Common mistakes

- **Children do not line up in a row.** A plain `div()` is not a flex container. Call `.flex()` first, then `.flex_col()`, `.items_center()` and `.gap_2()`.
- **`.active(...)` or `.on_click(...)` does not compile.** Add `.id("some-name")` to the element first.
- **Calling `.hover(...)` twice on one element.** In debug builds this stops with an error. Put all hover styles in one call.
- **Looking for `z-index`.** GPUI does not have one. Later siblings draw on top of earlier ones. See [Lay out your UI](/guides/layout/#how-is-this-different-from-css).

## Next steps

- [Lay out your UI](/guides/layout/) to arrange elements in rows, columns and grids.
- [Handle clicks and mouse input](/guides/events-and-interaction/) to make your styled elements do something.
- [Text and fonts](/guides/text-and-fonts/) for custom fonts and text layout.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/styled.rs` (the styling methods)
- `crates/gpui_macros/src/styles.rs` (the numbered scale: spacing, radius, shadow, cursor)
- `crates/gpui/src/style.rs` (the full list of style fields and their defaults)
- `crates/gpui/src/color.rs` (`rgb`, `hsla`, gradients)
- `crates/gpui/examples/shadow.rs`, `gradient.rs`
</details>
