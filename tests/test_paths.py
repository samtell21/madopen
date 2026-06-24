from madopen import paths


def test_db_path_uses_xdg_state_home(monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", "/tmp/xstate")
    assert paths.state_dir() == "/tmp/xstate/madopen"
    assert paths.db_path() == "/tmp/xstate/madopen/history.db"


def test_db_path_defaults_without_xdg(monkeypatch):
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setenv("HOME", "/home/u")
    assert paths.db_path() == "/home/u/.local/state/madopen/history.db"


def test_config_path_uses_xdg_config_home(monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/xcfg")
    assert paths.config_path() == "/tmp/xcfg/madopen/config.toml"
