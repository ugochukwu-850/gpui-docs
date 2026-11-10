---
title: "Entities: shared state you can watch"
description: Create, read, update and observe entities, send typed events, keep subscriptions alive, and split your app into models and views.
sidebar:
  order: 4
  label: Entities
---

:::note[Advanced]
This page is for readers who have finished the beginner path and want the full toolbox for entity state. Read [Thinking in GPUI](/start/thinking-in-gpui/) and [State and views](/guides/state-and-views/) first. Then read [How GPUI owns your data](/deep-dive/ownership-and-data-flow/) for the reasons behind the rules used here.
:::

An **entity** is a piece of state owned by the `App` and reached through an `Entity<T>` handle. If you know React, think of it as a piece of state that lives outside any one component, which many components can read and subscribe to. This page is the practical toolbox: how to create, read, update and watch entities.

:::tip[In short]
- `cx.new` creates an entity, `read` looks at it, and `update` changes it. `update` does **not** tell anyone about the change. You call `cx.notify()` for that.
- To react to another entity, use `observe` ("it changed, recompute") or `subscribe` ("this specific event happened").
- Observers and subscribers hand you a `Subscription`. Drop it and the callback stops. Store it in a field or call `.detach()`.
:::

## The shape of the API

```text
                 +-- cx.new(|cx| T { .. }) ---------> Entity<T>   (strong handle)
 create          |
                 |                                     |  .downgrade()
 use             +-- handle.read(cx)  / read_with       v
                 +-- handle.update(cx, |t, cx| ..)  WeakEntity<T>  (does not keep it alive)
                                  |
 announce                         +-- cx.notify()  ---> observers run, windows redraw
                                  +-- cx.emit(ev)  ---> subscribers run
```

## Creating

```rust
let counter: Entity<Counter> = cx.new(|cx: &mut Context<Counter>| Counter { count: 0 });
```

`new` is part of the `AppContext` trait, so it works on `&mut App`, `&mut Context<U>`, `AsyncApp` and test contexts. The closure receives a `Context<T>` for the entity being built. That lets you wire up subscriptions in the constructor, before the value even exists.

```rust
let second = cx.new(|cx: &mut Context<Counter>| {
    cx.observe(&first, |this: &mut Counter, first, cx| {
        this.count = first.read(cx).count * 2;
    })
    .detach();
    Counter { count: 0 }
});
```

Some constructors need a window, for example to create focus handles, shape text, or subscribe with an `*_in` method. Build the entity where you have a window. Both the build closure of `open_window` and `Render::render` receive one. There are also `|window, cx|` forms: `window.use_state(cx, |window, cx| ...)`, and `VisualContext::new_window_entity` for async window contexts.

If you need to know an entity's `EntityId` before its value exists, split creation in two. `cx.reserve_entity::<T>()` gives you a reservation (whose `entity_id()` you can read), and `cx.insert_entity(reservation, build)` fills it.

Creation also queues an `EntityCreated` effect. Anything registered with `App::observe_new::<T>(|this, window: Option<&mut Window>, cx| ...)` runs for each newly created `T`.

## Reading

```rust
let count = counter.read(cx).count;                        // needs &App
let count = counter.read_with(cx, |c, _app| c.count);      // any AppContext
```

- `read(&self, cx: &App) -> &T` returns a plain reference. It works with `&mut App` and `&mut Context<_>`, because they deref to `&App`. It does not work with `AsyncApp` or `TestAppContext`.
- `read_with(cx, |&T, &App| R)` works with every `AppContext`, including async and test contexts.

Reading never notifies. There is one subtlety, though: **reads during a draw are tracked**. Every entity read while a window is drawing is recorded, and the window subscribes to that set. See [How `notify` reaches the screen](/deep-dive/views-and-render/#how-notify-reaches-the-screen).

## Updating

```rust
counter.update(cx, |counter, cx| {
    counter.count += 1;
    cx.notify();
});
```

| Method | Closure gets | Notes |
| --- | --- | --- |
| `update(cx, \|&mut T, &mut Context<T>\| R)` | State and entity context | The workhorse. **Does not notify by itself.** |
| `update_in(cx, \|&mut T, &mut Window, &mut Context<T>\| R)` | Adds a window | Needs a `VisualContext` (`AsyncWindowContext`, `VisualTestContext`). Returns `C::Result<R>`. |
| `as_mut(cx)` | A `GpuiBorrow<T>` guard that derefs to `&mut T` | **Notifies when dropped.** Handy for one-liners. Not supported on `AsyncApp`. |
| `write(cx, value)` | Replaces the value, then calls `cx.notify()` | |

`update` returns whatever your closure returns, so it also works as "compute something while holding the entity":

```rust
let total = cart.update(cx, |cart, cx| {
    cart.items.push(item);
    cx.notify();
    cart.items.len()
});
```

The rule of thumb is to **call `cx.notify()` whenever a change should be visible to others**. That means observers, and the window that renders this entity. GPUI does not watch your fields, so it only redraws when you say the data changed. If your UI is stale after a state change, check this first.

## Weak handles and ids

A weak handle points at an entity without keeping it alive. Use one in async tasks, in stored callbacks, and for child-to-parent references.

```rust
let weak: WeakEntity<Counter> = counter.downgrade();   // or cx.weak_entity() inside an update
if let Some(strong) = weak.upgrade() { /* still alive */ }
weak.update(cx, |c, cx| { c.count += 1; cx.notify(); })?;   // Result<_>
weak.read_with(cx, |c, _| c.count)?;                         // Result<_>
```

- `entity.entity_id()` returns an `EntityId`. It is a `u64` underneath (`as_u64()`), and it is `Hash + Ord`, so it works as a map key. The handles themselves also implement `Hash`, `Eq` and `Ord` by id.
- `entity.into_any()` gives an `AnyEntity`. Calling `any.downcast::<T>()` returns `Result<Entity<T>, AnyEntity>`.

## Observing changes with `notify` and `observe`

`cx.notify()` is a statement that *this entity changed*. Other entities react to it with `observe`:

```rust
let sub = cx.observe(&other, |this: &mut Self, other: Entity<Other>, cx| {
    this.cached_len = other.read(cx).items.len();
    cx.notify();   // we changed too
});
```

There are several scopes of observer.

| Call | Callback signature |
| --- | --- |
| `cx.observe(&e, ..)` on `Context<T>` | `FnMut(&mut T, Entity<W>, &mut Context<T>)` |
| `cx.observe_in(&e, window, ..)` | `FnMut(&mut T, Entity<W>, &mut Window, &mut Context<T>)` |
| `cx.observe_self(..)` | `FnMut(&mut T, &mut Context<T>)` |
| `app.observe(&e, ..)` on `App` | `FnMut(Entity<W>, &mut App)` |
| `window.observe(&e, cx, ..)` | `FnMut(Entity<W>, &mut Window, &mut App)` |

What the source tells us about observers:

- Observers hold only a weak reference to the observed entity (`entity.downgrade()`). A `Context` observer reaches its own entity through a weak handle too. Neither keeps anything alive, and when either side dies the observer removes itself.
- A notification is merged with one that is already pending for the same entity.
- The callback runs after the notifying update finishes (when effects are flushed), not inside it.

## Typed events with `EventEmitter`, `emit` and `subscribe`

`notify` says "something changed". When observers need to know *what* happened, define an event type and opt in with `EventEmitter`:

```rust
struct Counter { count: usize }
struct Change { increment: usize }

impl EventEmitter<Change> for Counter {}

impl Counter {
    fn bump(&mut self, by: usize, cx: &mut Context<Self>) {
        self.count += by;
        cx.emit(Change { increment: by });
        cx.notify();
    }
}
```

An entity can implement `EventEmitter<E>` for any number of event types. Subscribers pick one by the type of the callback's event parameter:

```rust
let subscriber = cx.new(|cx: &mut Context<Counter>| {
    cx.subscribe(&counter, |this: &mut Counter, _emitter: Entity<Counter>, event: &Change, _cx| {
        this.count += event.increment * 2;
    })
    .detach();
    Counter { count: counter.read(cx).count * 2 }
});
```

This is the `ownership_post` example. The variants are `subscribe_in` (adds `&mut Window`), `subscribe_self` (emitter and subscriber are the same entity), `App::subscribe` and `Window::subscribe`.

GPUI queues events and delivers them when the outermost update completes. A subscriber can therefore update the emitter without tripping the reentrancy panic. It also means that `emit` inside an update does not run handlers *before* the next line.

A well-known built-in event is `DismissEvent`. A view that implements `Focusable + EventEmitter<DismissEvent> + Render` is a `ManagedView`. That is the contract used for menus, popovers and modals that tell their host "close me". `ui::ContextMenu` is an example.

### Observe or subscribe?

- Use **`observe`** when the observer only needs to re-read the other entity ("it changed, recompute").
- Use **`subscribe`** when the information is in the event (`Edited { range }`, `Selected(id)`), when the event is not a state change at all ("closed", "saved"), or when many different things can happen to one entity.
- Emitting both is common. Use `emit` for semantic events and `notify` for "re-render me".

## Subscription lifetimes

`observe`, `subscribe`, `observe_global`, `on_release` and all their `_in` forms return a `#[must_use]` `Subscription`. Its doc says: "When dropped, the subscription is cancelled and the callback will no longer be invoked." You have three choices.

```rust
// 1. Fire and forget: lives until the observed entity (or observer) is dropped.
cx.observe(&other, |_, _, _| {}).detach();

// 2. Own it: cancel by dropping or replacing the field.
struct Panel {
    _subscriptions: Vec<Subscription>,
    selection_sub: Option<Subscription>,
}

// 3. Combine: Subscription::join(a, b) makes one subscription of two.
```

The real `Editor` in `crates/gpui/examples/view_example/example_editor.rs` keeps `_subscriptions: Vec<Subscription>` for its focus, blur and value observers. It also keeps `_blink_task: Task<()>`. Tasks work the same way: dropping a `Task` cancels the work, so store it or call `.detach()`.

:::caution[Common mistake]
Discarding the subscription. A bare `cx.observe(&e, ...);` triggers the `must_use` warning. But `let _ = cx.observe(...);` silences the warning while still dropping the subscription immediately, so the callback never fires.

Bind it to a named variable (`let _sub = ...` lives until the end of the scope), push it into a field, or call `.detach()`.
:::

GPUI registers subscriptions as "pending" and activates them with a deferred effect at the end of the current update. A subscription created in the same update that emits is therefore still active before the event is delivered.

## Release hooks

These run when an entity goes away.

- `cx.on_release(|this: &mut T, app: &mut App| ...)` runs when GPUI releases this entity (the last strong handle dropped), before the value is dropped.
- `cx.observe_release(&other, |this: &mut T, other: &mut T2, cx: &mut Context<T>| ...)` reacts to *another* entity going away.
- `app.observe_release(&handle, |entity: &mut T, app: &mut App| ...)` is the same on `App`.
- `cx.on_drop(|this, cx| ...)` returns a guard (`Deferred`) that runs your closure when the guard is dropped.

## Globals as the third kind of observable

`cx.observe_global::<G>(|this, cx| ...)` on a `Context<T>` calls back when a global of type `G` is set or updated. It follows the same `Subscription` rules. See [Globals and state patterns](/deep-dive/globals-and-state-patterns/).

## Models versus views

An entity is a *model* when nothing renders it, and a *view* when its type implements `Render`. The two share every API above.

| | Model | View |
| --- | --- | --- |
| Holds | Domain state: a document, a list of tasks, a connection | UI state: selection, focus handle, scroll handle, which tab is open |
| Rendered? | No | Yes, via `Render::render` |
| Typical communication | `emit` events, `notify` | Reads models in `render`. Handles input by updating models and itself |
| Lifetime | As long as anything holds a handle | Usually as long as its parent holds it |

A typical split looks like this:

```rust
struct Todos { items: Vec<Todo> }            // model: plain data + methods
impl EventEmitter<TodosEvent> for Todos {}

struct TodoList {                             // view
    todos: Entity<Todos>,
    _subscriptions: Vec<Subscription>,
}

impl TodoList {
    fn new(todos: Entity<Todos>, cx: &mut Context<Self>) -> Self {
        let sub = cx.observe(&todos, |_, _, cx| cx.notify()); // redraw when the model changes
        Self { todos, _subscriptions: vec![sub] }
    }
}
```

## Patterns

- **Shared model, many views.** Hand the same `Entity<Model>` to several views. Each one reads it in `render` and, if it caches or derives data, observes it. The `view_example` shares an `Entity<String>` between an `Editor` view and a `CursorReadout`.
- **Parent owns children.** The parent stores `Entity<Child>` fields (or creates them with `window.use_state`) and renders them with `.child(self.child.clone())`.
- **Child talks up with events.** The child emits. The parent subscribes in its constructor and keeps the `Subscription`. The child never holds a strong reference to the parent.
- **Child gets the parent via a weak handle.** If the child must call back, give it `cx.weak_entity()`.
- **Entities inside collections.** Use `Vec<Entity<Row>>` or `HashMap<EntityId, Entity<Row>>`. Dropping the entry (the last handle) releases the row and its subscriptions.
- **Async results.** Use `cx.spawn(async move |this, cx| { ... this.update(cx, |this, cx| { ...; cx.notify() }).ok(); })`. Store the `Task` in a field if you want drop-to-cancel.
- **Entities of plain data.** `Entity<String>` is perfectly valid, as `view_example` shows. `cx.new(|_| String::new())` gives you a shared, observable string.

## Common mistakes

- **Updating or reading an entity from inside its own update.** It panics. See [reentrancy](/deep-dive/ownership-and-data-flow/#reentrancy-rules).
- **Mutating via `update` and forgetting `cx.notify()`.** The data changes, but nothing reacts.
- **Dropping a `Subscription` or a `Task`.** The callback or the work is cancelled.
- **Two entities holding strong `Entity<_>` handles to each other.** This leaks. Make one side a `WeakEntity`.
- **Calling `.upgrade().unwrap()` on a weak handle in async code.** The entity may have been released while you waited.
- **Two entities that observe each other, and both mutate and `notify` in their callbacks.** The chain may never settle. Add a condition so it stops.

## Next steps

- [Views and render](/deep-dive/views-and-render/): turn entity state into elements.
- [Globals and state patterns](/deep-dive/globals-and-state-patterns/): state that exists once per app.
- [Async and executors](/guides/async-and-executors/): tasks and weak handles in practice.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/app/entity_map.rs` (`Entity`, `WeakEntity`, `AnyEntity`, `EntityId`)
- `crates/gpui/src/app/context.rs` (`Context<T>` methods)
- `crates/gpui/src/app.rs` (`App::observe`, `subscribe`, `observe_new`, `observe_release`, `Effect`)
- `crates/gpui/src/subscription.rs` (`Subscription`, `detach`, `join`)
- `crates/gpui/src/gpui.rs` (`EventEmitter`)
- `crates/gpui/src/window.rs` (`DismissEvent`, `ManagedView`, `Window::observe`, `Window::subscribe`)
- `crates/gpui/examples/ownership_post.rs`, `crates/gpui/examples/testing.rs`
- `crates/gpui/examples/view_example/example_editor.rs`
</details>
