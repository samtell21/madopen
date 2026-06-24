#!/usr/bin/env python3
"""madopen — open recent/frequent files, zoxide-style.

A query is split into a *directory* part and a *filename* part. The directory
part is resolved with zoxide (proximity/frequency aware); the filename part is
fuzzy-matched against the files inside the resolved directories. An open-history
(`history.db`) is blended in by default, weighted so recent activity outweighs a
large pile of stale opens.

The chosen file is opened directly (terminal apps run in the current terminal,
GUI apps launch detached) and recorded in the history; its parent directory is
emitted on fd 3 so the sourced shell wrapper (`madopen.sh`) can cd into it.

External tools used directly (no shell wrappers): zoxide, fzf, gio, gtk-launch,
and madft (bundled in bin/, resolved by absolute path so madopen works anywhere).
"""
import os
import sys
import json
import shlex
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime

import click

HOME = os.environ.get("MADOPEN_HOME", "/home/samtell/projects/madopen")
DB_PATH = HOME + "/history.db"

# madft is bundled in bin/; fall back to PATH if it's been moved.
MADFT = os.path.join(HOME, "bin", "madft")
if not os.path.exists(MADFT):
    MADFT = "madft"

# Half-life (in days) of a single open in the recency-weighted frequency score.
# A visit today counts ~1.0; one half-life ago counts 0.5; two ago 0.25; etc.
HALF_LIFE_DAYS = 30.0

# .desktop search dirs, user overriding system.
APP_DIRS = [os.path.expanduser("~/.local/share/applications"), "/usr/share/applications"]


# --------------------------------------------------------------------------- #
# external command helpers
# --------------------------------------------------------------------------- #

def _run(argv, stdin=None):
    """Run `argv`, return stdout as text. `stdin`, if given, is bytes."""
    proc = subprocess.run(
        argv, input=stdin, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    return proc.stdout.decode("utf-8")


def zoxide_dirs(dquery):
    """{directory: normalized_score} for dirs matching `dquery` (split on '/').

    If `dquery` is itself a real directory zoxide didn't rank, seed it on top so
    an explicit path always wins."""
    tokens = [t for t in dquery.split("/") if t]
    scores = {}
    for line in _run(["zoxide", "query", "-l", "-s", "--", *tokens]).splitlines():
        line = line.strip()
        if line:
            score, path = line.split(maxsplit=1)
            scores[path] = float(score)
    if os.path.isdir(dquery):
        ap = os.path.abspath(dquery)
        if ap not in scores:
            scores[ap] = max(scores.values(), default=0.0) + 1
    return normalize(scores)


def zoxide_best(dquery):
    """Zoxide's single best directory for `dquery` ('' if none)."""
    tokens = [t for t in dquery.split("/") if t]
    return _run(["zoxide", "query", "--", *tokens]).strip()


def fzf_filter(items, query):
    """Order `items` by fuzzy match against `query` (non-interactive)."""
    items = list(items)
    if not items:
        return []
    return _run(["fzf", "--smart-case", "-f", query],
                stdin="\n".join(items).encode("utf-8")).splitlines()


# Picker preview: full path on top (so long paths are always visible), then a
# directory listing (eza) or file contents (bat), with plain fallbacks. A
# trailing " (new)" label (from the --new dir picker) is stripped first.
_FZF_PREVIEW = r"""
p={}; p="${p% (new)}"
printf '%s\n\n' "$p"
if [ -d "$p" ]; then
    eza -la --color=always --group-directories-first "$p" 2>/dev/null || ls -la "$p"
elif [ ! -e "$p" ]; then
    echo '(new file)'
elif file --mime-type -b "$p" 2>/dev/null | grep -qE '^(text/|application/(json|xml|javascript|toml|x-shellscript|x-yaml|x-desktop))'; then
    bat --color=always --style=numbers --line-range=:300 "$p" 2>/dev/null || head -n 300 "$p"
else
    file -b "$p"
fi
"""


def fzf_pick(items):
    """Interactive fzf pick over `items`; returns the chosen item ('' if none).

    Tab/Shift-Tab move the cursor down/up; a preview pane shows the full path
    plus a directory listing or file contents."""
    items = list(items)
    if not items:
        return ""
    return _run(
        ["fzf", "--smart-case",
         "--bind", "tab:down,shift-tab:up",
         "--preview", _FZF_PREVIEW,
         "--preview-window", "right:50%:wrap"],
        stdin="\n".join(items).encode("utf-8"),
    ).strip()


def list_files(directory, maxdepth):
    """Paths of files under `directory`, relative to it, down to `maxdepth`
    levels (maxdepth 1 = direct children, matching `find -maxdepth 1`). Relative
    paths keep sub-directory structure so depth > 1 actually resolves."""
    results = []
    base_depth = len(Path(directory).parts)
    try:
        for root, dirs, files in os.walk(directory):
            depth = len(Path(root).parts) - base_depth
            if depth < maxdepth:
                for f in files:
                    results.append(os.path.relpath(os.path.join(root, f), directory))
            if depth + 1 >= maxdepth:
                dirs[:] = []  # don't descend further
    except OSError:
        pass
    return results


def detect_mimetypes(paths):
    """{path: mimetype} via one batched `gio info` call."""
    paths = [str(p) for p in paths]
    if not paths:
        return {}
    out = _run(["gio", "info", "-a", "standard::content-type", *paths])
    result, current = {}, None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("local path: "):
            current = line[len("local path: "):]
        elif line.startswith("standard::content-type: ") and current is not None:
            result[current] = line[len("standard::content-type: "):]
            current = None
    return result


def mimetype_of(path):
    """MIME type of a single file ('' if undeterminable)."""
    return detect_mimetypes([path]).get(str(path), "")


# --------------------------------------------------------------------------- #
# madft (mimetype <-> app/category resolution)
# --------------------------------------------------------------------------- #

def default_app(mimetype):
    """The default .desktop id madft assigns to `mimetype` ('' if none)."""
    return _run([MADFT, "get", mimetype]).strip()


def app_mimetypes(app):
    """Set of mimetypes `app` handles, or None if madft doesn't know the app."""
    out = _run([MADFT, "app", app, "--json"])
    if not out.strip():
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    return {t["mime"] for t in data.get("types", [])}


def category_mimetypes(category):
    """Set of mimetypes under the madft `category` (empty if unknown)."""
    try:
        return set(json.loads(_run([MADFT, "types", category, "--json"])))
    except json.JSONDecodeError:
        return set()


# --------------------------------------------------------------------------- #
# launching
# --------------------------------------------------------------------------- #

def find_desktop(app_id):
    """Full path of a .desktop id (with or without the suffix), or ''."""
    if not app_id:
        return ""
    if not app_id.endswith(".desktop"):
        app_id += ".desktop"
    for d in APP_DIRS:
        p = os.path.join(d, app_id)
        if os.path.isfile(p):
            return p
    return ""


def desktop_exec(desktop_path):
    """(command_argv, terminal_bool) parsed from a .desktop file's [Desktop Entry].

    Field codes (%f, %U, %i, ...) are stripped; the caller appends the real file."""
    exec_line, terminal, in_entry = "", False, False
    with open(desktop_path) as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("["):
                in_entry = line == "[Desktop Entry]"
            elif in_entry and line.startswith("Exec=") and not exec_line:
                exec_line = line[len("Exec="):]
            elif in_entry and line.startswith("Terminal="):
                terminal = line[len("Terminal="):].strip().lower() == "true"
    argv = [t for t in shlex.split(exec_line) if not (len(t) == 2 and t[0] == "%")]
    return argv, terminal


def is_empty(path):
    try:
        return os.path.getsize(path) == 0
    except OSError:
        return False


def open_with(path, app=None, app_args=None):
    """Open `path`. Terminal apps run in the current terminal (blocking) so the
    caller's post-open existence check is accurate; GUI apps launch detached.

    `app` overrides the default handler (the `-a` flag); `app_args` are extra
    arguments passed to a terminal app before the file (e.g. nvim's `+10`)."""
    parent = str(Path(path).parent)

    if not exists_safe(path) or is_empty(path):
        mimetype = "text/plain"           # new/empty files open in the editor
    else:
        mimetype = mimetype_of(path) or "text/plain"

    app_id = app or default_app(mimetype) or default_app("text/plain")
    desktop = find_desktop(app_id)
    if not desktop:
        print(f"madopen: no .desktop for '{app_id}' ({mimetype})", file=sys.stderr)
        return

    argv, terminal = desktop_exec(desktop)
    if not argv:
        print(f"madopen: no Exec line in {desktop}", file=sys.stderr)
        return

    if terminal:
        # run in THIS terminal, blocking
        subprocess.run(argv + list(app_args or []) + [str(path)], cwd=parent)
    else:
        # GUI: let gtk-launch handle .desktop semantics, detached
        subprocess.Popen(
            ["gtk-launch", os.path.basename(desktop), str(path)],
            cwd=parent, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )


# --------------------------------------------------------------------------- #
# scoring helpers
# --------------------------------------------------------------------------- #

def weighted_ranks(ordered, reverse=False):
    """Turn an ordered list into weights in (0, 1]: the first item gets the
    highest weight, the last the lowest (flip with `reverse`). Duplicates
    accumulate."""
    weights = {}
    n = len(ordered)
    for i, item in enumerate(ordered):
        w = i / n
        if not reverse:
            w = 1 - w
        weights[item] = weights.get(item, 0.0) + w
    return weights


def normalize(scores):
    """Scale values to sum to 1, returned sorted by descending score."""
    total = sum(scores.values())
    if total == 0:
        return {}
    return sort_ranks({k: v / total for k, v in scores.items()})


def sort_ranks(scores):
    """Return `scores` as a dict ordered by descending value."""
    return dict(sorted(scores.items(), key=lambda kv: kv[1], reverse=True))


def recency_weight(epoch, now):
    """Half-life decay for a single open: 0.5 ** (age_in_days / HALF_LIFE_DAYS)."""
    age_days = (now - epoch) / 86400.0
    return 0.5 ** (age_days / HALF_LIFE_DAYS)


# --------------------------------------------------------------------------- #
# filesystem / mount awareness
# --------------------------------------------------------------------------- #

# fstypes whose mounts can disappear out from under us (network / fuse / removable)
_EPHEMERAL_PREFIXES = ("fuse", "nfs", "cifs", "smb", "afs", "9p", "ncp")
_EPHEMERAL_TYPES = {"vfat", "exfat", "ntfs", "ntfs3", "fuseblk", "msdos", "udf", "iso9660"}


def _unescape_mount(field):
    """Decode the octal escapes /proc/mounts uses for space/tab/newline/backslash."""
    return (field.replace(r"\040", " ").replace(r"\011", "\t")
                 .replace(r"\012", "\n").replace(r"\134", "\\"))


def _mount_table():
    """[(mountpoint, fstype), ...] from /proc/mounts, longest mountpoint first."""
    entries = []
    try:
        with open("/proc/mounts") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 3:
                    entries.append((_unescape_mount(parts[1]), parts[2]))
    except OSError:
        pass
    entries.sort(key=lambda e: len(e[0]), reverse=True)
    return entries


def mount_of(path):
    """(mountpoint, on_mount) for the filesystem `path` lives on: the longest
    mountpoint that is a prefix of `path`, plus 'Y' if its fstype is ephemeral
    (network/fuse/removable) else ''. ('', '') if undeterminable.

    Longest-prefix match against /proc/mounts, so it works wherever the
    filesystem is mounted — no hardcoded mount locations."""
    path = os.path.abspath(path)
    for mp, fstype in _mount_table():
        if path == mp or path.startswith(mp.rstrip("/") + "/"):
            ephemeral = fstype.startswith(_EPHEMERAL_PREFIXES) or fstype in _EPHEMERAL_TYPES
            return mp, ("Y" if ephemeral else "")
    return "", ""


def is_mounted(mountpoint):
    """Is `mountpoint` currently a live mount?"""
    return any(mp == mountpoint for mp, _ in _mount_table())


def exists_safe(path):
    """Path.exists() that returns False instead of raising on a broken mount."""
    try:
        return Path(path).exists()
    except OSError:
        return False


def file_state(path, mount, on_mount):
    """Classify `path` using the mount recorded for it: 'exists', 'gone', or
    'unreachable'.

    'gone' — the only state that may flag a history row deleted — means the file
    is cleanly absent AND the filesystem it was recorded on is currently mounted.
    A file on an unmounted/broken mount is 'unreachable', never 'gone', so an
    offline network file is not mistaken for a deletion."""
    try:
        if Path(path).exists():
            return "exists"
    except OSError:
        return "unreachable"            # broken mount (e.g. dead sshfs: ENOTCONN)
    if on_mount == "Y":                 # network/fuse/removable: trust only if live
        return "gone" if (mount and is_mounted(mount)) else "unreachable"
    if mount:                           # recorded internal fs: effectively always up
        return "gone"
    return "unreachable"                # legacy row, mount unknown: don't risk it


# --------------------------------------------------------------------------- #
# history database
# --------------------------------------------------------------------------- #

def connect():
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)
    return conn


def ensure_schema(conn):
    """Create the history table if absent and add the mount-tracking columns to
    pre-existing databases (idempotent migration)."""
    cur = conn.cursor()
    cur.execute(
        "create table if not exists madopen_files ("
        "epoch integer, directory text, filename text, deleted text, "
        "mount text default '', on_mount text default '')"
    )
    cols = {row[1] for row in cur.execute("pragma table_info(madopen_files)")}
    if "mount" not in cols:
        cur.execute("alter table madopen_files add column mount text default ''")
    if "on_mount" not in cols:
        cur.execute("alter table madopen_files add column on_mount text default ''")
    conn.commit()


def mark_deleted(cur, directory, filename):
    cur.execute(
        "update madopen_files set deleted = 'Y' "
        "where directory = ? and filename = ?",
        (directory, filename),
    )


def emit_dir(directory):
    """Send `directory` to the shell wrapper on fd 3, falling back to stdout when
    run directly (no wrapper, so fd 3 isn't open)."""
    line = directory + "\n"
    try:
        os.write(3, line.encode())
    except OSError:
        sys.stdout.write(line)


def record_open(target_path, peek, app=None, app_args=None):
    """Open `target_path`, record it in the history, and (unless `peek`) emit its
    parent directory on fd 3 for the shell wrapper to cd into.

    Existence is checked *after* the open so a brand-new file (created on save)
    is recorded, and the mount is captured while reachable so a future run can
    tell a real deletion from an offline mount."""
    path = Path(target_path)
    parent, name = str(path.parent), path.name

    open_with(target_path, app, app_args)

    mount, on_mount = mount_of(parent)
    with connect() as conn:
        cur = conn.cursor()
        state = file_state(path, mount, on_mount)
        if state == "exists":
            cur.execute(
                "insert into madopen_files "
                "(epoch, directory, filename, deleted, mount, on_mount) "
                "values (?, ?, ?, '', ?, ?)",
                (int(datetime.now().timestamp()), parent, name, mount, on_mount),
            )
            # resurrect any rows for this file previously flagged as deleted
            cur.execute(
                "update madopen_files set deleted = '' "
                "where directory = ? and filename = ?",
                (parent, name),
            )
            if not peek:
                emit_dir(parent)
        elif state == "gone":
            mark_deleted(cur, parent, name)
        # 'unreachable': leave the history untouched
        conn.commit()


def history_search(dq, fq="", include_deleted=False):
    """Rank previously-opened files for directory query `dq` (and optional
    filename query `fq`). An empty `dq` applies no directory bias (used by the
    history-exclusive mode, where the whole query filters on filename).

    Each past open contributes a recency-weighted vote (see `recency_weight`),
    summed per file and normalized; blended with fuzzy-match ranks for directory
    and filename. Returns [(directory, filename, score), ...] sorted descending.

    Files that no longer exist are flagged deleted. With `include_deleted` they
    are still returned (used by --new to suggest dirs); otherwise dropped."""
    now = datetime.now().timestamp()

    with connect() as conn:
        cur = conn.cursor()
        where = "" if include_deleted else " where deleted = ''"
        cur.execute(
            "select epoch, directory, filename, mount, on_mount "
            "from madopen_files" + where
        )
        rows = cur.fetchall()

        # recency-weighted frequency per (directory, filename), plus each
        # directory's recorded mount (to tell deletions from offline mounts)
        freq, dir_mount = {}, {}
        for epoch, d, f, mount, on_mount in rows:
            freq[(d, f)] = freq.get((d, f), 0.0) + recency_weight(epoch, now)
            if mount or d not in dir_mount:
                dir_mount[d] = (mount or "", on_mount or "")

        if dq in (".", ".."):
            dq = str(Path(dq).resolve())

        # fuzzy-rank distinct directories (no bias when dq is empty)
        dirs = {d for d, _ in freq}
        dscore = weighted_ranks(fzf_filter(dirs, dq)) if dq else {d: 0.0 for d in dirs}
        entries = [(d, f) for (d, f) in freq if d in dscore]
        if not entries:
            return []

        # fuzzy-rank distinct filenames among the surviving entries
        fscore = weighted_ranks(fzf_filter({f for _, f in entries}, fq))
        fscore[""] = 0.0

        # normalize the frequency component so it's comparable to the [0,1] ranks
        total = sum(freq[e] for e in entries)
        scored = []
        for (d, f) in entries:
            if f in fscore or fq == "":
                blended = dscore[d] + fscore.get(f, 0.0) + freq[(d, f)] / total
                scored.append((d, f, blended))

        # prune genuinely-deleted files; never delete merely-offline ones
        for i, (d, f, _) in enumerate(scored):
            mount, on_mount = dir_mount.get(d, ("", ""))
            state = file_state(Path(d) / f, mount, on_mount)
            if state == "gone":
                mark_deleted(cur, d, f)
            if state != "exists" and not include_deleted:
                scored[i] = (d, f, 0.0)
        conn.commit()

    scored = [(d, f, s) for d, f, s in scored if s > 0]
    scored.sort(reverse=True, key=lambda x: x[2])
    return scored


def best_hdir(history):
    """Directory with the highest total score across history results ('' if none)."""
    sums = {}
    for d, _, s in history:
        sums[d] = sums.get(d, 0.0) + s
    return max(sums, key=sums.get) if sums else ""


# --------------------------------------------------------------------------- #
# mime filtering (-a / -c)
# --------------------------------------------------------------------------- #

def filter_by_mime(paths, allowed):
    """Keep only `paths` whose detected mimetype is in `allowed`. None = no-op."""
    if allowed is None:
        return list(paths)
    mimes = detect_mimetypes(paths)
    return [p for p in paths if mimes.get(str(p)) in allowed]


# --------------------------------------------------------------------------- #
# modes
# --------------------------------------------------------------------------- #

def run_browse(dq, fq, mode, select, peek, directory, maxdepth, query,
               allowed, app, app_args):
    """Default mode: fuzzy-pick an existing file across zoxide-ranked dirs;
    create the query as a new file if nothing matches."""
    hist = history_search(dq, fq) if mode == "compare" else []

    scored = {}
    for d, dir_weight in zoxide_dirs(dq).items():
        names = list_files(d, maxdepth)
        if directory:
            matches = {f: 0.0 for f in fzf_filter(names, fq)}
        else:
            matches = weighted_ranks(fzf_filter(names, fq))
        for rel, w in matches.items():
            full = str(Path(d) / rel)
            if exists_safe(full):
                scored[full] = w + dir_weight

    if mode == "compare":
        for d, f, s in hist:
            full = str(Path(d) / f)
            scored[full] = scored.get(full, 0.0) + s

    if allowed is not None:
        keep = set(filter_by_mime(scored.keys(), allowed))
        scored = {p: s for p, s in scored.items() if p in keep}

    if not scored:
        # fall back to creating the query as a new (text) file — but only if the
        # active app/category filter can actually handle a new text file, so
        # `vim newfile.txt` creates while `-a imv foo` (no image) just reports.
        if not fq or (allowed is not None and "text/plain" not in allowed):
            print("no file found for query:", query, file=sys.stderr)
            sys.exit(1)
        target = dq if os.path.isdir(dq) else (zoxide_best(dq) or os.getcwd())
        new_path = str(Path(target) / fq)
        print(f"madopen: no match — creating {new_path}", file=sys.stderr)
        record_open(new_path, peek, app, app_args)
        return

    scored = normalize(scored)
    chosen = max(scored, key=scored.get) if select else fzf_pick(scored.keys())
    if chosen:
        record_open(chosen, peek, app, app_args)


def run_new(dq, fq, mode, select, peek, app, app_args):
    """--new: open `fq` as a (possibly brand-new) file in a resolved directory."""
    hist = history_search(dq, include_deleted=True) if mode == "compare" else []
    zdir = zoxide_best(dq)
    target_dir = zdir

    if mode == "compare" and hist:
        if select:
            best = best_hdir(hist)
            if best:
                ranked = fzf_filter([best, zdir], dq)
                target_dir = ranked[0] if ranked else best
        else:
            candidates = [d for d in ({d for d, _, _ in hist} | {zdir}) if d]
            labels = {}
            for d in candidates:
                path = Path(d) / fq
                labels[str(path) + ("" if exists_safe(path) else " (new)")] = d
            chosen = fzf_pick(labels.keys())
            if not chosen:
                sys.exit()
            target_dir = labels[chosen]

    if not target_dir:
        target_dir = dq if os.path.isdir(dq) else os.getcwd()

    record_open(str(Path(target_dir) / fq), peek, app, app_args)


def run_exclusive(query, select, peek, allowed, app, app_args):
    """-h: search history only. The whole query fuzzy-matches filenames in any
    directory (the `oh <thing>` use case)."""
    candidates = {}
    for d, f, s in history_search("", fq=query):
        full = str(Path(d) / f)
        if exists_safe(full):
            candidates[full] = s

    if allowed is not None:
        keep = set(filter_by_mime(candidates.keys(), allowed))
        candidates = {p: s for p, s in candidates.items() if p in keep}

    if not candidates:
        print("no file in history for:", query, file=sys.stderr)
        sys.exit(1)

    candidates = normalize(candidates)
    chosen = max(candidates, key=candidates.get) if select else fzf_pick(candidates.keys())
    if chosen:
        record_open(chosen, peek, app, app_args)


# --------------------------------------------------------------------------- #
# cli
# --------------------------------------------------------------------------- #

@click.command(context_settings={"help_option_names": ["--help"]})
@click.option("-a", "--application", metavar="APP[ ARGS]",
              help="Open with APP (a .desktop id like nvim) and only show files "
                   "it can open. Trailing args are passed to the app.")
@click.option("-c", "--category",
              help="Only show files in this madft category (e.g. Images, Text).")
@click.option("-h", "--history", "history_only", is_flag=True,
              help="Search history only (whole query fuzzy-matches by name).")
@click.option("--no-history", is_flag=True,
              help="Ignore history; filesystem search only.")
@click.option("-p", "--peek", is_flag=True, help="Open without cd-ing into the dir.")
@click.option("-n", "--new", is_flag=True, help="Open the query as a (new) file.")
@click.option("-s", "--select", is_flag=True,
              help="Auto-pick the top match instead of showing an fzf picker.")
@click.option("-d", "--directory", is_flag=True,
              help="Treat the whole query as a directory; browse its files.")
@click.option("-m", "--maxdepth", type=int, default=1, show_default=True,
              help="How deep to descend when listing files in a directory.")
@click.argument("query", nargs=-1, type=str)
def main(application, category, history_only, no_history, peek, new, select,
         directory, maxdepth, query):
    query = " ".join(query)

    # resolve -a into an app id + trailing args, and build the mime allow-set
    app, app_args = None, []
    if application:
        parts = application.split()
        app, app_args = parts[0], parts[1:]

    allowed = None
    if app:
        if not find_desktop(app):
            print(f"madopen: unknown application '{app}'", file=sys.stderr)
            sys.exit(1)
        allowed = app_mimetypes(app) or None   # no type info -> don't filter
    if category:
        cats = category_mimetypes(category)
        allowed = cats if allowed is None else (allowed & cats)

    if history_only:
        run_exclusive(query, select, peek, allowed, app, app_args)
        return

    mode = "suppress" if no_history else "compare"

    # split the query into a directory part (dq) and a filename part (fq);
    # in --directory mode the whole query is the directory spec.
    if directory:
        spec, fq = query, ""
    else:
        pq = Path(query)
        spec, fq = str(pq.parent), pq.name

    dq = str(Path(spec).expanduser())
    if dq in (".", ".."):
        dq = str(Path(dq).resolve())

    if new:
        run_new(dq, fq, mode, select, peek, app, app_args)
    else:
        run_browse(dq, fq, mode, select, peek, directory, maxdepth, query,
                   allowed, app, app_args)


def entry():
    """Console-script entry: dispatch `init` to the shell emitter, else run the CLI."""
    if len(sys.argv) >= 2 and sys.argv[1] == "init":
        from . import shell  # imported lazily; shell.py arrives in Task 3
        shell_arg = sys.argv[2] if len(sys.argv) > 2 else "zsh"
        return shell.shell_init(shell_arg)
    return main()


if __name__ == "__main__":
    entry()
