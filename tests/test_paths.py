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


def test_app_dirs_includes_data_home_first_then_data_dirs(monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/xdata")
    monkeypatch.setenv("XDG_DATA_DIRS", "/a:/b")
    assert paths.app_dirs() == [
        "/tmp/xdata/applications", "/a/applications", "/b/applications",
    ]


def test_app_dirs_defaults(monkeypatch):
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_DIRS", raising=False)
    monkeypatch.setenv("HOME", "/home/u")
    assert paths.app_dirs() == [
        "/home/u/.local/share/applications",
        "/usr/local/share/applications",
        "/usr/share/applications",
    ]
