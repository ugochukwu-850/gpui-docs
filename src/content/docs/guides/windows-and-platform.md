---
title: Windows, menus and the OS
description: Open more windows, set window options, add menus, show notifications, use the clipboard and control when your app quits.
sidebar:
  order: 11
  label: Windows and menus
---

A desktop app is more than one window. This page shows how to open extra windows, choose how they look, add a menu bar, copy to the clipboard and decide when your app quits.

## What you'll learn

- How to open a window with a title and a size
- How to open a second window or a dialog from a click
- How to ask the user to confirm something
- How to add a menu bar
- How to send a system notification and use the clipboard
- How to control when the app quits, and what differs between platforms

## Open a window with options

You already opened a window in [Hello World](/start/hello-world/). The first argument to `open_window` is `WindowOptions`. Fill in only the fields you care about:

```rust
use gpui::{App, Bounds, TitlebarOptions, WindowBounds, WindowOptions, px, size};

fn open_main_window(cx: &mut App) {
    let bounds = Bounds::centered(None, size(px(800.), px(600.)), cx);
    cx.open_window(
        WindowOptions {
            window_bounds: Some(WindowBounds::Windowed(bounds)),
            titlebar: Some(TitlebarOptions {
                title: Some("My notes".into()),
                ..Default::default()
            }),
            window_min_size: Some(size(px(400.), px(300.))),
            ..Default::default()
        },
        |_, cx| cx.new(|_| MyRoot),
    )
    .unwrap();
}
```

You get an 800 by 600 window in the middle of the screen, titled "My notes", that cannot shrink below 400 by 300. `MyRoot` stands for your own view. A real app should handle the `Result` instead of calling `unwrap()`.

Here are the options you will reach for most:

| Option | What it does |
|---|---|
| `window_bounds` | Position and size. `Windowed(bounds)`, `Maximized(..)` or `Fullscreen(..)` |
| `titlebar` | `None` removes the system title bar, so you can draw your own |
| `window_min_size` | The smallest size the user can drag to |
| `is_resizable`, `is_movable`, `is_minimizable` | All `true` by default |
| `focus`, `show` | Take focus when created, show when created (both `true`) |
| `window_background` | `Opaque` (default), `Transparent`, `Blurred`, and more |
| `kind` | What type of window it is (see next section) |

## Open a second window

Every window has its own root view. All windows share the same app, so they can share data too. To open another window when something is clicked, call `open_window` from a click handler:

```rust
div()
    .id("open-second")
    .child("Open another window")
    .on_click(|_, _window, cx| {
        let bounds = Bounds::centered(None, size(px(300.), px(200.)), cx);
        cx.open_window(
            WindowOptions {
                window_bounds: Some(WindowBounds::Windowed(bounds)),
                ..Default::default()
            },
            |_, cx| cx.new(|_| SecondView),
        )
        .unwrap();
    })
```

This is the pattern from `crates/gpui/examples/window.rs`. In that handler `cx` is the whole `App`, so opening a window is allowed.

:::caution[Common mistake]
Inside a handler made with `cx.listener(...)`, your view is in the middle of an update, and opening a window there can fail. Wrap the call in `cx.defer(move |cx| { ... })`. It then runs right after the update finishes.
:::

### Window kinds

`kind` in `WindowOptions` chooses what type of window you get:

| `WindowKind` | Behavior |
|---|---|
| `Normal` | A regular window (default) |
| `Dialog` | On top of its parent. The parent cannot be used until the dialog closes |
| `Floating` | A window that floats on top of its parent window |
| `PopUp` | Above all other windows. Use sparingly |

There are also kinds for native popups (`AnchoredPopup`) and Linux Wayland panels (`LayerShell`).

## Work with the current window

Your `render` method and event handlers receive a `window: &mut Window`. Some useful calls:

```rust
window.set_window_title("Untitled - My notes");
window.minimize_window();
window.toggle_fullscreen();
window.remove_window(); // close this window
```

### Ask the user to confirm

`window.prompt` shows a native dialog. It does not wait. It returns a receiver, and you `await` the answer in a task:

```rust
.on_click(|_, window, cx| {
    let answer = window.prompt(
        PromptLevel::Warning,
        "Delete this note?",
        Some("This cannot be undone."),
        &["Delete", "Cancel"],
        cx,
    );
    cx.spawn(async move |_cx| {
        if answer.await.unwrap() == 0 {
            println!("The user chose Delete");
        }
    })
    .detach();
})
```

The number is the index of the button that was clicked, so `0` is "Delete". See [Run work in the background](/guides/async-and-executors/) for how `cx.spawn` works.

To stop a window from closing (for example, with unsaved changes), use `window.on_window_should_close(cx, |window, cx| ...)` and return `false`.

## Decide when the app quits

By default, the app keeps running on macOS after the last window closes, and quits on Windows and Linux. Change that with a quit mode before `run`:

```rust
use gpui::QuitMode;

application()
    .with_quit_mode(QuitMode::LastWindowClosed) // or QuitMode::Explicit
    .run(|cx| { /* ... */ });
```

You can also quit from your own code with `cx.quit()`. This snippet is from `examples/on_window_close_quit.rs`. It quits when the last window closes, whatever the platform:

```rust
cx.on_window_closed(|cx, _window_id| {
    if cx.windows().is_empty() {
        cx.quit();
    }
})
.detach();
```

## Add a menu bar

Menu items run **actions**. Define the actions, register what they do, then describe the menu. This is adapted from `crates/gpui/examples/set_menus.rs`:

```rust
use gpui::{App, Menu, MenuItem, actions};

actions!(my_app, [Quit, NewNote]);

fn quit(_: &Quit, cx: &mut App) {
    cx.quit();
}

fn new_note(_: &NewNote, _cx: &mut App) { /* open a note window */ }

fn set_up_menus(cx: &mut App) {
    cx.on_action(quit);
    cx.on_action(new_note);
    cx.set_menus([Menu::new("My notes").items([
        MenuItem::action("New note", NewNote),
        MenuItem::separator(),
        MenuItem::action("Quit", Quit),
    ])]);
}
```

Call `set_up_menus(cx)` inside `run`. The shortcut shown next to an item comes from your key bindings. See [Actions and keybindings](/guides/actions-and-keybindings/).

`set_menus` replaces the whole menu, so call it again when an item's `.checked(..)` or `.disabled(..)` state changes. A menu item does nothing without a handler registered with `cx.on_action`.

Use `MenuItem::submenu(Menu::new("Mode").items([...]))` for nested menus.

## Send a system notification

These are the notifications from the operating system, not messages inside your window.

```rust
use gpui::{SystemNotification, SystemNotificationAction};

cx.set_app_identity("com.example.mynotes", "My notes"); // once, early

cx.show_system_notification(SystemNotification {
    tag: "export-done".into(), // posting the same tag again replaces it
    title: "Export finished".into(),
    body: "Your notes are saved.".into(),
    actions: vec![SystemNotificationAction {
        id: "open".into(),
        label: "Open".into(),
    }],
});
```

To react when the user clicks the notification or a button, register `cx.on_system_notification_response(|response, cx| ...)`. `response.action_id` is `None` when the user clicked the message itself. Use `cx.dismiss_system_notification("export-done")` to remove one.

Nothing happens on platforms that do not support them, or if the user denied permission. On macOS they only appear from an app bundle. The full program is `examples/system_notifications.rs`.

## Use the clipboard and open links

```rust
use gpui::ClipboardItem;

// Copy
cx.write_to_clipboard(ClipboardItem::new_string("Hello".to_string()));

// Paste (returns None if the clipboard has no text)
let text: Option<String> = cx.read_from_clipboard().and_then(|item| item.text());

// Open a link in the default browser
cx.open_url("https://zed.dev");
```

`cx.prompt_for_paths(..)` opens a file picker. It returns a receiver, like `prompt`.

## What differs between platforms

Options and calls that a platform does not support are accepted and ignored. Here is what is confirmed in the source:

| Feature | Where it works |
|---|---|
| `WindowBackgroundAppearance::MicaBackdrop` | Windows 11 |
| `WindowOptions::window_decorations` (client or server) | Linux (X11 and Wayland) |
| `WindowKind::LayerShell` | Linux, Wayland |
| `read_from_primary` (the middle-click selection) | Linux only |
| `WindowOptions::icon` | X11 only |
| `tabbing_identifier`, `use_display_p3` | macOS only |

## Common mistakes

- **The app does not quit on macOS.** That is the default. Set `QuitMode::LastWindowClosed`, or call `cx.quit()` from `on_window_closed`.

## Next steps

- [Actions and keybindings](/guides/actions-and-keybindings/) to give your menu items shortcuts
- [Test your app](/guides/testing/) to test code that opens windows and prompts
- [Focus](/guides/focus/) to understand which window and element gets key presses

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/platform.rs` (`WindowOptions`, `WindowKind`, `TitlebarOptions`, `SystemNotification`, `ClipboardItem`)
- `crates/gpui/src/app.rs` (`QuitMode`, `set_menus`, `open_url`, clipboard, notifications)
- `crates/gpui/src/window.rs` (`prompt`, `on_window_should_close`)
- `crates/gpui/examples/window.rs`, `set_menus.rs`, `system_notifications.rs`, `on_window_close_quit.rs`, `layer_shell.rs`
</details>
