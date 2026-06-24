"""madft_desktop_exec parses `madft app <id> desktop Exec Terminal` output into
(argv, terminal); field codes (%f/%U/%i/...) are stripped, unknown apps -> None."""
from madopen import cli


def test_terminal_app_parsed(monkeypatch):
    monkeypatch.setattr(cli, "_run", lambda argv, **k: "nvim %F\ntrue\n")
    argv, terminal = cli.madft_desktop_exec("nvim")
    assert argv == ["nvim"]            # %F stripped
    assert terminal is True


def test_gui_app_parsed_and_strips_field_codes(monkeypatch):
    monkeypatch.setattr(cli, "_run", lambda argv, **k: "qutebrowser --untrusted-args %u\nfalse\n")
    argv, terminal = cli.madft_desktop_exec("org.qutebrowser.qutebrowser")
    assert argv == ["qutebrowser", "--untrusted-args"]
    assert terminal is False


def test_unknown_app_returns_none(monkeypatch):
    # madft prints the error to stderr (dropped by _run); stdout is empty.
    monkeypatch.setattr(cli, "_run", lambda argv, **k: "")
    argv, terminal = cli.madft_desktop_exec("totallybogusapp")
    assert argv is None
    assert terminal is False


def test_empty_app_id_does_not_call_madft(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", lambda argv, **k: calls.append(argv) or "x\ntrue")
    argv, terminal = cli.madft_desktop_exec("")
    assert argv is None
    assert calls == []                 # short-circuits without invoking madft


def test_invokes_madft_with_expected_argv(monkeypatch):
    seen = {}
    monkeypatch.setattr(cli, "_run", lambda argv, **k: seen.update(argv=argv) or "nvim\ntrue")
    cli.madft_desktop_exec("nvim")
    assert seen["argv"] == [cli.MADFT, "app", "nvim", "desktop", "Exec", "Terminal"]
