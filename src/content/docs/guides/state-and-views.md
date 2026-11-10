---
title: Share state between views
description: Split a UI into child views, share data between them with an entity, and keep everything in sync.
sidebar:
  order: 1
  label: State and views
---

Real apps are made of several views that need to agree on some data. This guide shows you how to split a UI into a parent view and child views, share one piece of state between them, and keep the screen up to date.

**What you'll learn**

- How a view owns its data, and when a plain struct field is enough.
- How to make a child view and put it inside a parent.
- How to share state with an `Entity` handle.
- How a parent reacts when shared state changes.

You should be comfortable with the [counter tutorial](/tutorials/counter/) and the loop from [Thinking in GPUI](/start/thinking-in-gpui/).

## What you'll build

A small dashboard with two counter cards, "Apples" and "Pears". Click a card to add one to it. A line at the top shows the total of all clicks, and a "Reset all" button sets everything back to zero. When the total reaches ten, a message appears.

The cards and the total need to agree, so the interesting question is: where does the total live?

## A view owns its data

A view is a struct, and the data it needs is stored as fields on that struct. If only one view cares about a value, keep it as a plain field:

```rust
struct CounterCard {
    label: &'static str,
    count: usize,   // only this card needs to know its own count
}
```

You change it in an event handler, then call `cx.notify()` so GPUI redraws. Nothing else is needed. Most state in most apps stays this simple.

## Split the UI into child views

When a part of your UI has its own data and its own handlers, make it its own view. Each child view is an **entity**: a piece of state that GPUI owns, which you refer to through a handle of type `Entity<T>`. Our `CounterCard` will be one.

The parent stores a handle to each child and draws it by passing a clone of the handle to `.child(...)`:

```rust
struct Dashboard {
    apples: Entity<CounterCard>,
    pears: Entity<CounterCard>,
    // ...
}

// inside Dashboard's render:
div()
    .child(self.apples.clone())
    .child(self.pears.clone())
```

Cloning an `Entity` copies the handle, not the data. Both clones point at the same card.

:::caution[Common mistake]
Create child entities once, in the parent's constructor, and store the handles. If you call `cx.new(...)` inside `render`, you make a brand new child on every redraw and it loses its data.
:::

## Share state with an entity handle

Now the total. Both cards must add to it, and the dashboard must display it. No single card owns it, so it gets its own entity: a plain struct with no `Render` implementation.

```rust
struct Tally {
    total: usize,
}
```

Create it once in the parent and give each child a clone of the handle:

```rust
let tally = cx.new(|_| Tally { total: 0 });
let apples = cx.new(|_| CounterCard {
    label: "Apples",
    count: 0,
    tally: tally.clone(),   // the child gets a handle to the shared data
});
```

The child stores the handle in a field (`tally: Entity<Tally>`). To change the shared data from the child, you go through the handle with `update`:

```rust
self.tally.update(cx, |tally, cx| {
    tally.total += 1;
    cx.notify(); // tell GPUI the Tally changed
});
```

`update` gives your closure the data (`&mut Tally`) and a context for that entity. It does not call `notify` for you, so you call it yourself. To read the shared data, use `read`:

```rust
let total = self.tally.read(cx).total;
```

## Update from the parent

The parent can reach its children and the shared data through the same handles. For "Reset all", the dashboard updates each card and the tally:

```rust
for card in [&this.apples, &this.pears] {
    card.update(cx, |card, cx| {
        card.count = 0;
        cx.notify();
    });
}
this.tally.update(cx, |tally, cx| {
    tally.total = 0;
    cx.notify();
});
```

That is the pattern: hold a handle, call `update`, change the data, call `cx.notify()`. See the complete program below for the real code.

## React when another view changes: `observe`

To show the total, the dashboard reads `self.tally.read(cx).total` while it renders. But what if the dashboard needs to *do* something when the total changes, such as remember that we passed ten clicks?

Use `cx.observe`. It runs a function whenever another entity calls `cx.notify()`:

```rust
let subscription = cx.observe(&tally, |this, changed, cx| {
    this.reached_ten = changed.read(cx).total >= 10;
    cx.notify(); // the dashboard changed too, so redraw it
});
```

The function receives the observing view (`this`), a handle to the entity that changed, and a context. `observe` returns a `Subscription`. If you drop it, the observer stops working. Store it in a field, as the dashboard does with `_subscription`. If you want the observer to live as long as the entity does, call `.detach()` on it instead.

If the other view needs to tell you *what* happened, not just that something changed, use events with `cx.emit` and `cx.subscribe`. They are covered in the [Entities](/deep-dive/entities/#typed-events-with-eventemitter-emit-and-subscribe) deep dive.

## The complete program

Here is everything together. It uses the same `main` shape as [Hello World](/start/hello-world/).

<details>
<summary>Complete src/main.rs</summary>

```rust
use gpui::{
    App, Bounds, Context, Entity, Subscription, Window, WindowBounds, WindowOptions, div,
    prelude::*, px, rgb, size,
};
use gpui_platform::application;

// A plain data entity, shared by the dashboard and both cards.
struct Tally {
    total: usize,
}

// A child view. It owns its own count and holds a handle to the shared Tally.
struct CounterCard {
    label: &'static str,
    count: usize,
    tally: Entity<Tally>,
}

impl Render for CounterCard {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        div()
            .id(self.label)
            .p_4()
            .bg(rgb(0x313244))
            .cursor_pointer()
            .hover(|style| style.bg(rgb(0x45475a)))
            .child(format!("{}: {}", self.label, self.count))
            .on_click(cx.listener(|this, _event, _window, cx| {
                // Change my own data...
                this.count += 1;
                cx.notify();
                // ...and the shared data.
                this.tally.update(cx, |tally, cx| {
                    tally.total += 1;
                    cx.notify();
                });
            }))
    }
}

// The parent view. It owns the children and the shared Tally.
struct Dashboard {
    tally: Entity<Tally>,
    apples: Entity<CounterCard>,
    pears: Entity<CounterCard>,
    reached_ten: bool,
    _subscription: Subscription,
}

impl Dashboard {
    fn new(cx: &mut Context<Self>) -> Self {
        let tally = cx.new(|_| Tally { total: 0 });
        let apples = cx.new(|_| CounterCard {
            label: "Apples",
            count: 0,
            tally: tally.clone(),
        });
        let pears = cx.new(|_| CounterCard {
            label: "Pears",
            count: 0,
            tally: tally.clone(),
        });

        // Run this whenever the Tally calls cx.notify().
        let subscription = cx.observe(&tally, |this, changed, cx| {
            this.reached_ten = changed.read(cx).total >= 10;
            cx.notify();
        });

        Self {
            tally,
            apples,
            pears,
            reached_ten: false,
            _subscription: subscription,
        }
    }
}

impl Render for Dashboard {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        let total = self.tally.read(cx).total;

        div()
            .flex()
            .flex_col()
            .gap_4()
            .size_full()
            .p_4()
            .bg(rgb(0x1e1e2e))
            .text_color(rgb(0xcdd6f4))
            .child(format!("Total clicks: {total}"))
            .when(self.reached_ten, |this| this.child("That is ten clicks!"))
            .child(
                div()
                    .flex()
                    .gap_4()
                    .child(self.apples.clone())
                    .child(self.pears.clone()),
            )
            .child(
                div()
                    .id("reset")
                    .px_3()
                    .py_1()
                    .bg(rgb(0x313244))
                    .cursor_pointer()
                    .child("Reset all")
                    .on_click(cx.listener(|this, _event, _window, cx| {
                        for card in [&this.apples, &this.pears] {
                            card.update(cx, |card, cx| {
                                card.count = 0;
                                cx.notify();
                            });
                        }
                        this.tally.update(cx, |tally, cx| {
                            tally.total = 0;
                            cx.notify();
                        });
                    })),
            )
    }
}

fn main() {
    application().run(|cx: &mut App| {
        let bounds = Bounds::centered(None, size(px(500.), px(300.)), cx);
        cx.open_window(
            WindowOptions {
                window_bounds: Some(WindowBounds::Windowed(bounds)),
                ..Default::default()
            },
            |_, cx| cx.new(|cx| Dashboard::new(cx)),
        )
        .unwrap();
        cx.activate(true);
    });
}
```

</details>

Run it and click the cards. The total goes up with every click, and the message appears at ten.

## Plain field or entity?

Use this rule of thumb:

| Situation | Use |
| --- | --- |
| Only one view uses the value | A plain field on that view |
| A value is computed from props or fields and never shared | A plain field, or compute it in `render` |
| Several views must read or change the same value | An `Entity`, shared by cloning the handle |
| A part of the UI has its own state and handlers | A child view (an entity that implements `Render`) |
| One view must react when another changes | `cx.observe` (or events with `cx.subscribe`) |

Do not reach for entities too early. They add a little ceremony: handles, `update`, `read`. Start with plain fields, and move a value into an entity when a second view needs it.

## Common mistakes

:::caution[Common mistake]
**Changing shared data and forgetting `cx.notify()` on it.** The observers and the redraw only happen for the entity you notify. In the program above, `tally.update(...)` calls `cx.notify()` on the `Tally`, and each card notifies itself.
:::

- **Updating an entity from inside its own update.** If a view's own handler tries to call `update` on that same view's handle, GPUI panics. Inside the handler, use `this` and `cx` directly. See [reentrancy](/deep-dive/ownership-and-data-flow/#reentrancy-rules).
- **Dropping the `Subscription`.** Writing `let _ = cx.observe(...)` drops it at once and the callback never runs. Store it in a field, bind it to a named variable, or call `.detach()`.
- **Two entities holding strong handles to each other.** Neither can ever be freed. Let one side hold a weak handle (`WeakEntity`). See [Entities](/deep-dive/entities/#weak-handles-and-ids).
- **Two views that observe each other and both change data.** They can trigger each other forever. Add a condition so the chain stops.

## Next steps

- [Entities](/deep-dive/entities/): every way to create, read, update and observe entities.
- [Views and render](/deep-dive/views-and-render/): how views, children and `notify` fit together.
- [Todo list tutorial](/tutorials/todo-list/): a bigger app with a list of items.

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/app/entity_map.rs` (`Entity::update`, `Entity::read`)
- `crates/gpui/src/app/context.rs` (`Context::observe`, `notify`, `listener`)
- `crates/gpui/src/subscription.rs` (`Subscription`)
- `crates/gpui/src/util.rs` (`FluentBuilder::when`)
- `crates/gpui/examples/ownership_post.rs`
- `crates/gpui/examples/view_example/` (a shared `Entity<String>` between views)
</details>
