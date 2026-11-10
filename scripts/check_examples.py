"""Extract each page's complete `fn main` program and `cargo check` it against GPUI.
Usage: python3 scripts/check_examples.py <workdir>"""
import os, re, subprocess, sys
work = sys.argv[1]
docs = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src/content/docs')
REV = 'b5cd310b3b54dfc659fcc06453e6358843dfe216'
pages = {'hello-world':'start/hello-world.md','counter':'tutorials/counter.md','todo':'tutorials/todo-list.md',
         'longlists':'tutorials/long-lists.md','textinput':'tutorials/text-input.md','stateviews':'guides/state-and-views.md',
         'actions':'guides/actions-and-keybindings.md','focus':'guides/focus.md',
         'async':'guides/async-and-executors.md','animation':'guides/animation.md'}
only = sys.argv[2:] or list(pages)
env = dict(os.environ, CARGO_TARGET_DIR=os.path.join(work,'target'))
fail = 0
for name in only:
    t = open(os.path.join(docs, pages[name])).read()
    mains = [b for b in re.findall(r"```rust[^\n]*\n(.*?)```", t, re.S) if 'fn main' in b]
    if not mains: print(name, 'NO PROGRAM FOUND'); fail += 1; continue
    code = max(mains, key=len)
    d = os.path.join(work, name); os.makedirs(d + '/src', exist_ok=True)
    open(d + '/src/main.rs', 'w').write(code)
    extra = 'unicode-segmentation = "1"\n' if name == 'textinput' else ''
    open(d + '/Cargo.toml', 'w').write(f'''[package]
name = "chk-{name}"
version = "0.1.0"
edition = "2024"

[dependencies]
gpui = {{ git = "https://github.com/zed-industries/zed", rev = "{REV}" }}
gpui_platform = {{ git = "https://github.com/zed-industries/zed", rev = "{REV}", features = ["wayland", "x11"] }}
{extra}''')
    r = subprocess.run(['cargo', 'check', '--color', 'never'], cwd=d, env=env, capture_output=True, text=True)
    ok = r.returncode == 0
    print(f"{name}: {'OK' if ok else 'FAIL'} ({len(code.splitlines())} lines)")
    if not ok:
        fail += 1
        print('\n'.join(l for l in r.stderr.splitlines() if l.startswith(('error', ' -->', '  |')) or 'help' in l)[:3500])
sys.exit(1 if fail else 0)
