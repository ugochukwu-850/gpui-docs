# Contributing to GPUI Docs

Thanks for helping make GPUI easier to learn. This is an **unofficial** documentation site. Every page is written from the GPUI source code, so accuracy matters more than anything else.

## Quick start

```sh
npm install
npm run dev          # http://localhost:4321
npm run build        # production build into dist/
```

Pages are Markdown or MDX files in `src/content/docs/`. The sidebar builds itself from the folders:

| Folder | What goes there |
| --- | --- |
| `start/` | Introduction, install, first app, mental model |
| `tutorials/` | Step-by-step projects |
| `guides/` | Task-based "how do I...?" pages |
| `deep-dive/` | Advanced concepts |
| `codebase/` | A guided tour of the GPUI source |
| `reference/` | Lookup tables, glossary, errors |

## Before you open a pull request

1. Follow the writing guide below.
2. Check internal links and anchors:
   ```sh
   npm run build
   python3 -I scripts/linkcheck.py dist
   ```
3. If you changed a complete `main.rs` program, compile it against GPUI at the pinned commit. The script extracts each page's full program and runs `cargo check`:
   ```sh
   python3 -I scripts/check_examples.py /some/empty/workdir [page names]
   ```
   You need Rust and the system libraries from the installation page. Page names are listed at the top of the script.
4. Say in the pull request which Zed commit you verified against.

## Writing guide

The goal: docs as welcoming and clear as react.dev, Tauri, or Actix Web. A web developer who has never seen GPUI should be able to read a page top to bottom, understand it, and run the code. If a page reads like source-code notes, it has failed.

## Who you are writing for

A developer who knows JavaScript or TypeScript and probably React, and who is comfortable (or learning to be) with basic Rust. They have never used GPUI. They are smart but busy. They do not know any GPUI vocabulary and they do not know how the Zed codebase is laid out.

## Voice

- Friendly, direct, second person: "you", "let's", "we'll". Like a good colleague explaining at a whiteboard.
- Short sentences. Aim for under 25 words. One idea per paragraph, 1 to 4 sentences per paragraph.
- Active voice. Say what to do: "Call `cx.notify()` to redraw", not "A redraw can be requested by notifying".
- Plain words. Say "use", not "utilize". Say "draws", not "rasterizes" (unless the page is about rasterizing).
- Never write: simply, just, easy, obviously, trivially, of course, clearly. They make readers feel stupid.
- No emoji, no exclamation-mark enthusiasm, no marketing fluff.
- Sentence case headings. Prefer headings a reader would search for: "Respond to clicks", "Why isn't my UI updating?".

## Structure of every page

1. **Opening paragraph (1–2 sentences):** what this page helps you do, in plain words.
2. **"What you'll learn" (3–5 bullets)**. Tutorials use **"What you'll build"** first.
3. **The smallest working example first**, then explain it. Show before tell.
4. **Explain the code** ("How it works" / line-by-line). Walk through the important lines, say what each does and why it is there.
5. Build up in small steps. Each step adds one idea and (for tutorials) shows the result the reader should see.
6. **Common mistakes** or **Troubleshooting** when real mistakes exist (use `:::caution[Common mistake]`).
7. **Next steps**: 2–3 links to the logical next pages.
8. A final collapsed **"Source"** section listing repo-relative paths, so curious readers can follow into the code:

```md
<details>
<summary>Where this lives in the source</summary>

- `crates/gpui/src/element.rs`
</details>
```

## Teaching rules

- **Define every term the first time you use it**, in plain English, ideally with a React/web analogy. Example: "A *view* is a struct that knows how to draw itself. It is GPUI's version of a React component."
- Only compare to React where the comparison is accurate. Mark it with an aside: `:::note[Coming from React?]`. Do not force analogies that mislead.
- **Do not use internal jargon in beginner pages** (start, tutorials, guides): "retained/immediate mode", "effects queue", "leases", "arena", "hitbox", "dispatch tree", "request_layout/prepaint/paint" and similar. If one is truly unavoidable, define it in a sentence and link to the Deep Dive page. Those words belong in `deep-dive/`, `codebase/` and `reference/`.
- Introduce at most 2–3 new ideas per section. Big pages get split into sections with clear headings.
- Use concrete examples (a counter, a todo list, a sidebar), not abstract `Foo` and `Bar`.
- Explain **why**, not only what. "We call `cx.notify()` because GPUI does not watch your fields. It only redraws when you tell it the data changed."
- Tell the reader what they will **see** when the code runs ("A 500x500 window with a gray background and the text Hello, World!").

## Code

- Code must be **correct for the pinned commit** `b5cd310b` (check against a local checkout of the Zed repo at that commit). Never invent an API. If unsure, read the source or drop the snippet.
- Existing pages in `src/content/docs/` were derived from the source and are a good fact base. The five `main.rs` programs in `start/hello-world`, `tutorials/counter`, `todo-list`, `text-input`, `long-lists` are **compile-verified**: keep their final complete programs **byte-for-byte identical** (you may add comments only if you re-check that the code is otherwise unchanged).
- Prefer short snippets (under ~30 lines). Add `// comments` that explain intent. Use code block titles (` ```rust title="src/main.rs" `) and line highlights (` {3-5} `) where helpful.
- Large programs go in a collapsible `<details><summary>Complete src/main.rs</summary>` block after the step-by-step explanation, so the page does not become a wall of code. (In `.md` files raw `<details>` works; leave blank lines around the fenced code.)
- When a snippet is new (not copied from an example or a verified program), say so in your final report so a maintainer can compile-check it.
- Show commands with ` ```sh ` blocks.

## Components and asides

Plain `.md` is fine. If you need components (Tabs for per-OS instructions, Steps, CardGrid/LinkCard for Next steps, FileTree, Badge) rename the file to `.mdx` (delete the `.md`) and import from `@astrojs/starlight/components`. Use them where they genuinely help, not everywhere.

Asides, used sparingly:

- `:::tip[Title]` helpful shortcut.
- `:::note[Coming from React?]` analogy.
- `:::caution[Common mistake]` pitfalls.
- `:::danger` only for things that lose data or crash.

## Frontmatter

```yaml
---
title: Short, human title
description: One plain sentence on what the page helps you do.
sidebar:
  order: N
  label: Short sidebar label   # optional, use when title is long
---
```
Quote the `description` if it contains `:` or backticks.

## Links

- Internal links are absolute with a trailing slash: `/guides/styling/`.
- Section folders: `/start/`, `/tutorials/`, `/guides/`, `/deep-dive/`, `/codebase/`, `/reference/`.
- Link the first mention of a concept to its page. Do not link every mention.
- Check that every link target page exists. Check every `#anchor` you use matches a real heading.

## Before / after example

Before (cryptic):

> GPUI is a hybrid immediate and retained mode, GPU accelerated, UI framework. State lives in entities leased from the entity map during update; views build an element tree each frame.

After (clear):

> GPUI is a toolkit for building desktop apps in Rust. You describe what your window should look like, and GPUI draws it on your graphics card, which makes it very fast. It is what powers the Zed code editor.
>
> You write your UI as plain Rust structs. When your data changes, you tell GPUI, and it redraws the window.

## Accuracy first

Clear does not mean sloppy. Everything must still be true. If you simplify, simplify the explanation, not the facts. If you cannot confirm something in the source, leave it out or say plainly that it is unverified. Never add claims about performance, popularity or the future that the source does not support.
