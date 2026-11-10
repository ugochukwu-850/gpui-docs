---
title: What is GPUI?
description: A plain-English introduction to GPUI, the Rust UI framework behind the Zed editor, and a map of these docs.
sidebar:
  order: 1
  label: What is GPUI?
---

GPUI is a toolkit for building desktop apps in Rust. You describe what your window should look like, and GPUI draws it on your graphics card, which makes it fast. It is what powers the [Zed](https://zed.dev) code editor.

You write your UI as plain Rust structs. When your data changes, you tell GPUI, and it redraws the window.

**What you'll learn**

- What GPUI is good at, and who it is (and is not) for today.
- How these docs are organised, so you know where to go next.
- Whether your React or web background will help you here (it will, in places).

## What can you build with it?

GPUI was written to build Zed, so it is shaped by what an editor needs: lots of text, long lists, many panels, and a keyboard-first feel. The same strengths suit other desktop tools:

- Editors and IDE-style tools.
- Dashboards and data viewers with large tables or lists.
- Small utilities that should feel native and respond instantly.

Here is what GPUI code looks like. This is the heart of a small app: it shows a greeting inside a gray box.

```rust
impl Render for HelloWorld {
    fn render(&mut self, _window: &mut Window, _cx: &mut Context<Self>) -> impl IntoElement {
        div()
            .flex()
            .size(px(500.0))
            .bg(rgb(0x505050))
            .child(format!("Hello, {}!", self.text))
    }
}
```

You do not need to understand it yet. Notice the shape: a struct holds your data, and a `render` method turns that data into a small tree of boxes (`div()`), styled with methods whose names will look familiar if you have used Tailwind CSS. The [Hello World](/start/hello-world/) page builds and runs a full version.

GPUI draws with the GPU through the native graphics API of each platform: Metal on macOS, DirectX on Windows, and Vulkan or OpenGL on Linux.

## Who GPUI is for

GPUI is a good fit if you:

- Want to build a native desktop app in Rust.
- Care about speed, large lists and dense text.
- Are comfortable reading framework source code when the docs run out.

If you know a little Rust, you can follow along. The [Rust refresher](/start/rust-refresher/) covers the bits GPUI code leans on.

## Who GPUI is not for (yet)

Be honest with yourself about these before you start:

- **You need a stable API.** GPUI is pre-1.0. Its README says: "There will often be breaking changes between versions."
- **You want a big ready-made widget library.** The core crate has `div`, text, images, lists and a few more building blocks. There is no built-in button or text field, so you build those yourself. The tutorials show how.
- **You do not want to write Rust.** GPUI is a Rust library. There is no JavaScript or HTML layer.
- **You expect thorough official docs.** They are thin. The README says the best way to learn is to read the Zed source and the examples. These docs exist to fill that gap.

## Status

:::caution[Pre-1.0 and unofficial]
GPUI is under active development as part of building Zed. Features Zed does not need may be missing, and changes Zed needs can land quickly. This site is an unofficial guide written from the GPUI source at Zed commit `b5cd310b3b54dfc659fcc06453e6358843dfe216`. If something here disagrees with the code you build against, trust the code.
:::

Because of this, the [installation steps](/start/installation/) pin your project to one exact commit. Your app keeps building until you choose to upgrade.

## How these docs are organised

Read them in this order, and stop whenever you have what you need.

| Section | Use it when you want to... |
| --- | --- |
| **Start Here** (you are here) | Set up a project, run your first window, and learn the mental model. |
| **[Tutorials](/tutorials/counter/)** | Build a real app step by step: a counter, a todo list, a text input, and long lists. |
| **[Guides](/guides/styling/)** | Solve one specific problem: styling, layout, events, focus, async work, testing. |
| **[Deep Dive](/deep-dive/big-picture/)** | Understand why GPUI works the way it does. |

Two more sections sit at the bottom of the sidebar. The **Codebase Tour** shows you around the GPUI source, and the **[Reference](/reference/glossary/)** has a glossary, a list of common errors, and the Cargo features.

### Your reading path

1. [Rust refresher](/start/rust-refresher/): optional, skip it if you know Rust.
2. [Installation](/start/installation/): get a project that compiles.
3. [Hello World](/start/hello-world/): open your first window.
4. [Thinking in GPUI](/start/thinking-in-gpui/): the mental model in one page.
5. [Run the examples](/start/running-examples/): see what the official examples look like.
6. [Counter tutorial](/tutorials/counter/): your first interactive app.

## Coming from React or the web?

:::note[Coming from React?]
A lot will feel familiar. Your UI is a function of your data. You build it out of small pieces. Styling reads like utility classes. A GPUI **view** is close to a React component, `div()` is close to a `<div>`, and the flexbox layout works the way you expect.

Some things are different. There is no `useState`: your state is plain fields on a struct. There is no automatic re-render: after you change data, you call `cx.notify()`. And there is no JSX, HTML or CSS, only Rust method calls. [Thinking in GPUI](/start/thinking-in-gpui/) has a full side-by-side table.
:::

## A note on the technical name

Later docs describe GPUI as a "hybrid immediate and retained mode" framework. In short: your state lives in long-lived objects that GPUI owns, while the description of your UI is rebuilt from that state whenever the window needs to be drawn. You never edit a UI tree by hand. The [big picture](/deep-dive/big-picture/) page explains this properly, once you want it.

## Next steps

- New to Rust? Read the [Rust refresher](/start/rust-refresher/).
- Ready to code? Go to [Installation](/start/installation/).
- Want the outside world? See the [GPUI source](https://github.com/zed-industries/zed/tree/main/crates/gpui) and the [Zed community links](https://zed.dev/community-links).

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/README.md`
- `crates/gpui/src/gpui.rs`
- `crates/gpui/src/element.rs`
- `crates/gpui/src/_ownership_and_data_flow.rs`
</details>
