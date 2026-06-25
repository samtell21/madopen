# madopen todo

## New todos

- [x] Make this system-agnostic (XDG paths, no hardcoded home dir). **Published:**
      pip-installable package (`src/madopen/`, `madopen-bin` console script,
      `eval "$(madopen-bin init zsh)"`); history in `~/.local/state/madopen/`.
      Live at https://github.com/samtell21/madopen (+ origin on the pi).
- [x] Remove madft from bin — madft is now an external cargo dependency
      (`cargo install --git …` + `madft init`, which owns `categories.toml`).
      `bin/madft` deleted; resolved from PATH.
- [x] `-p`/peek uses the caller's cwd (so nvim's file-picker stays at the root);
      non-peek still uses the file's parent.
- [x] Flip tab/shift-tab (tab moves *up*) + wrap (`--cycle`).
- [ ] **proj-mode "directory is not in the project" bug** — still deferred.
      Likely a proj-side issue, not madopen; investigate `~/.config/proj` and
      record findings here (no madopen code change expected).

## Done this session (post-publish fixes)

- [x] Bespoke launcher: run the app's `.desktop` Exec directly (from
      `madft app <id> desktop`), **dropped gtk-launch**. Robust field-code
      handling (`build_launch_argv`).
- [x] Pass args to the app after `--` (works with/without `-a`),
      e.g. `o report -- -R`, `vim notes -- +42`.
- [x] Rich image previews: auto-detect backend (kitten in kitty → chafa →
      file), `--unicode-placeholder` for correct fzf-pane placement.
- [x] `-n` no longer suggests dirs whose only history is a *deleted* file.
- [x] `-p` shell function returns 0 (was leaking a phantom error code).

## Findings (not madopen bugs)

- mpv screenshots landing in `~`: mpv's built-in `pseudo-gui` profile sets
  `screenshot-dir=~~desktop/` and ignores cwd. Fix in `~/.config/mpv/mpv.conf`:
  `[pseudo-gui]` → `screenshot-directory=.` (madopen launches in the file's dir).
- `.py` with an html-ish comment reads as `text/html` to `file`/`xdg-mime`, but
  madopen detects via **gio** (`text/x-python3` → nvim), so opening is correct.
  Python's stdlib `mimetypes` is extension-only (None for extensionless files),
  so it can't replace gio. gio stays.

## Next / maybe

- [ ] Publish to PyPI (`python -m build` + `twine upload`; pkg is ready, v0.1.0).
- [ ] Watch: `-a`/`-c` filtering compares gio's mimetype to the app/category's
      declared types — if a file you expect under `vim`/`-c Text` doesn't show,
      it's a mimetype-name mismatch to chase.

---

## Cleanup first
- [x] Clear the fake history out of the db before starting for real

## Core model
- [x] Make history opt-in (don't watch the whole filesystem; don't let new files enter with zero history and never get picked)
- [x] Resolve the *directory* query with bare `z` (or a custom algo that factors in proximity)
- [x] Default behavior: `xdg-open` the fzf file-query result within that directory — no concept of history
- [x] If nothing matches, open the query string as a new file

## Flags
- [x] `-n` / `--new`: force new file → `touch` → add to history → `xdg-open` (empty file ⇒ text/plain ⇒ nvim)
- [x] `-h` / `--use-history`: look up in history, recency-aware (recent activity outweighs stale high-frequency stuff)
- [x] `-a`: use a given app, filter the search to files it can open (via `madft app`); also opens with that app, and `-a "nvim +N"` passes args
- [x] `-c`: filter to files in a given category (via `madft types`)
- [x] `-p` / `--peek`: open the file without cd-ing
    - so I can't cd the calling process, but I can print the new directory and wrap the thing in a sourced shell function.
    - `-p` would then print the cwd or nothing at all.
    - that sourced shell script will also add the env var and aliases and will be part of install. 
        - Basically what I have now but without extending PATH. Not necessary, as long as the main script itself is in the path and the env var is set
- [~] ~Default (or an always-on flag): cd into the file's directory~


## Nice-to-haves / maybes
- [x] Pass args through to declared apps (terminal apps, e.g. `-a "nvim +10"`)
- [ ] Convenience subcommand syntax: `madopen h <fuzzy>` — skipped; the `oh` alias covers it
- [x] Aliases: `o=madopen`, `oh=madopen -h`, `vim=madopen -a nvim`, `vimh=madopen -h -a nvim`

## Done in cleanup pass
- Consolidated all `bin/` bash helpers into `madopen.py` (calls zoxide/fzf/gio/gtk-launch/madft directly); only `madft` + `madopen.py` remain in `bin/`.
- Launcher is now in-process (was `touch-open`): terminal apps run in the current terminal, GUI apps detached via `gtk-launch`.
- `-h` is now a flag (history-exclusive); added `--no-history` (suppress). Default still blends.
- Fixed `-m/--maxdepth` > 1 (Python walk keeps sub-paths; the old `find|sed` basename-strip broke it).
