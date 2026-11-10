---
title: "Elements: the layer that draws"
description: The three-phase Element trait, how element ids keep state between frames, the built-in elements, and two worked examples of custom elements.
sidebar:
  order: 6
  label: Elements
---

:::note[Advanced]
This page is for readers who have finished the beginner path and want to know how `div()` and friends become pixels, or who need to write a custom element. Read [Thinking in GPUI](/start/thinking-in-gpui/) and [State and views](/guides/state-and-views/) first.
:::

Elements are the bottom layer of GPUI: the code that turns "what to show" into pixels. `div()` is an element. So is a string, an `img`, and the wrapper GPUI puts around each view. Most apps never implement one, but knowing the trait explains how everything above it works.

If you know the web, an element is a bit like a DOM node, with one big difference. GPUI builds the elements again every frame and throws them away, so they cannot hold state that must last.

:::tip[In short]
- Every element goes through three steps each frame: `request_layout` (how big do I want to be?), `prepaint` (now I know where I am), and `paint` (draw).
- Elements are thrown away after each frame. State that must last lives in an entity, or in element state keyed by an id.
- Most of the time you should not write an `Element`. Nest `div()`s, write a `RenderOnce` component, or use `canvas(...)`.
:::

The module docs in `element.rs` are direct about when to reach for the trait: "Only implement elements when you need to take manual control of the layout and painting process, such as when using your own custom layout algorithm or rendering a code editor."

## Three phases per frame

Every element goes through the same three calls once per frame, in this order. A building analogy helps. First you ask the architect how much room you need (layout). Then you are told which room you got and you set up your tools (prepaint). Last, you do the actual painting (paint).

```text
 request_layout   "How big do I want to be?"
      |            Ask the layout engine (Taffy) for a node, with a Style and
      |            child layout ids. Returns (LayoutId, RequestLayoutState).
      v
   [ Taffy computes bounds for the whole tree ]
      |
 prepaint         "Now I know where I am."
      |            Gets final Bounds. Register hitboxes, shape text, compute
      |            what you will paint. Returns PrepaintState.
      v
 paint            "Draw."
                   Push quads, glyphs, paths, images into the Scene. Register
                   mouse/keyboard listeners for this frame.
```

Some of those words may be new.

- **Taffy** is the layout library GPUI uses for flexbox and grid.
- A **hitbox** is an invisible rectangle that decides which element the mouse is over.
- **Shaping text** means turning a string into positioned glyphs (the shapes of the letters).
- The **Scene** is the list of shapes the GPU will draw.

State flows forward through the phases. The `RequestLayoutState` that `request_layout` returns is passed by `&mut` to `prepaint` and `paint`. The `PrepaintState` that `prepaint` returns is passed to `paint`. GPUI discards both after the frame.

## The `Element` trait

```rust
pub trait Element: 'static + IntoElement {
    type RequestLayoutState: 'static;
    type PrepaintState: 'static;

    fn id(&self) -> Option<ElementId>;
    fn source_location(&self) -> Option<&'static core::panic::Location<'static>>;

    fn request_layout(
        &mut self,
        id: Option<&GlobalElementId>,
        inspector_id: Option<&InspectorElementId>,
        window: &mut Window,
        cx: &mut App,
    ) -> (LayoutId, Self::RequestLayoutState);

    fn prepaint(
        &mut self,
        id: Option<&GlobalElementId>,
        inspector_id: Option<&InspectorElementId>,
        bounds: Bounds<Pixels>,
        request_layout: &mut Self::RequestLayoutState,
        window: &mut Window,
        cx: &mut App,
    ) -> Self::PrepaintState;

    fn paint(
        &mut self,
        id: Option<&GlobalElementId>,
        inspector_id: Option<&InspectorElementId>,
        bounds: Bounds<Pixels>,
        request_layout: &mut Self::RequestLayoutState,
        prepaint: &mut Self::PrepaintState,
        window: &mut Window,
        cx: &mut App,
    );

    // Provided: a11y_role, write_a11y_info, a11y_synthetic_children, into_any
}
```

The two associated types, `RequestLayoutState` and `PrepaintState`, are whatever you want to carry from one phase to the next. Use `()` when you carry nothing.

Details worth noting:

- **`Element: IntoElement`.** Every element must also convert into an element. For an element type that is just `type Element = Self; fn into_element(self) -> Self { self }`.
- **`source_location` has no default.** Return `None` unless you track `#[track_caller]` locations for the inspector.
- **Elements are used once per frame.** Because of that, the methods that take `&mut self` can `.take()` one-shot closures out of `Option` fields. `Canvas` stores its callbacks as `Option<Box<dyn FnOnce..>>` for this reason.
- **`cx` is `&mut App`, not a `Context`.** An element is not an entity. To touch entity state, hold an `Entity<T>` (or `WeakEntity<T>`) in the element and `read` or `update` it.
- **Each phase checks that it is the right one.** Methods like `window.paint_quad`, `window.insert_hitbox` and `window.request_layout` assert that you call them in the right phase (`debug_assert_prepaint`, `debug_assert_paint`). Calling a paint API from `request_layout` panics in debug builds.

### Ids and persistent state

`fn id(&self) -> Option<ElementId>` is how an element opts in to having an identity across frames.

`ElementId` is an enum with these variants: `View(EntityId)`, `Integer`, `Name`, `Uuid`, `FocusHandle`, `NamedInteger`, `Path`, `CodeLocation`, `NamedChild` and `OpaqueId`. It has `From` impls for the common cases (`&'static str`, `String`, `SharedString`, `usize`, `u64`, `i32`, `(&'static str, usize)`, `(&'static str, EntityId)`, `&FocusHandle`, and more).

When `id()` returns `Some`, GPUI pushes it on the window's id stack and passes a `GlobalElementId` to each method. A `GlobalElementId` is the whole *path* of ids from the root down to this element. Its docs say the id "must be unique among children of the first containing element with an id". Two siblings with the same id collide.

The global id is the key for state that has to survive the per-frame teardown. You use it during `prepaint` or `paint`:

```rust
window.with_element_state(global_id, |state: Option<MyState>, window| {
    let mut state = state.unwrap_or_default();
    // ... use and update state ...
    (result, state)   // returned state is stored for the next frame
})
```

This is how `div().id("x")` stores hover and active flags and scroll offsets. It is also how `window.use_state(...)` and `use_keyed_state(...)` keep an `Entity<S>` alive. Views get `ElementId::View(entity_id)` automatically.

On the user-facing side, `.id(..)` on an `InteractiveElement` stores the id in the `Interactivity` and returns `Stateful<Self>`, which forwards `Element::id()` to it. That is the link between `.id("btn")` and the three-method contract.

## `IntoElement` and `AnyElement`

```rust
pub trait IntoElement: Sized {
    type Element: Element;
    fn into_element(self) -> Self::Element;
    fn into_any_element(self) -> AnyElement { self.into_element().into_any() }
}
```

`IntoElement` is what `.child(..)` accepts. It is implemented for:

- every `Element`,
- `&'static str`, `String`, `Cow<'static, str>` and `SharedString` (text),
- `Entity<V: Render>` and `AnyView` (as a `ViewElement`),
- types with `#[derive(IntoElement)]`, which are stateless components (see [Views and render](/deep-dive/views-and-render/)).

`AnyElement` is the type-erased element. "Type-erased" means it can hold any element type behind one name. GPUI allocates it in an *arena*, a per-frame memory pool that is cleared after each frame.

Use `AnyElement` in these cases:

- to store mixed children (`SmallVec<[AnyElement; 2]>` in a component),
- to return different element types from `match` arms (`.into_any_element()`),
- to implement `ParentElement::extend`.

It implements `Element` and `IntoElement` itself. It also exposes the phases directly (`request_layout`, `prepaint`, `paint`, `layout_as_root`, `prepaint_at`) for elements that host children.

## Built-in elements

All of them live in `crates/gpui/src/elements/`. Everything except `ViewElement` and `Empty` is re-exported from `gpui`.

| Element | Constructor | What it does |
| --- | --- | --- |
| `Div` | `div()` | A flexbox, grid or block container. It takes `Styled`, `ParentElement` and `InteractiveElement`. It owns an `Interactivity` that carries listeners, hover and focus styles, and scroll state. This is the all-purpose building block. |
| `Img` | `img(source)` | Raster images from a path, a URL, an in-memory `Arc<RenderImage>` or `Arc<Image>`, or a custom loader. It supports `object_fit`, grayscale and other `StyledImage` options, and loads asynchronously through an image cache. |
| `ImageCacheElement` | `image_cache(provider)` | Scopes an image cache (such as `retain_all(id)`) to its children. |
| `Svg` | `svg().path("icons/x.svg")` | Renders an SVG from your `AssetSource`, or from `external_path`. The colour comes from `text_color`. `with_transformation(..)` rotates or scales. |
| `Canvas<T>` | `canvas(prepaint_fn, paint_fn)` | Closures over the low-level paint API, without writing an `Element`. You size it with `Styled`. |
| `List` | `list(ListState, render_item)` | A virtualised vertical list for **variable-height** items. "Virtualised" means only the visible rows are built. You must store a `ListState` on your view, created with `ListState::new(count, ListAlignment, overdraw)`. |
| `UniformList` | `uniform_list(id, count, \|range, window, cx\| Vec<R>)` | A virtualised list for **same-height** items. Only the visible rows are rendered. Use `UniformListScrollHandle` for scrolling. |
| Text | `"str"`, `String`, `SharedString` | Plain text, drawn with the inherited text style. |
| `StyledText` | `StyledText::new(text)` | Text with per-range `TextRun`s and highlights. |
| `InteractiveText` | | `StyledText` with click and hover on ranges. |
| `Anchored` | `anchored()` | Positions its children at a point or attached to bounds, flipping or snapping so they stay inside the window. Used for popovers and menus. |
| `Deferred` | `deferred(child)` | Lays out in place but paints after its ancestors, so it appears on top. `with_priority(n)` orders overlapping deferred draws. Pair it with `anchored()` for overlays. |
| `Surface` | `surface(source)` | A hardware video frame (`CVPixelBuffer`). Compiled for macOS and iOS only. |
| `AnimationElement` | `.with_animation(id, Animation, \|el, delta\| el)` | Wraps any element and re-renders it each frame with a changing `delta` from 0 to 1 (from `AnimationExt`). Variants: `.with_animations(..)` for chains and `.with_spring(..)`. |
| `ContainerQuery` | `container_query(\|size, window, cx\| element)` | Builds its content *after* layout from the size it was given, like a CSS container query. |
| `Empty` | `Empty` | Renders nothing (`display: none`). `EmptyView` is the view equivalent. |
| `ViewElement<V>` | `entity`, `AnyView` | Wraps a `View`: calls `render` and handles caching. You get it by passing an entity to `.child()`. |
| `Stateful<E>` | `.id(..)` on an interactive element | Adds an id and unlocks stateful interactivity. |

A short `uniform_list` example from the repository follows. Note how `cx.processor` bridges the entity method to the element's closure.

```rust
uniform_list(
    "entries",
    50,
    cx.processor(|_this, range, _window, _cx| {
        let mut items = Vec::new();
        for ix in range {
            items.push(div().id(ix).px_2().child(format!("Item {}", ix + 1)));
        }
        items
    }),
)
.h_full()
```

And an animation, from `examples/animation.rs`:

```rust
svg()
    .size_20()
    .path(ARROW_CIRCLE_SVG)
    .text_color(gpui::black())
    .with_animation(
        "image_circle",
        Animation::new(Duration::from_secs(2))
            .repeat()
            .with_easing(bounce(ease_in_out)),
        |svg, delta| svg.with_transformation(Transformation::rotate(percentage(delta))),
    )
```

## Walkthrough: `canvas`

`Canvas` is the shortest real element in the crate (`elements/canvas.rs`). It stores two callbacks and a style. It hands the paint callback the bounds and whatever `prepaint` returned.

```rust
pub struct Canvas<T> {
    prepaint: Option<Box<dyn FnOnce(Bounds<Pixels>, &mut Window, &mut App) -> T>>,
    paint: Option<Box<dyn FnOnce(Bounds<Pixels>, T, &mut Window, &mut App)>>,
    style: StyleRefinement,
}

impl<T: 'static> Element for Canvas<T> {
    type RequestLayoutState = Style;
    type PrepaintState = Option<T>;

    fn id(&self) -> Option<ElementId> { None }
    fn source_location(&self) -> Option<&'static core::panic::Location<'static>> { None }

    fn request_layout(&mut self, _id: Option<&GlobalElementId>, _inspector_id: Option<&InspectorElementId>,
                      window: &mut Window, cx: &mut App) -> (LayoutId, Style) {
        let mut style = Style::default();
        style.refine(&self.style);
        let layout_id = window.request_layout(style.clone(), [], cx);
        (layout_id, style)
    }

    fn prepaint(&mut self, _id: Option<&GlobalElementId>, _inspector_id: Option<&InspectorElementId>,
                bounds: Bounds<Pixels>, _request_layout: &mut Style,
                window: &mut Window, cx: &mut App) -> Option<T> {
        Some(self.prepaint.take().unwrap()(bounds, window, cx))
    }

    fn paint(&mut self, _id: Option<&GlobalElementId>, _inspector_id: Option<&InspectorElementId>,
             bounds: Bounds<Pixels>, style: &mut Style, prepaint: &mut Option<T>,
             window: &mut Window, cx: &mut App) {
        let prepaint = prepaint.take().unwrap();
        style.paint(bounds, window, cx, |window, cx| {
            (self.paint.take().unwrap())(bounds, prepaint, window, cx)
        });
    }
}
```

The parameter lists are reflowed for readability. Here is how each phase uses the associated types.

- **`request_layout`** turns the user's `StyleRefinement` (a partly filled-in style) into a concrete `Style`. It registers a leaf layout node, which is a node with no children (`&[]`). It returns the `Style` as the `RequestLayoutState`, so `paint` can draw the background, borders and shadows via `style.paint(..)` without recomputing.
- **`prepaint`** runs the user's first closure with the final `bounds`. Whatever it returns (`T`) becomes the `PrepaintState`. This is the place for work that needs the bounds but does not draw, such as shaping text or inserting hitboxes.
- **`paint`** runs the second closure inside `style.paint`, and hands it the bounds and `T`.

The user-facing result is the typical use:

```rust
canvas(
    |bounds, window, cx| { /* prepaint: compute something from bounds */ bounds },
    |bounds, state, window, cx| { window.paint_quad(fill(state, gpui::red())); },
)
.size_full()
```

## Walkthrough: a minimal custom element

An element that fills a box with a colour needs only a leaf layout and one paint call. This follows the shape of `Canvas` and of `EditorText` in the `view_example`. It is written from the real signatures but is not itself a file in the repository, and it has not been compiled.

```rust
use gpui::{
    App, Bounds, Element, ElementId, GlobalElementId, Hsla, InspectorElementId, IntoElement,
    LayoutId, Pixels, Style, Window, fill, px,
};

struct Swatch {
    color: Hsla,
}

impl IntoElement for Swatch {
    type Element = Self;
    fn into_element(self) -> Self::Element { self }
}

impl Element for Swatch {
    type RequestLayoutState = ();
    type PrepaintState = ();

    fn id(&self) -> Option<ElementId> { None }
    fn source_location(&self) -> Option<&'static core::panic::Location<'static>> { None }

    fn request_layout(
        &mut self,
        _id: Option<&GlobalElementId>,
        _inspector_id: Option<&InspectorElementId>,
        window: &mut Window,
        cx: &mut App,
    ) -> (LayoutId, Self::RequestLayoutState) {
        let mut style = Style::default();
        style.size.width = px(40.).into();
        style.size.height = px(40.).into();
        (window.request_layout(style, [], cx), ())
    }

    fn prepaint(
        &mut self,
        _id: Option<&GlobalElementId>,
        _inspector_id: Option<&InspectorElementId>,
        _bounds: Bounds<Pixels>,
        _request_layout: &mut Self::RequestLayoutState,
        _window: &mut Window,
        _cx: &mut App,
    ) -> Self::PrepaintState {
    }

    fn paint(
        &mut self,
        _id: Option<&GlobalElementId>,
        _inspector_id: Option<&InspectorElementId>,
        bounds: Bounds<Pixels>,
        _request_layout: &mut Self::RequestLayoutState,
        _prepaint: &mut Self::PrepaintState,
        window: &mut Window,
        _cx: &mut App,
    ) {
        window.paint_quad(fill(bounds, self.color));
    }
}
```

`div().child(Swatch { color: gpui::red() })` now works, because `Swatch: IntoElement`. You would see a 40 by 40 red square.

The real `EditorText` (in `crates/gpui/examples/view_example/example_editor.rs`) shows the full pattern for a stateful element that reads an entity.

- It holds an `editor: Entity<Editor>`. `Editor::render` just returns `EditorText { editor: cx.entity() }`.
- `request_layout` reads the editor's text (`self.editor.read(cx)`), counts the lines, and requests a width of `relative(1.)` and a height of `line_height * line_count`.
- `prepaint` shapes each line with `window.text_system().shape_line(..)` and computes a cursor rectangle with `fill(Bounds::new(..), colour)`. The shaped lines and the cursor are the `PrepaintState`.
- `paint` calls `window.handle_input(&focus_handle, ElementInputHandler::new(bounds, self.editor.clone()), cx)` to connect IME (input method) and text input. It then paints each `ShapedLine`, and finally `window.paint_quad(cursor)`.

## When to write a custom element

Write one when:

- you need your own layout algorithm, such as a grid with spanning rules, a tree table, or a canvas-like surface;
- you paint with primitives that `div` does not expose, such as shaped text lines, custom paths with `PathBuilder`, or GPU surfaces;
- you virtualise a large amount of content (`List` and `UniformList` are elements for this reason);
- you need to wire up platform input directly (`window.handle_input`);
- you draw overlays that must escape their parent's bounds (`window.with_content_mask`, `defer_draw`).

Do not write one when:

- composition does the job. Nest `div()`s and wrap them in a `RenderOnce` component;
- you only need a bit of custom drawing. Use `canvas(..)`;
- you only want something above other content. Use `deferred(anchored()...)`.

## Common mistakes

- **Painting in `request_layout`.** Layout only registers nodes. Paint and hitbox calls assert their phase.
- **Registering listeners outside `paint`.** Mouse and key listeners (`window.on_mouse_event(..)` and so on) are tied to the current frame's paint.
- **Expecting element fields to persist.** GPUI consumes elements every frame. Persist state with an entity, with `window.with_element_state` keyed by `GlobalElementId`, or with `use_state`.
- **Returning a `Some(id)` that is not unique among siblings,** or reusing one id for different state types.
- **Calling a phase twice.** `Drawable` panics with `must call request_layout only once`. Use `AnyElement`'s methods in order.
- **Wanting a `Context<T>` where an element has only `&mut App`.** Hold an entity handle and call `handle.update(cx, ..)`.

## Next steps

- [Views and render](/deep-dive/views-and-render/): how views and components produce elements.
- [Images, SVG and assets](/guides/images-svg-and-assets/): the `img` and `svg` elements in practice.
- [Text and fonts](/guides/text-and-fonts/): shaped text, which custom elements use.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/element.rs` (`Element`, `IntoElement`, `AnyElement`, `Drawable`, `GlobalElementId`, `Empty`)
- `crates/gpui/src/window.rs` (`ElementId`, `request_layout`, `insert_hitbox`, `with_element_state`, `use_state`, `with_content_mask`, `defer_draw`)
- `crates/gpui/src/elements/mod.rs` and each element: `div.rs`, `img.rs`, `svg.rs`, `canvas.rs`, `list.rs`, `uniform_list.rs`, `text.rs`, `anchored.rs`, `deferred.rs`, `surface.rs`, `animation.rs`, `container_query.rs`, `image_cache.rs`
- `crates/gpui/src/view.rs` (`ViewElement`)
- `crates/gpui/examples/view_example/example_editor.rs` (`EditorText`)
- `crates/gpui/examples/uniform_list.rs`, `crates/gpui/examples/animation.rs`
</details>
