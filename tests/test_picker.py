import os
from madopen import cli


def test_fzf_argv_has_flipped_binds_and_cycle():
    argv = cli.build_fzf_argv({"preview_window": "right:50%:wrap", "fzf_flags": []},
                              "PREVIEW")
    assert "tab:up,shift-tab:down" in argv      # Tab moves UP the list
    assert "--cycle" in argv                    # wrap around
    assert "PREVIEW" in argv                     # preview command threaded through
    i = argv.index("--preview-window")
    assert argv[i + 1] == "right:50%:wrap"


def test_fzf_argv_appends_extra_flags():
    argv = cli.build_fzf_argv({"preview_window": "x", "fzf_flags": ["--no-mouse"]}, "P")
    assert argv[-1] == "--no-mouse"


def test_custom_picker_path_returns_executable(tmp_path):
    script = tmp_path / "pick.sh"
    script.write_text("#!/bin/sh\ncat\n")
    os.chmod(script, 0o755)
    assert cli.custom_picker_path({"custom_picker": str(script)}) == str(script)


def test_custom_picker_path_none_when_unset_or_missing(tmp_path):
    assert cli.custom_picker_path({"custom_picker": None}) is None
    assert cli.custom_picker_path({"custom_picker": str(tmp_path / "nope.sh")}) is None
