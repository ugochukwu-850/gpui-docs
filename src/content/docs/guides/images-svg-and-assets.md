---
title: Show images, icons and SVG
description: Display pictures from files, bundled assets or URLs, draw recolorable icons, and paint simple shapes yourself.
sidebar:
  order: 9
  label: Images and assets
---

How do you show a logo, a photo from the web, or a small icon that changes color with your theme? GPUI has three building blocks for this, and this page shows each one.

## What you'll learn

- How to show an image with `img()`
- How to bundle files with your app using an asset source
- What to do while an image loads, or when it fails
- How to show web images (you need one extra step)
- How to draw a recolorable icon with `svg()`
- How to draw simple shapes yourself with `canvas`

## Pick the right tool

| You want | Use |
|---|---|
| A photo, PNG, JPEG, GIF, WebP, or a full-color SVG | `img(source)` |
| A one-color icon that follows `text_color` | `svg().path("icons/x.svg")` |
| Lines, charts, hand-drawn shapes | `canvas(..)` |

All three are ordinary elements. You size them like any other element and place them with flex layout (see [Lay things out](/guides/layout/)).

## Show an image

The smallest example is an image from your disk:

```rust
use std::path::PathBuf;
use gpui::{div, img, prelude::*, px};

div().child(img(PathBuf::from("/path/to/photo.png")).size(px(256.)))
```

You see the picture, squeezed into a 256 by 256 pixel box. `img` accepts several kinds of source, and GPUI picks the right way to load each one:

| You pass | GPUI loads it from |
|---|---|
| A `PathBuf` or `&Path` | The file system |
| A string that is a URL (`"https://..."`) | The network |
| Any other string (`"images/logo.png"`) | Your bundled assets (next section) |

:::caution[Common mistake]
A plain string is **not** treated as a file path. `img("photos/cat.png")` looks in your bundled assets, not on disk. For a file on disk, pass a `PathBuf`.
:::

These examples come from `crates/gpui/examples/image/image.rs`:

```rust
div()
    .child(img(local_path.clone()).size(px(256.)))            // a file on disk
    .child(img("image/app-icon.png").size(px(256.)))          // a bundled asset
    .child(img("https://picsum.photos/800/400").h(px(180.)))  // from the web
```

If you set only a width or only a height, the other side follows the picture's shape, so it is never stretched. Set neither, and you get the image's own size.

To control how a picture fills its box, use `object_fit`:

```rust
img(path).size(px(200.)).object_fit(gpui::ObjectFit::Cover) // crop to fill
```

The options are `Fill`, `Contain` (the default), `Cover`, `ScaleDown` and `None`. You can also call `.grayscale(true)`.

Animated GIFs and WebP files play on their own. `crates/gpui/examples/gif_viewer.rs` is a complete GIF viewer in about 20 lines.

## Bundle files with your app

An **asset source** is how your app finds files that ship with it: icons, images, fonts. You write a small struct that can load a file by name, and register it before the app runs. This is from `crates/gpui/examples/svg/svg.rs`:

```rust
use std::{fs, path::PathBuf};
use gpui::{AssetSource, SharedString};

struct Assets {
    base: PathBuf,
}

impl AssetSource for Assets {
    fn load(&self, path: &str) -> anyhow::Result<Option<std::borrow::Cow<'static, [u8]>>> {
        fs::read(self.base.join(path))
            .map(|data| Some(std::borrow::Cow::Owned(data)))
            .map_err(|err| err.into())
    }

    fn list(&self, path: &str) -> anyhow::Result<Vec<SharedString>> {
        fs::read_dir(self.base.join(path))
            .map(|entries| {
                entries
                    .filter_map(|e| e.ok()?.file_name().into_string().ok())
                    .map(SharedString::from)
                    .collect()
            })
            .map_err(|err| err.into())
    }
}
```

Register it with `with_assets` **before** calling `run`:

```rust
application()
    .with_assets(Assets { base: PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("assets") })
    .run(|cx: &mut gpui::App| { /* open windows */ });
```

Now `img("logo.png")` loads `assets/logo.png` from your project folder.

This version reads files from your project folder, which is fine while you develop. To ship one executable, embed the files with `include_bytes!` or a crate such as `rust-embed`, and return `Cow::Borrowed` from `load`.

## Loading and failed images

Images load in the background, so the window never freezes. While loading, the image shows nothing. When it is done, your view redraws.

You can show something else in the meantime, or when loading fails:

```rust
img("https://example.com/photo.jpg")
    .size(px(200.))
    .with_loading(|| div().child("Loading...").into_any_element())
    .with_fallback(|| div().child("Could not load image").into_any_element())
```

- `with_loading` appears only after 200 ms, so fast loads do not flash a spinner.
- `with_fallback` appears when the load fails (a missing file, a 404, a broken image).

Errors are also written to the log. See [Debug and speed up your app](/guides/debugging-and-performance/).

## Show images from the web

:::caution[Common mistake]
By default, GPUI cannot download anything. Its built-in HTTP client always fails, so `img("https://...")` never shows the picture. You have to give the app a real HTTP client first.
:::

```rust
let app = gpui_platform::application()
    .with_http_client(std::sync::Arc::new(my_http_client)); // anything that implements http_client::HttpClient
```

The GPUI examples use `reqwest_client::ReqwestClient`, a crate in the Zed repository. Like `with_assets`, this call goes before `run`. Downloaded images are kept in memory only, not on disk.

## Draw an icon with `svg()`

An SVG icon is usually one shape. `svg()` paints it as a stencil in the current text color. One file then works in any color, in light and dark mode.

```rust
use gpui::{rgb, svg};

svg()
    .path("svg/dragon.svg")      // found through your asset source
    .size_8()
    .text_color(rgb(0xff0000))   // the icon turns red
```

You can load the file three ways:

| Method | Source |
|---|---|
| `.path("icons/a.svg")` | Your asset source |
| `.external_path("/abs/path.svg")` | A file on disk |
| `.data(&bytes)` | Bytes you already have |

Two things to remember:

- **Set a size.** An `svg()` has no size of its own. Without `.size_8()` or `.w(..).h(..)` you see nothing.
- **Set a color.** The icon takes `text_color`, so a parent can set it for you.

If the SVG has several colors that you want to keep, use `img("icon.svg")` instead. It is drawn like a normal picture, but you cannot recolor it.

To spin or scale an icon, see [Animate things](/guides/animation/).

## Draw your own shapes

For anything that is not a picture or an icon (a chart, a line, a custom control) use `canvas`. It calls your function when it is time to paint, with the element's `bounds`:

```rust
use gpui::{PathBuilder, canvas, point, px};

canvas(
    |_bounds, _window, _cx| {},                         // step 1: prepare (nothing here)
    |bounds, _state, window, _cx| {                     // step 2: paint
        let mut builder = PathBuilder::stroke(px(2.));  // a 2px line
        builder.move_to(point(bounds.origin.x + px(10.), bounds.origin.y + px(10.)));
        builder.line_to(point(bounds.origin.x + px(100.), bounds.origin.y + px(60.)));
        if let Ok(path) = builder.build() {
            window.paint_path(path, gpui::black());
        }
    },
)
.size_full()
```

You see a black line from near the top-left of the canvas to a point further right and down. `PathBuilder` also has `fill()`, `curve_to`, `add_polygon`, `close` and `dash_array`. `crates/gpui/examples/painting.rs` is a drawing pad, a pie chart and gradients in one program.

The `window.paint_*` calls only work inside the paint function of a `canvas`. Calling them from `render` or a click handler panics.

## Common mistakes

- **Remote images never appear.** Install an HTTP client with `with_http_client`.
- **"Embedded image not found".** A plain string is looked up in your assets. Use a `PathBuf` for files on disk.
- **The SVG icon is invisible.** Give it a `text_color` and a size.
- **A multi-color SVG is one color.** That is what `svg()` does. Use `img()`.
- **Calling `with_assets` inside `run`.** It is too late there. Call it on the `Application` before `run`.
- **Memory grows in a long image gallery.** By default every image stays in memory. See `crates/gpui/examples/image_gallery.rs` for a cache that drops old images.

## Next steps

- [Animate things](/guides/animation/) to spin an icon
- [Work with text and fonts](/guides/text-and-fonts/) to load fonts from the same asset source
- [Elements](/deep-dive/elements/) if you want to write your own painting element

<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/assets.rs` (`AssetSource`)
- `crates/gpui/src/elements/img.rs`, `svg.rs`, `canvas.rs`
- `crates/gpui/src/path_builder.rs`
- `crates/gpui/src/app.rs` (`with_assets`, `with_http_client`)
- `crates/gpui/examples/image/image.rs`, `svg/svg.rs`, `gif_viewer.rs`, `image_gallery.rs`, `painting.rs`
</details>
