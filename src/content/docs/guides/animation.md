---
title: Animate things
description: Fade, pulse, spin and spring elements with a few lines, and learn what GPUI can and cannot animate.
sidebar:
  order: 10
  label: Animation
---

How do you make a loading spinner turn, or a box slide to a new place? In GPUI you wrap an element in an animation. This page shows the two kinds, timed animations and springs, and what to watch out for.

## What you'll learn

- How to run a timed animation with `with_animation`
- How to repeat, ease and chain animations
- How to spin an SVG icon
- When to use a spring instead
- What you cannot animate, and how to restart an animation

## How animations work

An animation in GPUI does not change your view's data. It wraps one element. On every frame, GPUI works out a number from the elapsed time and calls your function with it. Your function returns the element to draw for that frame.

That number is called `delta`. It goes from `0.0` at the start to `1.0` at the end.

So you animate how something *looks* (opacity, size, position, color), not what your view *stores*.

:::note[Coming from React?]
It is closer to a CSS animation than to React state. There is no animation timeline, and nothing in your struct changes. You describe "at progress `delta`, the element looks like this".
:::

## Your first animation

This program shows a square that fades in and out forever. It uses `with_animation`, which you get from the `AnimationExt` trait.

```rust title="src/main.rs"
use std::time::Duration;

use gpui::{
    Animation, AnimationExt as _, App, Bounds, Context, Window, WindowBounds, WindowOptions,
    bounce, div, ease_in_out, prelude::*, px, rgb, size,
};
use gpui_platform::application;

struct Pulse;

impl Render for Pulse {
    fn render(&mut self, _window: &mut Window, _cx: &mut Context<Self>) -> impl IntoElement {
        div()
            .flex()
            .size_full()
            .justify_center()
            .items_center()
            .bg(rgb(0x1e1e2e))
            .child(
                div()
                    .size_16()
                    .rounded_md()
                    .bg(rgb(0x89b4fa))
                    .with_animation(
                        "pulse", // an id: it names this animation
                        Animation::new(Duration::from_secs(2))
                            .repeat()
                            .with_easing(bounce(ease_in_out)),
                        |element, delta| element.opacity(0.3 + 0.7 * delta),
                    ),
            )
    }
}

fn main() {
    application().run(|cx: &mut App| {
        let bounds = Bounds::centered(None, size(px(300.), px(300.)), cx);
        cx.open_window(
            WindowOptions {
                window_bounds: Some(WindowBounds::Windowed(bounds)),
                ..Default::default()
            },
            |_, cx| cx.new(|_| Pulse),
        )
        .unwrap();
        cx.activate(true);
    });
}
```

You see a blue rounded square that gently fades between dim and fully visible every two seconds.

### How it works

`with_animation` takes three things:

1. **An id** (`"pulse"`). GPUI remembers the animation's progress under this id.
2. **An `Animation`**. It says how long it lasts and how it behaves.
3. **A function** `|element, delta| ...`. It gets the element and the progress, and returns the changed element. Here `0.3 + 0.7 * delta` keeps the opacity between 0.3 and 1.0.

The builder methods on `Animation`:

| Method | Meaning |
|---|---|
| `Animation::new(duration)` | Run once, at a steady speed |
| `.repeat()` | Loop forever |
| `.repeat_synced()` | Loop, and stay in step with other synced animations |
| `.with_easing(f)` | Change the speed curve |
| `.with_max_fps(n)` | Redraw at most `n` times a second |

A one-time animation stops at `delta = 1.0` and stays there.

## Easing: speed up and slow down

An easing function turns steady progress into something more natural. It takes a number and returns a number. GPUI includes:

| Function | Effect |
|---|---|
| `linear` | Steady speed |
| `quadratic` | Slow start, fast end |
| `ease_in_out` | Slow start and slow end |
| `ease_out_quint()` | Fast start, long slow stop |
| `bounce(easing)` | Plays forward, then backward (there and back) |
| `pulsating_between(min, max)` | A breathing value between `min` and `max` |

`bounce(ease_in_out)` is why the square above fades out again instead of jumping back to dim. You can pass any `Fn(f32) -> f32` as your own curve.

## Run animations one after another

`with_animations` runs several one-time animations in a row. Your function also learns which one is active:

```rust
div().with_animations(
    "intro",
    vec![
        Animation::new(Duration::from_millis(200)),
        Animation::new(Duration::from_millis(400)).with_easing(ease_in_out),
    ],
    |el, index, delta| match index {
        0 => el.opacity(delta),                                 // first fade in
        _ => el.opacity(1.0).ml(px(20.0 * (1.0 - delta))),      // then slide in
    },
)
```

## Spin an icon

CSS-style transforms do not exist for ordinary elements. The exception is `svg()`, which can rotate and scale. This is the spinner from `crates/gpui/examples/animation.rs`:

```rust
use gpui::{Animation, AnimationExt as _, Transformation, percentage, svg};

svg()
    .size_20()
    .path("image/arrow_circle.svg")
    .text_color(gpui::black())
    .with_animation(
        "image_circle",
        Animation::new(Duration::from_secs(2)).repeat(),
        |svg, delta| svg.with_transformation(Transformation::rotate(percentage(delta))),
    )
```

`percentage(delta)` turns "0 to 1" into "0 to a full turn". It needs a value between 0 and 1, so do not use an easing that overshoots here. You need an asset source for `.path(...)`. See [Show images, icons and SVG](/guides/images-svg-and-assets/).

## Use a spring when the target can change

A timed animation always takes the same time, and restarts if you interrupt it. A **spring** is for things that move toward a target which can change while they move: a panel that follows a selection, a thing you drag and release. The spring keeps its speed when the target changes, so it feels physical.

This is from the same example. The dot slides to `target_x`, and if `target_x` changes mid-move, it redirects smoothly:

```rust
use gpui::{AnimationExt as _, SpringAnimation, SpringConfig, rgba};

let spring = SpringConfig::new(170.0, 14.0, 1.0); // stiffness, damping, mass

div()
    .absolute()
    .size(px(24.))
    .rounded_full()
    .bg(rgba(0x3b82f6ff))
    .with_spring(
        "spring-position",
        SpringAnimation::new(spring).to(target_x).with_epsilon(0.25),
        |this, left| this.left(left),
    )
```

- **Stiffness** is how hard the spring pulls. **Damping** is how fast it calms down. Less damping means more wobble.
- `.to(target)` accepts a number, `Pixels`, `Rems` or a `bool`.
- `.with_epsilon(e)` says how close counts as "arrived". When it arrives, the animation stops asking for frames.
- A spring that appears for the first time starts **at** its target, so nothing moves. Use `.from(start)` for a slide-in.

Pick `with_animation` for fire-and-forget effects of a known length (spinners, flashes, fade-ins). Pick `with_spring` when the target changes while the element moves.

## What you can and cannot animate

You can animate anything your function can change on that element with the style methods: opacity, size, margins, padding, position, colors, borders, radii, and SVG rotation.

You cannot:

- Animate your own struct fields, scroll position or focus. These are not part of the element.
- Rotate or scale a `div`. Only `svg()` can.
- Get a smooth change by just changing a style. If you change `.bg(a)` to `.bg(b)`, it switches at once. Wrap it in an animation or spring.
- Animate an element as it leaves. When an element is removed from the tree, its animation goes with it.

## Common mistakes

:::caution[An animation that never restarts]
A one-time animation stays finished. To play it again, change its id: `format!("flash-{}", self.flash_count)`. Two animations in the same place with the same id share their progress.
:::

- **An id that changes on every render.** The animation restarts forever, because GPUI sees a brand-new animation each frame. Keep ids stable.
- **Assuming `delta` stays in 0 to 1.** Some easing curves overshoot. Clamp before passing it to something with limits, like `percentage`.
- **Leaving a spinner running when nobody sees it.** A repeating animation redraws the window every frame. Use `.with_max_fps(30.0)` for slow indicators.
- **Expecting a slide-in from a spring.** A new spring starts at its target. Add `.from(...)`.

### Reduced motion

If the user prefers less motion, call `cx.set_reduce_motion(true)`. Animations then draw their end state (or start state for repeating ones) and stop asking for frames. Make sure both look right.

## Next steps

- [Style your elements](/guides/styling/) for the values you can animate
- [Debug and speed up your app](/guides/debugging-and-performance/) to keep frame times low
- Want the why? [Views and render](/deep-dive/views-and-render/) explains why `render` runs again during an animation

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/elements/animation.rs` (`Animation`, `AnimationExt`, easing)
- `crates/gpui/src/spring.rs` (`SpringConfig`, `SpringAnimation`)
- `crates/gpui/src/elements/svg.rs` (`Transformation`)
- `crates/gpui/src/app.rs` (`reduce_motion`)
- `crates/gpui/examples/animation.rs`
</details>
