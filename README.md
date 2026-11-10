# GPUI Docs

Unofficial, beginner-friendly documentation for [GPUI](https://gpui.rs/), the GPU-accelerated Rust UI framework behind the [Zed](https://zed.dev) editor.

The official GPUI documentation is thin, so these docs are written by reading the source code. They aim to be as clear as the React or Tauri docs: plain English, a runnable example on every page, and a guided tour of the codebase for people who want to go deeper.

> **Status:** early. GPUI is pre-1.0 and its API changes often. Every page is checked against a pinned Zed commit (`b5cd310b`). Corrections are very welcome.

## What is inside

| Section | For |
| --- | --- |
| **Start Here** | What GPUI is, a Rust refresher, installation, Hello World, the mental model |
| **Tutorials** | Build a counter, a todo list, long lists and a text input |
| **Guides** | Styling, layout, events, shortcuts, focus, async work, text, assets, animation, windows, testing |
| **Deep Dive** | How GPUI owns data, contexts, entities, views and elements |
| **Codebase Tour** | How to read the GPUI source, and how one frame is drawn |
| **Reference** | Examples index, Cargo features, glossary, common errors |

## Run it locally

You need Node.js 20 or newer.

```sh
npm install
npm run dev      # http://localhost:4321
npm run build    # static site in dist/
```

Built with [Astro Starlight](https://starlight.astro.build).

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md). It covers the writing guide and the two checks every change should pass: a link checker and a compile check for full example programs.

## License

[Apache-2.0](LICENSE). Code samples are adapted from the GPUI source and examples, which are Apache-2.0 licensed by Zed Industries, Inc. See [NOTICE](NOTICE). This project is not affiliated with Zed Industries.
