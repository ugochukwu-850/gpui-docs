---
title: How GPUI owns your data
description: Why your state lives in the App, how Entity handles work, and the reentrancy rules behind the "already being updated" panic.
sidebar:
  order: 2
  label: How GPUI owns your data
---

:::note[Advanced]
This page is for readers who have finished the beginner path and want to know *why* GPUI state works the way it does. Read [Thinking in GPUI](/start/thinking-in-gpui/) and [State and views](/guides/state-and-views/) first.
:::

In GPUI one object, the `App`, owns all of your state. You get small handles to that state and pass the handles around. This page explains why, how the handles behave, and the one rule that causes most panics.

It follows the module docs in `_ownership_and_data_flow.rs` and the `ownership_post` example, and adds what the entity map and effect queue in the source show about the rules.

:::tip[In short]
- The `App` owns every entity. You hold an `Entity<T>` handle, which is like a numbered ticket: cheap to copy, useless without the `App`.
- While your code runs inside `update`, that entity is temporarily taken out of storage. That is why you cannot update or read it a second time from inside itself.
- Side effects like `notify`, `emit` and `observe` callbacks wait in a queue and run after the outermost `update` finishes.
:::

## The App owns, handles point

In GPUI every model or view is owned by a single top-level object, the `App`. You create an entity by handing the app a closure that builds the value. You get back a handle:

```rust
use gpui::{App, AppContext, Entity};

struct Counter {
    count: usize,
}

gpui_platform::application().run(|cx: &mut App| {
    let counter: Entity<Counter> = cx.new(|_cx| Counter { count: 0 });
    // ...
});
```

`Entity<Counter>` is, in the words of the source docs, "merely an inert identifier plus a compile-time type tag" with a reference count. It behaves like an `Rc` in one way: cloning it adds one to the count, and dropping it subtracts one. It differs in another: it gives you **no access to the value by itself**. To touch the state you need a reference to the `App` too.

```rust
counter.update(cx, |counter: &mut Counter, cx: &mut Context<Counter>| {
    counter.count += 1;
});

let n: usize = counter.read(cx).count;
```

A helpful picture is a coat check. The `App` is the cloakroom, your state is the coat, and the `Entity<T>` is the ticket. Anyone can carry a ticket, but you need the attendant to hand you the coat.

```text
  Your code                 App (the cloakroom)
  ---------                 -------------------
  Entity<Counter>  ticket   entity map:
  (id 7, refcount) -------> id 7 -> Counter { count: 0 }
  Entity<Counter>  ticket   id 8 -> Editor { .. }
  (a clone: same id)        id 9 -> Workspace { .. }
```

Inside, the `App` keeps a map from `EntityId` to a boxed value (`EntityId -> Box<dyn Any>`). The `update` call *leases* the value out of the map. In plain words, it removes the value for as long as your closure runs, hands you `&mut T`, and puts it back afterwards. That one mechanism explains most of the rules below.

```text
 counter.update(cx, |c, cx| { ... })

   EntityMap                         closure
   +-----------------------+
   | id 7 -> Counter {..}  |  lease   +-----------------------+
   +-----------------------+ -------> | c: &mut Counter       |
   | id 7 -> (empty)       |          | cx: &mut Context<..>  |
   +-----------------------+ <------- +-----------------------+
   | id 7 -> Counter {..}  |  end_lease
   +-----------------------+
```

## Why not `Rc<RefCell<T>>`?

You could share mutable state with `Rc<RefCell<T>>`, and GPUI does use `Rc`s internally. For application state, the entity model gives you several things a bare `RefCell` does not.

- **Notification is built in.** `cx.notify()`, `observe` and `subscribe` let other entities and windows react to changes. With a `RefCell` you would have to build that yourself and remember to call it.
- **Dependency tracking for rendering.** The entity map records which entities were read during a draw (`read_inner` and `lease_inner` insert into an accessed set). The window subscribes to that set when the draw ends. A `RefCell` read is invisible to the framework.
- **One owner, one place for effects.** Observers, events and releases run from the `App`'s effect queue (described below), not from arbitrary call stacks. They cannot interleave with a half-finished change.
- **Typed access with a context.** Every access needs a `cx`, so the compiler forces you through a place where GPUI can see what you do.
- **Cleanup hooks.** When the last strong handle goes away, GPUI releases the entity, removes its observers and event listeners, and runs `on_release` callbacks with the value.

The trade-off is that the handle-plus-context style is more verbose. Some mistakes also become runtime panics instead of compile errors (see the reentrancy rules).

## Strong and weak handles

There are two kinds of handle. A **strong** handle keeps the entity alive. A **weak** handle does not: it only lets you check whether the entity still exists.

| Handle | Keeps the entity alive? | Access |
| --- | --- | --- |
| `Entity<T>` | Yes | `read`, `read_with`, `update`, `update_in`, `as_mut`, `write` |
| `WeakEntity<T>` | No | `upgrade() -> Option<Entity<T>>`, plus `update`, `read_with` and `update_in`. Those last three return `Result`, because the entity may be gone. |
| `AnyEntity`, `AnyWeakEntity` | Yes, No | Type-erased. Call `downcast::<T>()` to get the typed handle back. |

Get a weak handle with `entity.downgrade()`. Inside an update you can also call `cx.weak_entity()`.

Use `WeakEntity` for anything that outlives the code that creates it and should not keep the entity alive. Examples are async tasks, callbacks stored in long-lived objects, and **back-references** from a child to its parent.

Strong cycles leak exactly as they do with `Rc`. If A holds an `Entity<B>` and B holds an `Entity<A>`, neither count reaches zero.

`Context::spawn` follows this rule for you. Its closure is given a `WeakEntity<T>`, "to avoid leaking the entity for a long-running process":

```rust
cx.spawn(async move |this, cx| {
    // `this: WeakEntity<Counter>`, `cx: &mut AsyncApp`
    this.update(cx, |counter, cx| {
        counter.count = 100;
        cx.notify();
    })
    .ok(); // Err if the entity was released while we waited
})
.detach();
```

## Update, notify, observe

The module docs build the next example in stages. Here it is whole. `second_counter` always mirrors twice the first counter's value.

```rust
use gpui::{App, AppContext, Context, Entity, prelude::*};

struct Counter {
    count: usize,
}

gpui_platform::application().run(|cx: &mut App| {
    let first_counter: Entity<Counter> = cx.new(|_cx| Counter { count: 0 });

    let second_counter = cx.new(|cx: &mut Context<Counter>| {
        // We can set up the callback before the Counter is even created.
        cx.observe(
            &first_counter,
            |second: &mut Counter, first: Entity<Counter>, cx| {
                second.count = first.read(cx).count * 2;
            },
        )
        .detach();

        Counter { count: 0 }
    });

    first_counter.update(cx, |counter, cx| {
        counter.count += 1;
        cx.notify(); // tell observers the state changed
    });

    assert_eq!(second_counter.read(cx).count, 2);
});
```

Two things are worth noticing.

- `observe` is called on the *observer's* `Context`. The callback therefore receives `&mut` access to the observer's own state, plus a handle to the observed entity. Internally the observer is reached through a weak handle, so observing does not keep the observer alive.
- The assertion holds because effects (here, the observer call) are flushed when the outermost `update` returns.

Typed events work the same way through `EventEmitter`, `cx.emit(...)` and `cx.subscribe(...)`. The [Entities](/deep-dive/entities/) page covers the full toolbox.

## Effects are deferred to the end of the update

An **effect** is a side effect that GPUI promises to run later. Calls like `notify`, `emit`, a global change and `cx.defer` do not run callbacks immediately. They push an `Effect` onto the `App`'s queue. The effect kinds are `Notify`, `Emit`, `NotifyGlobalObservers`, `Defer`, `EntityCreated` and `RefreshWindows`.

`App::update` counts how deeply nested it is. When the *outermost* update finishes, it calls `flush_effects`, which loops until the queue is empty.

```text
 first_counter.update(cx, |c, cx| {
     c.count += 1;
     cx.notify();      // queues Effect::Notify, does NOT call observers yet
     cx.emit(Evt);     // queues Effect::Emit
 });                   // <- update returns, flush_effects runs observers/subscribers
```

If an entity already has a `Notify` effect waiting, a second one is merged into it. Calling `cx.notify()` ten times in one update does not run observers ten times.

This design makes the next section manageable. A subscriber runs *after* the emitter's closure has returned, so it can safely update the emitter.

## Reentrancy rules

*Reentrancy* means calling into something while you are already inside it. Here the "something" is an entity's `update`.

While a closure passed to `update` runs, that entity's value is **out of the map**. Every rule below follows from that.

### 1. You cannot update or read an entity from inside its own update

Doing so panics with `cannot update Counter while it is already being updated` (or `cannot read ...`). Inside an update you already have the value: it is `self`, or the `&mut T` parameter.

```rust
// PANICS: `me` is leased out and is being updated right now.
fn bump(&mut self, cx: &mut Context<Self>) {
    let me = cx.entity();
    me.update(cx, |this, _| this.count += 1);
}

// Correct:
fn bump(&mut self, cx: &mut Context<Self>) {
    self.count += 1;
    cx.notify();
}
```

### 2. Mutual access panics too

Suppose A's update closure calls `b.update(cx, ...)`, and B's closure calls `a.update(cx, ...)`. By then A is already out of the map, so the inner call panics.

Break such cycles in one of two ways. You can use events, which are delivered after the update. Or you can use `cx.defer(...)` or `cx.defer_in(window, ...)`. The source docs say `defer` "schedules the given function to be run at the end of the current effect cycle, allowing entities that are currently on the stack to be returned to the app."

### 3. A view cannot read itself in `render`

`render` runs inside an update of that view. Use `&mut self` instead.

### 4. Reading other entities is fine

A parent can read its children. Children can read shared model entities. Only the entity currently on the stack is unavailable.

### 5. Updating nested entities is fine

This works as long as the entities are distinct:

```rust
a.update(cx, |a, cx| b.update(cx, |b, cx| { /* ... */ }));
```

It works because `Context<T>` is an `AppContext`, so you can pass it as the `cx` of another entity's update.

### 6. Do not re-enter the `App` itself

The app state sits inside a `RefCell` (wrapped as `AppCell`). Borrowing it again from inside an update panics. This matters most when you hold an `ApplicationHandle` from `run_embedded`. Its doc says `update` "must not be called re-entrantly from code that is already inside an update."

## Common mistakes

:::caution[Common mistake]
**Mutating without `cx.notify()`.** Observers and the view's cache are only told about changes you announce. The state changes, but nothing reacts.
:::

- **Dropping a `Subscription`.** `observe`, `subscribe` and friends return a `#[must_use]` `Subscription`. Dropping it cancels the callback. Either `.detach()` it, or store it in a field (commonly `_subscriptions: Vec<Subscription>`).
- **Holding a strong handle in a long task.** A spawned future that owns an `Entity<T>` keeps `T` alive until the future ends. Use the `WeakEntity` you are given.
- **Treating the result of `WeakEntity::update` as infallible.** It returns a `Result`, because the entity or its window may be gone. Use `.ok()` or `?`.

## Data flow in a typical app

Put the pieces together and data moves in one loop. State flows *down* when views read handles in `render`. Changes flow *up* when event handlers update entities.

```text
          user input / timers / network
                      |
                      v
        event handler  (cx.listener(|this, ev, window, cx| ...))
                      |   update entity state
                      v
              cx.notify()  /  cx.emit(Event)
                      |
         +------------+-------------+
         |                          |
   observers / subscribers     window redraw
   update *their* entities     Render::render reads entity state
   (and notify in turn)        -> elements -> pixels
```

Prefer this one-directional shape. Reach for `emit` and `subscribe` when a child must tell a parent something without knowing who the parent is.

## Next steps

- [Contexts](/deep-dive/contexts/): which `cx` you hold in each situation.
- [Entities](/deep-dive/entities/): the practical toolbox for creating, updating and observing.
- [Async and executors](/guides/async-and-executors/): how weak handles and tasks work together.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/_ownership_and_data_flow.rs`
- `crates/gpui/examples/ownership_post.rs`
- `crates/gpui/src/app/entity_map.rs` (`EntityMap`, `lease`, `double_lease_panic`, `Entity`, `WeakEntity`)
- `crates/gpui/src/app.rs` (`App::update`, `finish_update`, `flush_effects`, `Effect`, `AppCell`)
- `crates/gpui/src/app/context.rs` (`Context::notify`, `emit`, `spawn`, `defer_in`)
- `crates/gpui/src/subscription.rs` (`Subscription`)
</details>
