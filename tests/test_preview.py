from madopen import preview


def test_env_maps_backend_and_toggles():
    env = preview.build_preview_env({
        "image_backend": "kitten", "enable_video": False, "enable_pdf": True,
    })
    assert env["MADOPEN_IMAGE_BACKEND"] == "kitten"
    assert env["MADOPEN_ENABLE_VIDEO"] == ""      # falsy -> empty
    assert env["MADOPEN_ENABLE_PDF"] == "1"


def test_env_defaults_when_keys_absent():
    env = preview.build_preview_env({})
    assert env["MADOPEN_IMAGE_BACKEND"] == "auto"     # auto-detect by default
    assert env["MADOPEN_ENABLE_VIDEO"] == "1"
    assert env["MADOPEN_ENABLE_PDF"] == "1"


def test_preview_sh_has_placeholder_and_guards():
    assert "{}" in preview.PREVIEW_SH                 # fzf substitutes the path
    assert "command -v" in preview.PREVIEW_SH         # tools are guarded
    assert "(new)" in preview.PREVIEW_SH              # strips the --new label


def test_preview_sh_image_backend_autodetect():
    # auto picks native kitten inside kitty, else chafa
    assert "KITTY_WINDOW_ID" in preview.PREVIEW_SH
    assert "--unicode-placeholder" in preview.PREVIEW_SH   # correct fzf-pane placement
    assert "chafa" in preview.PREVIEW_SH
