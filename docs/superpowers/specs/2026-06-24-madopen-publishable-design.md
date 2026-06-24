# madopen — publishable redesign

**Date:** 2026-06-24
**Status:** Approved design, pre-implementation
**Goal:** Make madopen system-agnostic and publishable (pip/pipx, eventually PyPI):
remove hardcoded paths and the bundled `madft` binary, move data to XDG dirs,
ship the shell integration via a self-emitting `init` subcommand, and add a
configurable rich-preview picker. Plus three small, independent fixes.

> **Commit policy:** Per the maintainer, there is **no initial commit yet** — not
> even this spec. The repo has never tracked initial development, so everything
> lands in **one clean initial commit once it's all packaged and ready**. This
> spec lives as an untracked file until then.

---

## 1. Packaging & layout

madopen becomes a pip-installable package (`pipx install .` from a clone today,
PyPI later).

### New tree

```
madopen/
├── pyproject.toml          # name=madopen, requires-python>=3.11, deps=[click]
├── README.md               # rewritten (see §4)
├── src/madopen/
│   ├── __init__.py
│   ├── cli.py              # former bin/madopen.py, XDG-ified
│   ├── shell.py            # zsh/bash init templates + emitter
│   └── preview.py          # PREVIEW_SH shell-string constant + env builder (see §5)
└── docs/superpowers/specs/2026-06-24-madopen-publishable-design.md
```

- **`bin/` is deleted.** `bin/madft` (the ~2 MB binary) goes — madft is an
  external dependency (see §4). `bin/madopen.py` moves to `src/madopen/cli.py`.
- **`madopen.sh` is deleted** — its logic moves into `shell.py` (see §2).

### Entry point

```toml
[project.scripts]
madopen-bin = "madopen.cli:entry"
```

`entry()` is a thin dispatcher:

```python
def entry():
    if len(sys.argv) >= 2 and sys.argv[1] == "init":
        return shell_init(sys.argv[2] if len(sys.argv) > 2 else "zsh")  # from shell.py
    return main()  # the existing click command
```

This avoids restructuring the whole CLI into a click *group* with a fragile
"default subcommand". The binary is named `madopen-bin` so it never collides
with the `madopen` shell **function** (see §2) — different names, no recursion.

### Path resolution — XDG, nothing hardcoded

| What | Today | After |
|---|---|---|
| `history.db` | `MADOPEN_HOME/history.db` (the checkout) | `$XDG_STATE_HOME/madopen/history.db` → default `~/.local/state/madopen/`, created on first use |
| `madft` | bundled in `bin/`, absolute path | resolved from `PATH` only |
| `.desktop` dirs | `~/.local/share/applications` + `/usr/share/applications` | `$XDG_DATA_HOME` + `$XDG_DATA_DIRS` (mirrors how madft resolves them) |
| `MADOPEN_HOME` | hardcoded `/home/samtell/...` | **removed entirely** |
| config | none | `$XDG_CONFIG_HOME/madopen/config.toml` (optional, see §5) |

- `history.db` is machine-local regenerable **state**, so `XDG_STATE_HOME`
  (`~/.local/state`) is the correct bucket — distinct from madft's hand-editable
  `categories.toml` living in `XDG_DATA_HOME`.
- **`.envrc`** (the maintainer's dev-time direnv file with the hardcoded
  `/home/samtell/...` paths) is **gitignored** — it's personal, never committed,
  irrelevant to installed users.

---

## 2. Shell integration

The `cd`-into-the-directory behavior requires a shell **function** (a child
process can't `cd` its parent), so the integration ships zoxide-style: the binary
emits its own function.

- **`madopen-bin init zsh|bash`** prints **only** the `madopen()` function — the
  same fd-3 dance as today's `madopen.sh`, but calling `madopen-bin "$@"` instead
  of an absolute `MADOPEN_HOME` path. Function name `madopen` ≠ binary name
  `madopen-bin`, so no recursion.
- **No aliases** are emitted. The `o`/`oh`/`vim`/`vimh` aliases are personal
  taste and move to the user's own `.zshrc`; the README shows them as suggested
  examples.
- Users add one line to their rc:

  ```sh
  eval "$(madopen-bin init zsh)"
  # suggested aliases (optional, copy what you like):
  alias o='madopen'  oh='madopen -h'  vim='madopen -a nvim'  vimh='madopen -h -a nvim'
  ```

- `init` defaults to `zsh` if no shell argument is given; `bash` is also
  supported (the fd dance is effectively identical between the two).

---

## 3. Small, independent fixes

These need no design discussion; captured here so the implementation plan covers
them.

### 3.1 `-p` / `--peek` uses the caller's cwd

Thread the launch directory through `open_with`:

- **Without `-p`** → `cwd = file's parent` (unchanged; you're `cd`-ing there anyway).
- **With `-p`** → `cwd = os.getcwd()`, so a launched app's file-picker (nvim, etc.)
  sees the project root you deliberately stayed in, not the file's subdirectory.

(The maintainer confirmed the todo's wording was a typo: current `cwd=parent`
behavior is correct **without** `-p`.)

### 3.2 Flip Tab / Shift-Tab and wrap

In the Python picker (`fzf_pick`), change the bind from `tab:down,shift-tab:up`
to **`tab:up,shift-tab:down`** and add **`--cycle`** (wrap). Tab walks *up* the
list; Shift-Tab at the bottom wraps to the top. README picker section updated to
match. (These become part of the picker's built-in fzf defaults — see §5.)

### 3.3 proj-mode bug — investigation only

**No madopen code change.** Inspect `~/.config/proj` (the maintainer's personal,
unpublished productivity system) to find why its `cd`-into-directory zsh function
reports *"directory is not in the project"* for a directory that is in the
project. Record findings in `todo.md`. Likely a proj-side issue, as suspected.

---

## 4. Docs (README rewrite)

- **Install** section → `pipx install` (from the clone now, PyPI later); the
  `eval "$(madopen-bin init zsh)"` line; suggested aliases as examples.
- **`madft`** documented as a **cargo** dependency: `cargo install` then
  `madft init` (it owns `~/.local/share/madft/categories.toml`). Remove the old
  "bundled in `bin/`" line.
- Remove the `source madopen.sh` instruction.
- **Dependency table** updated: drop bundled-madft; add **optional** preview
  enhancers — `chafa` (images, video stills, pdf rendering), `ffmpegthumbnailer`
  (video frames), `poppler`/`pdftoppm` (pdf) — all degrade gracefully when absent.
- **Picker** section reflects the new Tab/Shift-Tab/`--cycle` behavior and the
  optional `config.toml`.

---

## 5. Configurable picker + rich previews

### What stays in Python vs. shell

Everything is in Python; the preview is shell **text** (as it already is today —
`_FZF_PREVIEW`), but stored as a Python string, not a separate file:

- **`fzf_filter`** (non-interactive `-f`, used for *ranking* inside scoring) — a
  pure algorithm primitive, **stays in Python**, unaffected.
- **`fzf_pick`** (the interactive picker) — **stays in Python**. It builds and
  runs the fzf invocation (this is where the §3.2 `tab`/`--cycle` defaults live),
  reads the optional `config.toml`, and passes the preview shell string to fzf's
  `--preview`.
- **`preview.py`** holds `PREVIEW_SH` (the renderer shell string) plus a small
  helper that builds the environment (image backend, toggles) from config. fzf
  runs the string via `sh -c` on each keystroke, so the render stays fast
  pure-shell — **Python is never in the per-keystroke loop**.

> Rationale (decided after review): launching fzf, parsing TOML, and dispatching
> to a custom picker are all one-shot orchestration — Python's job, which
> `fzf_pick` already does. The preview must *be* shell (fzf runs it directly),
> but where the shell text lives is free: a Python string keeps packaging simple
> (no package-data / `importlib.resources`) and matches "the picker is in
> Python." Shipping it as a standalone `.sh` file buys only shellcheck/syntax
> highlighting for a still-modest script — not worth the extra artifact now;
> trivially extractable later if it grows. A full standalone *picker* script was
> also considered and rejected: its claimed benefits (customization, no-TOML-dep)
> are either covered by the TOML + `custom_picker` mechanism below or too weak to
> justify a Python↔shell candidate/selection round-trip.

### The preview renderer (`PREVIEW_SH`)

A shell-string constant in `preview.py`, passed to fzf as the `--preview`
command (fzf substitutes the current item for `{}` and runs it via `sh -c`, as
today). Config-driven knobs (image backend, video/pdf toggles) are read from
`config.toml` by Python and passed to fzf's preview via environment variables.
Branches, each `command -v`-guarded so a missing tool degrades to today's
behavior:

| kind | tool | fallback |
|---|---|---|
| dir | `eza -la --color=always --group-directories-first` | `ls -la` |
| text | `bat --color=always --style=numbers` | `head -n 300` |
| image | `chafa -s ${FZF_PREVIEW_COLUMNS}x${FZF_PREVIEW_LINES}` (auto-detects kitty/sixel/iterm/symbols) | `file -b` |
| video | `ffmpegthumbnailer` → pipe into `chafa` | `file -b` |
| pdf | `pdftoppm -png -f 1 -l 1` → pipe into `chafa` | `pdfinfo` / `file -b` |
| other | `file -b` | — |

- Preserves today's behavior: prints the full path on top (so long paths are
  visible) and strips a trailing `" (new)"` label (from the `--new` dir picker).
- fzf exports `FZF_PREVIEW_COLUMNS` / `FZF_PREVIEW_LINES`, used to size images.
- The grown branch set lives in `PREVIEW_SH` (a Python string in `preview.py`);
  if it ever becomes unwieldy to maintain inside Python, extracting it to a real
  `.sh` file (for shellcheck) is a localized later change.

### `config.toml`

`$XDG_CONFIG_HOME/madopen/config.toml`, **all keys optional**, read by Python
(stdlib `tomllib`, hence `requires-python >= 3.11`; a `tomli` fallback is a
one-line option if a lower floor is ever wanted). Deliberately flat schema.
Illustrative:

```toml
# ~/.config/madopen/config.toml  (all optional)
preview_window = "right:50%:wrap"
enable_preview = true
image_backend  = "chafa"          # passed to the preview shell via env
enable_video   = true
enable_pdf     = true
fzf_flags      = ["--cycle"]      # extra flags appended to the defaults

# Full-control escape hatch — overrides everything above:
custom_picker  = "/path/to/my-picker.sh"
```

Two customization pipelines:

1. **Preset TOML** — presets configure the Python-built fzf invocation and are
   passed to the preview shell via environment variables. For users for whom
   defaults-plus-knobs suffice.
2. **`custom_picker`** — if set and executable, Python invokes that script
   **instead** of the built-in picker (candidates → stdin, selection ← stdout)
   and **ignores all other options** (we can't meaningfully inject presets into
   an arbitrary script). The custom picker lives at a **user-owned path**, so
   madopen updates never touch it.

Documented guidance: the built-in preview/picker is part of the installed
package — **don't edit it in place** (updates overwrite it). For full control,
point `custom_picker` at your own file.

---

## Out of scope (noted for later)

- **madft `.desktop` query.** The Python `.desktop` parsing (`find_desktop`,
  `desktop_exec`, `APP_DIRS`) is a self-contained seam. The maintainer plans to
  add a madft command (Rust) to return an app's `Exec`/`Terminal` lines, after
  which madopen can drop the Python parsing. Built on the current Python parsing
  for now; the eventual swap is a localized change.
```
