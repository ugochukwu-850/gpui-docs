---
title: Add keyboard shortcuts
description: Define actions, bind keys to them, handle them in your views, and set up app-wide shortcuts like Quit.
sidebar:
  order: 5
  label: Keyboard shortcuts
---

In GPUI, a keyboard shortcut does not run code directly. The key triggers an **action**, which is a named thing the user can do, like "Save" or "Quit". Your views listen for the action. This keeps key choices separate from the code that does the work, so you can change a shortcut without touching your views.

## What you'll learn

- What an action is and how to define one
- How to bind a key to an action
- How to handle the action in a view
- How to limit a shortcut to one part of your UI with key contexts
- How to add an app-wide shortcut such as Quit
- How to write shortcuts for macOS, Windows and Linux

## The idea in three steps

1. **Define an action.** An action is a tiny type, like `Save` or `Increment`. It names something the user can do.
2. **Bind a key to it.** "When the user presses `cmd-s`, trigger `Save`."
3. **Handle it.** An element says "when `Save` happens, run this code".

The same action can also come from a button, a menu item or your own code.

## Define actions

For actions that carry no data, use the `actions!` macro:

```rust
use gpui::actions;

actions!(counter, [Increment, Decrement, Save]);
```

This creates three types, `Increment`, `Decrement` and `Save`. The first word, `counter`, is a **namespace**. It makes the full names `counter::Increment` and so on, which must be unique in your app. Two actions with the same full name stop the app at startup.

Actions can also carry data. For those, derive `Action` on a struct with `#[action(namespace = ...)]`. This needs the `serde` and `schemars` crates, because actions can be built from JSON. Most apps start with plain `actions!`.

## Handle an action

Use `on_action` on an element. The easiest form is a method on your view:

```rust
impl Counter {
    fn increment(&mut self, _: &Increment, _window: &mut Window, cx: &mut Context<Self>) {
        self.count += 1;
        cx.notify();            // redraw
    }
}

// In render:
div()
    .track_focus(&self.focus_handle)
    .on_action(cx.listener(Self::increment))
    .on_action(cx.listener(|this, _: &Decrement, _window, cx| {
        this.count -= 1;
        cx.notify();
    }))
```

`cx.listener(...)` connects the handler to your view, the same way it does for `on_click`. See [Handle clicks and mouse input](/guides/events-and-interaction/#respond-to-a-click).

Notice `.track_focus(...)`. A handler only runs when the keyboard focus is on this element or inside it. Focus is where keyboard input goes. We cover it in [Manage keyboard focus](/guides/focus/).

## Bind keys

Bind keys once, when your app starts:

```rust
use gpui::KeyBinding;

cx.bind_keys([
    KeyBinding::new("up", Increment, None),
    KeyBinding::new("down", Decrement, None),
    KeyBinding::new("cmd-s", Save, None),
]);
```

`KeyBinding::new(keys, action, context)` takes a value of the action (`Save`, not `Save::default`). The third argument limits where the shortcut works. `None` means everywhere. We use it in the next section.

### How to write keys

Write modifiers first, joined with `-`: `ctrl-`, `alt-`, `shift-`, `cmd-`. Then the key.

| You write | Meaning |
| --- | --- |
| `"s"` | the S key |
| `"cmd-s"` | Command (macOS) or Windows/Super key (elsewhere) plus S |
| `"enter"`, `"escape"`, `"tab"`, `"space"`, `"up"`, `"left"` | named keys and arrows |
| `"cmd-k cmd-c"` | a sequence: press `cmd-k`, then `cmd-c` |

A single capital letter means Shift: `"cmd-S"` is `cmd-shift-s`. Write `"cmd-s"`.

## Limit shortcuts to part of the UI

Different parts of an app need different shortcuts. A **key context** is a label you put on part of your UI with `.key_context("Name")`. A shortcut bound to that label only works while the keyboard focus is inside that part.

```rust
// In render: label this part "Counter"
div()
    .key_context("Counter")
    .track_focus(&self.focus_handle)
    .on_action(cx.listener(Self::increment))

// At startup: only active inside "Counter"
cx.bind_keys([KeyBinding::new("up", Increment, Some("Counter"))]);
```

Now `up` increments only while the focus is inside the counter. In a text field with a different context, `up` can mean something else.

If two shortcuts match the same keys, the one in the innermost context wins. If they are equally deep, the one you bound last wins.

## Put it together: a counter with shortcuts

This program shows a number. Press the up arrow or down arrow to change it, and Cmd-Q (macOS) or Ctrl-Q (other systems) to quit.

<details>
<summary>Complete src/main.rs</summary>

```rust
use gpui::{
    App, Bounds, Context, FocusHandle, KeyBinding, Window, WindowBounds, WindowOptions, actions,
    div, prelude::*, px, rgb, size,
};
use gpui_platform::application;

actions!(counter, [Increment, Decrement, Quit]);

struct Counter {
    count: i32,
    focus_handle: FocusHandle,
}

impl Counter {
    fn new(window: &mut Window, cx: &mut Context<Self>) -> Self {
        // Focus the counter right away so the shortcuts work
        let focus_handle = cx.focus_handle();
        window.focus(&focus_handle, cx);
        Self {
            count: 0,
            focus_handle,
        }
    }

    fn increment(&mut self, _: &Increment, _window: &mut Window, cx: &mut Context<Self>) {
        self.count += 1;
        cx.notify();
    }

}

impl Render for Counter {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        div()
            .key_context("Counter")
            .track_focus(&self.focus_handle)
            .on_action(cx.listener(Self::increment))
            .on_action(cx.listener(|this, _: &Decrement, _window, cx| {
                this.count -= 1;
                cx.notify();
            }))
            .flex()
            .size_full()
            .justify_center()
            .items_center()
            .bg(rgb(0x1e1e2e))
            .text_color(rgb(0xcdd6f4))
            .text_3xl()
            .child(format!("{}", self.count))
    }
}

fn main() {
    application().run(|cx: &mut App| {
        // An app-wide action: no window or focus needed
        cx.on_action(|_: &Quit, cx| cx.quit());

        cx.bind_keys([
            KeyBinding::new("up", Increment, Some("Counter")),
            KeyBinding::new("down", Decrement, Some("Counter")),
            // Command-Q on macOS, Ctrl-Q everywhere else
            KeyBinding::new(
                if cfg!(target_os = "macos") { "cmd-q" } else { "ctrl-q" },
                Quit,
                None,
            ),
        ]);

        let bounds = Bounds::centered(None, size(px(400.), px(300.)), cx);
        cx.open_window(
            WindowOptions {
                window_bounds: Some(WindowBounds::Windowed(bounds)),
                ..Default::default()
            },
            |window, cx| cx.new(|cx| Counter::new(window, cx)),
        )
        .unwrap();
        cx.activate(true);
    });
}
```

</details>

You would see a dark window with the number `0` in the middle that changes as you press the arrows.

## Add a global shortcut like Quit

Some actions do not belong to any view: quit, open settings, show About. Handle them on the app itself with `cx.on_action`:

```rust
cx.on_action(|_: &Quit, cx| cx.quit());
cx.bind_keys([KeyBinding::new("cmd-q", Quit, None)]);
```

Global handlers run last, after the views have had their chance. Bind these with `None` as the context so they work wherever the focus is.

## Shortcuts on macOS, Windows and Linux

On macOS the usual shortcut modifier is Command. On Windows and Linux it is Ctrl. In GPUI, `cmd-` means the Command key on macOS but the Windows or Super key elsewhere, so `"cmd-s"` is probably not what a Windows user expects.

The simplest fix is to pick the string per platform, as the complete program above does with `cfg!(target_os = "macos")`. `KeyBinding::new` needs a string that lives forever (a `&'static str`), which literals are. To build the string at run time, use `KeyBinding::load`, which also understands a `secondary-` prefix: Command on macOS, Ctrl elsewhere.

## Trigger an action from code

An action is not tied to a key. A button can send it too, with `window.dispatch_action(Box::new(Save), cx)`. Menu items work the same way: see `crates/gpui/examples/set_menus.rs`.

## Which handler runs first?

When an action fires, GPUI starts at the focused element and moves outward through its parents until a handler takes it. Then it tries the app-wide handlers. The first handler takes the action; call `cx.propagate()` in it to let the parents see it too. Elements that are not around the focused one never see the action.

:::note
`crates/gpui/docs/key_dispatch.md` in the Zed repository is out of date. It shows `#[gpui::action]` and handler signatures that do not exist in this version. Use the code on this page instead.
:::

## Common mistakes

- **Nothing happens when I press the key.** Check, in order: Is the element (or something inside it) focused? Does the element with `on_action` call `.track_focus(...)`? Is the binding's context on the path to the focused element? Did you call `cx.bind_keys`?
- **A key context on an element that never gets focus.** Put `.key_context(...)` and `.track_focus(...)` on the same element.
- **A parent's handler never runs.** The child already took the action. Call `cx.propagate()` in the child.
- **Using `cmd-` on Linux and Windows.** It means the Super or Windows key there. Use `ctrl-` instead.
- **Tab does not move focus.** GPUI does not bind Tab for you. See [Manage keyboard focus](/guides/focus/#make-tab-work).

## Next steps

- [Manage keyboard focus](/guides/focus/) to control which element receives the keys.
- [Handle clicks and mouse input](/guides/events-and-interaction/) for the mouse side of interaction.
- [Input and dispatch internals](/codebase/input-and-dispatch-internals/) for the exact order GPUI uses to route keys.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/action.rs` (`actions!`, `Action`)
- `crates/gpui/src/keymap.rs`, `keymap/binding.rs`, `keymap/context.rs`
- `crates/gpui/src/platform/keystroke.rs` (key syntax)
- `crates/gpui/examples/set_menus.rs`, `on_window_close_quit.rs`, `tab_stop.rs`
</details>
