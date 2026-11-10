---
title: Handle clicks and mouse input
description: Respond to clicks, hover, mouse movement, scrolling, drag and drop, and show tooltips and cursors.
sidebar:
  order: 4
  label: Mouse and events
---

In GPUI, you attach handlers to elements while you build the UI in `render`. There is no `addEventListener` to call and no cleanup to do. A handler exists for as long as your `render` code says it should.

This page covers the mouse (and touch). For the keyboard, see [Add keyboard shortcuts](/guides/actions-and-keybindings/) and [Manage keyboard focus](/guides/focus/).

## What you'll learn

- How to respond to a click, and why the element needs an `.id()`
- How to track the mouse: down, up, move, hover and "click outside"
- How to read the scroll wheel
- How to build drag and drop
- How to add tooltips and change the cursor
- How to stop one element's click from reaching another

## Respond to a click

```rust
div()
    .id("save-button")
    .child("Save")
    .on_click(cx.listener(|this, _event, _window, cx| {
        this.saved = true;
        cx.notify();     // tell GPUI to redraw this view
    }))
```

When the user clicks "Save", the closure runs. You will see whatever your `render` function shows for `self.saved == true`.

Two parts need explaining:

- `.id("save-button")` gives the element a name. See the next section.
- `cx.listener(...)` lets the closure change your view. A plain closure cannot borrow your view, because it outlives the `render` call. `cx.listener` hands it `this`, which is your view, as the first argument.

`cx.notify()` is how you tell GPUI the data changed. GPUI does not watch your fields. If you forget this line, the state changes but the screen does not.

### Why do I need `.id()`?

Some mouse features need to remember something between frames: whether the button is pressed, how far you have scrolled, whether a drag has started. GPUI stores that memory under the element's **id**. Methods that need memory (`on_click`, `active`, `on_hover`, `on_drag`, `tooltip`, `overflow_scroll`) are only available after `.id(...)`, which turns a `Div` into a `Stateful<Div>`. Methods that do not need memory (`on_mouse_down`, `hover`, `on_mouse_move`, `on_scroll`, `occlude`) work on any `div()`.

Ids can be a string, a number, or a pair for lists:

```rust
div().id(("row", ix))     // "row" plus the row number
```

Make ids different from each other among siblings. Two elements with the same id would share their remembered state, such as pressed state and scroll position.

## Read details of the click

The closure gets a `ClickEvent`. Use it to tell clicks apart (`event.is_right_click()` and `event.modifiers()` are there too):

```rust
.on_click(cx.listener(|this, event: &ClickEvent, _window, cx| {
    if event.click_count() == 2 {
        this.open_item();            // double-click
    }
    let _position = event.position(); // where in the window
}))
```

A click counts when the mouse is pressed and released on the element. `on_click` also fires when the element has keyboard focus and the user presses Enter or Space, and on a touch tap. For other buttons (middle, for example), use `on_aux_click`.

## Track the mouse yourself

For finer control, use the low-level handlers:

```rust
div()
    .on_mouse_down(MouseButton::Left, cx.listener(|this, event: &MouseDownEvent, _window, cx| {
        this.drag_start = Some(event.position);
        cx.notify();
    }))
    .on_mouse_move(cx.listener(|this, event: &MouseMoveEvent, _window, cx| {
        this.cursor = event.position;
        cx.notify();
    }))
```

`.on_mouse_up(button, ...)` works the same way. These run only when the mouse is over the element. `MouseButton` comes from the `gpui` crate.

### Click outside an element

The usual way to close a menu or popover is `on_mouse_down_out`. It runs when the user presses the mouse anywhere except on this element:

```rust
popover
    .on_mouse_down_out(cx.listener(|this, _event, _window, cx| {
        this.menu_open = false;
        cx.notify();
    }))
```

## Respond to hover

There are two kinds of hover, for two different jobs:

- **Change how it looks:** `.hover(|style| style.bg(...))`. This is only styling. See [Style your UI](/guides/styling/#hover-and-pressed-styles).
- **Run your code:** `.on_hover(...)`. It needs an `.id()` and gets `true` when the mouse enters and `false` when it leaves.

```rust
div()
    .id("card")
    .on_hover(cx.listener(|this, hovered: &bool, _window, cx| {
        this.card_hovered = *hovered;
        cx.notify();
    }))
```

## Read the scroll wheel

To make an area scroll, you do not need a handler. Use `overflow_y_scroll()` (see [Lay out your UI](/guides/layout/#scroll-a-long-area)). To react to scrolling yourself, use `.on_scroll(...)`. It gets a `ScrollEvent` with a `delta` and the mouse `position`.

## Drag and drop

Dragging in GPUI is typed. You drag a value of some Rust type, and a drop target only accepts values of the type it asked for. You need three things:

1. A type for what you drag. It also draws the floating preview that follows the cursor, so it implements `Render`.
2. A source element with `on_drag`.
3. A target element with `on_drop`.

```rust
#[derive(Clone)]
struct Card {
    label: SharedString,
}

// The preview that follows the cursor
impl Render for Card {
    fn render(&mut self, _window: &mut Window, _cx: &mut Context<Self>) -> impl IntoElement {
        div()
            .px_3().py_2()
            .bg(rgb(0x2563eb))
            .text_color(gpui::white())
            .rounded_md()
            .shadow_md()
            .child(self.label.clone())
    }
}

// The source: drag this
div()
    .id("card-1")
    .cursor_move()
    .child("Card 1")
    .on_drag(Card { label: "Card 1".into() }, |card, _offset, _window, cx| {
        cx.new(|_| card.clone())          // build the preview
    })

// The target: drop here
div()
    .id("trash")
    .child("Drop here")
    .drag_over::<Card>(|style, _card, _window, _cx| style.bg(gpui::red().opacity(0.2)))
    .on_drop(cx.listener(|this, card: &Card, _window, cx| {
        this.dropped = Some(card.label.clone());
        cx.notify();
    }))
```

- `on_drag` starts a drag once the user moves the mouse a few pixels with the left button held.
- `drag_over::<Card>` styles the target while a `Card` is over it.
- `on_drop::<Card>` runs when the user lets go over the target.
- `can_drop(|value, window, cx| bool)` lets a target refuse a drop.
- Files dropped from the operating system arrive as `ExternalPaths`.

## Tooltips

A tooltip is a small view that appears when the user rests the mouse on an element. Write it like any view, then hand it to `.tooltip(...)`:

```rust
struct HelpTooltip {
    text: SharedString,
}

impl Render for HelpTooltip {
    fn render(&mut self, _window: &mut Window, _cx: &mut Context<Self>) -> impl IntoElement {
        div()
            .px_2().py_1()
            .rounded_md()
            .bg(rgb(0x000000))
            .text_color(rgb(0xffffff))
            .text_sm()
            .child(self.text.clone())
    }
}

div()
    .id("help")
    .child("?")
    .tooltip(|_window, cx| cx.new(|_| HelpTooltip { text: "Saves the file".into() }).into())
```

Each element can have one tooltip. Use `hoverable_tooltip(...)` if the user should be able to move the mouse onto the tooltip without it closing.

## Change the cursor

```rust
div().id("link").cursor_pointer().child("Open")     // hand cursor
div().cursor_text()                                  // I-beam
```

There are about twenty more, such as `cursor_move`, `cursor_grab` and the resize cursors.

## Stop a click from reaching other elements

Mouse events go first to the element drawn on top, then outward to the elements behind and around it. That is why a click on a button inside a clickable row can trigger both handlers.

To stop it, call `cx.stop_propagation()` in the inner handler:

```rust
.on_mouse_down(MouseButton::Left, |_event, _window, cx| {
    cx.stop_propagation();    // elements behind this one will not see the press
})
```

A related problem comes from popups and overlays. A plain `div` does not catch the mouse, so clicks and hover effects pass through it to whatever is underneath. Add `.occlude()` to block the mouse for everything behind the element:

```rust
div()
    .absolute()
    .inset_0()
    .occlude()                            // nothing behind this reacts to the mouse
    .bg(gpui::black().opacity(0.4))
    .child(dialog)
```

Use `.block_mouse_except_scroll()` instead if the content behind should still be able to scroll.

`.occlude()` only affects the mouse. To also draw the element on top, see `deferred` in [Lay out your UI](/guides/layout/#popovers-and-dropdowns).

## Common mistakes

- **`on_click` is not found.** Add `.id("some-name")` first.
- **The state changed but the screen did not.** Call `cx.notify()` in the handler.
- **Clicking a popover also clicks the thing behind it.** Add `.occlude()` to the popover, and use `on_mouse_down_out` to close it.
- **Calling `.hover(...)`, `.on_hover(...)`, `.tooltip(...)` or `.on_drag(...)` twice on one element.** In debug builds this stops with an error. Each one is allowed once.
- **A child's click also runs the parent's handler.** Call `cx.stop_propagation()` in the child.

## Next steps

- [Add keyboard shortcuts](/guides/actions-and-keybindings/) for keyboard input.
- [Manage keyboard focus](/guides/focus/) to make elements respond to Tab, Enter and Space.
- [Counter tutorial](/tutorials/counter/) for clicks and state in a complete app.
- [Input and dispatch internals](/codebase/input-and-dispatch-internals/) to learn exactly how mouse events are routed.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/elements/div.rs` (`InteractiveElement`, `StatefulInteractiveElement`, `Interactivity`)
- `crates/gpui/src/interactive.rs` (`ClickEvent`, mouse and scroll events)
- `crates/gpui/examples/drag_drop.rs` (a full drag and drop program)
- `crates/ui/src/components/tooltip.rs`
</details>
