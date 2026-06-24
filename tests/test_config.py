from madopen import config


def test_missing_file_returns_defaults(tmp_path):
    cfg = config.load_config(str(tmp_path / "nope.toml"))
    assert cfg["preview_window"] == "right:50%:wrap"
    assert cfg["enable_preview"] is True
    assert cfg["custom_picker"] is None
    assert cfg["fzf_flags"] == []


def test_overrides_applied(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(
        'preview_window = "down:40%"\n'
        'enable_video = false\n'
        'fzf_flags = ["--no-mouse"]\n'
        'custom_picker = "/x/pick.sh"\n'
    )
    cfg = config.load_config(str(p))
    assert cfg["preview_window"] == "down:40%"
    assert cfg["enable_video"] is False
    assert cfg["fzf_flags"] == ["--no-mouse"]
    assert cfg["custom_picker"] == "/x/pick.sh"
    # untouched keys keep defaults
    assert cfg["image_backend"] == "chafa"


def test_malformed_toml_falls_back_to_defaults(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text("this is = = not valid toml [[[")
    cfg = config.load_config(str(p))
    assert cfg["preview_window"] == "right:50%:wrap"


def test_returned_lists_are_isolated_from_defaults():
    cfg1 = config.load_config("/nonexistent/x.toml")
    cfg1["fzf_flags"].append("--mutated")
    cfg2 = config.load_config("/nonexistent/x.toml")
    assert cfg2["fzf_flags"] == []
