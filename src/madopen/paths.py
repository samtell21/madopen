"""XDG directory resolution. Pure and env-driven so tests can monkeypatch."""
import os


def _xdg(env, default_subpath):
    val = os.environ.get(env)
    if val:
        return val
    return os.path.join(os.path.expanduser("~"), default_subpath)


def state_dir():
    """The madopen state directory ($XDG_STATE_HOME/madopen)."""
    return os.path.join(_xdg("XDG_STATE_HOME", ".local/state"), "madopen")


def db_path():
    """Full path to the history database."""
    return os.path.join(state_dir(), "history.db")


def config_path():
    """Full path to the optional config.toml ($XDG_CONFIG_HOME/madopen)."""
    return os.path.join(_xdg("XDG_CONFIG_HOME", ".config"), "madopen", "config.toml")


def app_dirs():
    """`applications/` dirs, highest precedence first: data_home then data_dirs."""
    data_home = _xdg("XDG_DATA_HOME", ".local/share")
    data_dirs = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    bases = [data_home] + [d for d in data_dirs.split(":") if d]
    return [os.path.join(d, "applications") for d in bases]
