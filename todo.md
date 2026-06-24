# madopen todo

## New todos

- [ ] Make this system-agnostic. E.g., remove explicit references to my user directory, make the project home somewhere in ~/.local, ya know, standard stuff. I'd like to publish this on github as something people might want to use. I am already finding it very useful.
- [ ] Remove madft from bin, madft is installed separately as a dependency. Users are gonna want the whole install, including the initial categories.toml and the readme, so they can set default apps easily so madopen actually is useful
- [ ] But along the same lines, I'd typically use peek/-p when I am in the root folder of a project and I want to edit a file without leaving the root. Fine, it works. BUT the subproccess uses the cwd of the file, so file picker in nvim (and any other app if it has something like that) looks at *that* subdirectory, rather than the root directory that I specifically chose to stay in. So better behavior would to use the actual cwd opening the file when -p is used. With -p, current behavior using cwd=parent is fine.
- [ ] Small thing: lets flip tab and shift tab. fzf displays results in reverse. Best at the bottom. tab should move *up* the list.
    - [ ] also, wrap would be nice. But still, tab should move up. with wrap, then shift tab at the bottom would go to the top of the list.
- [ ] Small personal bug: when I am in project mode (see ~/.config/proj, it's a personal productivity system I do not intend to publish), using the zsh function that cds to the directory, I get an error that says the directory is not in the project, even when it is... Honestly, this is probably not a madopen problem but a proj problem, and I should deal with it there. But let's look into it and collect any useful info here about the issue, even if it does not involve changing any code here.

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
