---
title: "A real component library: the ui crate"
description: A guided tour of crates/ui, Zed's component library, as a real-world example of building reusable components on GPUI with RenderOnce, capability traits and theme-driven styling.
sidebar:
  order: 9
  label: The ui crate
---

`crates/ui` is the component library Zed's own interface is built from: buttons, labels, list items, menus. Reading it shows how a large team writes idiomatic GPUI code, which makes it the best example to read after you understand the framework. This page is a guided tour of it, read from commit `b5cd310b`. The crate is about 31.7k lines.

`ui` is **not part of GPUI**. It depends on GPUI (and on Zed-only crates), and it is licensed `GPL-3.0-or-later` in `crates/ui/Cargo.toml`, unlike `gpui`, which is `Apache-2.0`. Check the license before copying code from it.

## What you'll learn

- How a component is written: a builder struct that implements `RenderOnce`.
- How small "capability" traits (`Clickable`, `Disableable`, ...) give different components one shared API.
- How theming works, even though GPUI itself has no theme system.
- When a component should be an entity (`Render`) instead.
- Which file to read to learn each pattern.

:::note[Advanced]
This page is for readers who have built a few views and now want to build reusable components. You should know what `RenderOnce`, `IntoElement` and `FluentBuilder` are from the [Deep Dive](/deep-dive/elements/) pages. The reading is easier after [How the macros work](/codebase/macros/), because nearly every component uses `#[derive(IntoElement)]`.
:::

:::tip[In short]
1. A `ui` component is plain data: a struct with builder methods (`mut self -> Self`) and an `impl RenderOnce`. It has no state of its own.
2. Components that must remember something and notify (a tooltip, a context menu) are entities that implement `Render` instead.
3. Colors, spacing and elevation come from the theme at render time through `cx`, so changing the theme only needs a redraw.
:::

:::caution[It cannot be built from the GPUI-only checkout]
`ui` depends on workspace crates that are not part of a GPUI-only checkout: `theme`, `component`, `icons`, `menu`, `ui_macros`, `documented` (a crates.io dependency), plus `settings` and `theme_settings` for tests. Everything below was learned from reading, not compiling. Where behaviour depends on `theme`, `component` or `ui_macros`, this page says so instead of guessing.
:::

## Layout of the crate

```text
crates/ui/src
  ui.rs                 crate root: `pub use components::*; pub use prelude::*; pub use styles::*;`
  prelude.rs            what `use ui::prelude::*;` brings in
  component_prelude.rs  extras for components that register themselves in the gallery
  traits/               capability traits
      clickable.rs  disableable.rs  toggleable.rs  fixed.rs  visible_on_hover.rs
      styled_ext.rs     (StyledExt: h_flex, v_flex, elevation_1..3, border_*)
      transformable.rs  animation_ext.rs
  styles/               tokens
      color.rs (Color)  spacing.rs (DynamicSpacing)  elevation.rs (ElevationIndex)
      typography.rs (TextSize, Headline, StyledTypography)  severity.rs  units.rs
      appearance.rs  platform.rs  animation.rs
  components/           ~45 modules, one concept each (see below)
  utils/                color_contrast.rs, apca_contrast.rs, corner_solver.rs,
                        format_distance.rs, retained_focus.rs, search_input.rs, ...
```

Largest files: `components/context_menu.rs` (3,799 lines), `scrollbar.rs` (1,914), `data_table.rs` (1,485), `toggle.rs` (1,100), `ai/thread_item.rs` (1,061), `button/button_like.rs` (1,000).

`components.rs` lists the modules: `ai, avatar, banner, button, callout, chip, choice_card, collab, context_menu, count_badge, data_table, diff_stat, disclosure, divider, dropdown_menu, facepile, gradient_fade, group, icon, image, indent_guides, indicator, keybinding, keybinding_hint, label, list, modal, navigable, notification, popover, popover_menu, progress, project_empty_state, redistributable_columns, right_click_menu, scrollbar, stack, sticky_items, tab, tab_bar, toggle, tooltip, tree_view_item`.

## The prelude

A *prelude* is a module whose contents you import all at once with `use ...::*`, so every file starts with the same short line.

`crates/ui/src/prelude.rs` re-exports `gpui::prelude::*` plus the GPUI types components need every time (`App`, `Context`, `Div`, `ElementId`, `InteractiveElement`, `ParentElement`, `Pixels`, `RenderOnce`, `SharedString`, `Styled`, `Window`, `div`, `px`, `rems`, ...) and the crate's own vocabulary: the traits `Clickable`, `Disableable`, `Toggleable`, `FixedWidth`, `StyledExt`, `VisibleOnHover`, and the types `Button`, `ButtonCommon`, `ButtonSize`, `ButtonStyle`, `Color`, `Icon`, `IconName`, `IconSize`, `Label`, `LabelCommon`, `LabelSize`, `h_flex`, `v_flex`, `DynamicSpacing`, `ActiveTheme`. Most component files start with `use crate::prelude::*;` (or `use ui::prelude::*;` in doctests).

## The component pattern: a builder struct implementing `RenderOnce`

Take `Button` (`components/button/button.rs`, 690 lines):

```rust
#[derive(IntoElement, Documented, RegisterComponent)]
pub struct Button {
    base: ButtonLike,
    label: SharedString,
    label_color: Option<Color>,
    start_icon: Option<Icon>,
    // ...
}

impl Button {
    pub fn new(id: impl Into<ElementId>, label: impl Into<SharedString>) -> Self { /* defaults */ }
    pub fn color(mut self, label_color: impl Into<Option<Color>>) -> Self { self.label_color = label_color.into(); self }
    // each setter takes `mut self` and returns Self
}

impl RenderOnce for Button {
    fn render(mut self, window: &mut Window, cx: &mut App) -> ButtonLike { /* builds children and returns self.base... */ }
}
```

Points to take from it:

1. **Components are plain data, not entities.** `#[derive(IntoElement)]` (from `gpui_macros`, see [How the macros work](/codebase/macros/)) turns a `RenderOnce` struct into an element. The struct is consumed by `render(self, ...)`, which receives `&mut Window` and `&mut App`, not a `Context<Self>`: there is no state to notify.
2. **Builder methods take `mut self` and return `Self`**, so a component is configured in one chained expression. Optional values are `Option<T>` fields; `Button::new` sets them to `None`.
3. **`ElementId` is the first argument of anything interactive.** `Button::new("button_id", "Click me!")` passes the id to `ButtonLike::new(id)`, which later calls `.id(self.id.clone())` to turn its `Div` into a `Stateful<Div>` (required for `on_click`, hover/active styles and focus tracking). See [common errors](/reference/common-errors/).
4. **Composition by wrapping.** `Button` wraps `ButtonLike`, which wraps a `Div` (`base: Div`). `Button::render` returns a `ButtonLike` (`#[allow(refining_impl_trait)]` because `RenderOnce::render` is declared to return `impl IntoElement`), and `ButtonLike`'s own `RenderOnce` finally configures the `Div`: `self.base.h_flex().id(self.id).role(Role::Button)....font_ui(cx).group("").h(...).bg(style.enabled(layer, cx).background)...`.
5. **Conditional styling with `FluentBuilder`**: `.when(cond, |this| ...)`, `.when_some(option, |this, value| ...)`, `.when_else(cond, a, b)`, `.map(|this| match ... )` (from `gpui::util::FluentBuilder`, imported by `gpui::prelude`).
6. **Accessibility is built in.** `ButtonLike` carries `aria_label`, `aria_description`, `aria_role`, `aria_expanded`, `toggled` and applies `.role(..)` and the matching builder calls; `Button::render` defaults the label from its visible text and forwards a keybinding as `aria-keyshortcuts`.
7. **Theme access happens at render time through `cx`.** `Color::color(&self, cx: &App) -> Hsla` is a `match` that calls `cx.theme().colors().text`, `cx.theme().status().created`, and so on; `ButtonStyle::enabled(layer, cx)`, `hovered(...)`, `active(...)`, `focused(...)`, `disabled(...)` compute `ButtonLikeStyles` from the theme.

## Capability traits

A *capability trait* has one small job, such as "can be clicked". Different components implement the same trait, so `button.on_click(...)` and `icon_button.on_click(...)` look identical to the caller.

`traits/` defines one-method traits that make different components share an API:

| Trait | Method | Implemented by (examples) |
| --- | --- | --- |
| `Clickable` | `on_click(self, impl Fn(&ClickEvent, &mut Window, &mut App) + 'static) -> Self`, `cursor_style(self, CursorStyle) -> Self` | `Button`, `IconButton`, `ButtonLike` |
| `Disableable` | `disabled(self, bool) -> Self` | `Button`, `IconButton`, `ButtonLike`, `ListItem`, `DropdownMenu`, `TreeViewItem` |
| `Toggleable` | `toggle_state(self, bool) -> Self` | `Button`, `IconButton`, `ButtonLike`, `Tab`, `Disclosure`, `ListItem`, `ListHeader`, `TreeViewItem` |
| `FixedWidth` | `width(self, impl Into<DefiniteLength>)`, `full_width(self)` | `Button`, `IconButton`, `ButtonLike` |
| `VisibleOnHover` | `visible_on_hover(self, group_name)` | blanket impl for any `InteractiveElement + Styled` |
| `Transformable` | `transform(self, Transformation) -> Self` | `Icon`, `Vector` (used by `CommonAnimationExt::with_rotate_animation`) |
| `ButtonCommon: Clickable + Disableable` | `id`, `style`, `size`, `tooltip`, `tab_index`, `layer`, `track_focus` | the button family |
| `SelectableButton: Toggleable` | `selected_style` | `Button`, `IconButton` |

Each implementation of a capability trait on a wrapper forwards to `self.base` (see `impl Clickable for Button { fn on_click(mut self, handler) -> Self { self.base = self.base.on_click(handler); self } }`). `ToggleState { Unselected, Indeterminate, Selected }` (in `toggleable.rs`) is used by checkboxes and switches.

`StyledExt` (`traits/styled_ext.rs`) extends `gpui::Styled`: `h_flex()` is `self.flex().flex_row().items_center()`, `v_flex()` is `self.flex().flex_col()`, `elevation_1` ... `elevation_3` (and `_borderless` variants) apply `bg(cx.theme().colors().elevated_surface_background).rounded_lg().border_1().border_color(...).shadow(index.shadow(cx))`. The trait is also annotated with `gpui_macros::derive_inspector_reflection` in debug builds so the inspector can call its methods. The free functions `h_flex()` and `v_flex()` in `components/stack.rs` are `div().h_flex()` / `div().v_flex()` marked `#[track_caller]`.

## Theming approach

A *theme* is a set of named colors and sizes that can be swapped at run time, for example light and dark mode.

GPUI itself has no theme system beyond `gpui::colors` (`Colors` / `GlobalColors`, default colours for examples). Theming is entirely the `ui` + `theme` layer:

- `ActiveTheme` (from `theme`, not in the checkout) adds `cx.theme()`; its `colors()`, `status()` and `styles.player` hold semantic colours.
- `Color` (`styles/color.rs`) is the semantic enum components accept (`Default`, `Muted`, `Accent`, `Disabled`, `Error`, `Info`, `Hint`, `Created`, `Modified`, `Deleted`, `Conflict`, `Ignored`, `Selected`, `Placeholder`, `Player(u32)`, `Custom(Hsla)` ...). Its doc comment says to prefer semantic variants and that `Custom` "detach[es] it from any semantic meaning across themes".
- `DynamicSpacing` (`styles/spacing.rs`) is generated by `ui_macros::derive_dynamic_spacing!`. Variants are named `Base04`, `Base06`, `Base08`, `Base16`, ... meaning pixels at default density and rem size; `.rems(cx)` picks the value for the user's `UiDensity` (Compact / Default / Comfortable) from the tuple table in the file (for example `(1, 2, 4)`).
- `ElevationIndex` (`styles/elevation.rs`): `Background`, `Surface`, `EditorSurface`, `ElevatedSurface`, `ModalSurface`; maps to shadows and backgrounds via the theme.
- Typography: `StyledTypography` adds `font_ui(cx)` / `font_buffer(cx)` that read `theme::theme_settings(cx)`; `TextSize` and `Headline` give the type scale; `rems_from_px` converts.
- Because styling is evaluated in `render` from `cx`, a theme change only needs the window to redraw; nothing is subscribed per component.

## Stateful components: entities when state is needed

Not everything is `RenderOnce`. Components that own state are entities implementing `Render`:

- `Tooltip` (`components/tooltip.rs`): a struct with `impl Render for Tooltip`, created via `cx.new(|_| Tooltip { .. }).into()` inside builders like `Tooltip::text("...")`, which returns `impl Fn(&mut Window, &mut App) -> AnyView`. That signature is exactly what `.tooltip(...)` on GPUI elements accepts.
- `ContextMenu` (`components/context_menu.rs`): `impl Render`, `impl Focusable`, `impl EventEmitter<DismissEvent>`. It handles keyboard navigation, submenus and actions; its `render_menu_item` etc. are plain methods that return elements.
- `PopoverMenu`, `RightClickMenu`: implement GPUI's low-level `Element` trait directly (`impl<M: ManagedView> Element for PopoverMenu<M>`) with `with_element_state` to persist the open menu across frames.

The rule of thumb visible in the code: **if the component needs to remember something between frames and notify, it is an `Entity<T: Render>`; if it is a pure function of its inputs, it is a `RenderOnce` builder.** Persistent per-element state that does not need notifications uses `window.with_element_state` keyed by `GlobalElementId`.

## Registering components for a gallery

`#[derive(RegisterComponent)]` and `impl Component for Button { fn scope() -> ComponentScope { .. } fn preview(..) }` register each component, with examples built using `example_group_with_title` and `single_example`, into a component gallery. `Component`, `ComponentScope`, `RegisterComponent` come from the `component` and `ui_macros` crates, which are not in the checkout; the derive's expansion was not read. `Documented` (`documented` crate) turns doc comments into a constant used by the gallery.

## Which files to read to learn each pattern

| You want to learn | Read |
| --- | --- |
| The smallest `RenderOnce` component | `components/label/label.rs` and `label_like.rs` |
| Wrapping and forwarding (`base: Div`) | `components/button/button_like.rs` (`ButtonLike`), then `button.rs`, `icon_button.rs` |
| Slots (`start_slot`, `end_slot`, `children: SmallVec<[AnyElement; 2]>`) | `components/list/list_item.rs` |
| Selection / toggle states | `components/toggle.rs` (`Checkbox`, `Switch`), `toggle_button.rs` |
| Layout helpers | `components/stack.rs`, `components/group.rs`, `components/divider.rs` |
| Hover groups and `visible_on_hover` | `traits/visible_on_hover.rs` (8 lines), `list_item.rs` |
| Tooltips as entities | `components/tooltip.rs` |
| Entity-based popups with focus and dismissal | `components/context_menu.rs`, `components/popover_menu.rs` |
| Custom `Element` with element state | `components/popover_menu.rs`, `components/scrollbar.rs` |
| Virtualised content | `components/data_table.rs` and `components/indent_guides.rs` (both use GPUI `uniform_list`), `components/sticky_items.rs` |
| Animations | `traits/animation_ext.rs`, `styles/animation.rs` |
| The semantic colour mapping | `styles/color.rs`, `styles/elevation.rs` |
| Density-aware spacing | `styles/spacing.rs` |

## Try it yourself

These are reading exercises. Nothing here changes the repository.

1. Open `button_like.rs` and find where `.id(self.id.clone())` is called. Which GPUI trait does that unlock? (See the tutorial note about `Stateful<Div>` in [Counter](/tutorials/counter/).)
2. Find every place a `Button` adds `.when(...)`. Rewrite one by hand without `FluentBuilder`. What changes?
3. Read `Tooltip::text`. Why does it return a closure instead of an `AnyView`?
4. In `list_item.rs`, find the `visible_on_hover("list_item")` calls. Trace how the group name matches between the `ListItem` and its end slot.
5. Open `traits/clickable.rs` and `components/button/button.rs`. Find `impl Clickable for Button` and describe in one sentence what it forwards to.
6. Pick a component from the "Which files to read" table, then write on paper the builder you would add to it for a feature of your own.

## Next steps

- [How the macros work](/codebase/macros/): what `#[derive(IntoElement)]` generates for every component in this crate.
- [Elements](/deep-dive/elements/) and [Views and render](/deep-dive/views-and-render/): the concepts behind `RenderOnce` and `Render`.
- [Styling](/guides/styling/): the `Styled` methods used throughout `ui`.

<details>
<summary>Where this lives in the source</summary>

- `crates/ui/src/ui.rs`, `prelude.rs`, `components.rs`
- `crates/ui/src/components/button/` (`button.rs`, `button_like.rs`, `icon_button.rs`)
- `crates/ui/src/components/label/`, `list/list_item.rs`, `tooltip.rs`, `context_menu.rs`, `popover_menu.rs`, `toggle.rs`, `data_table.rs`
- `crates/ui/src/traits/` (`clickable.rs`, `disableable.rs`, `toggleable.rs`, `styled_ext.rs`, ...)
- `crates/ui/src/styles/` (`color.rs`, `spacing.rs`, `elevation.rs`, `typography.rs`)
- `crates/ui/Cargo.toml`
</details>
