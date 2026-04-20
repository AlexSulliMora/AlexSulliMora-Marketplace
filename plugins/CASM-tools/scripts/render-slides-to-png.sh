#!/usr/bin/env bash
#
# render-slides-to-png.sh
#
# Convert a compiled presentation to per-slide PNG screenshots so the
# presentation-reviewer agent can visually inspect actual rendered slides
# instead of inferring fullness from source text length.
#
# Usage: render-slides-to-png.sh <presentation-file> <output-dir>
#
# Supported inputs (auto-detected by extension):
#   *.html, *.htm  -> Revealjs         (decktape -> PDF -> pdftoppm -> PNG)
#   *.pptx, *.ppt  -> PowerPoint       (libreoffice -> PDF -> pdftoppm -> PNG)
#   *.pdf          -> Beamer / generic (pdftoppm -> PNG)
#
# Output: <output-dir>/slide-001.png, slide-002.png, ...
#
# Dependencies (only the ones needed for the chosen input format):
#   - pdftoppm        (poppler-utils; always required)
#   - decktape        OR  npx       (for .html)
#   - libreoffice     OR  soffice   (for .pptx / .ppt)

set -euo pipefail

if [ $# -ne 2 ]; then
    echo "Usage: $0 <presentation-file> <output-dir>" >&2
    exit 2
fi

PRES="$1"
OUT="$2"

if [ ! -f "$PRES" ]; then
    echo "Error: presentation file not found: $PRES" >&2
    exit 1
fi

if ! command -v pdftoppm >/dev/null 2>&1; then
    echo "Error: pdftoppm not found. Install poppler-utils (e.g. 'sudo apt install poppler-utils')." >&2
    exit 1
fi

mkdir -p "$OUT"
# Clear any stale screenshots from a prior iteration so slide count is accurate.
rm -f "$OUT"/slide-*.png

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

ext="${PRES##*.}"
ext="$(printf '%s' "$ext" | tr '[:upper:]' '[:lower:]')"

case "$ext" in
    html|htm)
        PDF="$TMP/slides.pdf"
        if command -v decktape >/dev/null 2>&1; then
            decktape reveal --size 1050x700 "$PRES" "$PDF"
        elif command -v npx >/dev/null 2>&1; then
            # -y auto-accepts the install prompt; decktape is fetched on first run and cached.
            npx -y decktape@latest reveal --size 1050x700 "$PRES" "$PDF"
        else
            echo "Error: neither 'decktape' nor 'npx' is available on PATH." >&2
            echo "Install Node.js (brings npx) OR install decktape globally: 'npm install -g decktape'." >&2
            exit 1
        fi
        ;;
    pptx|ppt)
        SOFFICE=""
        if command -v libreoffice >/dev/null 2>&1; then
            SOFFICE="libreoffice"
        elif command -v soffice >/dev/null 2>&1; then
            SOFFICE="soffice"
        fi
        if [ -z "$SOFFICE" ]; then
            echo "Error: libreoffice/soffice not found. Install LibreOffice (e.g. 'sudo apt install libreoffice')." >&2
            exit 1
        fi
        "$SOFFICE" --headless --convert-to pdf --outdir "$TMP" "$PRES" >/dev/null
        base="$(basename "$PRES")"
        base="${base%.*}"
        PDF="$TMP/${base}.pdf"
        if [ ! -f "$PDF" ]; then
            echo "Error: libreoffice did not produce a PDF at $PDF" >&2
            exit 1
        fi
        ;;
    pdf)
        PDF="$PRES"
        ;;
    *)
        echo "Error: unsupported extension .$ext (expected .html, .htm, .pptx, .ppt, or .pdf)" >&2
        exit 1
        ;;
esac

# Render the PDF to PNGs at 150 DPI. pdftoppm pads automatically based on
# page count (1-9 pages: no padding; 10-99: 2-digit; etc.). We normalize to
# 3-digit padding afterwards so sorting is stable regardless of deck size.
pdftoppm -r 150 -png "$PDF" "$OUT/slide"

cd "$OUT"
for f in slide-*.png; do
    [ -f "$f" ] || continue
    num="${f#slide-}"
    num="${num%.png}"
    if [[ "$num" =~ ^[0-9]+$ ]]; then
        # 10#$num forces base-10 interpretation (guards against leading zeros).
        padded="$(printf "%03d" "$((10#$num))")"
        if [ "$num" != "$padded" ]; then
            mv "$f" "slide-${padded}.png"
        fi
    fi
done

count=$(ls -1 slide-*.png 2>/dev/null | wc -l | tr -d ' ')
echo "Rendered ${count} screenshot(s) to ${OUT}"
