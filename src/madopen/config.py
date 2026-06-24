"""Read the optional ~/.config/madopen/config.toml. Flat schema, all keys
optional; missing or malformed files fall back to defaults."""
import tomllib

from . import paths

DEFAULTS = {
    "preview_window": "right:50%:wrap",
    "enable_preview": True,
    "image_backend": "chafa",
    "enable_video": True,
    "enable_pdf": True,
    "fzf_flags": [],
    "custom_picker": None,
}


def load_config(path=None):
    """Return the merged config dict (defaults overlaid with file values)."""
    path = path or paths.config_path()
    cfg = dict(DEFAULTS)
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except (FileNotFoundError, IsADirectoryError, tomllib.TOMLDecodeError):
        return cfg
    for key in DEFAULTS:
        if key in data:
            cfg[key] = data[key]
    return cfg
