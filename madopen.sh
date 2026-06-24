# madopen shell integration — source this from ~/.zshrc (or ~/.bashrc)
#
#   source /home/samtell/projects/madopen/madopen.sh
#
# Why a function and not just the script: a child process can't cd its parent
# shell. So madopen.py prints the target dir, and this wrapper cd's into it.
#
# The fd dance below matters: madopen.py emits the dir on fd 3, while fd 1 is
# pointed at the real terminal. That way an interactive editor (e.g. nvim) gets
# a real tty on stdout instead of our capture pipe, and the dir still comes back
# to us on fd 3. fzf is unaffected — it talks to /dev/tty directly regardless.

export MADOPEN_HOME="${MADOPEN_HOME:-/home/samtell/projects/madopen}"

madopen() {
    local dir
    # 3>&1  -> fd 3 becomes the command-substitution capture pipe
    # 1>/dev/tty -> the script's (and any editor's) stdout goes to the terminal
    dir="$("$MADOPEN_HOME/bin/madopen.py" "$@" 3>&1 1>/dev/tty)" || return
    [ -n "$dir" ] && [ -d "$dir" ] && cd -- "$dir"
}

alias o='madopen'              # browse + open
alias oh='madopen -h'          # search history only (oh <thing> from anywhere)
alias vim='madopen -a nvim'    # open with nvim, filtered to files nvim handles
alias vimh='madopen -h -a nvim'
