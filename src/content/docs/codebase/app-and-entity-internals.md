---
title: How state is stored and updated
description: How GPUI's App owns every entity, why updating an entity temporarily takes it out of storage, how queued effects run observers, and why updating something from inside its own update panics.
sidebar:
  order: 5
  label: How state is stored and updated
---

This page explains the machinery behind `Entity<T>`, `Context<T>`, `cx.notify()`, `cx.observe()` and `cx.emit()`: where your state lives, how you get `&mut` access to it, and why some calls wait their turn. The authors' own tutorial for the same ideas is `crates/gpui/src/_ownership_and_data_flow.rs`. This page is about how it is *implemented*. Everything was read from commit `b5cd310b`.

## What you'll learn

- Which object owns all your state, and what an `Entity<T>` handle really is.
- What a *lease* is, and why re-entrant updates panic with "already being updated".
- What the effect queue is, and why observers never run in the middle of your update.
- What globals, the arena and the different contexts hold.
- How to decode the common panic messages.

:::note[Advanced]
This page is for readers who finished the [Counter tutorial](/tutorials/counter/) and have hit (or want to avoid) the "already being updated" panic. You should know what `Entity<T>`, `cx.notify()` and `cx.observe()` do from the outside. The page defines every internal term when it first appears. For the same ideas without file names, see [Entities](/deep-dive/entities/) and [Ownership and data flow](/deep-dive/ownership-and-data-flow/).
:::

:::tip[In short]
1. One `App` owns every entity. An `Entity<T>` is a reference-counted *handle*, not the value itself.
2. `entity.update(cx, ...)` **moves the value out of storage** while your closure runs. That is why you get `&mut T` without a lock, and why touching the same entity again from inside panics.
3. Notifications, events and observers are **queued** and run only when the outermost update finishes, when nothing is borrowed any more.
:::

## Words you need first

| Term | Plain meaning |
| --- | --- |
| **Entity** | A value of your type (say `Counter`) owned by GPUI. You never own it directly. |
| **Handle** | The `Entity<Counter>` you hold. Cloning it adds a reference. When the last handle is dropped, the entity is freed. |
| **Lease** | GPUI taking your value out of storage for the length of an `update` call, then putting it back. |
| **Effect** | A queued to-do item, such as "run the observers of entity 12". |
| **Observer** | A callback registered with `cx.observe(...)` that runs after the observed entity calls `notify`. |
| **Subscription** | The token you get back when registering a callback. Dropping it cancels the callback. |
| **Global** | One value per type, stored on the `App` instead of in an entity (a theme, settings). |
| **Arena** | A fast bump allocator that is emptied all at once (see "The arena" below). |

## The one big owner

Everything hangs off a single `App`:

```text
Application(Rc<AppCell>)                    app.rs
   AppCell { app: RefCell<App>, borrow_origin: Cell<Option<(Location, &str)>> }
      App                                    app.rs  (struct App, starts at line 884)
        entities: EntityMap                  app/entity_map.rs
        windows: SlotMap<WindowId, Option<Box<Window>>>
        observers, event_listeners, release_listeners, global_observers ... : SubscriberSet<..>
        pending_effects: VecDeque<Effect>
        globals_by_type: TypeIdHashMap<Box<dyn Any>>
        element_arena, event_arena: Arena
        actions: Rc<ActionRegistry>, keymap: Rc<RefCell<Keymap>>
        platform: Rc<dyn Platform>, executors, text_system, ...
```

`Application` is what `gpui_platform::application()` returns. `Application::run(f)` hands the closure to `Platform::run`. When the platform has finished launching, it does `let cx = &mut *this.borrow_mut(); f(cx);` (`app.rs`). From then on, every callback from the OS (a frame request, an input event, a menu action) re-enters GPUI by borrowing the `AppCell` mutably.

`AppCell` is documented as a "temporary wrapper around `RefCell<App>` to help us debug any double borrows". A `RefCell` allows one mutable borrow at a time and panics on a second. If a second borrow happens, `AppBorrowError` builds the message:

```text
RefCell already borrowed: attempted mutable App borrow at <file:line>; existing mutable borrow group began at <file:line>
```

Building with `TRACK_THREAD_BORROWS` set (read with `option_env!`) additionally prints thread ids on every borrow and release.

## Entities: storage and handles

`crates/gpui/src/app/entity_map.rs` (1,421 lines) defines two cooperating structures.

```text
EntityMap
  entities:   SecondaryMap<EntityId, Box<dyn Any>>        the actual values
  ref_counts: Arc<RwLock<EntityRefCounts>>
                 counts:             SlotMap<EntityId, AtomicUsize>
                 dropped_entity_ids: Vec<EntityId>
  accessed_entities: RefCell<AccessedEntities>            see "Access tracking"

AnyEntity { entity_id, entity_type: TypeId, entity_map: Weak<RwLock<EntityRefCounts>> }
Entity<T> { any_entity: AnyEntity, entity_type: PhantomData<fn(T) -> T> }
WeakEntity<T> / AnyWeakEntity
```

In plain words: `entities` is a table from an id to your value (boxed so any type fits). `ref_counts` is a second table that counts how many handles point at each id. The handles you hold are small structs holding an id and a pointer to the count table.

- **Ids are generational.** `EntityId` is a `slotmap` key (`slotmap::new_key_type! { pub struct EntityId; }`). A freed slot's id is not equal to a later entity's id, so an old id never accidentally points at a new entity. It converts to and from `u64`.
- **Reference counting is in the handle, not in the map.** `AnyEntity::clone` does `fetch_add(1)` on the entity's `AtomicUsize` in `ref_counts` (asserting it is not already zero: `"Detected over-release of a entity."`). `Drop for AnyEntity` does `fetch_sub(1)`. When the previous value was `1`, it pushes the id onto `dropped_entity_ids`. The handle holds only a `Weak` pointer to the shared counts, so handles can be dropped on any thread, even after the `App` is gone.
- **The value is not freed at that moment.** The actual `Box<dyn Any>` is removed later, in `App::release_dropped_entities`. `flush_effects` runs it at the top of each loop iteration via `EntityMap::take_dropped`. It also removes the entity's observers, event listeners, window invalidator and current-window records. Then it runs the `release_listeners` (`cx.on_release`, `observe_release`) with `&mut dyn Any` access to the value right before it is dropped.
- **Creating an entity takes two steps.** `EntityMap::reserve` inserts `1` into `counts` and returns a `Slot<T>` holding the first `Entity<T>`. `insert` later stores the boxed value. `App::new` is `reserve` + build + `insert`, wrapped in `App::update`, and pushes `Effect::EntityCreated` so `observe_new` listeners run. `reserve_entity` and `insert_entity` expose the two halves, so you can learn an `EntityId` before the entity exists (`Reservation<T>` in `gpui.rs`).
- **Weak handles cannot resurrect.** `WeakEntity::upgrade` uses `atomic_incr_if_not_zero`, so upgrading a weak handle to a dying entity fails instead of bringing it back. `WeakEntity::update` therefore returns a `Result` (`"entity released"` is the context message).

### Leasing: how `update` gives you `&mut T`

There is no `RefCell` around each entity. Instead, `update` **moves the value out of the map** for the duration of your closure. Picture the table before, during and after:

```text
before update       entities: { 7: Counter{count:0}, 8: Editor{..} }

during update(7)    entities: {                       8: Editor{..} }
                    lease:    Counter{count:0}  <- your closure has &mut to this

after update(7)     entities: { 7: Counter{count:1}, 8: Editor{..} }
```

The code path:

```text
Entity::update(cx, f)
  -> cx.update_entity(handle, f)                 App: AppContext::update_entity   app.rs
  -> App::update_entity_erased(handle, ...)
       self.update(|cx| {                         start_update() ... finish_update()
           let mut lease = cx.entities.lease_erased(handle, type_name);   // entities.remove(id)
           f(lease.entity.as_deref_mut().unwrap(), cx);                   // your closure, with &mut App
           cx.entities.end_lease_erased(id, lease);                       // entities.insert(id, value)
       })
```

This is why your closure receives a `&mut Context<T>` that derefs to the whole `&mut App`: nothing else is borrowed. It is also exactly why re-entrancy is restricted. While the closure runs, the entity is absent from the map. Any attempt to lease or read it again finds nothing and panics through `double_lease_panic`:

```rust
#[track_caller]
fn double_lease_panic(operation: &str, entity_type: &str) -> ! {
    panic!("cannot {operation} {entity_type} while it is already being updated")
}
```

Both `EntityMap::read` (used by `Entity::read` and `read_entity`) and `lease_erased` call it. You can see either `cannot read MyView while it is already being updated` or `cannot update MyView while it is already being updated`.

Two supporting details:

- `LeaseInner` has a `Drop` that panics with `"Leases must be ended with EntityMap::end_lease"` if the value was never returned (unless the thread is already panicking).
- `GpuiBorrow<'a, T>` (what `Entity::as_mut` and `AppContext::as_mut` return) is the RAII form: it calls `start_update` and leases on creation. In `Drop` it calls `app.notify(entity_id)`, returns the lease and calls `finish_update`. So mutating through `as_mut` notifies automatically.

:::caution[Common mistake]
Calling `self_handle.update(cx, ...)` or `self_handle.read(cx)` from inside an update of the same entity panics with "already being updated". Inside the closure you already have `&mut T`, so use it. To touch the entity later, use `cx.defer` (see the tip below), or return the data you need out of the closure. [Common errors](/reference/common-errors/) lists the message too.
:::

### Access tracking

`EntityMap::read_inner` and `lease_inner` both do `accessed_entities.borrow_mut().innermost().insert(entity_id)`. In other words: every time anything reads or leases an entity, its id is written into a "seen during this draw" set. `AccessedEntities` keeps a `frame` set plus a stack of `scopes`.

`Window::draw` clears the set at the start (`clear_accessed`). Cached views push and pop a scope (`App::detect_accessed_entities`). The window stores the final set (`record_entities_accessed`), so it can be marked dirty when any of those entities calls `notify`. This is the link between `cx.notify()` and "redraw this window". See [How a frame is drawn](/codebase/frame-lifecycle/), step 4.

## Updates and the effect queue

Mutations never trigger observers synchronously. They are queued. Here is the whole mechanism:

```rust
pub(crate) fn update<R>(&mut self, update: impl FnOnce(&mut Self) -> R) -> R {
    self.start_update();                     // pending_updates += 1
    let result = update(self);
    self.finish_update();                    // if pending_updates == 1 { flush_effects() }; pending_updates -= 1
    result
}
```

Updates nest (an entity update inside an entity update, or an update inside a window update). Only the **outermost** one flushes. By then every lease has been returned, which is what makes it safe to call arbitrary observers.

`Effect` is a private enum in `app.rs`. This table shows what pushes each variant and what applying it does:

| Variant | Pushed by | Applied by |
| --- | --- | --- |
| `Notify { emitter }` | `App::notify` | `apply_notify_effect`: `self.observers.clone().retain(&emitter, |handler| handler(self))` |
| `Emit { emitter, event_type, event }` | `Context::emit` | `apply_emit_effect`: runs `event_listeners` whose stored `TypeId` equals `event_type` |
| `RefreshWindows` | `App::refresh_windows` | `apply_refresh_effect`: every window gets `refreshing = true` and is marked dirty |
| `NotifyGlobalObservers { global_type }` | `set_global`, `global_mut`, `default_global`, `remove_global`, `end_global_lease` | `apply_notify_global_observers_effect` |
| `Defer { callback }` | `App::defer` (and `Context::defer_in`, `observe` registration) | `apply_defer_effect`: `callback(self)` |
| `EntityCreated { entity, tid, window }` | `App::new` | `apply_entity_created_effect`: runs `new_entity_observers` for that type |

Three more details:

- **Deduplication.** `push_effect` deduplicates `Notify` (via `pending_notifications: FxHashSet<EntityId>`) and `NotifyGlobalObservers` (via `pending_global_notifications`). Ten `cx.notify()` calls on one entity before the flush produce one observer pass. `Emit` is never deduplicated: every event is delivered.
- **Event payloads.** `Effect::Emit` carries its payload as `ArenaBox<dyn Any>` allocated from `App::event_arena`. `flush_effects` calls `event_arena.clear()` when the queue is empty. This avoids a heap allocation per event.
- **Effects make effects.** An observer can call `notify` on another entity, so `flush_effects` loops until the queue is empty. [How a frame is drawn](/codebase/frame-lifecycle/), step 5, shows the loop in context.

:::tip[Use `defer` to escape a lease]
`Context::defer_in(window, f)` and `App::defer(f)` push `Effect::Defer`. Their documentation says "allowing entities that are currently on the stack to be returned to the app". Deferring is the intended way to do something to an entity that you cannot touch right now because it is mid-update.
:::

## Observers and subscriptions

`crates/gpui/src/subscription.rs` (559 lines) provides the callback registries.

- `SubscriberSet<EmitterKey, Callback>` is `Rc<RefCell<{ subscribers: BTreeMap<EmitterKey, BTreeMap<usize, Subscriber<Callback>>>, next_subscriber_id }>>`. In words: for each "emitter" it keeps the list of callbacks. The key is an `EntityId` for `observers`, `event_listeners` and `release_listeners`, and a `TypeId` for `global_observers` and `new_entity_observers`.
- `SingleSubscriberSet<Callback>` has no emitter key. It is used for `keystroke_observers`, `quit_observers`, `window_closed_observers`, `display_observers` and so on.
- Each `Subscriber` carries `state: Rc<Cell<SubscriberState>>` where `SubscriberState` is `Pending`, `Active` or `Dropped`.

### Why a new observer waits

`insert_pending` returns `(Subscription, activate)`. `App::new_observer` calls `self.defer(move |_| activate())`, so **a new observer is not eligible to run until the current effect cycle ends**. `remove` and `retain` skip pending entries. This stops a callback registered inside an `observe` callback from being invoked by the very `notify` that is running.

### How callbacks run

`retain(emitter, f)` takes the whole inner map for that emitter with `mem::take` while calling the callbacks. This lets a callback register new subscribers without a `RefCell` double borrow. Afterwards it keeps the callbacks for which `f` returned `true` and appends anything added in the meantime. Observer callbacks return `bool`: returning `false` unsubscribes (for example because the weak handle to the observer could not be upgraded).

### The `Subscription` handle

`Subscription` is `#[must_use]` and holds `unsubscribe: Option<Box<dyn FnOnce()>>`. `Drop` runs it. `Subscription::detach()` removes the closure so the registration lives until the observed entity is released. `Subscription::join(a, b)` combines two.

### An observer, end to end

The entity-facing wrappers in `app/context.rs` show the pattern. `Context::observe` captures a `WeakEntity<T>` of the *observer*. When invoked, it calls `invoke_observer`, which does `observer.upgrade()` and then `observer.update(cx, |observer, cx| on_notify(observer, observed, cx))`. That update is a normal lease. Because it runs from `flush_effects` at the outermost update, it cannot collide with an outer lease. This is the reason observers are effects and not direct calls.

`cx.subscribe(&emitter, ...)` and `cx.emit(event)` follow the same path through `event_listeners`, with `TypeId::of::<Evt>()` filtering. The `EventEmitter<E>` marker trait (`gpui.rs`) is what lets `emit` compile.

## Globals

A global is one value per type, stored on the `App`: `App::globals_by_type: TypeIdHashMap<Box<dyn Any>>`, keyed by `TypeId::of::<G>()` where `G: Global`. (`Global` in `global.rs` is an empty marker trait.)

| Method | Behavior |
| --- | --- |
| `global::<G>()` / `global_mut::<G>()` | Panic with `"no state of type {} exists"` if missing. `global_mut` also pushes `NotifyGlobalObservers`. |
| `try_global`, `has_global` | Non-panicking. |
| `set_global`, `default_global`, `remove_global` | All queue `NotifyGlobalObservers`. `remove_global` panics with `"no global added for {}"`. |
| `update_global(f)` (via `BorrowAppContext`) | `lease_global` (removes the value from the map), runs `f(&mut global, cx)`, then `end_global_lease` (reinserts and queues the notification). Same leasing idea as entities: reading the same global inside `f` fails because it is not in the map. |
| `observe_global::<G>(f)` | Registered in `global_observers`, activated through `defer`. |

The field comment in `App` explains drop order: "Drop globals last... any task attempting to spawn a blocking tokio task, might panic." This is why `gpui_tokio` stores its runtime in a global. For patterns that use globals, see [Globals and state patterns](/deep-dive/globals-and-state-patterns/).

## The arena

GPUI builds new elements every frame (see [How a frame is drawn](/codebase/frame-lifecycle/)). To make that cheap, it allocates them in an *arena*: a block of memory where each new value goes right after the previous one, and everything is freed at once by resetting. `crates/gpui/src/arena.rs` (401 lines) is a chunked bump allocator.

- `Arena { chunks: Vec<Chunk>, elements: Vec<ArenaElement>, valid: Rc<Cell<bool>>, current_chunk_index, chunk_size, scope_depth }`. Each `Chunk` has `start`, `end` and `offset` pointers; `allocate` aligns and bumps.
- `Arena::alloc(|| value)` writes the value into the current chunk (spilling to a new chunk if needed) and records a type-erased drop function in `elements`. It returns an `ArenaBox<T>` (a raw pointer plus a clone of `valid`). `ArenaBox::map` supports unsizing, which is how `ArenaBox<Drawable<E>>` becomes `ArenaBox<dyn ElementObject>` inside `AnyElement`.
- `Arena::clear()` runs all drops, flips `valid` to `false`, installs a fresh `valid`, and rewinds offsets. Any surviving `ArenaBox` panics on deref with `"attempted to dereference an ArenaRef after its Arena was cleared"`.
- `begin_scope` and `end_scope` form a depth counter. A `clear()` while `scope_depth > 0` is deferred (`"deferring arena clear; N enclosing scope(s) still active"`), which protects a nested draw.
- A chunk too small for an allocation panics with `"Arena chunk_size of {} is too small to allocate {} bytes"`.

`App` owns two arenas created with `Arena::new(1024 * 1024)`: `element_arena: Rc<RefCell<Arena>>` and `event_arena: Arena`.

The element arena is in its own `Rc` allocation for a subtle reason. Draws reach it through the raw-pointer thread local `CURRENT_ELEMENT_ARENA` (set by `ElementArenaScope::enter` in `Window::draw`) while a `&mut App` is live. Storing it inline would alias memory that the `&mut App` claims exclusively (see the field comment). The token `ArenaClearNeeded` returned by `draw` forces the caller to clear the arena after presenting.

## Contexts, in terms of what they hold

You meet several "context" types. This table says what each really contains.

| Type | Holds | Notes |
| --- | --- | --- |
| `App` | everything | Passed as `&mut App`. |
| `Context<'a, T>` | `app: &'a mut App`, `entity_state: WeakEntity<T>` | `Deref<Target = App>` and `DerefMut`. Adds `notify`, `emit`, `observe`, `subscribe`, `spawn`, `listener`, `defer_in`, `on_next_frame`, and more. |
| `Window` | window state | Not a context. Passed next to `cx`. |
| `AsyncApp` | `Weak<AppCell>`, both executors | `Clone + 'static`. `AsyncApp::app()` does `.upgrade().expect("app was released before async operation completed")`. `update` takes `borrow_mut()` on the cell, so calling it while the `App` is already borrowed hits the `RefCell already borrowed` panic. |
| `AsyncWindowContext` | an `AsyncApp` plus a window handle | Its `update` calls `App::update_window`, returning `Result`. |
| `TestAppContext` | test-only | Panics instead of returning `Result`. |

`App::update_window` takes the window out of its `SlotMap` slot (`Option::take`) while your closure runs. `update_window_id` returns `Err("window not found")` if that fails. So a nested update of the *same* window returns an error rather than a second `&mut Window` (the `Option<Box<Window>>` type in `App::windows` exists for this). `AppContext::read_window` is stricter: it does `.expect("attempted to read a window that is already on the stack")`. The [Contexts](/deep-dive/contexts/) deep-dive page covers the user-facing side.

## Why re-entrancy is restricted

Putting it together, the rules are consequences of three choices:

1. **One `&mut App` and no per-entity lock.** Updating an entity temporarily removes it, so a second access to the same entity inside its own update has nothing to find.
2. **Side effects are queued.** Observers, event handlers and release listeners run only at the end of the outermost update, when no leases are outstanding.
3. **One `RefCell` around the whole app.** Platform callbacks and async code enter through `AppCell::borrow_mut`, so a synchronous re-entry from inside an update is a borrow error.

Practical consequences you can trace in the code:

- `cx.emit` and `cx.notify` inside an update do not call anyone yet.
- To touch an entity that is currently leased, `defer`, or return the data you need out of the closure.
- To read your own entity's field while updating a different one, copy it out first.

## Leak detection

`EntityRefCounts` contains a `LeakDetector` when compiled with `cfg(any(test, gpui_leak_detection))`. `gpui_leak_detection` is set by `crates/gpui/build.rs` if the `leak-detection` Cargo feature is on, or the `GPUI_LEAK_DETECTION` environment variable is non-empty at build time. Each handle creation and release is recorded (with a backtrace when `LEAK_BACKTRACE` is non-empty). The detector panics on drop with `"Exited with leaked handles:\n..."` if handles remain. `App::leak_detector_snapshot` and `assert_no_new_leaks` give tests a precise check.

The usual cause is a strong-reference cycle. The detector's own documentation says "Entities are reference-counted structures that can own other entities allowing to form cycles". If two entities hold strong `Entity` handles to each other, neither count reaches zero. Use `WeakEntity` for one direction.

## Try it yourself

These are reading exercises. None changes the downloaded repository.

1. **Find the lease.** Open `crates/gpui/src/app/entity_map.rs` and find `lease_erased`. Which line removes the value from `entities`? Which function puts it back?
2. **Read the panic.** Find `double_lease_panic`. List every function that calls it. Which two operations can it name?
3. **Find the flush.** In `crates/gpui/src/app.rs`, read `update`, `start_update` and `finish_update`. Why does only the call where `pending_updates == 1` flush?
4. **Count the effects.** Read `flush_effects` and the `Effect` enum. For each variant, find the function that pushes it (`rg "Effect::Notify" crates/gpui/src`, and so on).
5. **Why defer an observer?** Read `new_observer` and `insert_pending`. Write down what could go wrong if a new observer were active immediately.
6. **Spot the cycle.** In `crates/gpui/src/app/entity_map.rs`, find the `LeakDetector` doc comment. Sketch two structs that would trigger it.
7. **Experiment outside the repository.** In a scratch project that depends on `gpui`, make a view call `cx.entity().update(cx, |_, _| {})` from its own `render` or from a `cx.listener` closure, and read the panic message. Match its wording to `double_lease_panic`. (Not run for this page; the call shape follows the source.)

## Next steps

- [How a frame is drawn](/codebase/frame-lifecycle/): see the effect queue and access tracking in context.
- [How input finds your code](/codebase/input-and-dispatch-internals/): how events reach the closures that call `update`.
- [How the macros work](/codebase/macros/): where `#[derive(IntoElement)]` and friends come from.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/app.rs` (`Application`, `AppCell`, `App`, `Effect`, `update`, `flush_effects`, globals, `release_dropped_entities`)
- `crates/gpui/src/app/entity_map.rs` (`EntityMap`, `Entity`, `WeakEntity`, leasing, `double_lease_panic`, `LeakDetector`)
- `crates/gpui/src/app/context.rs` (`Context<T>`, `observe`, `subscribe`, `emit`, `listener`)
- `crates/gpui/src/app/async_context.rs` (`AsyncApp`, `AsyncWindowContext`)
- `crates/gpui/src/subscription.rs`, `crates/gpui/src/global.rs`, `crates/gpui/src/arena.rs`
- `crates/gpui/src/_ownership_and_data_flow.rs` (the authors' own tutorial)
</details>
