---
title: "The big picture: state, views and elements"
description: A map of how GPUI fits together, from the data you own to the pixels on screen, and where each later Deep Dive page fits in.
sidebar:
  order: 1
  label: The big picture
---

:::note[Advanced]
This page is for readers who have finished the beginner path and want a mental map of the whole framework. Read [Thinking in GPUI](/start/thinking-in-gpui/) and [State and views](/guides/state-and-views/) first. The rest of the Deep Dive section zooms into the parts drawn here.
:::

GPUI is built from three layers: your **data**, the **views** that describe how that data looks, and the **elements** that become pixels. This page shows how the three fit together and how one frame travels from a data change to the screen.

:::tip[In short]
- All state lives in one object, the `App`. You hold small handles (`Entity<T>`) that point into it, never the data itself.
- A view is an entity that can draw itself. It describes the UI as a tree of elements, and GPUI throws that tree away after each frame.
- Calling `cx.notify()` is how you say "my data changed, redraw". GPUI does not watch your fields.
:::

## Three layers

The GPUI README calls these three levels *registers*. Each one has its own kind of context (the `cx` argument) passed to your code. Almost everything else in these docs is a detail of one of the three.

If you know React, the closest comparison is this. It is only a rough guide, because GPUI does not diff a virtual DOM.

| Layer | What you work with | React-ish comparison | Lifetime |
| --- | --- | --- | --- |
| **State** | `Entity<T>` | A store or a piece of state | Kept until the last handle is dropped. |
| **Views** | `Entity<V>` where `V: Render` | A component with state | The state is kept. The UI it returns is rebuilt whenever needed. |
| **Elements** | `div()`, `img()`, or your own `impl Element` | DOM nodes | Rebuilt every frame and thrown away. |

The contexts each layer receives:

| Layer | Context you receive |
| --- | --- |
| State | `&mut App`, `&mut Context<T>` |
| Views | `&mut Window`, `&mut Context<V>` |
| Elements | `&mut Window`, `&mut App` |

A **view** is not a separate kind of thing. It is an entity whose type implements the `Render` trait. If you only need to hold data that several parts of the app talk about, you use an entity and never render it. People call that a *model*. If you want pixels, you make the entity renderable.

```text
  your data            how it looks              what gets drawn
 +-----------+       +----------------+       +-------------------+
 | Entity<T> | ----> | Render::render | ----> | div() / img() /   |
 | (state)   |       | (a view)       |       | text (elements)   |
 +-----------+       +----------------+       +-------------------+
   kept                 kept, but it             rebuilt and
                        re-describes the UI      dropped each frame
```

## A complete app

Here is the `hello_world` example, trimmed down. Read it once with the three layers in mind.

```rust
use gpui::{App, Context, SharedString, Window, WindowOptions, div, prelude::*, rgb};
use gpui_platform::application;

struct HelloWorld {
    text: SharedString,
}

impl Render for HelloWorld {
    fn render(&mut self, _window: &mut Window, _cx: &mut Context<Self>) -> impl IntoElement {
        div()
            .flex()
            .size_full()
            .justify_center()
            .items_center()
            .bg(rgb(0x505050))
            .text_color(rgb(0xffffff))
            .child(format!("Hello, {}!", self.text))
    }
}

fn main() {
    application().run(|cx: &mut App| {
        cx.open_window(WindowOptions::default(), |_window, cx| {
            cx.new(|_cx| HelloWorld { text: "World".into() })
        })
        .unwrap();
        cx.activate(true);
    });
}
```

Running it opens a window with a dark gray background and the text "Hello, World!" in the middle. Here is how the code maps to the layers.

1. `application()` comes from the `gpui_platform` crate. It picks the right backend for your operating system and returns a `gpui::Application`. Calling `run` starts the platform event loop and then calls your closure once the app has launched.
2. Your closure gets `&mut App`, the owner of everything.
3. `open_window` creates a `Window` and calls your closure to build the **root view**. The root view must be an `Entity<V>` where `V: Render`. The call to `cx.new(...)` is the **state** layer creating an entity.
4. `HelloWorld::render` is the **view** layer. It returns `div()...`, and `div()` is the **element** layer.

## One owner for all state

Everything stateful is owned by a single `App`. You never own an entity directly. You hold an `Entity<T>` handle, which is a reference-counted ticket. The ticket only works when you also have a reference to the `App` (or something that derefs to it, like a `Context`).

A good everyday picture is a coat check. The `App` is the cloakroom, the entity is your coat, and the `Entity<T>` is the numbered ticket. You can pass tickets around freely, but you need the attendant (the `App`) to get at the coat.

```text
 Application::run(|cx: &mut App| { ... })
        |
        v
 +------------------------ App ------------------------+
 |  entities:  EntityId -> Box<dyn Any>                |
 |  windows:   WindowId -> Window { root view, ... }   |
 |  globals:   TypeId   -> Box<dyn Any>                |
 |  observers, event listeners, executors, platform... |
 +--------------------------------------------------------+
        ^                    ^                   ^
        |                    |                   |
   Entity<Counter>     Entity<Editor>      Entity<Workspace>
   (handle: id +       (handle)            (handle, also the
    refcount)                               window's root view)
```

This is why typical GPUI code has no `Rc<RefCell<T>>`. [How GPUI owns your data](/deep-dive/ownership-and-data-flow/) explains the reasons and the rules.

## How a frame goes from state to pixels

GPUI is described in its README as a hybrid of two older styles. In *retained mode*, the framework keeps a long-lived tree of widgets and you edit it. In *immediate mode*, you re-describe the whole UI every frame. GPUI keeps your state (retained) but rebuilds the description of the UI each time (immediate).

It does not diff a virtual DOM, and it does not keep a retained widget tree. When a window needs to be drawn, GPUI asks the root view to describe itself *right now*, works out where everything goes, paints it, and discards the description.

```text
 your code                         GPUI
 ---------                         ----
 counter.update(cx, |c, cx| {
     c.count += 1;
     cx.notify();          --->   window marked dirty, platform asked
 });                              for a frame

                                  Window::draw
                                    1. render      call Render::render on views
                                                   -> tree of elements
                                    2. layout      each element asks for a layout
                                                   node; Taffy (flexbox/grid)
                                                   computes bounds
                                    3. prepaint    each element gets its bounds,
                                                   registers hitboxes, shapes text
                                    4. paint       elements push quads, glyphs,
                                                   images into a Scene
                                    swap frames, run focus listeners
                                  present(Scene)  -> GPU draws it

                                  element tree dropped; next draw starts again
```

A few words in that diagram are new, so here they are in plain English:

- **Taffy** is the layout library GPUI uses. It does the flexbox and grid math that decides how big each element is and where it goes.
- **Bounds** are the final position and size of an element after layout.
- A **hitbox** is an invisible rectangle used to decide which element the mouse is over.
- A **Scene** is the list of shapes (rectangles, glyphs, images) that the GPU will draw.

The three element methods you will meet in [Elements](/deep-dive/elements/) map onto steps 2 to 4: `request_layout`, `prepaint` and `paint`. Step 1 happens inside a wrapper called `ViewElement`. Every entity-backed view becomes one when you pass it to `.child(...)`.

Three consequences to keep in mind:

- **`render` runs often and must be cheap.** GPUI calls it for every uncached view on every drawn frame. Do not do I/O or build big structures in it. Keep state in the entity, and only *describe* UI in `render`.
- **Calling `cx.notify()` is how you say "my output changed".** If you change view state and forget it, the data changes but the screen may not. See [Views and render](/deep-dive/views-and-render/).
- **Elements are throwaway.** The doc comment on the `element` module says the element tree, and the callbacks registered with it, are dropped before the next frame. Anything that must survive a frame (a scroll offset, hover state, the contents of a text field) lives in an entity, or in element state keyed by an id.

## The main types

Skim this table now and come back when a name is unfamiliar. The [glossary](/reference/glossary/) has more.

| Type | What it is |
| --- | --- |
| `Application` | The builder for your app before it runs: `with_assets`, `with_http_client`, `run`. Created by `gpui_platform::application()`. |
| `App` | The one object that owns entities, windows, globals, the keymap and platform services. |
| `Entity<T>` | A strong, reference-counted handle to a `T` owned by the `App`. `WeakEntity<T>` is the version that does not keep the value alive. |
| `Context<'a, T>` | A `&mut App` plus "I am entity `T`". It derefs to `App` and adds `notify`, `emit`, `observe`, `subscribe`, `spawn` and `listener`. |
| `Window` | The state of one OS window: focus, size, text style, the root view, painting APIs. It is **not** a context. It is passed alongside one. |
| `AsyncApp`, `AsyncWindowContext` | Owned (`'static`) versions of the above that you can hold across an `await`. |
| `Render` | The trait for an entity that can draw itself: `fn render(&mut self, &mut Window, &mut Context<Self>) -> impl IntoElement`. |
| `RenderOnce` | The trait for stateless components that are consumed when rendered: `fn render(self, &mut Window, &mut App) -> impl IntoElement`. |
| `Element` | The low-level trait with three methods: `request_layout`, `prepaint`, `paint`. |
| `IntoElement` | Anything that can become an element: strings, `div()`, your `#[derive(IntoElement)]` components, and `Entity<V: Render>`. |
| `AnyElement`, `AnyView` | A type-erased element and a type-erased view. |
| `Styled` | The Tailwind-style builder methods (`.flex()`, `.p_4()`, `.bg(...)`) on anything that holds a `StyleRefinement`. |
| `ParentElement`, `InteractiveElement`, `StatefulInteractiveElement` | The families of builder methods behind `.child()`, `.on_mouse_down()` and `.on_click()`. |

`use gpui::prelude::*;` brings in the traits you need for the fluent APIs. They are `AppContext`, `BorrowAppContext`, `Context`, `Element`, `InteractiveElement`, `IntoElement`, `ParentElement`, `Refineable`, `Render`, `RenderOnce`, `StatefulInteractiveElement`, `Styled`, `StyledImage`, `VisualContext` and `FluentBuilder` (which gives you `.when(...)`, `.when_some(...)` and `.map(...)`).

## A one-page map

```text
                         +------------------+
                         |   Application    |  configure, then run()
                         +--------+---------+
                                  |
                                  v
  globals  <--------------+--------------+------------> platform services
  (Global trait)          |     App      |              (clipboard, menus,
                          +--+--------+--+               open_url, ...)
                             |        |
          cx.new / update    |        |  cx.open_window
                             v        v
                      +-----------+  +---------+
                      | Entity<T> |  | Window  |-- root: Entity<V: Render>
                      +-----+-----+  +----+----+
        notify / emit       |             |  draw each frame
        observe / subscribe |             v
                            |        Render::render  ->  elements (div, img, ...)
                            |                              |
                            +--- cx.listener(...) <--------+  event handlers call
                                 back into entity state       back into entities
```

## Next steps

Read the rest of this section in this order.

1. [How GPUI owns your data](/deep-dive/ownership-and-data-flow/): why you hold handles, and what the borrow rules are.
2. [Contexts](/deep-dive/contexts/): which `cx` you hold and what it can do.
3. [Entities](/deep-dive/entities/): create, read, update, observe and emit.
4. [Views and render](/deep-dive/views-and-render/): turning state into elements, caching and components.
5. [Elements](/deep-dive/elements/): the low-level trait and the built-in elements.
6. [Globals and state patterns](/deep-dive/globals-and-state-patterns/): app-wide state and architecture patterns.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/README.md` (the "Big Picture" section)
- `crates/gpui/src/element.rs` (module docs, `Element`, `IntoElement`, `Render`, `RenderOnce`)
- `crates/gpui/src/app.rs` (`Application`, `App`, `open_window`, `flush_effects`)
- `crates/gpui/src/window.rs` (`Window::draw`, `draw_roots`)
- `crates/gpui/src/prelude.rs`
- `crates/gpui/examples/hello_world.rs`
</details>
