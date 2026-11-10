---
title: How input finds your code
description: Follow a mouse click or a keystroke from the operating system to your listener, through hit testing, the dispatch tree, the keymap, actions and focus.
sidebar:
  order: 6
  label: How input finds your code
---

This page follows an input event, such as a click or a key press, from the operating system to the closure you wrote. It covers hit testing, mouse listeners, the keymap, actions and focus. It was read from commit `b5cd310b`. The data structures used here are built while a frame is drawn, so [How a frame is drawn](/codebase/frame-lifecycle/) is the page to read first.

## What you'll learn

- How every OS event becomes one type, `PlatformInput`.
- How GPUI decides which element is under the mouse (hit testing) and who gets the click.
- How a keystroke is matched against key bindings and turned into an *action*.
- How focus decides where keystrokes go.
- Why action handlers and mouse handlers have opposite default propagation.

:::note[Advanced]
This page is for readers who have used `on_click`, `on_action` and key bindings (see [Actions and keybindings](/guides/actions-and-keybindings/), [Focus](/guides/focus/) and [Events and interaction](/guides/events-and-interaction/)) and want to know what happens underneath. It defines each internal term when it first appears.
:::

:::tip[In short]
1. Every backend turns native input into one enum, `PlatformInput`. `Window::dispatch_event` then routes it: mouse events to a flat list of listeners, keyboard events through the dispatch tree and keymap.
2. Mouse hit testing is a linear scan over the hitboxes recorded when the frame was painted. It is not a spatial tree.
3. Keystrokes reach your code through the **focused** element. An action handler on an element only fires if that element or one of its descendants has focus.
:::

## The route at a glance

```text
OS event
  |  (backend: Win32 message / NSEvent / Wayland or X11 event / DOM event / UIKit touch)
  v
PlatformInput                      interactive.rs   one enum for all backends
  |
  v
PlatformWindow::on_input callback  registered in Window::new
  |
  v
Window::dispatch_event             window.rs
  |-- mouse-ish events  --> dispatch_mouse_event  --> flat list of mouse listeners (hitbox checks inside)
  |-- keyboard events   --> dispatch_key_event    --> DispatchTree + Keymap --> actions / key listeners
  `-- touch events      --> dispatch_touch_event  --> gesture recognizer --> synthesized mouse/scroll events
  |
  v
DispatchEventResult { propagate, default_prevented }   returned to the platform
```

Terms you will meet:

- A **listener** is a closure GPUI calls when an event happens, such as the one you pass to `.on_click(...)`.
- A **hitbox** is a rectangle recorded during drawing that says "the mouse can hit me here".
- A **key context** is a label such as `"Editor"` that an element attaches to itself, so key bindings can apply only inside it.
- An **action** is a named command (for example `Undo`) that a keystroke maps to.
- **Focus** is which element receives keyboard input right now.

## 1. Backends turn native events into `PlatformInput`

`PlatformInput` (`crates/gpui/src/interactive.rs`) is the single type every backend turns native input into:

```rust
pub enum PlatformInput {
    KeyDown(KeyDownEvent), KeyUp(KeyUpEvent), ModifiersChanged(ModifiersChangedEvent),
    MouseDown(MouseDownEvent), MouseUp(MouseUpEvent), MousePressure(MousePressureEvent),
    MouseMove(MouseMoveEvent), MouseExited(MouseExitEvent),
    Scroll(ScrollEvent), Pinch(PinchEvent),
    LongPress(LongPressEvent), TouchDrag(TouchDragEvent), BackGesture(BackGestureEvent),
    FileDrop(FileDropEvent), Touch(TouchEvent),
}
```

Where the translation happens (all verified by reading the files):

| Backend | Translation point |
| --- | --- |
| macOS | `platform_input_from_native` in `gpui_macos/src/events.rs` (maps `NSEvent` to `PlatformInput`, including `parse_keystroke` and layout handling). |
| Windows | `handle_msg` in `gpui_windows/src/events.rs`, called from `window_procedure` in `window.rs`; e.g. `handle_mouse_move_msg`, `handle_key_event`. |
| Linux | `WaylandWindowStatePtr::handle_input` (`wayland/window.rs`) is called from the Wayland client dispatch code; X11 does the equivalent from X events in `x11/client.rs`. Keyboard translation uses `xkbcommon`. |
| Web | `gpui_web/src/events.rs` (DOM events), `ime_mirror.rs` (IME). |
| iOS | `gpui_ios/src/ios/events.rs`, `text_input.rs`; touches are delivered raw as `PlatformInput::Touch`. |

Each backend then calls the callback that GPUI installed on the platform window: `platform_window.on_input(Box::new(move |event| handle.update(&mut cx, |_, window, cx| window.dispatch_event(event, cx))...))` (in `Window::new`). The callback's return type is `DispatchEventResult { propagate, default_prevented }`. Backends use it: the Wayland `handle_input` returns early if `!result.propagate`, and otherwise falls back to inserting `key_char` into the platform input handler for plain/shift-only `KeyDown`s.

Keyboard events carry a `Keystroke` (`platform/keystroke.rs`): `modifiers: Modifiers`, `key: String` (the logical key), `key_char: Option<String>` (text this press would insert). `Keystroke::parse("cmd-shift-p")` is the inverse used by bindings.

## 2. `Window::dispatch_event`

`dispatch_event` (`window.rs`) is the first thing that runs on the foreground thread:

1. Records `last_input_modality` (`Keyboard` for `KeyDown`; `Mouse` for `MouseMove`/`MouseDown`; `Touch`) and calls `refresh()` when it changes, because hover styles are suppressed under keyboard modality.
2. Sets `cx.propagate_event = true` and `self.default_prevented = false`.
3. Updates `mouse_position` and `modifiers` from the event. File drops are rewritten as mouse events plus an `AnyDrag` carrying the paths (`FileDropEvent::Entered/Pending/Submit/Exited/Ended`).
4. Routes by type: `event.mouse_event()` -> `dispatch_mouse_event`; `event.keyboard_event()` -> `dispatch_key_event`; `event.touch_event()` -> `dispatch_touch_event`.
5. Notes whether the event invalidated the window (`invalidator.update_count()` increased) for the input-rate tracker that keeps presenting briefly after high-rate input.

`cx.stop_propagation()` sets `App::propagate_event = false`; `cx.propagate()` sets it to `true`. `Window::prevent_default()` sets `default_prevented`, which the built-in focus-on-click listener checks.

## 3. Hit testing: what is under the pointer?

A *hit test* answers "which elements are under the mouse right now?". Here it is a plain scan over a list.

Hit testing is **linear and happens after the fact**, not in a spatial tree.

During `prepaint`, elements call `Window::insert_hitbox(bounds, behavior)`, which records a `Hitbox { id, bounds, content_mask, behavior }` in `next_frame.hitboxes` in tree (back-to-front paint) order. `HitboxId` is a monotonically increasing `u64` (`next_hitbox_id`).

`Frame::hit_test(position)` (`window.rs`):

```rust
for hitbox in self.hitboxes.iter().rev() {            // front-most first
    let bounds = hitbox.bounds.intersect(&hitbox.content_mask.bounds);
    if bounds.contains(&position) {
        hit_test.ids.push(hitbox.id);
        if !set_hover_hitbox_count && hitbox.behavior == HitboxBehavior::BlockMouseExceptScroll {
            hit_test.hover_hitbox_count = hit_test.ids.len();
            set_hover_hitbox_count = true;
        }
        if hitbox.behavior == HitboxBehavior::BlockMouse { break; }
    }
}
if !set_hover_hitbox_count { hit_test.hover_hitbox_count = hit_test.ids.len(); }
```

The result is a `HitTest { ids: SmallVec<[HitboxId; 8]>, hover_hitbox_count }`: all hitboxes under the pointer, front-most first, truncated at the first `BlockMouse`. `HitboxBehavior` has three values (`Normal`, `BlockMouse`, `BlockMouseExceptScroll`); `InteractiveElement::occlude` sets `BlockMouse`.

Two views of that result:

- `HitboxId::is_hovered(window)` (and `Hitbox::is_hovered`): true if the id is among the first `hover_hitbox_count` ids, or the hitbox has captured the pointer (`Window::capture_pointer`, released automatically on mouse up). It returns `false` under keyboard modality.
- `HitboxId::should_handle_scroll(window)`: true if the id is anywhere in `ids` (so a scroll container behind a `BlockMouseExceptScroll` overlay still scrolls).

The hit test is recomputed at the start of `dispatch_mouse_event` from `rendered_frame` and once at the end of prepaint in `draw_roots` (`self.mouse_hit_test = self.next_frame.hit_test(self.mouse_position)`, used for hover styles while painting).

:::note[`bounds_tree.rs` is not hit testing]
`crates/gpui/src/bounds_tree.rs` is an R-tree used by `Scene` to assign z-order to painted primitives. Despite the name, hit testing does not use it; it iterates `Frame::hitboxes`.
:::

## 4. Mouse dispatch: who gets the click?

Mouse listeners are **not** stored per element in a tree. During `paint`, `Window::on_mouse_event::<E>(listener)` pushes a type-erased closure onto one flat `Vec<Option<AnyMouseListener>>`, `next_frame.mouse_listeners`, in paint order (parents before children). `Div`'s `paint_mouse_listeners` registers one closure per `.on_mouse_down(...)`, `.on_click(...)`, `.on_hover(...)`... each capturing a clone of the element's `Hitbox`. The closure itself decides whether it applies. For example `Interactivity::on_mouse_down` is:

```rust
move |event, phase, hitbox, window, cx| {
    if phase == DispatchPhase::Bubble && event.button == button && hitbox.is_hovered(window) {
        listener(event, window, cx)
    }
}
```

`Window::dispatch_mouse_event(event, cx)`:

1. `self.mouse_hit_test = self.rendered_frame.hit_test(self.mouse_position())`.
2. If the inspector is picking, route the event there and return.
3. Take the listener vector out of `rendered_frame.mouse_listeners` (so listeners can register more without borrowing).
4. **Capture phase**: iterate in registration order calling `listener(event, DispatchPhase::Capture, ...)`; stop if `!cx.propagate_event`.
5. **Bubble phase** (if still propagating): iterate in **reverse** registration order with `DispatchPhase::Bubble`. Because children were registered after parents, reverse order visits the front-most element first, which is bubbling.
6. Put the vector back. If a drag is active: a `MouseMoveEvent` triggers `refresh()` so the drag preview follows the cursor, and a `MouseUpEvent` clears `cx.active_drag` and refreshes.
7. On mouse up, release any pointer capture.
8. `reset_cursor_style(cx)` after listeners ran, so a drag started by a listener affects the cursor in the same event.

`DispatchPhase` is `Capture` or `Bubble`. Typical listeners ignore `Capture`; the `_out` variants (`on_mouse_down_out`) use it to detect clicks outside an element.

`ClickEvent` (an enum with `Mouse`, `Keyboard` and `Touch` variants in `interactive.rs`) is synthesised by `Div` (mouse down and up on the same hitbox, keyboard activation, or a recognised tap) rather than delivered by the platform.

Touch input takes a parallel route: `dispatch_touch_event` feeds `TouchEvent`s to `TouchGestureRecognizer` (`gestures.rs`), which produces taps (synthesised mouse press/release so ordinary click listeners work), pans (synthesised `ScrollEvent`s with momentum), long presses and back gestures, then dispatches them.

## 5. The `DispatchTree`: a map for keyboard input

Mouse events find their target by position. Keyboard events have no position, so GPUI needs another structure: the *dispatch tree*, a tree of nodes that mirrors the element tree and records key contexts and key and action listeners.

`DispatchTree` (`crates/gpui/src/key_dispatch.rs`) is built every frame alongside the element tree and lives in `Frame::dispatch_tree`:

```rust
pub(crate) struct DispatchTree {
    node_stack: Vec<DispatchNodeId>,
    pub(crate) context_stack: Vec<KeyContext>,
    view_stack: Vec<EntityId>,
    nodes: Vec<DispatchNode>,
    focusable_node_ids: FxHashMap<FocusId, DispatchNodeId>,
    view_node_ids: FxHashMap<EntityId, DispatchNodeId>,
    keymap: Rc<RefCell<Keymap>>,
    action_registry: Rc<ActionRegistry>,
}
pub(crate) struct DispatchNode {
    key_listeners, action_listeners, modifiers_changed_listeners,
    context: Option<KeyContext>, focus_id: Option<FocusId>, view_id: Option<EntityId>,
    parent: Option<DispatchNodeId>,
}
```

How it is populated:

- **Prepaint**: `Drawable::prepaint` calls `push_node()` before and `pop_node()` after each element's `prepaint`, so there is one node per element, with `parent` links following the element tree. Elements call `set_focus_handle` (-> `set_focus_id`, records `focusable_node_ids`) and `set_view_id` here.
- **Paint**: `Drawable::paint` calls `set_active_node(node_id)` with the node created in prepaint. While painting, `Window::set_key_context(KeyContext)`, `Window::on_key_event`, `Window::on_modifiers_changed` and `DispatchTree::on_action` attach to the *active node*.
- **Reuse**: cached views copy their subtree from the previous frame with `reuse_subtree`, which returns a `ReusedSubtree` that remaps node ids.

`DispatchNodeId` is an index only, and is documented as unstable between frames. `dispatch_path(target)` walks `parent` links and returns root-to-target. `focus_path(focus_id)` does the same collecting only nodes that have a `focus_id`. `view_path_reversed(view_id)` walks up collecting `view_id`s and is what `Window::mark_view_dirty` uses to dirty ancestor views.

Key point: the dispatch path is derived from the **focused node** (`Window::focus_node_id_in_rendered_frame`), falling back to the root node if nothing is focused. That is why an action handler on an element only fires if that element or a descendant has focus.

## 6. Focus: where keystrokes go

- `FocusHandle` (`window.rs`): `id: FocusId`, `handles: Arc<RwLock<FocusMap>>`, plus `tab_index` and `tab_stop`. Cloning increments a ref count in the `FocusMap`; dropping the last handle marks the id in `dropped_handles`, which `App::release_dropped_focus_handles` processes in `flush_effects` (blurring any window whose focus pointed at it).
- `Window::focus(&handle, cx)` sets `self.focus = Some(handle.id)`, bumps `focus_generation`, clears pending multi-key input and calls `refresh()`. `Window::blur` clears it.
- An element becomes focusable by `.track_focus(&handle)` (`InteractiveElement`), which at prepaint calls `Window::set_focus_handle`; that records `next_frame.focus = Some(id)` **only if the handle is currently focused** (`focus_handle.is_focused(self)`) and registers the node in `focusable_node_ids`. A focusable `Div` also registers a mouse-down listener that focuses it (suppressed by `prevent_default`).
- After the frame swap, `Window::draw` compares the old and new `focus_path()` and window-active state and fires `focus_listeners` with a `WindowFocusEvent`. The listener-registration APIs `Context::on_focus`, `on_blur`, `on_focus_in`, `on_focus_out` and `Window::on_focus_in` / `on_focus_out` are built on this, and the `focus` / `in_focus` / `focus_visible` style refinements on `Div` read the same focus state.
- Tab navigation uses `Frame::tab_stops: TabStopMap` (`tab_stop.rs`), populated during prepaint with `tab_index`/`tab_stop`.
- `Focusable` (`window.rs`) is the trait views implement (`fn focus_handle(&self, cx) -> FocusHandle`) so others can focus them.

## 7. Keystrokes: from key press to action

`Window::dispatch_key_event(event, cx)` (`window.rs`), in order:

1. If `invalidator.is_dirty()`, draw first (`self.draw(cx).clear(cx)`) so the dispatch tree matches the screen.
2. Compute `node_id` (focused node or root) and `dispatch_path`.
3. Modifier-only presses: for `ModifiersChangedEvent`, if one modifier was pressed and released with no other input in between, synthesise a `Keystroke` whose key is `"shift"`, `"control"`, `"alt"`, `"platform"` or `"function"`. This allows bindings like `shift shift`.
4. For `KeyDown`, take `event.keystroke`; hide the cursor if configured (`CursorHideMode`).
5. Decide `InputPreference`: if the event says `prefer_character_input` and the platform input handler `accepts_text_input`, character input wins and key bindings are skipped (so typing `AltGr` characters in a text field works).
6. Run `dispatch_keystroke_interceptors` (`cx.intercept_keystrokes`). If an interceptor stops propagation, jump to step 11.
7. Merge with `pending_input` (earlier keystrokes of a multi-stroke binding, dropped if focus changed) and call `DispatchTree::dispatch_key(pending, keystroke, &dispatch_path)`.
8. If the result has `to_replay`, call `replay_pending_input` (re-dispatch earlier keystrokes that turned out not to start a binding).
9. If the result has `pending`, store it in `window.pending_input` with a timeout (`PENDING_INPUT_TIMEOUT` = 1 second, `new_pending_input_timeout`), call `pending_input_changed` observers, set `propagate_event = false`, and return. When the timer fires, `flush_dispatch` converts pending input into replays.
10. Otherwise, if preference is `KeyBindings`, for each matched binding call `dispatch_action_on_node(node_id, binding.action, cx)`; if an action handler stops propagation, notify keystroke observers and return.
11. `finish_dispatch_key_event`: raw key listeners (`dispatch_key_down_up_event`: capture pass root-to-focus, then bubble pass focus-to-root over `node.key_listeners`), then `dispatch_modifiers_changed_event`, then keystroke observers (`cx.observe_keystrokes`).

So **actions run before raw `on_key_down` listeners**, and a handled action prevents them.

### `DispatchTree::dispatch_key`

```rust
input.push(keystroke);
let (bindings, pending, context_stack) = self.bindings_for_input(&input, dispatch_path);
if pending       { return DispatchResult { pending: input, pending_has_binding: !bindings.is_empty(), .. } }
else if !bindings.is_empty() { return DispatchResult { bindings, .. } }
else if input.len() == 1     { return DispatchResult { .. /* nothing */ } }
input.pop();
let (suffix, mut to_replay) = self.replay_prefix(input, dispatch_path);
let mut result = self.dispatch_key(suffix, keystroke, dispatch_path);  // retry with the shorter prefix
```

`bindings_for_input` builds the **context stack** from the dispatch path: `dispatch_path.iter().filter_map(|id| self.node(*id).context.clone())`, ordered root to focus, then asks `Keymap::bindings_for_input(input, &context_stack)`.

### `Keymap`

`keymap.rs` stores `bindings: Vec<KeyBinding>` in insertion order, `binding_indices_by_action_id`, `disabled_binding_indices` and a `version`. `KeyBinding` (`keymap/binding.rs`) holds a `Box<dyn Action>`, parsed `keystrokes`, an optional `context_predicate: Rc<KeyBindingContextPredicate>`, and metadata. `KeyBinding::new("cmd-k left", MyAction, Some("Editor"))` parses with `Keystroke::parse` and panics on bad input; `KeyBinding::load` returns a `Result` and resolves `secondary-`.

`Keymap::resolve_bindings_for_input` (the heart):

1. Walk bindings in **reverse insertion order**, so later bindings win ties.
2. Skip a binding unless `binding_enabled` returns a depth: `predicate.depth_of(contexts)` returns the **deepest** prefix of the context stack at which the predicate matches (`None` if none); a binding without a predicate matches at `contexts.len()`.
3. `KeyBinding::match_keystrokes(typed)` returns `None` (no match), `Some(false)` (complete match) or `Some(true)` (typed is a proper prefix: the binding is *pending*).
4. Complete matches are sorted by depth descending, then index descending. So a binding in a deeper (more focused) context beats a shallower one, regardless of insertion order.
5. `NoAction` bindings suppress matching bindings from equal-or-weaker sources; `Unbind` suppresses the named action for those keystrokes. Both are applied here.
6. The second tuple element tells the caller whether any non-suppressed pending binding exists.

`KeyBindingContextPredicate` (`keymap/context.rs`) is the small expression language: `Identifier`, `Equal(key, value)`, `NotEqual`, `Not`, `And`, `Or`, and `Descendant(parent, child)` (the `>` operator). A `KeyContext` is the set of identifiers and `key=value` pairs an element declares with `.key_context("Editor mode=full")`. `KeyContext::new_with_defaults(os)` adds an `os` entry (`macos`, `linux`, `windows`, `ios`, `android`).

## 8. Actions: named commands

An action is a type implementing the `Action` trait (`action.rs`): `boxed_clone`, `partial_eq`, `name`, `name_for_type`, `build(json)`, plus optional `action_json_schema`, `deprecated_aliases`, `deprecation_message`, `documentation`.

### Registration without a central list

`#[derive(Action)]` (`gpui_macros/src/derive_action.rs`) and `actions!(namespace, [A, B])` generate `impl Action` and call `generate_register_action`, which emits, inside a hidden `fn __autogenerated()` on the type:

```rust
gpui::private::inventory::submit! { gpui::MacroActionBuilder(__gpui_actions_builder_<lowercase type name>) }
```

`inventory` collects all such submissions across the linked binary at startup. `ActionRegistry::default()` (created once in `App::new_app`) calls `load_actions()`, iterating `inventory::iter::<MacroActionBuilder>` and calling `insert_action`. The registry keeps `by_name`, `names_by_type_id`, `all_names`, `deprecated_aliases`, `deprecation_messages` and `documentation`. A duplicate name **panics** at app creation:

```text
Action with name `{name}` already registered (might be registered in `#[action(deprecated_aliases = [...])]`.
```

This registry is what lets a keymap file say `"cmd-s": "workspace::Save"` or `["editor::SelectNext", { "replace_newest": true }]`: `ActionRegistry::build_action(name, json)` looks up the builder and deserialises. `KeyBinding::new` bypasses it by taking a typed value. `#[action(no_register)]` skips the `inventory` submission; `#[action(no_json)]` makes `build` always fail. `Action` names are `namespace::Name`; the namespace is optional unless you need to refer to it from JSON.

### Listeners

`div().on_action(cx.listener(Editor::undo))` records an action listener on the element; at paint it calls `DispatchTree::on_action(TypeId, Rc<dyn Fn(&dyn Any, DispatchPhase, &mut Window, &mut App)>)` for the active node. `Window::dispatch_action_on_node_inner(node_id, action, cx)`:

```text
1. global action listeners, Capture phase        (cx.on_action(...) registered on App)
2. window nodes root -> focus, Capture           (node.action_listeners where type matches)
3. window nodes focus -> root, Bubble            (cx.propagate_event = false BEFORE each call)
4. global action listeners, Bubble (reverse)     (propagate_event = false before each call)
```

Step 3's behaviour is the unusual one: in the bubble phase `propagate_event` is set to `false` before each listener runs, so **an action handler consumes the action unless it calls `cx.propagate()`**. (Mouse listeners are the opposite: they propagate unless they call `cx.stop_propagation()`.) The docs in `App::stop_propagation` / `App::propagate` say the same.

`Window::dispatch_action(action, cx)` (also exposed as `cx.dispatch_action`) uses `cx.defer`, so the dispatch runs at the end of the current effect cycle, from the currently focused node. `App::dispatch_action` picks the active window or falls back to global listeners only. `App::is_action_available` and `DispatchTree::available_actions` implement menu-item enabled state from the same tree.

## 9. Text input and IME

An *IME* (input method editor) is the operating system feature that composes characters, for example typing Japanese or accented letters.

Keystrokes that should insert text go through the platform's input method, not key bindings. An element that edits text calls `Window::handle_input(&focus_handle, input_handler, cx)` during paint (it only registers if the handle is focused); `input_handler` is typically `ElementInputHandler::new(bounds, entity)` over an `EntityInputHandler` implementation (`input.rs`). `Window::draw` takes the last registered handler from `next_frame.input_handlers`, hands it to the platform with `platform_window.set_input_handler`, and tracks whether the focused element accepts text input so `dispatch_key_event` can choose `InputPreference::CharacterInput`. After application-driven edits call `Window::notify_text_input_changed` and `notify_text_selection_changed` so native text services stay in sync.

## 10. Try it yourself: follow a click

These are reading exercises. Open these in order and answer the question at each stop. Nothing here changes the repository.

1. `gpui_windows/src/events.rs`, `handle_mouse_move_msg` (or `gpui_macos/src/events.rs::platform_input_from_native`): what struct is built and what does it carry?
2. `Window::new` in `window.rs`, `platform_window.on_input`: what does the closure call?
3. `Window::dispatch_event` and `dispatch_mouse_event`: which field is recomputed first?
4. `Frame::hit_test`: why does iterating in reverse give the correct front-most element?
5. `Interactivity::paint_mouse_listeners` in `elements/div.rs`: where does `hitbox.is_hovered(window)` come from?
6. `Interactivity::on_click` and `ClickEvent`: how does a click get built out of a down and an up?
7. What did your listener call that eventually reached `Window::draw`? (`cx.notify()`, then [How a frame is drawn](/codebase/frame-lifecycle/).)

For the keyboard side:

8. In `Window::dispatch_key_event`, find the line that decides between `InputPreference::CharacterInput` and key bindings. When does text win?
9. In `Keymap::resolve_bindings_for_input`, find the sort that orders complete matches. Write one sentence on why a deeper context wins.
10. In `dispatch_action_on_node_inner`, find where `cx.propagate_event = false` is set before each bubble-phase listener. Compare with the mouse listener loop in `dispatch_mouse_event`.

## Next steps

- [How GPUI talks to your OS](/codebase/platform-backends/): the backend side of step 1, per operating system.
- [How the macros work](/codebase/macros/): what `#[derive(Action)]` and `actions!` generate, which feeds the registry in section 8.
- [Actions and keybindings](/guides/actions-and-keybindings/): the user-facing guide to the same machinery.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/interactive.rs` (`PlatformInput`, event structs, `ClickEvent`)
- `crates/gpui/src/window.rs` (`dispatch_event`, `dispatch_mouse_event`, `dispatch_key_event`, `Frame::hit_test`, `Hitbox`, `FocusHandle`, `dispatch_action_on_node_inner`)
- `crates/gpui/src/key_dispatch.rs` (`DispatchTree`, `dispatch_key`)
- `crates/gpui/src/keymap.rs`, `crates/gpui/src/keymap/binding.rs`, `crates/gpui/src/keymap/context.rs`
- `crates/gpui/src/action.rs`, `crates/gpui/src/input.rs`, `crates/gpui/src/gestures.rs`, `crates/gpui/src/tab_stop.rs`
- `crates/gpui/src/elements/div.rs` (`paint_mouse_listeners`)
- `crates/gpui_macros/src/derive_action.rs`
- backends: `gpui_macos/src/events.rs`, `gpui_windows/src/events.rs`, `gpui_linux/src/linux/wayland/window.rs`, `gpui_web/src/events.rs`, `gpui_ios/src/ios/events.rs`
</details>
