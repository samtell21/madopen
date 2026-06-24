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
