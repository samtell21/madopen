# madopen

Open recent/frequent files from anywhere, zoxide-style.

`madopen` resolves a **directory** with [zoxide](https://github.com/ajeetdsouza/zoxide)
(proximity/frequency aware), fuzzy-matches a **filename** against the files inside
it with [fzf](https://github.com/junegunn/fzf), blends in a recency-weighted
open-history, and opens your pick with the right app — terminal apps (nvim) in the
current terminal, GUI apps detached. It can also `cd` your shell into the file's
directory.

```
o report            # fuzzy-find & open a file near you, then cd there
oh interstellar     # open something from history by name, from anywhere
vim notes.md        # open (or create) with nvim, filtered to files nvim handles
o -n proj/scratch   # create a new file in the best match for "proj"
```

## How it works

A query is split into a directory part and a filename part:

- **`o foo`** — directory defaults to the current dir; fuzzy-find `foo` in zoxide-ranked dirs.
- **`o proj/foo`** — resolve `proj` via zoxide, fuzzy-find `foo` inside.

Results come from three sources, scored on one normalized scale and merged:

1. **zoxide** rank of the candidate directories,
2. **fzf** fuzzy rank of filenames within them,
3. **history** — past opens, each weighted by `0.5 ** (age_days / 30)`, so recent
   activity outweighs a large pile of stale opens (a 30-day half-life).

If nothing matches, the query is created as a new file (in the matched dir, or the
current dir). Picking a file records it in the history and prints its directory so
the shell wrapper can `cd` there.

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

## Options

| flag | meaning |
|---|---|
| `-a, --application APP[ ARGS]` | Open with `APP` (a `.desktop` id like `nvim`) and only show files it can open. Trailing args pass through to the app, e.g. `-a "nvim +10"`. |
| `-c, --category CAT` | Only show files in a madft category (e.g. `Images`, `Text`). Combines with `-a`. |
| `-h, --history` | Search history only; the whole query fuzzy-matches by name in any directory. |
| `--no-history` | Ignore history; filesystem search only. (Default blends history in.) |
| `-n, --new` | Open the query as a (possibly brand-new) file. |
| `-p, --peek` | Open without `cd`-ing into the file's directory. |
| `-s, --select` | Auto-pick the top match instead of showing the picker. |
| `-d, --directory` | Treat the whole query as a directory and browse its files. |
| `-m, --maxdepth N` | How deep to descend when listing files (default `1`). |

## The picker

- **Tab / Shift-Tab** move the cursor **up / down** (the list wraps); arrows and `Ctrl-n`/`Ctrl-p` also work.
- A **preview pane** shows the full path (so long paths are always visible) plus a
  directory listing (`eza`) or file contents (`bat`).
- Type to fuzzy-filter; **Enter** opens.

## History & removable mounts

The history lives at `~/.local/state/madopen/history.db` (SQLite). Each open records
the filesystem mountpoint it was on. A history entry is only flagged deleted when the
file is genuinely gone — absent *while its recorded filesystem is mounted*. Files
on an offline or broken mount (e.g. a disconnected sshfs) are treated as
*unreachable*, never deleted, so they come back when the mount returns.
