---
title: "Tutorial: Build a text input"
description: "The advanced tutorial: build a single-line text field with a cursor, selection, mouse support and input method (IME) support."
sidebar:
  order: 4
  label: Text input
---

In this tutorial you will build a text field from scratch: a box where you can type, move a cursor, select text and click to place the cursor. It is the hardest tutorial in this set, because text input is hard everywhere, not only in GPUI.

:::note[This is the advanced tutorial]
Finish the [counter](/tutorials/counter/) and [todo list](/tutorials/todo-list/) tutorials first. The final program is about 900 lines. You do not have to understand every line before you run it. It is fine to copy the complete file from the end of this page, run it, and come back to read it later. The page walks through the file one building block at a time.
:::

## What you'll build

A 400 by 200 window with a gray background and:

- a white text box across the top with the gray placeholder text "Type here..."
- a solid blue cursor bar where you type or click
- typing, **Backspace**, **Delete**, **Left**, **Right**, **Home** and **End**
- selection with **Shift + Left**, **Shift + Right**, **Ctrl + A** and click-and-drag, drawn as a light blue highlight
- a line below the box that reports what you typed, for example `You typed 5 bytes: "hello"`
- support for input methods, such as typing Japanese or using dead keys, with the text being composed shown underlined

This is a trimmed version of the `input` example in the GPUI repository. We left out the clipboard, the character palette and the keystroke log.

## What you'll learn

- What makes text input harder than a button
- The five building blocks: a focus handle, actions with key bindings, a state struct, an input handler that talks to the operating system, and a custom element that paints
- How the pieces fit together in one program

## Project setup

Follow [Installation](/start/installation/), with two changes.

:::caution[Common mistake]
Set `edition = "2024"` in your `Cargo.toml`. This program uses a language feature (let-chains, in the paint code) that does not compile on edition 2021.
:::

Also add the `unicode-segmentation` crate. You will see in a moment why we need it.

```toml
[dependencies]
gpui = { git = "https://github.com/zed-industries/zed", rev = "b5cd310b3b54dfc659fcc06453e6358843dfe216" }
gpui_platform = { git = "https://github.com/zed-industries/zed", rev = "b5cd310b3b54dfc659fcc06453e6358843dfe216", features = ["font-kit", "wayland", "x11"] }
unicode-segmentation = "1"
```

## What makes text input hard

A button needs a click handler. A text field needs answers to many questions that look simple until you try them:

- **What is one character?** An emoji with a skin-tone modifier is several Unicode `char`s, but the user sees one symbol and expects one press of the arrow key to move over it. The unit the user sees is called a *grapheme cluster*. We use the `unicode-segmentation` crate to find these boundaries.
- **Where exactly is the cursor?** Rust strings are UTF-8, and we store positions as *byte offsets* into the string. But the operating system's text APIs count in UTF-16 units, so we convert between the two.
- **What about languages that need composition?** A user typing Japanese presses `k`, `a`, sees `か` underlined, picks a conversion, and confirms it. Dead keys on European keyboards, emoji pickers and voice dictation work in a similar way. The tool that does this is called an *input method editor* (IME). The operating system talks to your app through a special interface, and your app has to answer.
- **Which character is under the mouse?** To place the cursor on a click, we need to know where each character sits on screen.

GPUI does not include a ready-made text field in its core crate. It gives you the building blocks, and this tutorial assembles them.

## The shape of the solution

Three pieces cooperate:

| Piece | What it does |
| --- | --- |
| `TextInput` (a view) | Owns the text, the selection and the focus handle. Handles key actions and mouse events. Answers the operating system's text questions. |
| `TextElement` (a custom element) | Lays out, shapes and paints one line of text, plus the cursor and selection. |
| `InputDemo` (a view) | The window's root. Contains the input and the "You typed..." line. |

Why a custom element instead of a `div` with text inside? The input needs to know where each character sits, so it can turn a mouse position into a text offset and tell the IME where to show its pop-up. A plain `div` text child does not expose that. So `TextElement` shapes the text itself (shaping means turning a string into positioned glyphs) and saves the result back into the view.

We now go through the five building blocks in the order a user would meet them.

## Building block 1: A focus handle

Keyboard input goes to one place at a time. The place that currently receives it has *focus*. A `FocusHandle` is a ticket that says "this thing can have focus". Without one, the field would never receive a key press.

Here is how `TextInput` hands out its handle:

```rust
impl Focusable for TextInput {
    fn focus_handle(&self, _: &App) -> FocusHandle {
        self.focus_handle.clone()
    }
}
```

The `Focusable` trait lets other code find the handle of any view. Then, in `render`, you attach the handle to an element with `.track_focus(...)`:

```rust
.key_context("TextInput")
.track_focus(&self.focus_handle(cx))
```

That element is now a focus target: clicking it gives it focus, and key presses are sent to it. The `.key_context("TextInput")` line labels this part of the UI, which block 2 uses.

Finally, `main` focuses the input when the window opens, so you can type straight away:

```rust
text_input.focus_handle(cx).focus(window, cx);
```

Read more in the [focus guide](/guides/focus/).

## Building block 2: Actions and key bindings

An *action* is a named operation, such as "move left" or "delete backward". Instead of reacting to the raw key `backspace`, your view handles the action `Backspace`. A separate list of *key bindings* says which keys trigger which action.

This split matters. Key bindings become data. Users can rebind them, and the same action can come from a menu or from code.

Actions without data are declared with a macro:

```rust
actions!(
    text_input,
    [
        Backspace,
        Delete,
        Left,
        Right,
        SelectLeft,
        SelectRight,
        SelectAll,
        Home,
        End,
        Quit,
    ]
);
```

This creates ten empty structs. The first word, `text_input`, is a namespace for them.

A handler for an action is a method with a particular shape. Here is the one for Left:

```rust
fn left(&mut self, _: &Left, window: &mut Window, cx: &mut Context<Self>) {
    if self.selected_range.is_empty() {
        self.move_to(self.previous_boundary(self.cursor_offset()), window, cx);
    } else {
        self.move_to(self.selected_range.start, window, cx)
    }
}
```

If nothing is selected, the cursor moves one character left. If there is a selection, pressing Left collapses it to its start, as in most editors.

You attach handlers in `render` with `cx.listener`, exactly as you did for clicks:

```rust
.on_action(cx.listener(Self::backspace))
.on_action(cx.listener(Self::delete))
.on_action(cx.listener(Self::left))
.on_action(cx.listener(Self::right))
```

The key bindings are registered once, in `main`:

```rust
cx.bind_keys([
    KeyBinding::new("backspace", Backspace, None),
    KeyBinding::new("delete", Delete, None),
    KeyBinding::new("left", Left, None),
    KeyBinding::new("right", Right, None),
    KeyBinding::new("shift-left", SelectLeft, None),
    KeyBinding::new("shift-right", SelectRight, None),
    KeyBinding::new("cmd-a", SelectAll, None),
    KeyBinding::new("ctrl-a", SelectAll, None),
    KeyBinding::new("home", Home, None),
    KeyBinding::new("end", End, None),
    KeyBinding::new("cmd-q", Quit, None),
]);
cx.on_action(|_: &Quit, cx| cx.quit());
```

A few notes on these lines:

- Keystroke strings are written as modifier, dash, key: `shift-left`.
- `cmd` means the platform key: Command on macOS, and the Super (Windows) key elsewhere. On Linux and Windows the usual select-all is Ctrl, so the program binds both `cmd-a` and `ctrl-a`.
- The third argument is a *key context*. We pass `None`, which means the binding works everywhere. You could pass `Some("TextInput")` to make it work only when focus is inside an element labeled `.key_context("TextInput")`. Contexts let different parts of the UI reuse the same keys for different things.
- `Quit` is handled with `cx.on_action`, not on an element, so it works no matter what has focus.

Read more in [Actions and key bindings](/guides/actions-and-keybindings/).

## Building block 3: The state struct

Here is everything `TextInput` remembers:

```rust
struct TextInput {
    focus_handle: FocusHandle,
    content: SharedString,
    placeholder: SharedString,
    selected_range: Range<usize>,
    selection_reversed: bool,
    marked_range: Option<Range<usize>>,
    last_layout: Option<ShapedLine>,
    last_bounds: Option<Bounds<Pixels>>,
    is_selecting: bool,
}
```

- `content` is the text. Every field named `*_range` holds **byte offsets** into it.
- `selected_range` is the selection. When it is empty (for example `3..3`), it is the cursor position.
- `selection_reversed` records which end of the selection the cursor is on. If you selected from right to left, the cursor is at the start.
- `marked_range` is the IME's composing text, such as `か` before you confirm it. It is `None` when nothing is being composed.
- `last_layout` and `last_bounds` are filled in by the element each time it paints. Mouse handlers read them to turn a position on screen into a text offset.
- `is_selecting` is `true` while you drag with the mouse button held.

### Moving the cursor by whole characters

Two helpers find the boundaries between graphemes. They use `grapheme_indices` from `unicode-segmentation`:

```rust
fn previous_boundary(&self, offset: usize) -> usize {
    self.content
        .grapheme_indices(true)
        .rev()
        .find_map(|(idx, _)| (idx < offset).then_some(idx))
        .unwrap_or(0)
}

fn next_boundary(&self, offset: usize) -> usize {
    self.content
        .grapheme_indices(true)
        .find_map(|(idx, _)| (idx > offset).then_some(idx))
        .unwrap_or(self.content.len())
}
```

`previous_boundary` walks backwards to find the start of the previous grapheme. `next_boundary` walks forwards. If there is none, they fall back to the start or the end of the text.

### Changing the selection

All cursor and selection changes go through two methods:

```rust
fn move_to(&mut self, offset: usize, window: &Window, cx: &mut Context<Self>) {
    self.selected_range = offset..offset;
    self.selection_reversed = false;
    window.notify_text_selection_changed(&self.focus_handle);
    cx.notify()
}
```

`move_to` puts the cursor at one place. `select_to` (in the complete file) extends the selection to a new place. They do two kinds of notification. `cx.notify()` redraws the window, as always. `window.notify_text_selection_changed(...)` tells the operating system that the selection moved, so the IME can keep its own copy up to date.

### Converting between UTF-8 and UTF-16

The operating system gives us ranges in UTF-16 units. Our `content` uses UTF-8 byte offsets. These two functions convert:

```rust
fn offset_from_utf16(&self, offset: usize) -> usize {
    let mut utf8_offset = 0;
    let mut utf16_count = 0;

    for ch in self.content.chars() {
        if utf16_count >= offset {
            break;
        }
        utf16_count += ch.len_utf16();
        utf8_offset += ch.len_utf8();
    }

    utf8_offset
}
```

`offset_to_utf16` does the reverse. The loop walks the text one `char` at a time and counts how many UTF-8 bytes and UTF-16 units it has passed.

## Building block 4: The input handler

Key bindings handle shortcuts, but ordinary typing does not go through them. Pressing `a` does not trigger an action. Instead, the operating system's text system receives the key, applies any composition rules (dead keys, IME), and then calls into your app to say "insert this text".

The way your app answers is by implementing `EntityInputHandler` on `TextInput`. These are its main methods. All ranges are in UTF-16 units.

| Method | The operating system is asking... |
| --- | --- |
| `selected_text_range` | Where is the cursor or selection? |
| `marked_text_range` | Which part of the text is being composed? |
| `text_for_range` | What text is in this range? |
| `replace_text_in_range` | Replace this range with final text. Normal typing arrives here. |
| `replace_and_mark_text_in_range` | Replace this range with composing text, and mark it as composing. |
| `unmark_text` | Composition is finished. |
| `bounds_for_range` | Where on screen is this range? (Used to place the IME's candidate window.) |
| `character_index_for_point` | Which character is under this point? |

The most important method is `replace_text_in_range`, because pressing `a` ends up in it:

```rust
fn replace_text_in_range(
    &mut self,
    range_utf16: Option<Range<usize>>,
    new_text: &str,
    window: &mut Window,
    cx: &mut Context<Self>,
) {
    let range = range_utf16
        .as_ref()
        .map(|range_utf16| self.range_from_utf16(range_utf16))
        .or(self.marked_range.clone())
        .unwrap_or(self.selected_range.clone());

    self.content =
        (self.content[0..range.start].to_owned() + new_text + &self.content[range.end..])
            .into();
    self.selected_range = range.start + new_text.len()..range.start + new_text.len();
    self.selection_reversed = false;
    self.marked_range.take();
    window.notify_text_input_changed(&self.focus_handle);
    cx.notify();
}
```

Read the body in order:

1. Work out which part of the text to replace. If the operating system gave a range, use it. Otherwise use the composing range, and if there is none, use the current selection. When you type `a` with nothing selected, that range is empty, so the new text is inserted at the cursor.
2. Build the new string from the text before the range, the new text, and the text after it.
3. Move the cursor to just after the inserted text, and clear any composing range.
4. Tell the operating system the text changed, and redraw.

**Backspace reuses this method.** The `backspace` action extends the selection one grapheme backwards, then calls `replace_text_in_range(None, "", ...)` to replace the selection with nothing. The `delete` action does the same going forwards. That is the whole implementation of deleting.

The other methods (`replace_and_mark_text_in_range`, `bounds_for_range` and so on) follow the same pattern: convert the UTF-16 range, then read or change `content`. Read them in the complete file.

### Plugging the handler in

Writing the handler is not enough. You also have to tell the window about it. That happens during painting, in building block 5:

```rust
window.handle_input(
    &focus_handle,
    ElementInputHandler::new(bounds, self.input.clone()),
    cx,
);
```

`ElementInputHandler::new(bounds, entity)` wraps your `TextInput` so the window can talk to it. The `bounds` tell the operating system where the text box is on screen. The window uses the handler only for the frame being painted, and only while the focus handle has focus. So the element registers it again on every paint.

## Building block 5: A custom element that paints

An *element* is the thing GPUI draws. `div` is an element. Here we write our own, `TextElement`, so we can control how the text is shaped and painted. (The [Elements deep dive](/deep-dive/elements/) explains the idea in depth.)

Each frame, GPUI goes through three steps with every element:

1. **Layout**: the element says how big it wants to be.
2. **Prepaint**: now that the size is known, the element prepares what it will draw.
3. **Paint**: the element draws.

`TextElement` holds a handle to the input view. An `Entity<TextInput>` is that handle: a reference to a view that GPUI owns. (See [Entities](/deep-dive/entities/).)

```rust
struct TextElement {
    input: Entity<TextInput>,
}

struct PrepaintState {
    line: Option<ShapedLine>,
    cursor: Option<PaintQuad>,
    selection: Option<PaintQuad>,
}
```

`PrepaintState` carries the results of step 2 to step 3: the shaped line of text, and two colored rectangles (a *quad* is a filled rectangle) for the cursor and the selection.

The `impl IntoElement for TextElement` and the `id` and `source_location` methods are short boilerplate. Skip them for now. The three interesting methods follow.

### Layout: one line, full width

```rust
let mut style = Style::default();
style.size.width = relative(1.).into();
style.size.height = window.line_height().into();
(window.request_layout(style, [], cx), ())
```

This asks for a box as wide as the parent (`relative(1.)` means 100%) and one line high.

### Prepaint: shape the text and place the cursor

Prepaint does the most work. First it chooses what text to show. If the field is empty, it shows the placeholder in a faint color:

```rust
let (display_text, text_color) = if content.is_empty() {
    (input.placeholder.clone(), hsla(0., 0., 0., 0.2))
} else {
    (content, style.color)
};
```

Then it describes how to style the text. A `TextRun` is a stretch of text with one style. Normally the whole line is one run. While an IME is composing, the line is split into up to three runs so the middle one can be underlined:

```rust
let runs = if let Some(marked_range) = input.marked_range.as_ref() {
    vec![
        TextRun {
            len: marked_range.start,
            ..run.clone()
        },
        TextRun {
            len: marked_range.end - marked_range.start,
            underline: Some(UnderlineStyle {
                color: Some(run.color),
                thickness: px(1.0),
                wavy: false,
            }),
            ..run.clone()
        },
        TextRun {
            len: display_text.len() - marked_range.end,
            ..run
        },
    ]
    .into_iter()
    .filter(|run| run.len > 0)
    .collect()
} else {
    vec![run]
};
```

Next it shapes the text. This produces a `ShapedLine`, which knows where every character sits:

```rust
let font_size = style.font_size.to_pixels(window.rem_size());
let line = window
    .text_system()
    .shape_line(display_text, font_size, &runs, None);
```

Last, it uses `line.x_for_index(offset)` to find the x position of a text offset. With that, it builds the cursor (a 2 pixel wide blue bar) when nothing is selected, or the selection highlight (a rectangle from the start x to the end x) when something is:

```rust
let cursor_pos = line.x_for_index(cursor);
let (selection, cursor) = if selected_range.is_empty() {
    (
        None,
        Some(fill(
            Bounds::new(
                point(bounds.left() + cursor_pos, bounds.top()),
                size(px(2.), bounds.bottom() - bounds.top()),
            ),
            gpui::blue(),
        )),
    )
} else {
    // ... the selection rectangle, filled with rgba(0x3311ff30)
```

### Paint: draw, and save the layout

Paint registers the input handler (you saw this above), then draws the selection, the text and the cursor:

```rust
if let Some(selection) = prepaint.selection.take() {
    window.paint_quad(selection)
}
let line = prepaint.line.take().unwrap();
line.paint(
    bounds.origin,
    window.line_height(),
    gpui::TextAlign::Left,
    None,
    window,
    cx,
)
.unwrap();

if focus_handle.is_focused(window)
    && let Some(cursor) = prepaint.cursor.take()
{
    window.paint_quad(cursor);
}
```

The selection is painted first so the text appears on top of it. The cursor is only painted when the field has focus. Finally, paint saves the shaped line and the bounds back into the view:

```rust
self.input.update(cx, |input, _cx| {
    input.last_layout = Some(line);
    input.last_bounds = Some(bounds);
});
```

These two fields are what the mouse code needs.

## Mouse handling

The view's `render` attaches mouse listeners:

```rust
.on_mouse_down(MouseButton::Left, cx.listener(Self::on_mouse_down))
.on_mouse_up(MouseButton::Left, cx.listener(Self::on_mouse_up))
.on_mouse_up_out(MouseButton::Left, cx.listener(Self::on_mouse_up))
.on_mouse_move(cx.listener(Self::on_mouse_move))
```

Pressing the button starts a selection (with Shift held, it extends the existing selection). Moving the mouse extends the selection while `is_selecting` is true. Releasing ends it. `on_mouse_up_out` makes sure the selection ends even if you release the button outside the text box.

To turn a mouse position into a text offset, the view uses the layout saved by the element:

```rust
line.closest_index_for_x(position.x - bounds.left())
```

`closest_index_for_x` finds the character nearest to an x position. We subtract `bounds.left()` because the mouse position is measured from the window's edge, while the line starts at the left edge of the text box.

## The root view

`InputDemo` is the window's root. It shows the input and the line below it:

```rust
let text = self.text_input.read(cx).content.clone();
div()
    .bg(rgb(0xaaaaaa))
    .flex()
    .flex_col()
    .gap_2()
    .size_full()
    .child(self.text_input.clone())
    .child(format!("You typed {} bytes: {:?}", text.len(), text))
```

In `main`, the demo asks to be told when the input changes, so the "You typed" line stays current:

```rust
cx.observe(&text_input, |_, _, cx| cx.notify()).detach();
```

## Put it together

Here is the complete program. Copy it into `src/main.rs` and run it with `cargo run`.

<details>
<summary>Complete src/main.rs</summary>

```rust title="src/main.rs"
use std::ops::Range;

use gpui::{
    App, Bounds, Context, CursorStyle, ElementId, ElementInputHandler, Entity, EntityInputHandler,
    FocusHandle, Focusable, GlobalElementId, KeyBinding, LayoutId, MouseButton, MouseDownEvent,
    MouseMoveEvent, MouseUpEvent, PaintQuad, Pixels, Point, ShapedLine, SharedString, Style,
    TextRun, UTF16Selection, UnderlineStyle, Window, WindowBounds, WindowOptions, actions, div,
    fill, hsla, point, prelude::*, px, relative, rgb, rgba, size, white,
};
use gpui_platform::application;
use unicode_segmentation::*;

actions!(
    text_input,
    [
        Backspace,
        Delete,
        Left,
        Right,
        SelectLeft,
        SelectRight,
        SelectAll,
        Home,
        End,
        Quit,
    ]
);

struct TextInput {
    focus_handle: FocusHandle,
    content: SharedString,
    placeholder: SharedString,
    selected_range: Range<usize>,
    selection_reversed: bool,
    marked_range: Option<Range<usize>>,
    last_layout: Option<ShapedLine>,
    last_bounds: Option<Bounds<Pixels>>,
    is_selecting: bool,
}

impl TextInput {
    fn left(&mut self, _: &Left, window: &mut Window, cx: &mut Context<Self>) {
        if self.selected_range.is_empty() {
            self.move_to(self.previous_boundary(self.cursor_offset()), window, cx);
        } else {
            self.move_to(self.selected_range.start, window, cx)
        }
    }

    fn right(&mut self, _: &Right, window: &mut Window, cx: &mut Context<Self>) {
        if self.selected_range.is_empty() {
            self.move_to(self.next_boundary(self.selected_range.end), window, cx);
        } else {
            self.move_to(self.selected_range.end, window, cx)
        }
    }

    fn select_left(&mut self, _: &SelectLeft, window: &mut Window, cx: &mut Context<Self>) {
        self.select_to(self.previous_boundary(self.cursor_offset()), window, cx);
    }

    fn select_right(&mut self, _: &SelectRight, window: &mut Window, cx: &mut Context<Self>) {
        self.select_to(self.next_boundary(self.cursor_offset()), window, cx);
    }

    fn select_all(&mut self, _: &SelectAll, window: &mut Window, cx: &mut Context<Self>) {
        self.move_to(0, window, cx);
        self.select_to(self.content.len(), window, cx)
    }

    fn home(&mut self, _: &Home, window: &mut Window, cx: &mut Context<Self>) {
        self.move_to(0, window, cx);
    }

    fn end(&mut self, _: &End, window: &mut Window, cx: &mut Context<Self>) {
        self.move_to(self.content.len(), window, cx);
    }

    fn backspace(&mut self, _: &Backspace, window: &mut Window, cx: &mut Context<Self>) {
        if self.selected_range.is_empty() {
            let prev = self.previous_boundary(self.cursor_offset());
            if self.cursor_offset() == prev {
                window.play_system_bell();
                return;
            }
            self.select_to(prev, window, cx)
        }
        self.replace_text_in_range(None, "", window, cx)
    }

    fn delete(&mut self, _: &Delete, window: &mut Window, cx: &mut Context<Self>) {
        if self.selected_range.is_empty() {
            let next = self.next_boundary(self.cursor_offset());
            if self.cursor_offset() == next {
                window.play_system_bell();
                return;
            }
            self.select_to(next, window, cx)
        }
        self.replace_text_in_range(None, "", window, cx)
    }

    fn on_mouse_down(
        &mut self,
        event: &MouseDownEvent,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        self.is_selecting = true;
        window.request_virtual_keyboard();

        if event.modifiers.shift {
            self.select_to(self.index_for_mouse_position(event.position), window, cx);
        } else {
            self.move_to(self.index_for_mouse_position(event.position), window, cx)
        }
    }

    fn on_mouse_up(&mut self, _: &MouseUpEvent, _window: &mut Window, _: &mut Context<Self>) {
        self.is_selecting = false;
    }

    fn on_mouse_move(
        &mut self,
        event: &MouseMoveEvent,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        if self.is_selecting {
            self.select_to(self.index_for_mouse_position(event.position), window, cx);
        }
    }

    fn move_to(&mut self, offset: usize, window: &Window, cx: &mut Context<Self>) {
        self.selected_range = offset..offset;
        self.selection_reversed = false;
        window.notify_text_selection_changed(&self.focus_handle);
        cx.notify()
    }

    fn cursor_offset(&self) -> usize {
        if self.selection_reversed {
            self.selected_range.start
        } else {
            self.selected_range.end
        }
    }

    fn index_for_mouse_position(&self, position: Point<Pixels>) -> usize {
        if self.content.is_empty() {
            return 0;
        }

        let (Some(bounds), Some(line)) = (self.last_bounds.as_ref(), self.last_layout.as_ref())
        else {
            return 0;
        };
        if position.y < bounds.top() {
            return 0;
        }
        if position.y > bounds.bottom() {
            return self.content.len();
        }
        line.closest_index_for_x(position.x - bounds.left())
    }

    fn select_to(&mut self, offset: usize, window: &Window, cx: &mut Context<Self>) {
        if self.selection_reversed {
            self.selected_range.start = offset
        } else {
            self.selected_range.end = offset
        };
        if self.selected_range.end < self.selected_range.start {
            self.selection_reversed = !self.selection_reversed;
            self.selected_range = self.selected_range.end..self.selected_range.start;
        }
        window.notify_text_selection_changed(&self.focus_handle);
        cx.notify()
    }

    fn offset_from_utf16(&self, offset: usize) -> usize {
        let mut utf8_offset = 0;
        let mut utf16_count = 0;

        for ch in self.content.chars() {
            if utf16_count >= offset {
                break;
            }
            utf16_count += ch.len_utf16();
            utf8_offset += ch.len_utf8();
        }

        utf8_offset
    }

    fn offset_to_utf16(&self, offset: usize) -> usize {
        let mut utf16_offset = 0;
        let mut utf8_count = 0;

        for ch in self.content.chars() {
            if utf8_count >= offset {
                break;
            }
            utf8_count += ch.len_utf8();
            utf16_offset += ch.len_utf16();
        }

        utf16_offset
    }

    fn range_to_utf16(&self, range: &Range<usize>) -> Range<usize> {
        self.offset_to_utf16(range.start)..self.offset_to_utf16(range.end)
    }

    fn range_from_utf16(&self, range_utf16: &Range<usize>) -> Range<usize> {
        self.offset_from_utf16(range_utf16.start)..self.offset_from_utf16(range_utf16.end)
    }

    fn previous_boundary(&self, offset: usize) -> usize {
        self.content
            .grapheme_indices(true)
            .rev()
            .find_map(|(idx, _)| (idx < offset).then_some(idx))
            .unwrap_or(0)
    }

    fn next_boundary(&self, offset: usize) -> usize {
        self.content
            .grapheme_indices(true)
            .find_map(|(idx, _)| (idx > offset).then_some(idx))
            .unwrap_or(self.content.len())
    }
}

impl EntityInputHandler for TextInput {
    fn text_for_range(
        &mut self,
        range_utf16: Range<usize>,
        actual_range: &mut Option<Range<usize>>,
        _window: &mut Window,
        _cx: &mut Context<Self>,
    ) -> Option<String> {
        let range = self.range_from_utf16(&range_utf16);
        actual_range.replace(self.range_to_utf16(&range));
        Some(self.content[range].to_string())
    }

    fn selected_text_range(
        &mut self,
        _ignore_disabled_input: bool,
        _window: &mut Window,
        _cx: &mut Context<Self>,
    ) -> Option<UTF16Selection> {
        Some(UTF16Selection {
            range: self.range_to_utf16(&self.selected_range),
            reversed: self.selection_reversed,
        })
    }

    fn set_selected_text_range(
        &mut self,
        range_utf16: Range<usize>,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        self.selected_range = self.range_from_utf16(&range_utf16);
        self.selection_reversed = false;
        window.notify_text_selection_changed(&self.focus_handle);
        cx.notify();
    }

    fn text_length_utf16(
        &mut self,
        _window: &mut Window,
        _cx: &mut Context<Self>,
    ) -> Option<usize> {
        Some(self.content.encode_utf16().count())
    }

    fn marked_text_range(
        &self,
        _window: &mut Window,
        _cx: &mut Context<Self>,
    ) -> Option<Range<usize>> {
        self.marked_range
            .as_ref()
            .map(|range| self.range_to_utf16(range))
    }

    fn unmark_text(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        self.marked_range = None;
        window.notify_text_input_changed(&self.focus_handle);
        cx.notify();
    }

    fn replace_text_in_range(
        &mut self,
        range_utf16: Option<Range<usize>>,
        new_text: &str,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        let range = range_utf16
            .as_ref()
            .map(|range_utf16| self.range_from_utf16(range_utf16))
            .or(self.marked_range.clone())
            .unwrap_or(self.selected_range.clone());

        self.content =
            (self.content[0..range.start].to_owned() + new_text + &self.content[range.end..])
                .into();
        self.selected_range = range.start + new_text.len()..range.start + new_text.len();
        self.selection_reversed = false;
        self.marked_range.take();
        window.notify_text_input_changed(&self.focus_handle);
        cx.notify();
    }

    fn replace_and_mark_text_in_range(
        &mut self,
        range_utf16: Option<Range<usize>>,
        new_text: &str,
        new_selected_range_utf16: Option<Range<usize>>,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) {
        let range = range_utf16
            .as_ref()
            .map(|range_utf16| self.range_from_utf16(range_utf16))
            .or(self.marked_range.clone())
            .unwrap_or(self.selected_range.clone());

        self.content =
            (self.content[0..range.start].to_owned() + new_text + &self.content[range.end..])
                .into();
        if !new_text.is_empty() {
            self.marked_range = Some(range.start..range.start + new_text.len());
        } else {
            self.marked_range = None;
        }
        let insertion_start_utf16 = self.offset_to_utf16(range.start);
        let inserted_length_utf16 = new_text.encode_utf16().count();
        self.selected_range = new_selected_range_utf16
            .map(|selected| {
                self.range_from_utf16(
                    &(insertion_start_utf16 + selected.start.min(inserted_length_utf16)
                        ..insertion_start_utf16 + selected.end.min(inserted_length_utf16)),
                )
            })
            .unwrap_or_else(|| range.start + new_text.len()..range.start + new_text.len());
        self.selection_reversed = false;

        window.notify_text_input_changed(&self.focus_handle);
        cx.notify();
    }

    fn bounds_for_range(
        &mut self,
        range_utf16: Range<usize>,
        bounds: Bounds<Pixels>,
        _window: &mut Window,
        _cx: &mut Context<Self>,
    ) -> Option<Bounds<Pixels>> {
        let last_layout = self.last_layout.as_ref()?;
        if last_layout.text != self.content {
            return None;
        }
        let range = self.range_from_utf16(&range_utf16);
        Some(Bounds::from_corners(
            point(
                bounds.left() + last_layout.x_for_index(range.start),
                bounds.top(),
            ),
            point(
                bounds.left() + last_layout.x_for_index(range.end),
                bounds.bottom(),
            ),
        ))
    }

    fn selection_bounds_for_range(
        &mut self,
        range_utf16: Range<usize>,
        bounds: Bounds<Pixels>,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) -> Vec<Bounds<Pixels>> {
        self.bounds_for_range(range_utf16, bounds, window, cx)
            .into_iter()
            .collect()
    }

    fn character_index_for_point(
        &mut self,
        point: gpui::Point<Pixels>,
        _window: &mut Window,
        _cx: &mut Context<Self>,
    ) -> Option<usize> {
        let line_point = self.last_bounds?.localize(&point)?;
        let last_layout = self.last_layout.as_ref()?;

        if last_layout.text != self.content {
            return None;
        }
        let utf8_index = last_layout.closest_index_for_x(line_point.x);
        Some(self.offset_to_utf16(utf8_index))
    }
}

struct TextElement {
    input: Entity<TextInput>,
}

struct PrepaintState {
    line: Option<ShapedLine>,
    cursor: Option<PaintQuad>,
    selection: Option<PaintQuad>,
}

impl IntoElement for TextElement {
    type Element = Self;

    fn into_element(self) -> Self::Element {
        self
    }
}

impl Element for TextElement {
    type RequestLayoutState = ();
    type PrepaintState = PrepaintState;

    fn id(&self) -> Option<ElementId> {
        None
    }

    fn source_location(&self) -> Option<&'static core::panic::Location<'static>> {
        None
    }

    fn request_layout(
        &mut self,
        _id: Option<&GlobalElementId>,
        _inspector_id: Option<&gpui::InspectorElementId>,
        window: &mut Window,
        cx: &mut App,
    ) -> (LayoutId, Self::RequestLayoutState) {
        let mut style = Style::default();
        style.size.width = relative(1.).into();
        style.size.height = window.line_height().into();
        (window.request_layout(style, [], cx), ())
    }

    fn prepaint(
        &mut self,
        _id: Option<&GlobalElementId>,
        _inspector_id: Option<&gpui::InspectorElementId>,
        bounds: Bounds<Pixels>,
        _request_layout: &mut Self::RequestLayoutState,
        window: &mut Window,
        cx: &mut App,
    ) -> Self::PrepaintState {
        let input = self.input.read(cx);
        let content = input.content.clone();
        let selected_range = input.selected_range.clone();
        let cursor = input.cursor_offset();
        let style = window.text_style();

        let (display_text, text_color) = if content.is_empty() {
            (input.placeholder.clone(), hsla(0., 0., 0., 0.2))
        } else {
            (content, style.color)
        };

        let run = TextRun {
            len: display_text.len(),
            font: style.font(),
            color: text_color,
            background_color: None,
            underline: None,
            strikethrough: None,
        };
        let runs = if let Some(marked_range) = input.marked_range.as_ref() {
            vec![
                TextRun {
                    len: marked_range.start,
                    ..run.clone()
                },
                TextRun {
                    len: marked_range.end - marked_range.start,
                    underline: Some(UnderlineStyle {
                        color: Some(run.color),
                        thickness: px(1.0),
                        wavy: false,
                    }),
                    ..run.clone()
                },
                TextRun {
                    len: display_text.len() - marked_range.end,
                    ..run
                },
            ]
            .into_iter()
            .filter(|run| run.len > 0)
            .collect()
        } else {
            vec![run]
        };

        let font_size = style.font_size.to_pixels(window.rem_size());
        let line = window
            .text_system()
            .shape_line(display_text, font_size, &runs, None);

        let cursor_pos = line.x_for_index(cursor);
        let (selection, cursor) = if selected_range.is_empty() {
            (
                None,
                Some(fill(
                    Bounds::new(
                        point(bounds.left() + cursor_pos, bounds.top()),
                        size(px(2.), bounds.bottom() - bounds.top()),
                    ),
                    gpui::blue(),
                )),
            )
        } else {
            (
                Some(fill(
                    Bounds::from_corners(
                        point(
                            bounds.left() + line.x_for_index(selected_range.start),
                            bounds.top(),
                        ),
                        point(
                            bounds.left() + line.x_for_index(selected_range.end),
                            bounds.bottom(),
                        ),
                    ),
                    rgba(0x3311ff30),
                )),
                None,
            )
        };
        PrepaintState {
            line: Some(line),
            cursor,
            selection,
        }
    }

    fn paint(
        &mut self,
        _id: Option<&GlobalElementId>,
        _inspector_id: Option<&gpui::InspectorElementId>,
        bounds: Bounds<Pixels>,
        _request_layout: &mut Self::RequestLayoutState,
        prepaint: &mut Self::PrepaintState,
        window: &mut Window,
        cx: &mut App,
    ) {
        let focus_handle = self.input.read(cx).focus_handle.clone();
        window.handle_input(
            &focus_handle,
            ElementInputHandler::new(bounds, self.input.clone()),
            cx,
        );
        if let Some(selection) = prepaint.selection.take() {
            window.paint_quad(selection)
        }
        let line = prepaint.line.take().unwrap();
        line.paint(
            bounds.origin,
            window.line_height(),
            gpui::TextAlign::Left,
            None,
            window,
            cx,
        )
        .unwrap();

        if focus_handle.is_focused(window)
            && let Some(cursor) = prepaint.cursor.take()
        {
            window.paint_quad(cursor);
        }

        self.input.update(cx, |input, _cx| {
            input.last_layout = Some(line);
            input.last_bounds = Some(bounds);
        });
    }
}

impl Render for TextInput {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        div()
            .flex()
            .key_context("TextInput")
            .track_focus(&self.focus_handle(cx))
            .cursor(CursorStyle::IBeam)
            .on_action(cx.listener(Self::backspace))
            .on_action(cx.listener(Self::delete))
            .on_action(cx.listener(Self::left))
            .on_action(cx.listener(Self::right))
            .on_action(cx.listener(Self::select_left))
            .on_action(cx.listener(Self::select_right))
            .on_action(cx.listener(Self::select_all))
            .on_action(cx.listener(Self::home))
            .on_action(cx.listener(Self::end))
            .on_mouse_down(MouseButton::Left, cx.listener(Self::on_mouse_down))
            .on_mouse_up(MouseButton::Left, cx.listener(Self::on_mouse_up))
            .on_mouse_up_out(MouseButton::Left, cx.listener(Self::on_mouse_up))
            .on_mouse_move(cx.listener(Self::on_mouse_move))
            .bg(rgb(0xeeeeee))
            .line_height(px(30.))
            .text_size(px(24.))
            .child(
                div()
                    .h(px(30. + 4. * 2.))
                    .w_full()
                    .p(px(4.))
                    .bg(white())
                    .child(TextElement { input: cx.entity() }),
            )
    }
}

impl Focusable for TextInput {
    fn focus_handle(&self, _: &App) -> FocusHandle {
        self.focus_handle.clone()
    }
}

struct InputDemo {
    text_input: Entity<TextInput>,
}

impl Render for InputDemo {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        let text = self.text_input.read(cx).content.clone();
        div()
            .bg(rgb(0xaaaaaa))
            .flex()
            .flex_col()
            .gap_2()
            .size_full()
            .child(self.text_input.clone())
            .child(format!("You typed {} bytes: {:?}", text.len(), text))
    }
}

fn main() {
    application().run(|cx: &mut App| {
        let bounds = Bounds::centered(None, size(px(400.0), px(200.0)), cx);
        cx.bind_keys([
            KeyBinding::new("backspace", Backspace, None),
            KeyBinding::new("delete", Delete, None),
            KeyBinding::new("left", Left, None),
            KeyBinding::new("right", Right, None),
            KeyBinding::new("shift-left", SelectLeft, None),
            KeyBinding::new("shift-right", SelectRight, None),
            KeyBinding::new("cmd-a", SelectAll, None),
            KeyBinding::new("ctrl-a", SelectAll, None),
            KeyBinding::new("home", Home, None),
            KeyBinding::new("end", End, None),
            KeyBinding::new("cmd-q", Quit, None),
        ]);
        cx.on_action(|_: &Quit, cx| cx.quit());

        cx.open_window(
            WindowOptions {
                window_bounds: Some(WindowBounds::Windowed(bounds)),
                ..Default::default()
            },
            |window, cx| {
                let text_input = cx.new(|cx| TextInput {
                    focus_handle: cx.focus_handle(),
                    content: "".into(),
                    placeholder: "Type here...".into(),
                    selected_range: 0..0,
                    selection_reversed: false,
                    marked_range: None,
                    last_layout: None,
                    last_bounds: None,
                    is_selecting: false,
                });
                text_input.focus_handle(cx).focus(window, cx);
                cx.new(|cx| {
                    cx.observe(&text_input, |_, _, cx| cx.notify()).detach();
                    InputDemo { text_input }
                })
            },
        )
        .unwrap();
        cx.activate(true);
    });
}
```
</details>

Type some text, use the arrow keys, hold Shift to select, and click to place the cursor. If you have an input method installed (for Japanese or Chinese, say), try composing text. The underlined run is the `marked_range`, drawn as the underlined `TextRun` from prepaint.

## Where to go from here

- **Clipboard**: the upstream example also has copy, cut and paste actions, built on `cx.read_from_clipboard()` and `cx.write_to_clipboard(...)`.
- **Tests**: the bottom of the upstream `input.rs` has `#[gpui::test]` tests that check the UTF-16 conversions.
- **Reusable components**: `crates/gpui/examples/view_example` splits this idea into an `Editor` entity plus `Input` and `TextArea` layers.

## Next steps

- [Actions and key bindings](/guides/actions-and-keybindings/) covers key contexts, precedence and menus.
- [Focus](/guides/focus/) explains focus handles and tab order in full.
- [Elements](/deep-dive/elements/) explains the layout, prepaint and paint steps in depth.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/examples/input.rs`
- `crates/gpui/examples/view_example/`
- `crates/gpui/src/input.rs` (`EntityInputHandler`, `ElementInputHandler`)
- `crates/gpui/src/platform.rs` (`InputHandler`, `UTF16Selection`)
- `crates/gpui/src/window.rs` (`Window::handle_input`, `notify_text_input_changed`)
- `crates/gpui/src/element.rs` (`Element`)
- `crates/gpui/src/platform/keystroke.rs` (keystroke parsing, `cmd`, `secondary`)
- `crates/gpui/docs/key_dispatch.md`
</details>
