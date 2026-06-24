import os
from madopen import cli


def test_launch_cwd_without_peek_is_file_parent():
    assert cli.resolve_launch_cwd("/a/b/c.txt", peek=False) == "/a/b"


def test_launch_cwd_with_peek_is_caller_cwd(monkeypatch):
    monkeypatch.setattr(os, "getcwd", lambda: "/project/root")
    assert cli.resolve_launch_cwd("/a/b/c.txt", peek=True) == "/project/root"
