"""Shell integration emitted by `madopen-bin init <shell>` (zoxide-style).

A child process can't cd its parent shell, so madopen-bin prints the directory
on fd 3 and this function cd's into it. The function is named `madopen` while
the binary is `madopen-bin`, so there is no recursion.
"""
import sys

# The body is POSIX-sh compatible, so the same text serves zsh and bash.
_FUNCTION = r"""madopen() {
    local dir
    # 3>&1  -> fd 3 becomes the command-substitution capture pipe
    # 1>/dev/tty -> the binary's (and any editor's) stdout goes to the terminal
    dir="$(madopen-bin "$@" 3>&1 1>/dev/tty)" || return
    [ -n "$dir" ] && [ -d "$dir" ] && cd -- "$dir"
}
"""

_SUPPORTED = ("zsh", "bash")


def shell_init(shell="zsh"):
    """Emit the madopen shell function for `shell`. Returns an exit code."""
    if shell not in _SUPPORTED:
        sys.stderr.write(
            f"madopen: unsupported shell '{shell}' (supported: {', '.join(_SUPPORTED)})\n"
        )
        return 1
    sys.stdout.write(_FUNCTION)
    return 0
