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


def test_entry_init_emits_shell_function(monkeypatch, capsys):
    import madopen.cli as cli
    monkeypatch.setattr(sys, "argv", ["madopen-bin", "init", "zsh"])
    rc = cli.entry()
    out = capsys.readouterr().out
    assert rc == 0
    assert "madopen()" in out
    assert "madopen-bin" in out


def test_split_app_args():
    import madopen.cli as cli
    assert cli.split_app_args(["madopen-bin", "report", "--", "-R", "-n"]) == \
        (["madopen-bin", "report"], ["-R", "-n"])
    assert cli.split_app_args(["madopen-bin", "report"]) == \
        (["madopen-bin", "report"], [])


def test_entry_captures_post_double_dash_args(monkeypatch):
    import madopen.cli as cli
    captured = {}
    monkeypatch.setattr(cli, "main",
                        lambda: captured.update(argv=list(sys.argv),
                                                extra=list(cli._EXTRA_APP_ARGS)))
    monkeypatch.setattr(sys, "argv", ["madopen-bin", "-a", "nvim", "report", "--", "-R"])
    cli.entry()
    assert captured["extra"] == ["-R"]
    assert "--" not in captured["argv"]
    assert captured["argv"] == ["madopen-bin", "-a", "nvim", "report"]
