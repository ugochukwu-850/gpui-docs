---
title: How a frame is drawn
description: Follow one click on a counter button from the mouse to the pixels, step by step, with the function and file for every step.
sidebar:
  order: 4
  label: How a frame is drawn
---

This page follows one click all the way through GPUI: from the mouse button, through your code, to the new pixels on screen. If you read only one page of the Codebase tour, read this one. Nearly everything else in GPUI hangs off this path.

Everything here was read from commit `b5cd310b`. Line numbers are left out on purpose, because they drift. Function and type names are the reliable handle: search for them with `rg`.

## What you'll learn

- The 12 steps between "the user clicked" and "the new number is on screen", with the function and file for each.
- Why GPUI queues work instead of doing it immediately, and why it keeps two frames.
- What `request_layout`, `prepaint` and `paint` are, and why there are three phases.
- How the drawn result (the *scene*) reaches the graphics card.
- Where to look when the screen does not update.

:::note[Advanced]
This page is for readers who finished the [Counter tutorial](/tutorials/counter/) and wonder what happens after `cx.notify()`. You need to know what a view, `Render` and `cx.notify()` are. The page introduces every other term when it first appears. For a version without file names, see [The big picture](/deep-dive/big-picture/).
:::

:::tip[In short]
1. `cx.notify()` does not draw anything. It marks the window as *dirty* and queues a note. Drawing happens later, when the operating system next asks for a frame.
2. To draw, GPUI runs your `render` function, lays the result out, works out where the mouse can hit, and records shapes in a *scene*. The graphics backend then draws the scene.
3. GPUI keeps two frames: the one on screen (used to answer clicks) and the one being built.
:::

## Words you need first

These terms appear in every step. Skim the table now and come back to it as often as you like.

| Term | Plain meaning |
| --- | --- |
| **Entity** | A piece of state owned by GPUI. You hold a handle (`Entity<T>`) to it. Your `Counter` is an entity. |
| **View** | An entity that implements `Render`, so it can draw itself. GPUI's version of a component with state. |
| **Element** | A throwaway description of part of the UI, such as a `div`. Your `render` builds a tree of them every frame. |
| **Frame** | Everything GPUI builds for one picture of the window: the drawing, the hit areas, the listeners. |
| **Dirty** | "This window needs a new frame." |
| **Effect** | A queued to-do item, such as "tell the observers of this entity that it changed". |
| **Hitbox** | A rectangle that says "the mouse can hit me here". Hover and click use hitboxes. |
| **Scene** | The list of rectangles, shadows, glyphs and images to draw, in a form every graphics backend understands. |
| **Backend** | The crate that talks to one operating system (see [How GPUI talks to your OS](/codebase/platform-backends/)). |

## The example: a click on the counter

We use the counter from the [Counter tutorial](/tutorials/counter/). It has a view and a button. This is the only code you need for the walk-through:

```rust
struct Counter {
    count: i32,
}

impl Render for Counter {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        div()
            // ... layout and style, as in the tutorial
            .child(format!("Count: {}", self.count))
        // ... buttons are children too
    }
}
```

and the handler on the Increment button:

```rust
button("Increment").on_click(cx.listener(|this, _event, _window, cx| {
    this.count += 1;
    cx.notify();
}))
```

The window shows `Count: 0`. You press and release the mouse on **Increment**. A moment later the window shows `Count: 1`. The 12 steps below are what happens in between.

:::note[A click is two events, so usually two frames]
When the mouse button goes down on an element with a click listener, `Div` remembers the press and calls `window.refresh()`, which marks the window dirty (so a pressed style can show). The click listener fires later, on mouse **up**. This page follows the mouse-up, because that is the event that changes `count`.
:::

## The whole path at a glance

The numbers match the headings below. Each line names the function and the file where it happens.

```text
PART A: the click becomes "this window is dirty"
(runs on the main thread, inside ONE call into App)

 [1] OS reports mouse-up         backend: e.g. gpui_macos/src/events.rs
      |                          platform_input_from_native -> PlatformInput
      v
 [2] Window::dispatch_event      window.rs
      |  -> dispatch_mouse_event   hit test, then capture + bubble listeners
      v
 [3] your click closure          elements/div.rs  paint_mouse_listeners
      |                          app/context.rs   Context::listener
      |  count += 1              (Counter is leased from the EntityMap)
      v
 [4] cx.notify()                 app/context.rs   Context::notify
      |  -> App::notify          app.rs
      |  -> WindowInvalidator::invalidate_view     window.rs
      |        dirty = true, dirty_views += Counter, Effect::Notify queued,
      |        platform "waker" called
      v
 [5] outermost update ends       app.rs   finish_update -> flush_effects
         observers run; queue empty -> PlatformWindow::schedule_frame()

PART B: the dirty window becomes pixels
(a later turn of the platform's event loop)

 [6] platform frame source fires    vsync / wl_surface.frame / display link /
      |                             requestAnimationFrame
      |  -> on_request_frame callback          window.rs  (set up in Window::new)
      v
 [7] Window::draw                  window.rs   set the stage
      |   ElementArenaScope::enter, invalidate_entities, clear_accessed
      v
     Window::draw_roots            window.rs
 [8]    phase 1  request_layout    element.rs, view.rs   Counter::render RUNS HERE
      |         + compute_layout   taffy.rs              (sizes and positions)
 [9]    phase 2  prepaint          element.rs            hitboxes, dispatch nodes
 [10]   phase 3  paint             element.rs            Scene primitives, listeners
      v
 [11] finish the frame             window.rs   Frame::finish, swap frames,
      |                            record_entities_accessed
      v
 [12] Window::present              window.rs
         -> PlatformWindow::draw(&Scene)   backend renderer -> GPU -> screen
         -> arena cleared
```

Part A is quick and happens right inside the input event. Part B happens when the operating system is ready for a new picture, usually once per screen refresh.

## Part A: from click to dirty window

### Step 1. The operating system reports the click

**What happens.** Your operating system tells the GPUI backend that the mouse button went up. The backend turns that native event into a `PlatformInput::MouseUp(...)` value. Every backend produces this one type, so the rest of GPUI does not care which OS it is on.

**Where in the code.**

- macOS: `platform_input_from_native` in `crates/gpui_macos/src/events.rs`.
- Windows: `handle_msg` in `crates/gpui_windows/src/events.rs`.
- Linux: `handle_input` in `crates/gpui_linux/src/linux/wayland/window.rs` (X11 does the same from `x11/client.rs`).
- The enum itself: `PlatformInput` in `crates/gpui/src/interactive.rs`.

The backend then calls the callback GPUI installed with `PlatformWindow::on_input` (in `Window::new`, `crates/gpui/src/window.rs`). That callback runs `handle.update(&mut cx, |_, window, cx| window.dispatch_event(event, cx))`.

**Why it is designed this way.** GPUI's core never calls an OS function. It registers callbacks, and each backend calls them. That is what lets one framework run on five platforms. The full list of per-backend translation points is in [How input finds your code](/codebase/input-and-dispatch-internals/).

### Step 2. The window decides who gets the event

**What happens.** `Window::dispatch_event` looks at the event and routes it. A mouse event goes to `dispatch_mouse_event`. That function:

1. Runs a *hit test*: it finds every hitbox under the pointer, front-most first.
2. Takes the window's one flat list of mouse listeners.
3. Calls each listener once in the **capture** phase (in registration order), and, if nobody stopped it, once in the **bubble** phase (in reverse order, so the front-most element goes first).

**Where in the code.** `Window::dispatch_event` and `Window::dispatch_mouse_event` in `window.rs`, and `Frame::hit_test` in the same file.

**Why it is designed this way.** Notice that dispatch reads `rendered_frame`: the frame that is **already on screen**. The listeners and hitboxes it uses were recorded when the frame was painted (step 10). So a click always goes to what the user can actually see, even if your state has changed since. That is also why GPUI keeps two frames; see step 11.

### Step 3. Your closure runs

**What happens.** One of the mouse listeners is the click handler that `Div` registered for the Increment button. On mouse-up, in the capture phase, it checks that it remembers a mouse-down and that the pointer is still over its hitbox. In the bubble phase it builds a `ClickEvent` from the earlier mouse-down and this mouse-up, and calls your `on_click` closure. That closure is the one `cx.listener` made.

`cx.listener` holds a *weak* handle to your `Counter`. When called, it does `view.update(cx, ...)`. `update` takes the `Counter` **out of GPUI's entity storage** for the duration of your closure (a *lease*) and hands you `&mut Counter` and a `Context<Counter>`. Your code runs: `this.count += 1`.

**Where in the code.**

- `Interactivity::paint_mouse_listeners` in `crates/gpui/src/elements/div.rs`: the mouse-up listener that builds `ClickEvent::Mouse` and loops over `click_listeners`.
- `Context::listener` and `invoke_listener` in `crates/gpui/src/app/context.rs`.
- `Entity::update` leads to `App::update_entity_erased` in `app.rs` and `lease_erased` in `app/entity_map.rs`. [How state is stored and updated](/codebase/app-and-entity-internals/) covers leasing in depth.

**Why it is designed this way.** `on_click` takes a plain closure with no access to your view, so `cx.listener` bridges the gap. The weak handle means a pending listener does not keep a closed view alive. If the view is gone, `update` returns an error and the listener ignores it.

### Step 4. `cx.notify()` marks the window dirty

**What happens.** `Context::notify` is one line: it calls `App::notify(entity_id)`. That function asks, "Is any window currently *showing* this entity?"

During every draw, GPUI records which entities were read or leased (more in step 11). The result is stored per window in `App::tracked_entities`. A reverse map, `App::window_invalidators_by_entity`, maps an entity to a `WindowInvalidator` for each window that showed it. A *window invalidator* is a small shared object that holds the window's dirty flag. `App::notify` keeps only the invalidators whose window still tracks the entity, then:

- **if any window shows the entity** (our case): calls `WindowInvalidator::invalidate_view(entity_id, cx)` on each;
- **otherwise**: pushes `Effect::Notify { emitter }` directly (deduplicated through `App::pending_notifications`), so that `cx.observe` callbacks still run.

`invalidate_view` does four things, but only when the window is not in the middle of a draw (`draw_phase == DrawPhase::None`):

1. inserts the entity into `dirty_views`;
2. sets `dirty = true`;
3. pushes `Effect::Notify { emitter: entity }` onto the app's effect queue, so observers of that entity run too;
4. if the window *newly became* dirty, calls the window's `platform_waker`. That is `PlatformWindow::frame_waker()`, which restarts a frame source that went to sleep while the window was idle.

Nothing has been drawn. The counter on screen still says `Count: 0`.

**Where in the code.** `Context::notify` in `app/context.rs`, `App::notify` in `app.rs`, `WindowInvalidator::invalidate_view` in `window.rs`.

**Why it is designed this way.** GPUI does not watch your struct's fields. It cannot know that `count` changed, so you tell it. Marking a flag is cheap, so you can call `notify` many times and still draw once.

:::note[Other things also mark a window dirty]
`Window::refresh()` sets `refreshing = true` and marks the window dirty (it does nothing while a draw is in progress). `Window::focus`, `Window::blur` and a change of input type (mouse versus keyboard) call it. `Effect::RefreshWindows` (`App::refresh_windows`) does it for every window. `refreshing` also forces every cached view to render again; see "Cached views" below.
:::

:::note[`notify` is not a re-render request for one view only]
Dirtiness is tracked per *window*, through the set of entities the window read while it last drew. So calling `notify` on any entity read during the last draw makes that window draw again. For ordinary (uncached) views the whole tree is rendered on that draw, so you do not need `cx.observe(...)` for rendering to follow state. Cached views are the exception.
:::

### Step 5. The effect queue flushes and a frame is requested

**What happens.** Your closure returns, and so do the nested calls around it. GPUI counts how many `App::update` calls are in progress (`pending_updates`). When the **outermost** one finishes, `finish_update` calls `flush_effects`. In our case, the outermost update is the window update that wraps `dispatch_event` from step 1.

`flush_effects` loops:

1. `release_dropped_entities()`: entities whose reference count reached zero are removed. Their observers and listeners go with them, and release listeners run one last time.
2. `release_dropped_focus_handles()`.
3. Pop one `Effect` from the queue and apply it. There are six variants: `Notify`, `Emit`, `RefreshWindows`, `NotifyGlobalObservers`, `Defer`, `EntityCreated`. Applying `Notify` runs every `cx.observe` callback for that entity.
4. When the queue is empty: for every window, if the window is dirty, or owes a present, or has next-frame callbacks, call `platform_window.schedule_frame()`. Then clear the event arena and stop.

`flush_effects` does **not** draw. The one exception is tests: in test mode (`GpuiMode::Test`) it draws dirty windows inline, so tests do not need a platform frame source.

**Where in the code.** `App::update`, `finish_update` and `flush_effects` in `crates/gpui/src/app.rs`.

**Why it is designed this way.** Observers and event handlers can call back into your entities. If they ran while your closure still held the `Counter` lease, they would find it missing. Queueing everything until the outermost update ends guarantees that every lease has been returned first. [How state is stored and updated](/codebase/app-and-entity-internals/) explains this in detail.

## Part B: from dirty window to pixels

### Step 6. The platform asks for a frame

**What happens.** Each backend has a *frame source*: something that fires roughly once per screen refresh. When it fires, it calls the callback GPUI registered with `PlatformWindow::on_request_frame`.

| Backend | Frame source (verified in the named file) |
| --- | --- |
| Wayland | `wl_surface.frame` callbacks: `WaylandWindowStatePtr::frame`, `frame_callback_fired`, `complete_frame` in `gpui_linux/src/linux/wayland/window.rs`. |
| macOS | `CAMetalDisplayLink` on macOS 14+, otherwise a shared `CVDisplayLink` registry: `gpui_macos/src/display_link.rs`, `FrameSource` in `gpui_macos/src/window.rs`. |
| Windows | A vsync provider based on DWM timing: `gpui_windows/src/vsync.rs`. |
| Web | `requestAnimationFrame`: `gpui_web/src/window.rs`. |
| iOS | `CADisplayLink`: `gpui_ios/src/ios/application.rs`. |

The callback is built in `Window::new` (search for `platform_window.on_request_frame`). It receives `RequestFrameOptions { require_presentation, force_render, signal_at, signal_source }` and does, in order:

1. **Re-entrancy guard.** If `draw_in_progress()` (an element arena scope is active), it defers the request and remembers `force_render`. This exists for Windows, where nested message pumping can request a frame in the middle of a draw.
2. **Pacing.** A `FramePacer` and `minimum_frame_interval(...)` enforce spacing between frames for inactive windows, low power mode and thermal state. A throttled request calls `schedule_frame()` again and returns.
3. **Next-frame callbacks.** Everything registered with `Window::on_next_frame` runs now.
4. **Draw if needed.** `should_draw = invalidator.is_dirty() || force_render`. If true: `window.draw(cx)`, then `window.present()`, then `arena_clear_needed.clear(cx)`. If false but a presentation is owed (`needs_present`), only `present()` runs.
5. **Keep going if needed.** If the window is still dirty or has pending next-frame callbacks (an animation, or an invalidation that happened during the draw), it calls `schedule_frame()` and wakes the platform again.

`Window::draw` is also called directly in three other places: from `App::open_window` (so the first frame exists before the handle is returned), from `Window::dispatch_key_event` when the window is dirty (so key dispatch sees an up-to-date dispatch tree), and from `flush_effects` in test mode.

**Where in the code.** The `on_request_frame` closure in `Window::new` in `window.rs`, plus the frame source files in the table.

**Why it is designed this way.** Drawing on demand, at the display's pace, means a window with nothing to show costs almost nothing. It also means ten `notify` calls in a row cost one frame, not ten. The pacing rules slow frames down for inactive windows, low power mode and thermal pressure.

### Step 7. `Window::draw` sets the stage

**What happens.** `Window::draw` produces a new frame and stores it in `rendered_frame`. It does not show it yet. It starts with five set-up actions:

1. `ElementArenaScope::enter(&cx.element_arena)`: from here on, elements are allocated in a *bump allocator*. A bump allocator hands out memory by moving a pointer forward, and frees everything at once by moving it back.
2. If `platform_window.prepare_frame()` says so, `refresh()`.
3. `invalidate_entities()`: for each dirty view (our `Counter`), mark it **and all of its ancestors** dirty. This uses `rendered_frame.dispatch_tree.view_path_reversed`.
4. `cx.entities.clear_accessed()`: start recording which entities `render` reads. Then `invalidator.set_dirty(false)`.
5. Hand the previous text-input handler back to the frame, so frames that reuse cached content find it where they expect it.

**Where in the code.** `Window::draw`, `invalidate_entities` and `ElementArenaScope` in `window.rs`; `clear_accessed` in `app/entity_map.rs`.

**Why it is designed this way.** Elements are created fresh every frame and thrown away together at the end. A bump allocator makes that cheap to allocate and cheap to free. The dirty flag is cleared at the start so that, once the frame is done, "dirty" again means "something changed since". That is what the follow-up check at the end of step 6 looks for.

### Step 8. Phase 1, `request_layout`: your `render` runs

**What happens.** `Window::draw_roots` sets `DrawPhase::Prepaint` and turns the window's root view into an element: `self.root.clone().into_any_element()`. That is a `ViewElement` (`view.rs`).

A *draw phase* is a stage of one frame in which only some methods are allowed. Every element goes through three phases, in this order, and each phase finishes for the whole tree before the next begins:

| Phase | Question the element answers |
| --- | --- |
| `request_layout` | "How much space do I want, and how do my children fit in me?" |
| `prepaint` | "Now that I know my exact position and size, where are my hit areas?" |
| `paint` | "What exactly do I draw, and what do I do on the next event?" |

For `Counter`, `ViewElement::request_layout` calls `request_layout_view`, then `render_view`, then `any_view::render::<V>`, then `Entity::update(...)`, and finally **your `Counter::render(&mut self, window, cx)`**. This is where the new count gets into the picture: `render` reads `self.count`, which is now 1, and builds `Count: 1`. The returned element tree is asked for its layout immediately.

Each element builds nodes in a *layout tree* and returns a `LayoutId`. `Div` calls `Window::request_layout(style, child_layout_ids, cx)`, which converts GPUI's `Style` into a taffy style (`impl ToTaffy for Style` in `taffy.rs`) and calls `TaffyLayoutEngine::request_layout`. Taffy is the layout library GPUI uses to implement flexbox. Text is a leaf whose size depends on its content, so it calls `Window::request_measured_layout(style, measure_fn)`. Taffy calls that measure function later while it solves the layout. That is how text wraps at the width its parent allows.

Then comes the layout itself. `root_element.prepaint_as_root(...)` runs `layout_as_root`, which calls `Window::compute_layout` and then `TaffyLayoutEngine::compute_layout` in `taffy.rs`. Taffy solves the whole tree for the available space. Taffy's own pixel rounding is disabled (`taffy.disable_rounding()`); GPUI rounds to device pixels itself when it reads results with `layout_bounds(id, scale_factor)`.

Nothing is positioned yet when `request_layout` itself runs. This phase may call `Window::request_layout`, `with_id` and `with_element_state`.

**Where in the code.**

- `Window::draw_roots` in `window.rs`.
- `ViewElement::request_layout`, `request_layout_view` and `render_view` in `view.rs`.
- `Element::request_layout` in `element.rs`; `Div`'s version in `elements/div.rs`.
- `TaffyLayoutEngine` in `taffy.rs`.

**Why it is designed this way.** Layout needs two passes: first every element states what it needs, then the engine decides every position at once. A parent cannot place a child before it knows how big the child wants to be. Running `render` in this first phase means state is read exactly once per frame, at the start.

:::note[For an ordinary view, `render` runs on every frame in which its parent renders]
What `notify` changes is which views may be *skipped*. A view embedded with `.cached(style)` is laid out from the style you gave it, without calling `render`. See "Cached views" below.
:::

### Step 9. Phase 2, `prepaint`: positions are known

**What happens.** Layout is solved, so every element can ask for its final bounds. `Drawable::prepaint` reads `bounds = window.layout_bounds(layout_id)`, pushes a node on the *dispatch tree*, calls `Element::prepaint`, then pops the node. (The dispatch tree records which elements can receive keyboard input; see [How input finds your code](/codebase/input-and-dispatch-internals/).) The returned `PrepaintState` is kept for paint.

Inside `prepaint` an element can:

- insert **hitboxes**: `Window::insert_hitbox(bounds, HitboxBehavior)`. The current clip is captured, and the `Hitbox` is pushed to `next_frame.hitboxes`;
- bind its focus handle: `Window::set_focus_handle`;
- lay out and prepaint its children, offset by its own scroll position via `with_element_offset`;
- request deferred draws (`Window::defer_draw`).

The Increment button has a click listener, hover and active styles and a cursor style, so its `Div` inserts a hitbox. A `Div` only does so when it needs one (`Interactivity::should_insert_hitbox`: a non-default hitbox behavior, a cursor style, a group, a scroll offset, a tracked focus handle, hover styles, or certain listeners).

After the root is prepaint-ed, `draw_roots` also handles *deferred* draws (`deferred()` elements such as popovers get a second round of prepaint), then the prompt, active drag or tooltip, and finally computes `mouse_hit_test = next_frame.hit_test(mouse_position)` so hover styles are right while painting.

**Where in the code.** `Drawable::prepaint` in `element.rs`, `Window::insert_hitbox` in `window.rs`, `Div`'s prepaint in `elements/div.rs`.

**Why it is designed this way.** Hitboxes need final screen positions, and positions do not exist until layout is done. That is why this phase sits between `request_layout` and `paint`. It is also where GPUI decides things like "is this element hovered?" so that paint can use the answer.

### Step 10. Phase 3, `paint`: shapes and listeners

**What happens.** `draw_roots` sets `DrawPhase::Paint` and calls `root_element.paint(...)`. `Drawable::paint` activates the dispatch node created in prepaint and calls `Element::paint`. During paint an element does two kinds of things:

- **It emits drawing.** `Window::paint_quad`, `paint_path`, `paint_glyph`, `paint_emoji`, `paint_svg`, `paint_image`, `paint_underline`, `paint_drop_shadows` and `paint_surface` each end in `next_frame.scene.insert_primitive(...)`. `Window::paint_layer(bounds, ...)` pushes and pops a scene layer. For the counter: the button's background and rounded corners are *quads*, and the label `Count: 1` becomes glyph sprites.
- **It registers listeners for the next event.** `Window::on_mouse_event` pushes onto `next_frame.mouse_listeners`. `Window::on_key_event`, `DispatchTree::on_action`, `Window::set_key_context` and `Window::handle_input` (text input) do the same kind of thing.

`Div`'s `paint_mouse_listeners` turns each `.on_mouse_down(...)`, `.on_click(...)` and so on into a closure that captures a clone of the element's `Hitbox` and registers it with `window.on_mouse_event`. That is why events later "know" which element they belong to: the closure checks `hitbox.is_hovered(window)`. This is the loop closing: **the listeners you registered here are the ones step 2 will call on your next click.**

Text reaches the scene as sprites: `Window::paint_glyph` asks `sprite_atlas.get_or_insert_with(key, || text_system.rasterize_glyph(&params))` (the `PlatformAtlas` trait). It inserts a `MonochromeSprite` or `SubpixelSprite` that refers to the returned `AtlasTile`. An *atlas* is one big GPU texture holding many small images, here the letter shapes.

**Where in the code.** `Drawable::paint` in `element.rs`, the `Window::paint_*` methods in `window.rs`, `Scene::insert_primitive` in `scene.rs`, `paint_mouse_listeners` in `elements/div.rs`.

**Why it is designed this way.** Painting does not draw to the screen. It only records what to draw into the scene. That separates "what the picture looks like" from "which graphics API draws it", so one framework can use Metal, Direct3D, Vulkan and WebGPU. Registering listeners during paint means the code that draws an element also owns its behavior, with no separate event table to keep in sync.

:::caution[Common mistake]
Every `Window::paint_*` and `Window::on_*_event` method asserts `DrawPhase::Paint`. Layout and hitbox methods assert `DrawPhase::Prepaint`. These are `debug_assert!`s, so they fire only in debug builds. The messages are `"this method can only be called during paint"` and `"this method can only be called during request_layout, or prepaint"`. If you see one, you called a method in the wrong phase.
:::

### Step 11. The frame is finished and swapped

**What happens.** Back in `Window::draw`, after `draw_roots`:

1. Register the new input handler with the platform window (for text input and IME).
2. `layout_engine.clear()` and `text_system().finish_frame()`.
3. `next_frame.finish(&mut rendered_frame)` carries over element state that was used, and `Scene::finish()` sorts primitives by draw order.
4. Set the phase to `Focus`, then **swap** `rendered_frame` and `next_frame`, and clear the new `next_frame`.
5. If the focus path or the window-active state changed, fire the focus listeners.
6. `record_entities_accessed(cx)`: the window now subscribes to everything `render` read this time. That includes `Counter`, so the next `cx.notify()` finds its way back to this window (this is what step 4 depended on).
7. Reset the cursor style, set `refreshing = false` and `needs_present = true`, and return an `ArenaClearNeeded` token.

Two frames exist at all times. `Frame` (in `window.rs`) holds the `Scene`, `hitboxes`, `mouse_listeners`, the `DispatchTree`, `element_states`, `deferred_draws`, `tooltip_requests`, `cursor_styles`, `input_handlers` and `tab_stops`.

| Frame | Role |
| --- | --- |
| `rendered_frame` | What was last drawn. Event dispatch and hit testing use it (steps 2 and 3). |
| `next_frame` | Being built right now. After the swap it becomes `rendered_frame`. |

**Where in the code.** The second half of `Window::draw`, `Frame::finish`, `Scene::finish`, and `Window::record_entities_accessed` / `App::record_entities_accessed` in `app.rs`.

**Why it is designed this way.** If there were only one frame, an event arriving during a draw would hit a half-built list of hitboxes. With two, the on-screen frame is never touched while the new one is built. `draw` returns an `ArenaClearNeeded` token, marked `#[must_use]`. Its doc comment says the element arena "has been used and so must be cleared before the next draw". The caller decides when to clear, and `on_request_frame` does it right after `present`.

### Step 12. The scene is presented

**What happens.** `Window::present` has two lines of substance:

```rust
self.platform_window.draw(&self.rendered_frame.scene);
self.needs_present.set(false);
```

`PlatformWindow::draw(&self, scene: &Scene)` is the boundary between GPUI and a graphics API. The backend walks the scene in batches and issues GPU draw calls. After that, the `on_request_frame` closure calls `arena_clear_needed.clear(cx)`. All `AnyElement`s drawn this frame are dropped, and the bump allocator is reset. Elements never outlive the frame that created them. Only `Frame` data (scene, hitboxes, listeners, dispatch tree, element state) does.

The window now shows `Count: 1`.

| Backend | `draw` implementation (verified) |
| --- | --- |
| Linux (Wayland, X11) | The window holds a `gpui_wgpu::WgpuRenderer`. If `renderer.device_lost()`, it calls `recover(...)`. Otherwise it requests a `wl_surface.frame` callback (Wayland) and calls `renderer.draw(scene)`. Files: `gpui_linux/src/linux/wayland/window.rs`, `x11/window.rs`. |
| `WgpuRenderer::draw` | In `gpui_wgpu/src/wgpu_renderer.rs`: acquire `surface.get_current_texture()`, handle `Suboptimal`, `Lost`, `Outdated`, `Timeout` and `Occluded` by reconfiguring or returning `false`, call `core.render_frame(scene, ...)` (iterates `scene.batches()` and issues instanced draws with the WGSL shaders in `shaders.wgsl`), then `queue.present(frame)`. |
| Windows | `DirectXRenderer::draw`, then `render` (clear, upload instance buffers, one `draw_*` per `PrimitiveBatch`), then `present` (`IDXGISwapChain1`), with `skip_draws` after a device-lost recovery. File: `gpui_windows/src/directx_renderer.rs`. |
| macOS | `WindowState.renderer.draw(scene)` in `gpui_macos/src/window.rs`. The Metal renderer is in `gpui_apple`, which is not in this checkout. |
| iOS | `self.renderer.lock().draw(scene)` with a `MetalRenderer` hosted by a `CAMetalLayer` view (`gpui_ios/src/ios/window.rs`). |
| Web | `WgpuRenderer` on a canvas surface, after resizing the canvas if `pending_physical_size` changed (`gpui_web/src/window.rs`). |
| Headless and tests | `HeadlessWindow` (Linux) draws nothing; `TestWindow` records. |

The glyph and image atlas is per window: `Window::sprite_atlas` comes from `PlatformWindow::sprite_atlas()` (`WgpuAtlas`, `DirectXAtlas`, a Metal atlas). The scene stores only `AtlasTile` references. That is why `force_render` calls `Window::refresh()` first: after a GPU device loss, cached views must not replay tile references into a recreated atlas (see the comment in the `on_request_frame` closure).

**Where in the code.** `Window::present` in `window.rs`, `PlatformWindow::draw` in `platform.rs`, and the backend files in the table.

**Why it is designed this way.** The scene is the only drawing data that crosses the platform boundary. A renderer has to draw eight kinds of primitive and knows nothing about views, entities or layout. (A backend also supplies a text system and an atlas; see [How GPUI talks to your OS](/codebase/platform-backends/).)

## The timeline for two frames

Here are the same events along a time axis. The left side is GPUI on the main thread. The right side is the platform.

```text
event / task            App (main thread)                             platform
--------------------------------------------------------------------------------------
click handler runs  --> entity.update(cx, ..); cx.notify()
                        WindowInvalidator: dirty = true, wake  -----> frame source armed
                        flush_effects: observers; schedule_frame ---> request_frame
                                                   <------------------ on_request_frame
                        Window::draw  (layout, prepaint, paint)
                        Window::present  -------------------------->  renderer.draw(scene)
                        arena cleared                                  swap chain present
(idle: nothing dirty, no next-frame callbacks)  frame source parks / is ignored
```

## Deeper reference

The rest of the page is reference material. You can skip it on a first read and return when a question sends you here.

### The `Element` trait and the `Drawable` wrapper

Each element implements the `Element` trait (`element.rs`). The parameter types are shortened here:

```rust
fn request_layout(&mut self, id, inspector_id, window, cx) -> (LayoutId, Self::RequestLayoutState);
fn prepaint(&mut self, id, inspector_id, bounds, request_layout_state, window, cx) -> Self::PrepaintState;
fn paint(&mut self, id, inspector_id, bounds, request_layout_state, prepaint_state, window, cx);
```

Generic code never calls these directly. It calls them through `Drawable<E>`, a wrapper holding an `ElementDrawPhase` enum (`Start`, `RequestLayout`, `LayoutComputed`, `Prepaint`, `Painted`). The state machine panics on misuse:

- `"must call request_layout only once"`
- `"must call request_layout before prepaint"`
- `"must call prepaint before paint"`
- `"cannot measure after painting"`

`Drawable::request_layout` also pushes the element's `GlobalElementId` onto `window.element_id_stack` when the element has an `id()`. That is what scopes persistent element state (the state `.id("...")` unlocks in the Counter tutorial).

`AnyElement` wraps an `ArenaBox<dyn ElementObject>`: elements are allocated in the per-`App` arena, and the arena is reset after the frame is presented. [How state is stored and updated](/codebase/app-and-entity-internals/) covers the arena.

### The `draw_roots` sequence

Steps 8 to 10 happen inside `Window::draw_roots`. In pseudocode:

```text
root_element = root.into_any_element()
root_layout_id = root_element.request_layout(window, cx)               [phase 1]
layout_engine.stretch_auto_size_to_fill(root_layout_id, viewport, scale)
root_element.prepaint_as_root(origin 0,0, viewport size, window, cx)  [phase 2]
      = layout_as_root(...)  -> Window::compute_layout -> TaffyLayoutEngine::compute_layout
      + with_absolute_element_offset(origin, |w| prepaint(w))
prepaint_deferred_draws(cx)         // deferred() elements: second round of prepaint
prepaint prompt | active drag | tooltip
mouse_hit_test = next_frame.hit_test(mouse_position)
phase = DrawPhase::Paint
root_element.paint(window, cx)                                         [phase 3]
paint_deferred_draws(cx)
paint prompt | active drag | tooltip
(accessibility tree update if active)
```

### Cached views

The window's root is an `AnyView` (`Window::root`). A view embedded with `.cached(style)` (`Entity::cached` / `AnyView::cached`) is laid out from the style you gave it, **without calling `render`**. In `prepaint_view` it checks a cache key (`bounds`, `content_mask`, `text_style`, `opacity`), that the view is not in `window.dirty_views`, and that `window.refreshing` is false. If all hold, it calls `Window::reuse_prepaint` with the saved `PrepaintStateIndex` range, and later `reuse_paint` with the `PaintIndex` range. These copy hitboxes, dispatch nodes, mouse listeners, scene operations and so on from the previous frame instead of rebuilding them. This is also why `Scene` records `paint_operations` and has `Scene::replay(range, prev_scene)`.

A `RenderOnce` component has no entity, so it takes the stateless path (`request_layout_component`, `prepaint_component`, `paint_component`). It is rendered each time and never cached.

### Entity access tracking

`EntityMap::read` and `lease` insert the entity id into `accessed_entities`. `App::detect_accessed_entities` (used by cached views) pushes a scope. `Window::draw` clears the set at the start, and `record_entities_accessed` stores the final set into `App::tracked_entities` and `window_invalidators_by_entity` at the end. Cached views remember their own accessed set (`ViewElementState::accessed_entities`) and add it back when they replay, so a reused subtree still keeps its entities subscribed.

### The scene in detail

`Scene` (`scene.rs`) is the render-agnostic output of painting:

```rust
pub struct Scene {
    paint_operations: Vec<PaintOperation>,      // for replay
    primitive_bounds: BoundsTree<ScaledPixels>, // assigns z-order
    layer_stack: Vec<DrawOrder>,
    pub shadows: Vec<Shadow>,
    pub quads: Vec<Quad>,
    pub paths: Vec<Path<ScaledPixels>>,
    pub underlines: Vec<Underline>,
    pub monochrome_sprites: Vec<MonochromeSprite>,
    pub subpixel_sprites: Vec<SubpixelSprite>,
    pub polychrome_sprites: Vec<PolychromeSprite>,
    pub surfaces: Vec<PaintSurface>,
}
```

Primitives are in **device-scaled pixels** (`ScaledPixels`). `Window::paint_*` scales logical `Pixels` by `window.scale_factor()`. Here is what each primitive is for:

| Primitive | Used for |
| --- | --- |
| `Quad` | Backgrounds, borders, rounded rects (with `Background`: solid, gradient or pattern). |
| `Shadow` | Box shadows. |
| `Path` | Tessellated vector fills and strokes (`PathBuilder`). |
| `Underline` | Underlines and strikethroughs (straight or wavy). |
| `MonochromeSprite` | Glyphs and SVG masks: an alpha mask from the atlas tinted with a color. |
| `SubpixelSprite` | LCD subpixel-antialiased glyphs. |
| `PolychromeSprite` | Colour bitmaps: images, emoji. |
| `PaintSurface` | A platform surface (video or pixel buffer). |

**Draw order.** `Scene::insert_primitive` clips the primitive's bounds against its `content_mask` and drops it if empty. Then it assigns `order`. Inside a layer it uses the layer's order. Otherwise it uses `primitive_bounds.insert(clipped_bounds)`. `BoundsTree::insert` returns **one more than the maximum order of any intersecting bounds already inserted**. Overlapping primitives therefore get increasing z-order, while non-overlapping ones can share an order and be batched.

**Batching.** `Scene::finish` (called from `Frame::finish`) sorts each vector by `order` (sprites also by atlas texture id). `Scene::batches()` returns an iterator of `PrimitiveBatch` values (`Shadows(range)`, `Quads(range)`, `Paths(range)`, `Underlines(range)`, `MonochromeSprites { texture_id, range }`, `SubpixelSprites {..}`, `PolychromeSprites {..}`, `Surfaces(range)`). It repeatedly picks the kind with the lowest next `order` and extends the batch while that kind stays below the next competing kind's order. Renderers draw batch by batch, which keeps draw calls few while preserving overlap order.

## Where to look when something is wrong

| Symptom | Start here |
| --- | --- |
| UI does not update after a state change | `Context::notify`. Is the changed entity read during `render`? (`EntityMap::read_inner`, `Window::record_entities_accessed`.) For a cached view, `prepaint_view` in `view.rs`. |
| An element is positioned wrongly | `TaffyLayoutEngine::compute_layout`, the `Style` to taffy conversion in `taffy.rs`, `Window::layout_bounds`. |
| Hover or click goes to the wrong element | `Window::insert_hitbox`, `Frame::hit_test`, `HitboxBehavior` (see [How input finds your code](/codebase/input-and-dispatch-internals/)). |
| Something draws in the wrong order | `Scene::insert_primitive` order assignment, `BoundsTree::insert`, `deferred()` and `paint_layer`. |
| Window freezes or redraws constantly | The `on_request_frame` closure in `Window::new`, and the platform's frame source (table in step 6). |

## Try it yourself

All of these are reading exercises. None changes the downloaded repository. If you want to see a function run, copy `crates/gpui/examples/hello_world.rs` into a scratch project outside the checkout, depend on `gpui` as in [Installation](/start/installation/), and add `println!` calls to your own code.

1. **Find the pipeline.** In `crates/gpui/src/app/context.rs`, find `Context::notify`. Follow the call into `App::notify` in `app.rs`, then into `WindowInvalidator::invalidate_view` in `window.rs`. Write down the four things `invalidate_view` does.
2. **Where does the frame request come from?** Open `flush_effects` in `app.rs`. Find the line that calls `schedule_frame()`. Under what three conditions is it called?
3. **Read the draw.** Open `Window::draw` in `window.rs`. Find the call to `draw_roots`, then the `mem::swap` of `rendered_frame` and `next_frame`. What happens to the old frame right after the swap?
4. **Spot the three phases.** Open `draw_roots`. Find `set_phase(DrawPhase::Prepaint)` and `set_phase(DrawPhase::Paint)`. Where is `request_layout` called relative to them?
5. **Run `render` once per frame.** In `Window::new`, find `platform_window.on_request_frame`. In scratch code of your own, put a `println!` at the top of your view's `render` and watch how often it prints when you move the mouse over a button with a hover style, and when you leave the window idle. What does the output tell you about step 8?
6. **Count the frames of a click.** In a scratch copy of the counter, print from `render`. Press and hold the mouse on a button without releasing, then release. Match the prints to the mouse-down `window.refresh()` call and to the `cx.notify()` call. (This relies on the tutorial's button having a click listener; see `paint_mouse_listeners`.)
7. **Debugger breakpoints.** If you run the counter in a scratch project that depends on a local `gpui` checkout, a debugger breakpoint on `WindowInvalidator::invalidate_view` and on `Window::draw` shows the gap between steps 4 and 7 as two different stack traces. Nothing in the checkout needs to change; set the breakpoints from your debugger. (The breakpoint names are real functions in the source; the debugger workflow itself was not tried for this page.)

## Next steps

- [How state is stored and updated](/codebase/app-and-entity-internals/): steps 3 to 5 in full, including leases, the effect queue and observers.
- [How input finds your code](/codebase/input-and-dispatch-internals/): steps 1 to 3 in full, plus keyboard and focus.
- [How GPUI talks to your OS](/codebase/platform-backends/): step 12 and the frame sources of step 6, backend by backend.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/app/context.rs` (`Context::notify`, `Context::listener`, `invoke_listener`)
- `crates/gpui/src/app.rs` (`App::notify`, `App::update`, `finish_update`, `flush_effects`, `Effect`)
- `crates/gpui/src/app/entity_map.rs` (`lease_erased`, `clear_accessed`)
- `crates/gpui/src/window.rs` (`WindowInvalidator::invalidate_view`, `Window::new`, `Window::draw`, `draw_roots`, `present`, `Frame`, `insert_hitbox`, `dispatch_event`, `dispatch_mouse_event`)
- `crates/gpui/src/element.rs` (`Element`, `Drawable`), `crates/gpui/src/view.rs` (`ViewElement`, `request_layout_view`, `prepaint_view`)
- `crates/gpui/src/elements/div.rs` (`paint_mouse_listeners`, `should_insert_hitbox`)
- `crates/gpui/src/taffy.rs`, `crates/gpui/src/scene.rs`, `crates/gpui/src/bounds_tree.rs`
- `crates/gpui/src/platform.rs` (`PlatformWindow::draw`, `on_request_frame`)
- `crates/gpui_wgpu/src/wgpu_renderer.rs`, `crates/gpui_windows/src/directx_renderer.rs`
- frame sources: `gpui_linux/src/linux/wayland/window.rs`, `gpui_macos/src/display_link.rs`, `gpui_windows/src/vsync.rs`, `gpui_web/src/window.rs`, `gpui_ios/src/ios/application.rs`
</details>
