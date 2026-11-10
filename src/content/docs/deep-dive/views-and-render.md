---
title: "Views and render: turning state into UI"
description: How the Render trait works, how to compose child views, how cx.notify() reaches the screen, when to cache a view, and how to write stateless components.
sidebar:
  order: 5
  label: Views and render
---

:::note[Advanced]
This page is for readers who have finished the beginner path and want to understand what happens behind `Render::render`. Read [Thinking in GPUI](/start/thinking-in-gpui/) and [State and views](/guides/state-and-views/) first.
:::

A **view** is an entity whose type implements `Render`. It owns state and, whenever GPUI needs to draw it, describes itself as a tree of elements. A **component** is a stateless piece of UI built with `RenderOnce`. Together they are the middle layer of the [big picture](/deep-dive/big-picture/).

:::note[Coming from React?]
A view is roughly a class component with state, and `render` is roughly its `render()` method. The big difference is that GPUI does not compare the old and new output. It simply draws what `render` returns. You tell GPUI when to call it again with `cx.notify()`, which plays the role of `setState`.
:::

:::tip[In short]
- A view is an entity with a `render` method. `render` reads `self` and returns a tree of elements. Keep it cheap, because it runs often.
- `cx.notify()` marks the view as changed. GPUI then calls `render` again at the next frame. Without it, the data changes but the screen does not.
- For UI that is only a function of its inputs, write a `RenderOnce` component instead. Components have no state of their own.
:::

```text
 Workspace (view, Entity<Workspace>)
 ├── Sidebar   (view, Entity<Sidebar>)      each view has its own state
 │    └── Label, Button      (components: RenderOnce, no state)
 └── Editor    (view, Entity<Editor>)
      └── div(), text, ...   (elements: rebuilt every frame)
```

## The `Render` trait

```rust
pub trait Render: 'static + Sized {
    fn render(&mut self, window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement;
}
```

`render` takes `&mut self`, so it can update state lazily. Its main job, though, is to read `self` and return elements.

GPUI calls `render` inside an update of the view. That has two consequences. You cannot `read` or `update` the view's own `Entity` in there (use `self`). And `cx` is a `Context<Self>`, so `cx.listener(...)`, `cx.entity()`, `cx.notify()` and `cx.new(...)` are all available.

Here is a small counter view.

```rust
struct Counter {
    count: usize,
}

impl Render for Counter {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        div()
            .id("counter")
            .flex()
            .gap_2()
            .child(format!("Count: {}", self.count))
            .child(
                div()
                    .id("inc")
                    .px_2()
                    .bg(rgb(0x313244))
                    .hover(|s| s.bg(rgb(0x45475a)))
                    .child("+")
                    .on_click(cx.listener(|this, _event, _window, cx| {
                        this.count += 1;
                        cx.notify();
                    })),
            )
    }
}
```

Here is what the interesting lines do.

- `cx.listener(|this, event, window, cx| ...)` turns a closure over `&mut Counter` into the `Fn(&E, &mut Window, &mut App)` that elements want. It captures a *weak* handle to the view, so the handler never keeps the view alive. Method references work too: `.on_click(cx.listener(Self::on_next_image))`.
- `cx.notify()` inside the handler tells GPUI the view's data changed, so it draws the view again.
- The return type is `impl IntoElement`, so you return the element builder directly. When branches have different types, call `.into_any_element()` on each. You can also use the `FluentBuilder` helpers (`.when(cond, |this| ...)`, `.when_some(opt, |this, v| ...)`, `.map(...)`) to stay in one expression.

## Window root and opening windows

Every window has one root view, an `Entity<V>` with `V: Render`. You supply it when opening the window:

```rust
let handle: WindowHandle<Counter> = cx.open_window(WindowOptions::default(), |window, cx| {
    cx.new(|_cx| Counter { count: 0 })
})?;
```

The build closure must return an `Entity<V>`, which you build with `cx.new`. GPUI draws the window once before `open_window` returns.

- `handle.update(cx, |root: &mut Counter, window, cx| ...)` runs code against the root and the window. It returns a `Result`, because the window can be closed or the root's type can change.
- `handle.root(cx)` returns the `Entity<Counter>`. `handle.read(cx)` and `read_with` read it.
- `window.root::<E>()` is the accessor on the `Window` side. `window.replace_root(cx, |window, cx| ...)` swaps the root view and refreshes the window.
- A window root fills the window. `draw_roots` stretches an `auto`-sized root to the viewport.

## Composing child views

An `Entity<V: Render>` is itself an `IntoElement`. Passing a clone as a child embeds that view in the tree:

```rust
struct Workspace {
    sidebar: Entity<Sidebar>,
    editor: Entity<Editor>,
}

impl Render for Workspace {
    fn render(&mut self, _w: &mut Window, _cx: &mut Context<Self>) -> impl IntoElement {
        div()
            .flex()
            .size_full()
            .child(self.sidebar.clone())
            .child(self.editor.clone())
    }
}
```

Under the hood the entity becomes a `ViewElement`. It gives the child a *reactive boundary*. The child has its own identity (`ElementId::View(entity_id)`), its own element-state namespace, and its own notify target.

Create children once and store them. Calling `cx.new(...)` inside `render` allocates a new entity every frame and loses the child's state.

When you need view-local state that is created from `render`, use `window.use_state(cx, |window, cx| ...)` or `use_keyed_state(key, cx, init)`. They keep the value in element state for as long as the element is drawn in consecutive frames. The `view_example` creates its editors this way:

```rust
let notes = window.use_state(cx, |window, cx| Editor::new("multi\nline", window, cx));
```

`use_state` is keyed by call site (it uses `#[track_caller]`). If the call site runs several times per frame, such as in a loop or a list item, use `use_keyed_state` with a distinguishing key.

### Type-erased views: `AnyView`

`AnyView::from(entity)` (or `entity.into()`) erases the concrete type but keeps the ability to render. `Window` uses it for the root, for tooltips (`.tooltip(|window, cx| AnyView)`), for the active drag preview and for prompts.

You can call `downcast::<T>()` on it to get a `Result<Entity<T>, AnyView>` back. You can also `downgrade()` it to an `AnyWeakView`, and call `.cached(style)` on it just like on a typed entity.

## How `notify` reaches the screen

This is the loop that closes the circle between your data and the screen.

1. During a draw, GPUI records every entity that was read or updated. At the end of the draw the window stores that set (`record_entities_accessed`). The `App` keeps a map from each entity to the windows that displayed it.
2. `cx.notify()` calls `App::notify(entity_id)`. If a window has that entity in its tracked set, the window is invalidated (`invalidate_view`). The entity goes into the window's `dirty_views`, the window is marked dirty, and the platform is asked for a frame. Observers also run.
3. At the next `Window::draw`, GPUI expands the dirty entities to include their ancestor views. `mark_view_dirty` does this by walking the dispatch tree's view path.
4. GPUI re-renders the views. Which ones it re-renders depends on caching, described next.

```text
 cx.notify()  ->  App::notify(id)  ->  window tracking id? --yes--> dirty_views += id (+ ancestors)
                                                |                    platform asked for a frame
                                                no                          |
                                                v                           v
                                       only observers run          Window::draw -> render
```

What this means in practice:

- **You need `cx.notify()` on the entity whose state changed.** Other entities that merely read it are not told about the change unless they observe it.
- **Notifying a model that no window has read** only runs its observers. No frame is requested.
- **It is cheap to over-call `notify`.** The effect is merged with one that is already pending.
- `window.refresh()` marks the whole window dirty and sets the `refreshing` flag, which bypasses caching for that frame.

## View caching with `.cached()`

By default GPUI re-renders every view every time its window draws, because a render is the only way to know what to put on screen. For big, mostly static subtrees you can opt in to reuse:

```rust
use gpui::StyleRefinement;

div().child(editor.cached(StyleRefinement::default().size_full()))
```

`Entity::cached(style)` (and `AnyView::cached(style)`) returns a `ViewElement` that skips re-rendering the child. It replays the child's previous prepaint and paint output instead. The rules, from `view.rs`, are these.

- **When the cache is reused.** The cache is reused "until the entity is notified (or the cached bounds / text style change)". The key also includes the content mask and the opacity, and any `window.refresh()` bypasses it.
- **You must supply a definite layout style.** A cached view is laid out from the `StyleRefinement` you pass. GPUI does not measure it from its contents, because rendering to measure is exactly what caching avoids. `StyleRefinement::default().size_full()` is the usual choice.
- **It only applies to entity-backed views.** For stateless `RenderOnce` components, `ViewElement::cached` is crate-private on purpose: "A stateless view has no such contract, so a frozen subtree could never be invalidated."
- **The cache is keyed on the view's own notify.** If a cached view reads another entity (a model, or a shared `Entity<String>`), a `notify` on that model does not invalidate the cached view. The `Editor` in `view_example` therefore observes its value and calls `cx.notify()` on itself:

  ```rust
  let value_sub = cx.observe(&value, |this, value, cx| {
      // ...clamp the cursor...
      cx.notify(); // the cache is keyed on *our* notify, not the value's
  });
  ```

  A test in `deferred.rs` states the same point: "A plain entity read has no dispatch-tree path to invalidate the cached panel."
- **Tracked entities are restored.** The entities a cached view touched are remembered and restored when its output is reused, so the window stays subscribed to them.
- **The inspector turns caching off.** While the element inspector is picking, caching is switched off.

Use `.cached()` for large independent panes such as editors and panels. Do not use it for every small view.

## Stateless components with `RenderOnce`

Not everything needs an entity. A reusable chunk of UI that is described entirely by its inputs is a **component**. Think of a React function component with props and no state.

```rust
use gpui::{AnyElement, App, IntoElement, ParentElement, RenderOnce, Window, div, prelude::*};
use smallvec::SmallVec;

#[derive(IntoElement)]
pub struct Popover {
    children: SmallVec<[AnyElement; 2]>,
    aside: Option<AnyElement>,
}

impl RenderOnce for Popover {
    fn render(self, _window: &mut Window, _cx: &mut App) -> impl IntoElement {
        div()
            .flex()
            .gap_1()
            .child(div().children(self.children))
            .when_some(self.aside, |this, aside| this.child(aside))
    }
}

impl Popover {
    pub fn new() -> Self {
        Self { children: SmallVec::new(), aside: None }
    }

    pub fn aside(mut self, aside: impl IntoElement) -> Self {
        self.aside = Some(aside.into_any_element());
        self
    }
}

impl ParentElement for Popover {
    fn extend(&mut self, elements: impl IntoIterator<Item = AnyElement>) {
        self.children.extend(elements)
    }
}
```

This follows `crates/ui/src/components/popover.rs`. Here are the points to notice.

- `RenderOnce::render` takes `self` by value, so the component is consumed. It gets `&mut Window` and `&mut App`, not a `Context`, since there is no entity.
- `#[derive(IntoElement)]` makes the type usable as a child. It generates `type Element = ViewElement<Self>`, so components ride on the same machinery as views, with no entity identity. The source puts it this way: "`None` behaves like a stateless component".
- The builder style (`Popover::new().aside(...).child(...)`) is a convention. Each method takes and returns `self`, so components compose like built-in elements.
- Implement `ParentElement` (just `extend`) to get `.child()` and `.children()` for free.
- Implement `Styled` (return `&mut self.style`, where `style: StyleRefinement`) to get all the Tailwind-style methods. `ui::Divider` does this and applies the style with `base.style().refine(&self.style)`.
- Pass any state the component needs, such as `Entity<Model>` handles or booleans, as fields. Components cannot own persistent state.

When a component needs *both* parent-supplied props and a backing entity for identity, implement the `View` trait by hand (`entity_id()` and `render(self, window, cx)`) and keep `#[derive(IntoElement)]`. The `Input` type in `examples/view_example/example_input.rs` does exactly this. It is keyed on its string or editor entity, so its internal `use_state` never collides across inputs.

### Which one should I use?

| Need | Use |
| --- | --- |
| Persistent state, handles events, others observe it | `Render` on an entity |
| A pure function of inputs, reused in many places | `RenderOnce` + `#[derive(IntoElement)]` |
| A big pane worth caching | An entity view + `.cached(style)` |
| Custom layout or painting | An [`Element`](/deep-dive/elements/) |

## The builder trait families

Built-in elements get their methods from a few traits. All of them are in `gpui::prelude`.

- **`Styled`** has `style(&mut self) -> &mut StyleRefinement`, plus hundreds of generated methods: `.flex()`, `.flex_col()`, `.gap_2()`, `.p_4()`, `.bg(..)`, `.size_full()`, `.rounded_md()`, `.text_color(..)`.
- **`ParentElement`** has `extend`, `.child(impl IntoElement)` and `.children(iter)`.
- **`InteractiveElement`** needs `interactivity()`. It adds `.on_mouse_down(..)`, `.on_key_down(..)`, `.on_action(..)`, `.track_focus(..)`, `.key_context(..)`, `.hover(..)`, `.focus(..)`, `.occlude()`, drag and drop handlers, and `.id(..)`.
- **`StatefulInteractiveElement`** is only available once the element has an id. Calling `.id("x")` converts a `Div` into a `Stateful<Div>`. It adds `.on_click(..)`, `.on_hover(..)`, `.tooltip(..)`, `.active(..)`, `.overflow_scroll()`, `.track_scroll(..)`, `.focusable()`, and accessibility setters like `.role(..)` and `.aria_label(..)`.

This is why the counter above calls `.id("inc")` before `.on_click(..)`. State such as "is the mouse currently pressed" must be stored across frames, and an id is the key to find it.

## Common mistakes

:::caution[Common mistake]
**State change without `cx.notify()`.** The view's data is correct, but the screen is stale.
:::

- **Expensive work in `render`.** It runs on every draw. Precompute in event handlers or tasks and store the result.
- **Creating entities in `render`.** Each frame makes a new one. Store child entities in fields, or use `window.use_state`.
- **Missing `.id(..)`** before `.on_click(..)`, `.overflow_scroll()` or `.tooltip(..)`. Those methods only exist on `Stateful<_>`, so the compiler tells you.
- **Duplicate ids among siblings.** State keyed by the element id will collide. Use `ElementId::from((name, index))`-style ids in loops.
- **A cached view that reads a model but does not observe it.** It never updates. Observe the model and call `cx.notify()` on the view.
- **Two views keyed on the same entity as siblings.** This happens with a hand-written `View::entity_id`. They share element state silently. Nesting is fine, siblings are not.
- **Reading the view's own entity inside `render`.** It panics. Use `self`.

## Next steps

- [Elements](/deep-dive/elements/): the low-level trait that views and components build on.
- [Globals and state patterns](/deep-dive/globals-and-state-patterns/): app-wide state and how views depend on it.
- [Animation](/guides/animation/): drive redraws over time.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/element.rs` (`Render`, `RenderOnce`, `ParentElement`, `IntoElement`)
- `crates/gpui/src/view.rs` (`AnyView`, `View`, `ViewElement`, `Entity::cached`, cache key and reuse logic)
- `crates/gpui/src/window.rs` (`Window::draw`, `draw_roots`, `use_state`, `WindowHandle`, `mark_view_dirty`)
- `crates/gpui/src/app.rs` (`App::notify`, `open_window`)
- `crates/gpui/src/elements/div.rs` (`InteractiveElement`, `StatefulInteractiveElement`, `Stateful`)
- `crates/gpui/src/styled.rs` (`Styled`)
- `crates/gpui_macros/src/derive_into_element.rs`
- `crates/gpui/examples/view_example/` (`example_editor.rs`, `example_input.rs`, `view_example_main.rs`)
- `crates/ui/src/components/popover.rs`, `crates/ui/src/components/divider.rs`
</details>
