"""The fzf preview renderer, kept as a shell-string constant (fzf runs it via
`sh -c` on each cursor move, so Python is never in the per-keystroke loop).

Config knobs arrive as environment variables (see build_preview_env): the image
backend and the video/pdf toggles. Every external tool is `command -v`-guarded,
so a missing tool degrades to `file -b` / `head` / `ls`.
"""

# Renders the item passed by fzf as {}. Layout: full path on top (so long paths
# are always visible), then a kind-specific body. A trailing " (new)" label
# (from the --new dir picker) is stripped first.
PREVIEW_SH = r"""
p={}; p="${p% (new)}"
printf '%s\n\n' "$p"

img() {
    backend="${MADOPEN_IMAGE_BACKEND:-chafa}"
    if [ "$backend" = "kitten" ] && command -v kitten >/dev/null 2>&1; then
        kitten icat --clear --transfer-mode=memory \
            --stdin=no --place="${FZF_PREVIEW_COLUMNS}x${FZF_PREVIEW_LINES}@0x0" "$1" 2>/dev/null && return
    fi
    if command -v chafa >/dev/null 2>&1; then
        chafa -s "${FZF_PREVIEW_COLUMNS}x${FZF_PREVIEW_LINES}" "$1" 2>/dev/null && return
    fi
    file -b "$1"
}

if [ -d "$p" ]; then
    eza -la --color=always --group-directories-first "$p" 2>/dev/null || ls -la "$p"
elif [ ! -e "$p" ]; then
    echo '(new file)'
else
    mt=$(file --mime-type -b "$p" 2>/dev/null)
    case "$mt" in
        image/*)
            img "$p" ;;
        video/*)
            if [ -n "$MADOPEN_ENABLE_VIDEO" ] && command -v ffmpegthumbnailer >/dev/null 2>&1; then
                tmp=$(mktemp --suffix=.png 2>/dev/null) || tmp=/tmp/madopen_vprev.png
                ffmpegthumbnailer -i "$p" -o "$tmp" -s 0 >/dev/null 2>&1 && img "$tmp"
                rm -f "$tmp"
            else
                file -b "$p"
            fi ;;
        application/pdf)
            if [ -n "$MADOPEN_ENABLE_PDF" ] && command -v pdftoppm >/dev/null 2>&1; then
                tmp=$(mktemp 2>/dev/null) || tmp=/tmp/madopen_pprev
                pdftoppm -png -f 1 -l 1 -scale-to 1000 "$p" "$tmp" >/dev/null 2>&1 && img "${tmp}-1.png"
                rm -f "${tmp}"*.png "$tmp"
            else
                pdfinfo "$p" 2>/dev/null || file -b "$p"
            fi ;;
        text/* | application/json | application/xml | application/javascript \
            | application/toml | application/x-shellscript | application/x-yaml \
            | application/x-desktop)
            bat --color=always --style=numbers --line-range=:300 "$p" 2>/dev/null \
                || head -n 300 "$p" ;;
        *)
            file -b "$p" ;;
    esac
fi
"""


def build_preview_env(config):
    """Environment variables consumed by PREVIEW_SH, derived from config."""
    return {
        "MADOPEN_IMAGE_BACKEND": config.get("image_backend") or "chafa",
        "MADOPEN_ENABLE_VIDEO": "1" if config.get("enable_video", True) else "",
        "MADOPEN_ENABLE_PDF": "1" if config.get("enable_pdf", True) else "",
    }
