"""build_launch_argv expands .desktop Exec field codes and places app_args + file."""
from madopen import cli


def test_standalone_file_code_places_args_before_file():
    assert cli.build_launch_argv(["nvim", "%F"], "/a/b.txt", ["-R"]) == \
        ["nvim", "-R", "/a/b.txt"]


def test_no_file_code_appends_args_then_file():
    assert cli.build_launch_argv(["foo", "--bar"], "/a/b.txt", ["-x"]) == \
        ["foo", "--bar", "-x", "/a/b.txt"]


def test_mpv_double_dash_url_code():
    assert cli.build_launch_argv(
        ["mpv", "--player-operation-mode=pseudo-gui", "--", "%U"], "/v.mp4", []
    ) == ["mpv", "--player-operation-mode=pseudo-gui", "--", "/v.mp4"]


def test_gnarly_env_prefix_and_concatenated_codes():
    toks = ["env", "LANG=banana", "/bin/foobar",
            "--computer-will-set-ablaze-without-this", "%A%B%C%D%E%F%G"]
    assert cli.build_launch_argv(toks, "/x.iso", []) == [
        "env", "LANG=banana", "/bin/foobar",
        "--computer-will-set-ablaze-without-this", "/x.iso",
    ]


def test_embedded_file_code_substitutes_in_place():
    assert cli.build_launch_argv(["app", "--uri=%u"], "/a/b.txt", []) == \
        ["app", "--uri=/a/b.txt"]


def test_percent_literal_and_dropped_codes():
    # %% -> %, %i and %c dropped, %F is the file slot
    assert cli.build_launch_argv(
        ["app", "--pct=100%%", "%i", "%c", "%F"], "/f", []
    ) == ["app", "--pct=100%", "/f"]


def test_bare_dropped_code_token_removed():
    # a lone %i (icon) with no icon collapses to nothing and is dropped
    assert cli.build_launch_argv(["app", "%i", "%f"], "/f", []) == ["app", "/f"]
