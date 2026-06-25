"""history_search must not surface malformed rows whose filename is empty —
their path collapses to the directory itself (e.g. `.`), which exists as a
directory and so survives existence-pruning, polluting every result."""
import sqlite3
from datetime import datetime
from pathlib import Path

from madopen import cli, paths


def _seed(db_path, rows):
    conn = sqlite3.connect(db_path)
    cli.ensure_schema(conn)
    conn.executemany(
        "insert into madopen_files "
        "(epoch, directory, filename, deleted, mount, on_mount) "
        "values (?, ?, ?, '', '', '')",
        rows,
    )
    conn.commit()
    conn.close()


def test_history_search_skips_empty_filename_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    Path(paths.state_dir()).mkdir(parents=True, exist_ok=True)

    realdir = tmp_path / "proj"
    realdir.mkdir()
    (realdir / "notes.md").write_text("hi")  # a real file so its row survives

    now = int(datetime.now().timestamp())
    _seed(paths.db_path(), [
        (now, str(realdir), "notes.md"),
        (now, ".", ""),               # the junk row that produced the `.` candidate
        (now, str(realdir), ""),      # another empty-filename row
    ])

    results = cli.history_search(str(realdir), fq="")
    returned = [str(Path(d) / f) for d, f, _ in results]

    assert "." not in returned                    # the bug: no directory candidate
    assert all(f for _, f, _ in results)          # no empty-filename rows leak through
    assert any(p.endswith("notes.md") for p in returned)  # real files still returned


def test_run_new_excludes_deleted_dirs(tmp_path, monkeypatch):
    """`-n a.py` must not suggest dirs whose only a.py history is a deleted file."""
    import pytest
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    Path(paths.state_dir()).mkdir(parents=True, exist_ok=True)

    cur = tmp_path / "cur"
    cur.mkdir()
    (cur / "a.py").write_text("x")                # existing a.py here

    now = int(datetime.now().timestamp())
    conn = sqlite3.connect(paths.db_path())
    cli.ensure_schema(conn)
    conn.execute(
        "insert into madopen_files (epoch, directory, filename, deleted, mount, on_mount) "
        "values (?, ?, ?, '', '', '')", (now, str(cur), "a.py"))
    conn.execute(
        "insert into madopen_files (epoch, directory, filename, deleted, mount, on_mount) "
        "values (?, ?, ?, 'Y', '', '')", (now, "/gone/scratch", "a.py"))  # deleted
    conn.commit()
    conn.close()

    captured = {}

    def _pick(items):
        captured["items"] = list(items)
        return ""                                # pick nothing -> run_new exits

    monkeypatch.setattr(cli, "fzf_pick", _pick)
    monkeypatch.setattr(cli, "zoxide_best", lambda dq: "")

    with pytest.raises(SystemExit):              # fzf_pick returns "" -> run_new exits
        cli.run_new(str(cur), "a.py", "compare", False, False, None, [])

    labels = captured.get("items", [])
    assert not any("/gone/scratch" in lbl for lbl in labels)   # deleted dir excluded
    assert any("a.py" in lbl for lbl in labels)                # real candidate present
