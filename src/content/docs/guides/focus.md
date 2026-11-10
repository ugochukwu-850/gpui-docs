---
title: Manage keyboard focus
description: Make elements focusable, move focus from code, style the focused element, and set up Tab navigation.
sidebar:
  order: 6
  label: Focus
---

**Focus** decides which element receives the keyboard. At any moment, at most one element in a window has focus. It is where typing goes, where keyboard shortcuts are looked up, and which button reacts when you press Enter.

## What you'll learn

- How to make an element focusable
- How to move focus from your code
- How to style the focused element
- How to make Tab and Shift-Tab move between elements
- How to run code when focus changes

## Make an element focusable

In GPUI you do not focus an element by its id. You create a **focus handle**, which is a small token that stands for one focusable thing. You create it once, store it in your view, and attach it to an element with `.track_focus(...)`.

```rust
use gpui::{Context, FocusHandle, Window, div, prelude::*};

struct Panel {
    focus_handle: FocusHandle,   // made once with cx.focus_handle() when you create the view
}

impl Render for Panel {
    fn render(&mut self, window: &mut Window, _cx: &mut Context<Self>) -> impl IntoElement {
        div()
            .id("panel")
            .track_focus(&self.focus_handle)                         // attach the handle
            .focus(|style| style.border_color(gpui::blue()))         // style when focused
            .border_2()
            .child(if self.focus_handle.is_focused(window) { "focused" } else { "not focused" })
    }
}
```

Click the panel and its border turns blue and the text says "focused".

`.track_focus(...)` does three things. It makes the element focusable, makes a mouse click on the element focus it, and lets the element's key shortcuts work when focus is inside it.

:::caution[Common mistake]
Create the handle in your constructor, not in `render`. Each call to `cx.focus_handle()` makes a new handle. If `render` makes one each time, the focus is lost on the next redraw.
:::

## Move focus from your code

Focus an element yourself with `window.focus(...)`:

```rust
window.focus(&self.focus_handle, cx);   // focus this element
```

A common place is the constructor of your window's main view, so keyboard shortcuts work as soon as the window opens: create the handle, then call `window.focus(&handle, cx)`. The form below does this.

You can also ask about the current focus:

```rust
handle.is_focused(window)             // is this exact element focused?
handle.contains_focused(window, cx)   // is it, or something inside it, focused?
```

Focus is nested: if a text field inside a panel has focus, the panel "contains" the focus too.

## Show a focus ring

Two methods style an element depending on focus (a third, `.in_focus(...)`, also applies when something inside is focused):

| Method | Applies when |
| --- | --- |
| `.focus(\|s\| ..)` | this element is focused |
| `.focus_visible(\|s\| ..)` | this element is focused **and** the user got there with the keyboard |

The last one works like `:focus-visible` in CSS. After a mouse click, `.focus(...)` styles apply but `.focus_visible(...)` styles do not. After pressing Tab, both apply.

Which to use? Use `focus_visible` for buttons and links, so a mouse click does not leave a ring behind. Use `focus` for text inputs, where the user always wants to see where they are typing.

```rust
div()
    .id("save")
    .track_focus(&self.save_focus)
    .border_2()
    .border_color(gpui::transparent_black())
    .focus_visible(|style| style.border_color(gpui::rgb(0x10b981)))   // green ring for keyboard users
    .child("Save")
```

See `crates/gpui/examples/focus_visible.rs` for a full demo.

## Make Tab work

Tab navigation is not on by default. You need two things.

**1. Mark the elements as tab stops.** A plain handle is focusable by click, but Tab skips it. Give it a position:

```rust
let first = cx.focus_handle().tab_index(1).tab_stop(true);
let second = cx.focus_handle().tab_index(2).tab_stop(true);
```

Tab visits elements from the lowest `tab_index` to the highest, then wraps around to the start.

**2. Bind Tab and Shift-Tab to actions that move focus.** GPUI gives you the moves, `window.focus_next(cx)` and `window.focus_prev(cx)`, but you connect the keys yourself. This code is from `crates/gpui/examples/tab_stop.rs`:

```rust
actions!(example, [Tab, TabPrev]);

// At startup
cx.bind_keys([
    KeyBinding::new("tab", Tab, None),
    KeyBinding::new("shift-tab", TabPrev, None),
]);

// On an element that contains the focusable ones
div()
    .track_focus(&self.focus_handle)
    .on_action(cx.listener(|_, _: &Tab, window, cx| window.focus_next(cx)))
    .on_action(cx.listener(|_, _: &TabPrev, window, cx| window.focus_prev(cx)))
```

If you are new to actions and key bindings, read [Add keyboard shortcuts](/guides/actions-and-keybindings/) first.

`.tab_stop(false)` keeps an element focusable by click or code, but Tab skips it. For groups with their own numbering, see `.tab_group()` in `tab_stop.rs`.

## Try it: a small form

This program shows three fields. Click a field to focus it, or press Tab and Shift-Tab to move between them. The focused field gets a blue border.

The fields here are plain boxes, not real text inputs. For typing text, follow the [text input tutorial](/tutorials/text-input/).

<details>
<summary>Complete src/main.rs</summary>

```rust
use gpui::{
    App, Bounds, Context, FocusHandle, KeyBinding, Window, WindowBounds, WindowOptions, actions,
    div, prelude::*, px, rgb, size,
};
use gpui_platform::application;

actions!(form, [NextField, PrevField]);

struct Form {
    root: FocusHandle,
    fields: Vec<(&'static str, FocusHandle)>,
}

impl Form {
    fn new(window: &mut Window, cx: &mut Context<Self>) -> Self {
        let fields = vec![
            ("Name", cx.focus_handle().tab_index(1).tab_stop(true)),
            ("Email", cx.focus_handle().tab_index(2).tab_stop(true)),
            ("Message", cx.focus_handle().tab_index(3).tab_stop(true)),
        ];
        window.focus(&fields[0].1, cx); // start with the first field focused
        Self {
            root: cx.focus_handle(),
            fields,
        }
    }
}

impl Render for Form {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        div()
            .id("form")
            .track_focus(&self.root)
            .on_action(cx.listener(|_, _: &NextField, window, cx| window.focus_next(cx)))
            .on_action(cx.listener(|_, _: &PrevField, window, cx| window.focus_prev(cx)))
            .size_full()
            .flex()
            .flex_col()
            .gap_3()
            .p_6()
            .bg(rgb(0x1e1e2e))
            .text_color(rgb(0xcdd6f4))
            .children(self.fields.iter().enumerate().map(|(ix, (label, handle))| {
                div()
                    .id(("field", ix))
                    .track_focus(handle)
                    .px_3()
                    .py_2()
                    .rounded_md()
                    .border_2()
                    .border_color(rgb(0x45475a))
                    .focus(|style| style.border_color(rgb(0x89b4fa)))
                    .child(*label)
            }))
    }
}

fn main() {
    application().run(|cx: &mut App| {
        cx.bind_keys([
            KeyBinding::new("tab", NextField, None),
            KeyBinding::new("shift-tab", PrevField, None),
        ]);

        let bounds = Bounds::centered(None, size(px(400.), px(300.)), cx);
        cx.open_window(
            WindowOptions {
                window_bounds: Some(WindowBounds::Windowed(bounds)),
                ..Default::default()
            },
            |window, cx| cx.new(|cx| Form::new(window, cx)),
        )
        .unwrap();
        cx.activate(true);
    });
}
```

</details>

Notes on the code:

- Each field has its own handle, created once in `Form::new` and kept in the `fields` list.
- `window.focus(&fields[0].1, cx)` focuses the first field when the window opens.
- The outer `div` holds the Tab actions. They run because the focused field is inside it.
- The fields use `focus`, so the blue border shows after a click as well as after Tab.

## Run code when focus changes

Sometimes you want to react when the user leaves a field, for example to save what they typed. Register a listener on the context. It gives you a `Subscription`, and the listener stops when you drop it, so keep it in a field:

```rust
let subscription = cx.on_focus_out(&self.focus_handle, window, |this, _event, _window, cx| {
    this.save_draft();       // the user left this field
    cx.notify();
});
```

Also available: `cx.on_focus`, `cx.on_blur` (the handle itself) and `cx.on_focus_in` (the handle or anything inside it).

## Common mistakes

- **Creating the handle in `render`.** Make it once in the constructor and store it in your view.
- **Tab does nothing.** You need both a tab stop (`tab_index(..)` and `tab_stop(true)`) and a key binding that calls `window.focus_next(cx)`.
- **Shortcuts never fire.** Nothing inside the element with `on_action` has focus. Call `window.focus(&handle, cx)` in your constructor.
- **A focus ring shows after every mouse click.** You used `.focus(...)` where `.focus_visible(...)` was meant.
- **A focus listener stops working.** You dropped the `Subscription`. Store it in a field, or call `.detach()` on it.

## Next steps

- [Add keyboard shortcuts](/guides/actions-and-keybindings/) to bind keys to actions.
- [Text input tutorial](/tutorials/text-input/) for a focusable text field that accepts typing.
- [Style your UI](/guides/styling/#hover-and-pressed-styles) for more on state-based styles.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/window.rs` (`FocusHandle`, `focus`, `blur`, `focus_next`, `focus_prev`)
- `crates/gpui/src/app/context.rs` (`on_focus`, `on_blur`, `on_focus_in`, `on_focus_out`)
- `crates/gpui/src/elements/div.rs` (`track_focus`, `tab_index`, `tab_stop`, `tab_group`, `focus`, `focus_visible`)
- `crates/gpui/examples/tab_stop.rs`, `focus_visible.rs`
</details>
