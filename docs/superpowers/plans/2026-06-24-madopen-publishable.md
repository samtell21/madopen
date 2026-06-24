# madopen Publishable Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn madopen into a system-agnostic, pip-installable tool (XDG paths, self-emitting shell integration, configurable rich-preview picker) plus three small fixes, ready for one clean initial commit.

**Architecture:** A `src/`-layout Python package (`madopen`) exposing a `madopen-bin` console script whose `entry()` dispatches `init` (emit shell function) vs. the existing click CLI. XDG path resolution and config loading move to small focused modules; the interactive picker stays in Python with the preview as a Python shell-string constant; `madft` becomes an external `PATH` dependency.

**Tech Stack:** Python ≥3.11 (stdlib `tomllib`), `click`, `pytest` (dev), setuptools (src layout). External runtime tools: `zoxide`, `fzf`, `gio`, `gtk-launch`, `madft`, `file`; optional preview tools `bat`, `eza`, `chafa`, `ffmpegthumbnailer`, `pdftoppm`.

## Global Constraints

- **No commits until the final task.** The repo has no commits; everything accumulates in the working tree and lands in **one maintainer-gated initial commit** (Task 10). Each task's gate is *tests passing*, not a commit. Do not run `git commit` until Task 10, and only on explicit maintainer go-ahead.
- **`requires-python >= 3.11`** (use stdlib `tomllib`; no `tomli` dependency).
- **Runtime dependency: `click` only.** Dev dependency: `pytest`.
- **Binary is named `madopen-bin`; the shell function is named `madopen`.** Never the same name (recursion).
- **`madft` is resolved from `PATH` only** — no bundled binary, no `MADOPEN_HOME`.
- **All external tools are optional-at-render-time where reasonable:** preview branches are `command -v`-guarded and degrade to `file -b`/`head`/`ls`.
- **Paths are XDG, resolved at call time** (so tests can monkeypatch env): history DB in `$XDG_STATE_HOME/madopen/`, config in `$XDG_CONFIG_HOME/madopen/`, `.desktop` dirs from `$XDG_DATA_HOME` + `$XDG_DATA_DIRS`.
- Reference spec: `docs/superpowers/specs/2026-06-24-madopen-publishable-design.md`.

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml` (create) | package metadata, `click` dep, `madopen-bin` entry point, src layout |
| `src/madopen/__init__.py` (create) | `__version__` |
| `src/madopen/cli.py` (move from `bin/madopen.py`) | CLI, modes, scoring, history, launching, picker, `entry()` |
| `src/madopen/paths.py` (create) | XDG path resolution (pure, env-driven) |
| `src/madopen/config.py` (create) | `load_config()` — read `config.toml`, apply defaults |
| `src/madopen/shell.py` (create) | `shell_init()` — emit the `madopen` shell function |
| `src/madopen/preview.py` (create) | `PREVIEW_SH` string + `build_preview_env()` |
| `tests/*.py` (create) | pytest suite for the pure helpers |
| `README.md` (rewrite) | install via pipx, `init` eval line, madft as cargo dep, alias examples |
| `.gitignore` (modify) | add `.envrc`; drop obsolete `history.db*` |
| `bin/madft`, `bin/madopen.py`, `bin/__pycache__`, `madopen.sh` (delete) | superseded |

---

### Task 1: Scaffold the package

**Files:**
- Create: `pyproject.toml`
- Create: `src/madopen/__init__.py`
- Move: `bin/madopen.py` → `src/madopen/cli.py`
- Modify: `src/madopen/cli.py` (add `entry()`, fix `__main__` guard)
- Create: `tests/test_entry.py`

**Interfaces:**
- Produces: console script `madopen-bin = "madopen.cli:entry"`; `entry()` returns an int exit code or `None`; `main` is the existing click command (unchanged behavior for non-`init` args).

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "madopen"
version = "0.1.0"
description = "Open recent/frequent files from anywhere, zoxide-style."
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
dependencies = ["click"]

[project.optional-dependencies]
dev = ["pytest"]

[project.scripts]
madopen-bin = "madopen.cli:entry"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: Move the module and create `__init__.py`**

```bash
mkdir -p src/madopen tests
mv bin/madopen.py src/madopen/cli.py
printf '__version__ = "0.1.0"\n' > src/madopen/__init__.py
```

- [ ] **Step 3: Add `entry()` and update the `__main__` guard in `src/madopen/cli.py`**

Add near the bottom of `cli.py`, replacing the existing `if __name__ == "__main__":` block:

```python
def entry():
    """Console-script entry: dispatch `init` to the shell emitter, else run the CLI."""
    if len(sys.argv) >= 2 and sys.argv[1] == "init":
        from . import shell  # imported lazily; shell.py arrives in Task 3
        shell_arg = sys.argv[2] if len(sys.argv) > 2 else "zsh"
        return shell.shell_init(shell_arg)
    return main()


if __name__ == "__main__":
    entry()
```

(`shell.py` does not exist until Task 3; the lazy import inside the `init`
branch means non-`init` invocations — everything tested here — never touch it.)

- [ ] **Step 4: Create the dev environment and install editable**

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

- [ ] **Step 5: Write the smoke test** — `tests/test_entry.py`

```python
import subprocess
import sys


def test_console_script_help_runs():
    # The installed entry point responds to --help via the click CLI.
    out = subprocess.run(
        [sys.executable, "-m", "madopen.cli", "--help"],
        capture_output=True, text=True,
    )
    assert out.returncode == 0
    assert "Usage" in out.stdout


def test_entry_dispatches_non_init_to_main(monkeypatch):
    import madopen.cli as cli
    called = {}
    monkeypatch.setattr(cli, "main", lambda: called.setdefault("main", True))
    monkeypatch.setattr(sys, "argv", ["madopen-bin", "report"])
    cli.entry()
    assert called.get("main") is True
```

- [ ] **Step 6: Run the tests**

Run: `.venv/bin/pytest tests/test_entry.py -v`
Expected: PASS (2 passed)

---

### Task 2: XDG path resolution

**Files:**
- Create: `src/madopen/paths.py`
- Modify: `src/madopen/cli.py` (replace `HOME`/`DB_PATH`/`MADFT`/`APP_DIRS`; update `connect()`, `find_desktop()`)
- Create: `tests/test_paths.py`

**Interfaces:**
- Produces: `paths.state_dir() -> str`, `paths.db_path() -> str`, `paths.config_path() -> str`, `paths.app_dirs() -> list[str]`. All read env at call time.

- [ ] **Step 1: Write the failing test** — `tests/test_paths.py`

```python
from madopen import paths


def test_db_path_uses_xdg_state_home(monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", "/tmp/xstate")
    assert paths.state_dir() == "/tmp/xstate/madopen"
    assert paths.db_path() == "/tmp/xstate/madopen/history.db"


def test_db_path_defaults_without_xdg(monkeypatch):
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setenv("HOME", "/home/u")
    assert paths.db_path() == "/home/u/.local/state/madopen/history.db"


def test_config_path_uses_xdg_config_home(monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/xcfg")
    assert paths.config_path() == "/tmp/xcfg/madopen/config.toml"


def test_app_dirs_includes_data_home_first_then_data_dirs(monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/xdata")
    monkeypatch.setenv("XDG_DATA_DIRS", "/a:/b")
    assert paths.app_dirs() == [
        "/tmp/xdata/applications", "/a/applications", "/b/applications",
    ]


def test_app_dirs_defaults(monkeypatch):
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_DIRS", raising=False)
    monkeypatch.setenv("HOME", "/home/u")
    assert paths.app_dirs() == [
        "/home/u/.local/share/applications",
        "/usr/local/share/applications",
        "/usr/share/applications",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_paths.py -v`
Expected: FAIL with "No module named 'madopen.paths'"

- [ ] **Step 3: Create `src/madopen/paths.py`**

```python
"""XDG directory resolution. Pure and env-driven so tests can monkeypatch."""
import os


def _xdg(env, default_subpath):
    val = os.environ.get(env)
    if val:
        return val
    return os.path.join(os.path.expanduser("~"), default_subpath)


def state_dir():
    """The madopen state directory ($XDG_STATE_HOME/madopen)."""
    return os.path.join(_xdg("XDG_STATE_HOME", ".local/state"), "madopen")


def db_path():
    """Full path to the history database."""
    return os.path.join(state_dir(), "history.db")


def config_path():
    """Full path to the optional config.toml ($XDG_CONFIG_HOME/madopen)."""
    return os.path.join(_xdg("XDG_CONFIG_HOME", ".config"), "madopen", "config.toml")


def app_dirs():
    """`applications/` dirs, highest precedence first: data_home then data_dirs."""
    data_home = _xdg("XDG_DATA_HOME", ".local/share")
    data_dirs = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    bases = [data_home] + [d for d in data_dirs.split(":") if d]
    return [os.path.join(d, "applications") for d in bases]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_paths.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Wire `paths` into `cli.py`**

In `src/madopen/cli.py`, add `from . import paths` to the imports.

Delete these module-level lines:

```python
HOME = os.environ.get("MADOPEN_HOME", "/home/samtell/projects/madopen")
DB_PATH = HOME + "/history.db"

# madft is bundled in bin/; fall back to PATH if it's been moved.
MADFT = os.path.join(HOME, "bin", "madft")
if not os.path.exists(MADFT):
    MADFT = "madft"
```

Replace with:

```python
# madft is an external dependency, resolved from PATH.
MADFT = "madft"
```

Delete the module-level `APP_DIRS = [...]` line entirely.

Update `connect()` to use the XDG db path and ensure its directory exists:

```python
def connect():
    os.makedirs(paths.state_dir(), exist_ok=True)
    conn = sqlite3.connect(paths.db_path())
    ensure_schema(conn)
    return conn
```

In `find_desktop()`, change the loop header from `for d in APP_DIRS:` to:

```python
    for d in paths.app_dirs():
```

- [ ] **Step 6: Verify nothing references the deleted names**

Run: `grep -nE "MADOPEN_HOME|DB_PATH|APP_DIRS|HOME \+" src/madopen/cli.py`
Expected: no output (all references removed).

- [ ] **Step 7: Run the full suite + a smoke run**

Run: `.venv/bin/pytest -q && .venv/bin/python -m madopen.cli --help`
Expected: tests PASS; `--help` prints usage.

---

### Task 3: Self-emitting shell integration

**Files:**
- Create: `src/madopen/shell.py`
- Create: `tests/test_shell.py`
- (Modify already done in Task 1: `entry()` dispatches `init`.)
- Delete: `madopen.sh`

**Interfaces:**
- Consumes (from Task 1): `entry()` calls `shell.shell_init(shell_arg)`.
- Produces: `shell.shell_init(shell="zsh") -> int` — writes the function to stdout, returns 0 on success, nonzero for an unsupported shell.

- [ ] **Step 1: Write the failing test** — `tests/test_shell.py`

```python
from madopen import shell


def test_init_emits_function_calling_the_binary(capsys):
    rc = shell.shell_init("zsh")
    out = capsys.readouterr().out
    assert rc == 0
    assert "madopen()" in out                 # defines the function
    assert "madopen-bin" in out               # calls the binary (no recursion)
    assert "3>&1 1>/dev/tty" in out           # the fd-3 cd dance is preserved
    assert "cd -- " in out


def test_init_emits_no_aliases(capsys):
    shell.shell_init("zsh")
    out = capsys.readouterr().out
    assert "alias o=" not in out
    assert "alias oh=" not in out


def test_init_bash_supported(capsys):
    assert shell.shell_init("bash") == 0
    assert "madopen()" in capsys.readouterr().out


def test_init_unsupported_shell_errors():
    assert shell.shell_init("fish") != 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_shell.py -v`
Expected: FAIL with "No module named 'madopen.shell'"

- [ ] **Step 3: Create `src/madopen/shell.py`**

```python
"""Shell integration emitted by `madopen-bin init <shell>` (zoxide-style).

A child process can't cd its parent shell, so madopen-bin prints the directory
on fd 3 and this function cd's into it. The function is named `madopen` while
the binary is `madopen-bin`, so there is no recursion.
"""
import sys

# The body is POSIX-sh compatible, so the same text serves zsh and bash.
_FUNCTION = r"""madopen() {
    local dir
    # 3>&1  -> fd 3 becomes the command-substitution capture pipe
    # 1>/dev/tty -> the binary's (and any editor's) stdout goes to the terminal
    dir="$(madopen-bin "$@" 3>&1 1>/dev/tty)" || return
    [ -n "$dir" ] && [ -d "$dir" ] && cd -- "$dir"
}
"""

_SUPPORTED = ("zsh", "bash")


def shell_init(shell="zsh"):
    """Emit the madopen shell function for `shell`. Returns an exit code."""
    if shell not in _SUPPORTED:
        sys.stderr.write(
            f"madopen: unsupported shell '{shell}' (supported: {', '.join(_SUPPORTED)})\n"
        )
        return 1
    sys.stdout.write(_FUNCTION)
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_shell.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Add an `entry()` dispatch test** — append to `tests/test_entry.py`

```python
def test_entry_init_emits_shell_function(monkeypatch, capsys):
    import madopen.cli as cli
    monkeypatch.setattr(sys, "argv", ["madopen-bin", "init", "zsh"])
    rc = cli.entry()
    out = capsys.readouterr().out
    assert rc == 0
    assert "madopen()" in out
    assert "madopen-bin" in out
```

- [ ] **Step 6: Delete the old shell file**

```bash
rm -f madopen.sh
```

- [ ] **Step 7: Run the suite + verify the real entry point**

Run: `.venv/bin/pytest -q && .venv/bin/madopen-bin init zsh`
Expected: tests PASS; the command prints the `madopen()` function.

---

### Task 4: `-p`/`--peek` uses the caller's cwd

**Files:**
- Modify: `src/madopen/cli.py` (`open_with`, `record_open`; add `resolve_launch_cwd`)
- Create: `tests/test_peek.py`

**Interfaces:**
- Produces: `resolve_launch_cwd(path, peek) -> str` — `os.getcwd()` when `peek`, else the file's parent dir.
- Changed: `open_with(path, app=None, app_args=None, cwd=None)` — `cwd` overrides the launch directory (defaults to the file's parent). `record_open` passes `cwd=resolve_launch_cwd(target_path, peek)`.

- [ ] **Step 1: Write the failing test** — `tests/test_peek.py`

```python
import os
from madopen import cli


def test_launch_cwd_without_peek_is_file_parent():
    assert cli.resolve_launch_cwd("/a/b/c.txt", peek=False) == "/a/b"


def test_launch_cwd_with_peek_is_caller_cwd(monkeypatch):
    monkeypatch.setattr(os, "getcwd", lambda: "/project/root")
    assert cli.resolve_launch_cwd("/a/b/c.txt", peek=True) == "/project/root"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_peek.py -v`
Expected: FAIL with "module 'madopen.cli' has no attribute 'resolve_launch_cwd'"

- [ ] **Step 3: Add `resolve_launch_cwd` and thread `cwd` through `open_with`**

Add this helper above `open_with` in `cli.py`:

```python
def resolve_launch_cwd(path, peek):
    """Launch directory for an opened file: the caller's cwd under --peek (so the
    app's file-picker sees the dir you stayed in), else the file's own parent."""
    return os.getcwd() if peek else str(Path(path).parent)
```

Change the `open_with` signature and its `cwd` usage:

```python
def open_with(path, app=None, app_args=None, cwd=None):
    """... (existing docstring) ...

    `cwd` overrides the directory the app is launched in (default: the file's
    parent); --peek passes the caller's cwd so a file-picker stays at the root."""
    parent = str(Path(path).parent)
    launch_cwd = cwd or parent
```

Then in the two launch calls within `open_with`, replace `cwd=parent` with `cwd=launch_cwd`:

```python
    if terminal:
        subprocess.run(argv + list(app_args or []) + [str(path)], cwd=launch_cwd)
    else:
        subprocess.Popen(
            ["gtk-launch", os.path.basename(desktop), str(path)],
            cwd=launch_cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
```

- [ ] **Step 4: Pass the peek-derived cwd from `record_open`**

In `record_open`, change the `open_with` call from `open_with(target_path, app, app_args)` to:

```python
    open_with(target_path, app, app_args, cwd=resolve_launch_cwd(target_path, peek))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_peek.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Manual smoke check**

From a project root containing a subdir with a file, run `madopen -p sub/file.txt`
(after Task 3's `eval`), confirm your shell stays put and nvim's file browser
shows the root, not `sub/`. Then run without `-p` and confirm it cd's into `sub/`.

---

### Task 5: Config loader

**Files:**
- Create: `src/madopen/config.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Consumes: `paths.config_path()`.
- Produces: `config.load_config(path=None) -> dict` with keys `preview_window` (str), `enable_preview` (bool), `image_backend` (str), `enable_video` (bool), `enable_pdf` (bool), `fzf_flags` (list[str]), `custom_picker` (str|None). Missing/malformed file → all defaults.

- [ ] **Step 1: Write the failing test** — `tests/test_config.py`

```python
from madopen import config


def test_missing_file_returns_defaults(tmp_path):
    cfg = config.load_config(str(tmp_path / "nope.toml"))
    assert cfg["preview_window"] == "right:50%:wrap"
    assert cfg["enable_preview"] is True
    assert cfg["custom_picker"] is None
    assert cfg["fzf_flags"] == []


def test_overrides_applied(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(
        'preview_window = "down:40%"\n'
        'enable_video = false\n'
        'fzf_flags = ["--no-mouse"]\n'
        'custom_picker = "/x/pick.sh"\n'
    )
    cfg = config.load_config(str(p))
    assert cfg["preview_window"] == "down:40%"
    assert cfg["enable_video"] is False
    assert cfg["fzf_flags"] == ["--no-mouse"]
    assert cfg["custom_picker"] == "/x/pick.sh"
    # untouched keys keep defaults
    assert cfg["image_backend"] == "chafa"


def test_malformed_toml_falls_back_to_defaults(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text("this is = = not valid toml [[[")
    cfg = config.load_config(str(p))
    assert cfg["preview_window"] == "right:50%:wrap"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: FAIL with "No module named 'madopen.config'"

- [ ] **Step 3: Create `src/madopen/config.py`**

```python
"""Read the optional ~/.config/madopen/config.toml. Flat schema, all keys
optional; missing or malformed files fall back to defaults."""
import tomllib

from . import paths

DEFAULTS = {
    "preview_window": "right:50%:wrap",
    "enable_preview": True,
    "image_backend": "chafa",
    "enable_video": True,
    "enable_pdf": True,
    "fzf_flags": [],
    "custom_picker": None,
}


def load_config(path=None):
    """Return the merged config dict (defaults overlaid with file values)."""
    path = path or paths.config_path()
    cfg = dict(DEFAULTS)
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except (FileNotFoundError, IsADirectoryError, tomllib.TOMLDecodeError):
        return cfg
    for key in DEFAULTS:
        if key in data:
            cfg[key] = data[key]
    return cfg
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: PASS (3 passed)

---

### Task 6: Preview module (rich renderer + env)

**Files:**
- Create: `src/madopen/preview.py`
- Create: `tests/test_preview.py`
- Modify: `src/madopen/cli.py` (remove the old `_FZF_PREVIEW` constant; Task 7 wires in `PREVIEW_SH`)

**Interfaces:**
- Consumes: a config dict (from Task 5).
- Produces: `preview.PREVIEW_SH` (str, contains the `{}` fzf placeholder) and `preview.build_preview_env(config) -> dict[str, str]` mapping `MADOPEN_IMAGE_BACKEND`, `MADOPEN_ENABLE_VIDEO`, `MADOPEN_ENABLE_PDF`.

- [ ] **Step 1: Write the failing test** — `tests/test_preview.py`

```python
from madopen import preview


def test_env_maps_backend_and_toggles():
    env = preview.build_preview_env({
        "image_backend": "kitten", "enable_video": False, "enable_pdf": True,
    })
    assert env["MADOPEN_IMAGE_BACKEND"] == "kitten"
    assert env["MADOPEN_ENABLE_VIDEO"] == ""      # falsy -> empty
    assert env["MADOPEN_ENABLE_PDF"] == "1"


def test_env_defaults_when_keys_absent():
    env = preview.build_preview_env({})
    assert env["MADOPEN_IMAGE_BACKEND"] == "chafa"
    assert env["MADOPEN_ENABLE_VIDEO"] == "1"
    assert env["MADOPEN_ENABLE_PDF"] == "1"


def test_preview_sh_has_placeholder_and_guards():
    assert "{}" in preview.PREVIEW_SH                 # fzf substitutes the path
    assert "command -v" in preview.PREVIEW_SH         # tools are guarded
    assert "(new)" in preview.PREVIEW_SH              # strips the --new label
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_preview.py -v`
Expected: FAIL with "No module named 'madopen.preview'"

- [ ] **Step 3: Create `src/madopen/preview.py`**

```python
"""The fzf preview renderer, kept as a shell-string constant (fzf runs it via
`sh -c` on each cursor move, so Python is never in the per-keystroke loop).

Config knobs arrive as environment variables (see build_preview_env): the image
backend and the video/pdf toggles. Every external tool is `command -v`-guarded,
so a missing tool degrades to `file -b` / `head` / `ls`.
"""

# Renders the item passed by fzf as {}. Layout: full path on top (so long paths
# are always visible), then a kind-specific body. A trailing " (new)" label
# (from the --new dir picker) is stripped first.
PREVIEW_SH = r"""
p={}; p="${p% (new)}"
printf '%s\n\n' "$p"

img() {
    backend="${MADOPEN_IMAGE_BACKEND:-chafa}"
    if [ "$backend" = "kitten" ] && command -v kitten >/dev/null 2>&1; then
        kitten icat --clear --transfer-mode=memory \
            --stdin=no --place="${FZF_PREVIEW_COLUMNS}x${FZF_PREVIEW_LINES}@0x0" "$1" 2>/dev/null && return
    fi
    if command -v chafa >/dev/null 2>&1; then
        chafa -s "${FZF_PREVIEW_COLUMNS}x${FZF_PREVIEW_LINES}" "$1" 2>/dev/null && return
    fi
    file -b "$1"
}

if [ -d "$p" ]; then
    eza -la --color=always --group-directories-first "$p" 2>/dev/null || ls -la "$p"
elif [ ! -e "$p" ]; then
    echo '(new file)'
else
    mt=$(file --mime-type -b "$p" 2>/dev/null)
    case "$mt" in
        image/*)
            img "$p" ;;
        video/*)
            if [ -n "$MADOPEN_ENABLE_VIDEO" ] && command -v ffmpegthumbnailer >/dev/null 2>&1; then
                tmp=$(mktemp --suffix=.png 2>/dev/null) || tmp=/tmp/madopen_vprev.png
                ffmpegthumbnailer -i "$p" -o "$tmp" -s 0 >/dev/null 2>&1 && img "$tmp"
                rm -f "$tmp"
            else
                file -b "$p"
            fi ;;
        application/pdf)
            if [ -n "$MADOPEN_ENABLE_PDF" ] && command -v pdftoppm >/dev/null 2>&1; then
                tmp=$(mktemp 2>/dev/null) || tmp=/tmp/madopen_pprev
                pdftoppm -png -f 1 -l 1 -scale-to 1000 "$p" "$tmp" >/dev/null 2>&1 && img "${tmp}-1.png"
                rm -f "${tmp}"*.png "$tmp"
            else
                pdfinfo "$p" 2>/dev/null || file -b "$p"
            fi ;;
        text/* | application/json | application/xml | application/javascript \
            | application/toml | application/x-shellscript | application/x-yaml \
            | application/x-desktop)
            bat --color=always --style=numbers --line-range=:300 "$p" 2>/dev/null \
                || head -n 300 "$p" ;;
        *)
            file -b "$p" ;;
    esac
fi
"""


def build_preview_env(config):
    """Environment variables consumed by PREVIEW_SH, derived from config."""
    return {
        "MADOPEN_IMAGE_BACKEND": config.get("image_backend") or "chafa",
        "MADOPEN_ENABLE_VIDEO": "1" if config.get("enable_video", True) else "",
        "MADOPEN_ENABLE_PDF": "1" if config.get("enable_pdf", True) else "",
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_preview.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Remove the old preview constant from `cli.py`**

Delete the entire `_FZF_PREVIEW = r"""..."""` block (the multi-line preview
string and its leading comment) from `src/madopen/cli.py`. It is replaced by
`preview.PREVIEW_SH`, wired up in Task 7.

Run: `grep -n "_FZF_PREVIEW" src/madopen/cli.py`
Expected: no output.

---

### Task 7: Rework the interactive picker (config + previews + custom_picker)

**Files:**
- Modify: `src/madopen/cli.py` (`_run` gains `env`; new `build_fzf_argv`, `custom_picker_path`; rewrite `fzf_pick`)
- Create: `tests/test_picker.py`

**Interfaces:**
- Consumes: `config.load_config` (Task 5), `preview.PREVIEW_SH` + `preview.build_preview_env` (Task 6).
- Produces: `build_fzf_argv(config, preview_cmd) -> list[str]`; `custom_picker_path(config) -> str|None`; `fzf_pick(items)` unchanged signature/return (chosen item or `""`).

- [ ] **Step 1: Write the failing test** — `tests/test_picker.py`

```python
import os
from madopen import cli


def test_fzf_argv_has_flipped_binds_and_cycle():
    argv = cli.build_fzf_argv({"preview_window": "right:50%:wrap", "fzf_flags": []},
                              "PREVIEW")
    assert "tab:up,shift-tab:down" in argv      # Tab moves UP the list
    assert "--cycle" in argv                    # wrap around
    assert "PREVIEW" in argv                     # preview command threaded through
    i = argv.index("--preview-window")
    assert argv[i + 1] == "right:50%:wrap"


def test_fzf_argv_appends_extra_flags():
    argv = cli.build_fzf_argv({"preview_window": "x", "fzf_flags": ["--no-mouse"]}, "P")
    assert argv[-1] == "--no-mouse"


def test_custom_picker_path_returns_executable(tmp_path):
    script = tmp_path / "pick.sh"
    script.write_text("#!/bin/sh\ncat\n")
    os.chmod(script, 0o755)
    assert cli.custom_picker_path({"custom_picker": str(script)}) == str(script)


def test_custom_picker_path_none_when_unset_or_missing(tmp_path):
    assert cli.custom_picker_path({"custom_picker": None}) is None
    assert cli.custom_picker_path({"custom_picker": str(tmp_path / "nope.sh")}) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_picker.py -v`
Expected: FAIL with "module 'madopen.cli' has no attribute 'build_fzf_argv'"

- [ ] **Step 3: Add `env` support to `_run`**

In `cli.py`, update `_run` to accept an optional `env`:

```python
def _run(argv, stdin=None, env=None):
    """Run `argv`, return stdout as text. `stdin`, if given, is bytes."""
    proc = subprocess.run(
        argv, input=stdin, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env,
    )
    return proc.stdout.decode("utf-8")
```

- [ ] **Step 4: Add the picker helpers and rewrite `fzf_pick`**

Add `from . import config as config_mod` and `from . import preview` to the imports.

Add the two pure helpers near `fzf_pick`:

```python
def build_fzf_argv(config, preview_cmd):
    """Assemble the interactive fzf argv from config. Tab moves up the list,
    Shift-Tab down, and --cycle wraps (best match sits at the bottom)."""
    argv = [
        "fzf", "--smart-case",
        "--bind", "tab:up,shift-tab:down",
        "--cycle",
        "--preview", preview_cmd,
        "--preview-window", config.get("preview_window", "right:50%:wrap"),
    ]
    argv += list(config.get("fzf_flags") or [])
    return argv


def custom_picker_path(config):
    """Path of a user-supplied picker if set and executable, else None."""
    p = config.get("custom_picker")
    if p and os.access(p, os.X_OK):
        return p
    return None
```

Rewrite `fzf_pick`:

```python
def fzf_pick(items):
    """Interactive pick over `items`; returns the chosen item ('' if none).

    Reads config.toml: a custom_picker (if set/executable) replaces the built-in
    picker entirely (candidates on stdin, selection on stdout, other options
    ignored); otherwise fzf runs with the configured window/flags and the rich
    preview, whose tool toggles are passed through the environment."""
    items = list(items)
    if not items:
        return ""
    stdin = "\n".join(items).encode("utf-8")
    config = config_mod.load_config()

    custom = custom_picker_path(config)
    if custom:
        return _run([custom], stdin=stdin).strip()

    if config.get("enable_preview", True):
        argv = build_fzf_argv(config, preview.PREVIEW_SH)
    else:
        argv = ["fzf", "--smart-case", "--bind", "tab:up,shift-tab:down", "--cycle"]
        argv += list(config.get("fzf_flags") or [])

    env = {**os.environ, **preview.build_preview_env(config)}
    return _run(argv, stdin=stdin, env=env).strip()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_picker.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Full suite + manual picker check**

Run: `.venv/bin/pytest -q`
Expected: all PASS.

Then manually: `madopen report` in a populated dir — confirm Tab moves the
cursor **up**, Shift-Tab down, the list wraps, and previews render (text via
`bat`; an image shows metadata here since `chafa` is absent — proving graceful
degradation). Optionally drop a `~/.config/madopen/config.toml` with
`preview_window = "down:40%"` and confirm the window moves.

---

### Task 8: Docs rewrite + cleanup + deletions

**Files:**
- Rewrite: `README.md`
- Modify: `.gitignore`
- Delete: `bin/madft`, `bin/__pycache__`, and the now-empty `bin/`

**Interfaces:** none (docs/housekeeping).

- [ ] **Step 1: Delete the bundled binary and stale bin/ contents**

```bash
rm -rf bin/madft bin/__pycache__
rmdir bin 2>/dev/null || true
```

(`bin/madopen.py` was moved in Task 1; `bin/` should now be empty.)

- [ ] **Step 2: Update `.gitignore`**

Set `.gitignore` to:

```gitignore
.projrc
.envrc
__pycache__/
*.pyc
.venv/
*.egg-info/
build/
dist/
```

(`history.db*` is dropped — the DB now lives in `~/.local/state/madopen/`, never in the repo.)

- [ ] **Step 3: Rewrite `README.md`**

Replace the **Install**, **Aliases**, and **The picker** sections so they read:

````markdown
## Install

madopen is a Python package; install it with pipx (or pip):

```sh
git clone <repo-url> madopen && cd madopen
pipx install .            # or: pip install --user .
```

Then add the shell integration to your `~/.zshrc` (or `~/.bashrc`) — this defines
the `madopen` function (needed so it can `cd` your shell; a child process can't):

```sh
eval "$(madopen-bin init zsh)"     # use `bash` for bash
```

Suggested aliases (optional — copy what you like into your rc):

```sh
alias o='madopen'              # browse + open
alias oh='madopen -h'          # search history only
alias vim='madopen -a nvim'    # open with nvim, filtered to files it handles
alias vimh='madopen -h -a nvim'
```

### Dependencies

| Required | for |
|---|---|
| `python3` ≥ 3.11 + `click` | the tool (installed by pipx) |
| `zoxide` | directory resolution |
| `fzf` | the picker |
| `gio` (glibc/`glib2`) | accurate MIME detection |
| `gtk-launch` (`gtk3`/`gtk4`) | launching GUI apps |
| [`madft`](https://github.com/<you>/madft) | MIME → app/category resolution — `cargo install --path .` then `madft init` |
| `file` | preview text-detection |

Optional preview enhancers (all degrade gracefully if absent): **`bat`**, **`eza`**
(nicer text/dir previews), **`chafa`** (inline images), **`ffmpegthumbnailer`**
(video stills), **`poppler`/`pdftoppm`** (PDF first-page).

### Configuration (optional)

Drop a `~/.config/madopen/config.toml` to tune the picker. All keys are optional:

```toml
preview_window = "right:50%:wrap"
enable_preview = true
image_backend  = "chafa"          # or "kitten"
enable_video   = true
enable_pdf     = true
fzf_flags      = ["--cycle"]

# Full control: point at your own picker script (stdin = candidates,
# stdout = selection). When set, the options above are ignored.
custom_picker  = "/path/to/my-picker.sh"
```

The built-in picker/preview ships inside the package — don't edit it in place
(updates overwrite it); use `custom_picker` for full control.
````

Update the data-path mention under **History & removable mounts** from
`history.db` "lives in `history.db` (SQLite, gitignored)" to
"lives at `~/.local/state/madopen/history.db` (SQLite)". In **The picker**
section, change the Tab/Shift-Tab line to: "**Tab / Shift-Tab** move the cursor
**up / down** (the list wraps); arrows and `Ctrl-n`/`Ctrl-p` also work."

- [ ] **Step 4: Sanity-check the README has no stale references**

Run: `grep -nE "source .*madopen.sh|MADOPEN_HOME|bundled in .*bin|bin/madft" README.md`
Expected: no output.

- [ ] **Step 5: Full suite + fresh-install smoke test**

```bash
.venv/bin/pytest -q
.venv/bin/pip install -e . >/dev/null && .venv/bin/madopen-bin init zsh >/dev/null && echo OK
```

Expected: tests PASS; prints `OK`.

---

### Task 9: Maintainer-gated initial commit

**Files:** all of the above.

**Interfaces:** none.

> **GATE:** Do not run this task until the maintainer explicitly says to commit.
> This is the single clean initial commit they asked to defer.

- [ ] **Step 1: Final verification before committing**

```bash
.venv/bin/pytest -q
git status
git add -A --dry-run
```

Expected: all tests PASS; review that staged paths include `pyproject.toml`,
`src/madopen/*`, `tests/*`, `README.md`, `.gitignore`, `docs/`, `todo.md`, and
that `.envrc`, `.venv/`, `__pycache__/`, `*.egg-info/` are **excluded**.

- [ ] **Step 2: Create the initial commit (only on maintainer go-ahead)**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat: initial release — system-agnostic, pip-installable madopen

Package as `madopen` (src layout, `madopen-bin` console script). XDG paths
(history in ~/.local/state), self-emitting `init` shell integration, configurable
rich-preview picker (chafa/ffmpegthumbnailer/pdftoppm), peek uses caller cwd,
Tab/Shift-Tab flipped with wrap. madft is now an external dependency.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: Confirm**

Run: `git log --oneline -1 && git status`
Expected: the initial commit is present; working tree clean (modulo ignored files).

---

## Self-Review

**Spec coverage:**
- §1 Packaging & layout → Tasks 1 (scaffold/entry/pyproject), 2 (XDG paths, madft via PATH, MADOPEN_HOME removed), 8 (.gitignore `.envrc`, delete `bin/madft`). ✓
- §2 Shell integration → Task 3 (`init` emitter, function-only, no aliases), entry dispatch in Tasks 1+3. ✓
- §3.1 peek-cwd → Task 4. ✓  §3.2 tab/cycle → Task 7 (picker defaults). ✓  §3.3 proj investigation → **deferred by maintainer** (post-build, separate session). ✓
- §4 Docs → Task 8 (README incl. madft cargo dep, alias examples, dependency table, picker section). ✓
- §5 Configurable picker + previews → Task 5 (config), 6 (PREVIEW_SH + env), 7 (build_fzf_argv, custom_picker, wiring). ✓
- "Out of scope" madft .desktop seam → intentionally untouched. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N"; every code step shows full code. ✓

**Type consistency:** `resolve_launch_cwd(path, peek)`, `open_with(..., cwd=None)`, `build_fzf_argv(config, preview_cmd)`, `custom_picker_path(config)`, `load_config(path=None)`, `build_preview_env(config)`, `shell_init(shell="zsh")`, `entry()` — names/signatures match across defining and consuming tasks. `_run(argv, stdin=None, env=None)` extension is consumed only after it's added (Task 7). ✓
