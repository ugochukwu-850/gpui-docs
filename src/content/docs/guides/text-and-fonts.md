---
title: Work with text and fonts
description: Change the size, weight and color of text, handle long text, style part of a string, and add your own font.
sidebar:
  order: 8
  label: Text and fonts
---

How do you make text bigger, bold or blue? How do you cut off a long file name with "..."? This page shows the everyday text tools in GPUI, with a small example for each.

## What you'll learn

- How to style text with `text_xl()`, `font_weight()` and friends
- How text styles pass down from parent to child
- How to wrap, truncate or clamp long text
- How to style part of a string (a bold word, a colored letter)
- How to add your own font file

## Show and style text

In GPUI a string is already an element. You pass it to `.child(...)`, and style it through its parent:

```rust
use gpui::{FontWeight, prelude::*, div, px, rgb};

div()
    .text_xl()                          // font size
    .font_weight(FontWeight::SEMIBOLD)  // weight
    .italic()
    .text_color(rgb(0x2563eb))          // color
    .child("Hello, text!")
```

You see "Hello, text!" in large, semi-bold, italic blue letters.

The style methods come from the `Styled` trait, which is part of `gpui::prelude::*`. Here are the ones you will use most:

| You want | Use |
|---|---|
| Preset sizes | `.text_xs()` `.text_sm()` `.text_base()` `.text_lg()` `.text_xl()` `.text_2xl()` ... |
| An exact size | `.text_size(px(14.))` |
| Line spacing | `.line_height(relative(1.4))` (a multiple of the font size) or `.line_height(px(20.))` |
| Weight | `.font_weight(FontWeight::BOLD)` |
| Slanted or underlined | `.italic()` `.underline()` `.line_through()` |
| Alignment | `.text_left()` `.text_center()` `.text_right()` |
| Color | `.text_color(rgb(0x222222))` |
| A font | `.font_family("Menlo")` |

## Text styles pass down to children

Set a text style on a parent, and every child below it inherits the style. This works like CSS inheritance.

```rust
div()
    .text_sm()
    .text_color(rgb(0x555555))
    .child("This is small and gray")
    .child(
        div()
            .child("So is this")
            .child(div().text_color(rgb(0xcc0000)).child("This is small and red")),
    )
```

A child can override just one thing (the color here) and keep the rest.

:::note[Coming from React?]
This is the same idea as CSS inheritance. Set `font-size` on a parent `div` and its children pick it up. You do not pass a `style` prop down by hand.
:::

## Pick a font family

`.font_family("...")` takes a font name. GPUI knows three special names:

| Name | You get |
|---|---|
| `.SystemUIFont` | The standard font for your operating system (the default) |
| `.ZedSans` | IBM Plex Sans |
| `.ZedMono` | Lilex, a monospaced coding font |

`.SystemUIFont` always works. The other two need their font data to be loaded (see below). Any other name has to match a font that is installed on the user's computer, or one you add yourself (see below). If GPUI cannot find a font, it tries a list of common fallbacks such as Helvetica, Segoe UI and Noto Sans.

:::caution[Common mistake]
Do not assume `.ZedSans` or `.ZedMono` are installed on the user's computer. If you want a font to look the same everywhere, ship it with your app.
:::

## Handle long text

By default, text wraps to the width of its container. Three tools change that.

```rust
// Keep it on one line and cut off the end with "…"
div().w(px(300.)).truncate().child(long_text);

// Show at most two lines, then "…"
div().w(px(300.)).text_ellipsis().line_clamp(2).child(long_text);

// Keep it on one line and clip it, with no marker
div().w(px(300.)).whitespace_nowrap().overflow_hidden().child(long_text);
```

`truncate()` is a shortcut for "no wrapping, hide the overflow, add an ellipsis". These examples come from `crates/gpui/examples/text_wrapper.rs`.

For file names and paths, you can choose where the "..." goes:

| Method | Keeps |
|---|---|
| `.text_ellipsis()` | The start of the text |
| `.text_ellipsis_start()` | The end (good for paths) |
| `.text_ellipsis_middle()` | Both ends (good for file names) |

:::caution[Common mistake]
Truncation needs a **limited width**. In a flex row, a child is as wide as its content unless something limits it, so nothing ever overflows and nothing is cut. Give the element a width (`.w(px(300.))`, `.w_full()`), or use `.flex_1().min_w_0()` inside a row. Then add `overflow_hidden()` (`truncate()` and `line_clamp()` already include it).
:::

## Style part of a string

Sometimes one word needs to be bold, or one letter a different color. Use `StyledText` and give it ranges to highlight:

```rust
use gpui::{FontStyle, FontWeight, StyledText};

StyledText::new("ABCD").with_highlights([
    (0..1, FontWeight::EXTRA_BOLD.into()), // "A" is extra bold
    (2..3, FontStyle::Italic.into()),      // "C" is italic
])
```

This is the example from `crates/gpui/examples/text_layout.rs`. The result shows **A**B*C*D.

Each range is a pair of **byte positions**. `0..1` covers the first byte, `2..3` the third. For plain English that is the same as letter positions. For text like "héllo", the "é" takes two bytes, so count bytes, not characters (`char_indices()` helps). Cutting in the middle of a character panics.

A highlight can also change the color, background, underline and strikethrough. Build one directly:

```rust
use gpui::{HighlightStyle, hsla};

let marker = HighlightStyle {
    color: Some(hsla(0.0, 0.8, 0.4, 1.0)),
    ..Default::default()
};
StyledText::new("Error: disk full").with_highlights([(0..5, marker)])
```

Keep the ranges sorted and not overlapping.

## Add your own font

Embed the font file in your program and give the bytes to GPUI. Do this before you open any window:

```rust
use std::borrow::Cow;
use gpui::App;

application().run(|cx: &mut App| {
    let fonts = vec![Cow::Borrowed(
        &include_bytes!("../assets/fonts/MyFont-Regular.ttf")[..],
    )];
    cx.text_system().add_fonts(fonts).expect("failed to load fonts");

    // ...open your windows here
});
```

Then use it by its family name: `div().font_family("My Font").child("Hello")`. The family name is the name stored inside the font file. Your system font viewer shows it.

This is the same approach as `crates/gpui/examples/text.rs`, which loads the Lilex font. `cx.text_system().all_font_names()` lists every family GPUI can see, which helps when a name does not match.

If you load fonts through an asset system instead of `include_bytes!`, see [Show images, icons and SVG](/guides/images-svg-and-assets/).

## Use `SharedString` for stored text

You will see `SharedString` in many GPUI examples. It is a string that is cheap to clone, because `render` runs often and hands the same text to elements again and again. Store `SharedString` in your view instead of `String`:

```rust
use gpui::SharedString;

struct Label {
    title: SharedString,
}

let a: SharedString = "Hello".into();                // from &str
let b: SharedString = format!("{}!", a).into();      // from String
let c = SharedString::new_static("Hello");           // from a constant, no allocation
```

You can pass a `SharedString` straight to `.child(...)` or `.id(...)`.

## Text on each platform

GPUI uses the text engine of each operating system: Core Text on macOS, DirectWrite on Windows, and cosmic-text on Linux. Letter spacing can differ slightly between them.

:::caution[No text on macOS?]
On macOS, GPUI needs the `font-kit` feature of `gpui_platform`. If it is off, no text is drawn at all. Check the dependency section in [Cargo features](/reference/cargo-features/).
:::

## Common mistakes

- **Counting characters instead of bytes** in `with_highlights`. Use byte positions.
- **Truncating without a width.** Give the element a width and `overflow_hidden()`.
- **Registering fonts after opening windows.** Add them first.
- **Assuming a font exists.** A name only works if the font is installed or added. Prefer `.SystemUIFont` or a font you ship.
- **Building a new `String` for each frame.** Store a `SharedString` and clone it.

## Next steps

- [Style your elements](/guides/styling/) for colors, borders and spacing
- [Lay things out](/guides/layout/) to see why text width depends on its container
- [Show images, icons and SVG](/guides/images-svg-and-assets/) to load fonts through an asset source

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/styled.rs` (text style methods)
- `crates/gpui/src/text_system.rs` (`add_fonts`, `all_font_names`)
- `crates/gpui/src/elements/text.rs` (`StyledText`)
- `crates/gpui/src/style.rs` (`HighlightStyle`, `TextOverflow`)
- `crates/gpui/examples/text.rs`, `text_layout.rs`, `text_wrapper.rs`
</details>
