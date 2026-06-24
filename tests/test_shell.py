from madopen import shell


def test_init_emits_function_calling_the_binary(capsys):
    rc = shell.shell_init("zsh")
    out = capsys.readouterr().out
    assert rc == 0
    assert "madopen()" in out                 # defines the function
    assert "madopen-bin" in out               # calls the binary (no recursion)
    assert "3>&1 1>/dev/tty" in out           # the fd-3 cd dance is preserved
    assert "cd -- " in out


def test_init_emits_no_aliases(capsys):
    shell.shell_init("zsh")
    out = capsys.readouterr().out
    assert "alias o=" not in out
    assert "alias oh=" not in out


def test_init_bash_supported(capsys):
    assert shell.shell_init("bash") == 0
    assert "madopen()" in capsys.readouterr().out


def test_init_unsupported_shell_errors(capsys):
    assert shell.shell_init("fish") != 0
    assert "unsupported" in capsys.readouterr().err
