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

Dependencies:

| Required | for |
|---|---|
| `python3` + `click` | the tool |
| `zoxide` | directory resolution |
| `fzf` | the picker |
| `gio` (glibc/`glib2`) | accurate MIME detection |
| `gtk-launch` (`gtk3`/`gtk4`) | launching GUI apps |
| `madft` | MIME → app/category resolution (bundled in `bin/`) |
| `file` | preview text-detection |

Optional: **`bat`** and **`eza`** make the preview nicer (plain `head`/`ls` fallbacks otherwise).

Source the shell integration from your `~/.zshrc` (or `~/.bashrc`):

```sh
source /path/to/madopen/madopen.sh
```

That sets `MADOPEN_HOME`, defines the `madopen` shell function (needed so it can
`cd` your shell — a child process can't), and installs the aliases.

## Aliases

| alias | expands to | use |
|---|---|---|
| `o`    | `madopen`         | browse + open |
| `oh`   | `madopen -h`      | search history only (by name, from anywhere) |
| `vim`  | `madopen -a nvim` | open with nvim, filtered to files nvim handles |
| `vimh` | `madopen -h -a nvim` | same, from history |

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

- **Tab / Shift-Tab** move the cursor down / up (arrows and `Ctrl-n`/`Ctrl-p` also work).
- A **preview pane** shows the full path (so long paths are always visible) plus a
  directory listing (`eza`) or file contents (`bat`).
- Type to fuzzy-filter; **Enter** opens.

## History & removable mounts

The history lives in `history.db` (SQLite, gitignored). Each open records the
filesystem mountpoint it was on. A history entry is only flagged deleted when the
file is genuinely gone — absent *while its recorded filesystem is mounted*. Files
on an offline or broken mount (e.g. a disconnected sshfs) are treated as
*unreachable*, never deleted, so they come back when the mount returns.
