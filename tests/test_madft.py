"""madft_desktop_exec parses `madft app <id> desktop Exec Terminal` into
(exec_tokens, terminal) with field codes INTACT (build_launch_argv expands them);
unknown apps -> (None, False)."""
from madopen import cli


def test_terminal_app_parsed(monkeypatch):
    monkeypatch.setattr(cli, "_run", lambda argv, **k: "nvim %F\ntrue\n")
    tokens, terminal = cli.madft_desktop_exec("nvim")
    assert tokens == ["nvim", "%F"]    # raw tokens, %F kept
    assert terminal is True


def test_gui_app_parsed_keeps_field_codes(monkeypatch):
    monkeypatch.setattr(cli, "_run", lambda argv, **k: "qutebrowser --untrusted-args %u\nfalse\n")
    tokens, terminal = cli.madft_desktop_exec("org.qutebrowser.qutebrowser")
    assert tokens == ["qutebrowser", "--untrusted-args", "%u"]
    assert terminal is False


def test_unknown_app_returns_none(monkeypatch):
    # madft prints the error to stderr (dropped by _run); stdout is empty.
    monkeypatch.setattr(cli, "_run", lambda argv, **k: "")
    tokens, terminal = cli.madft_desktop_exec("totallybogusapp")
    assert tokens is None
    assert terminal is False


def test_empty_app_id_does_not_call_madft(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", lambda argv, **k: calls.append(argv) or "x\ntrue")
    tokens, terminal = cli.madft_desktop_exec("")
    assert tokens is None
    assert calls == []                 # short-circuits without invoking madft


def test_invokes_madft_with_expected_argv(monkeypatch):
    seen = {}
    monkeypatch.setattr(cli, "_run", lambda argv, **k: seen.update(argv=argv) or "nvim\ntrue")
    cli.madft_desktop_exec("nvim")
    assert seen["argv"] == [cli.MADFT, "app", "nvim", "desktop", "Exec", "Terminal"]
