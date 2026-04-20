---
name: preprocess
description: This skill converts an academic paper PDF into a markdown cache (paper.md) using marker-pdf so downstream agents can prefer a pre-parsed text cache over re-reading the PDF on every iteration. Triggers on "preprocess paper", "convert paper to markdown", and is invoked automatically at the start of summarize, extend, present, and run whenever paper.md does not exist or is stale relative to the source PDF.
argument-hint: "<path-to-paper.pdf>"
allowed-tools: ["Read", "Write", "Bash", "Grep", "Glob"]
---

# Preprocess Paper

Convert the paper PDF to markdown so downstream agents read a pre-parsed text cache instead of re-parsing the PDF on every iteration. The cached markdown lives at `paper-extension/paper.md` and is stamped with the source PDF's SHA256 so stale caches are detected automatically.

## Prerequisites

- A PDF file path must be provided as an argument
- `marker_single` should be available on PATH (installed via `pip install marker-pdf`)
- If `marker_single` is missing, this skill exits cleanly with an install hint. The pipeline tolerates a missing `paper.md` — downstream agents fall back to reading the PDF directly — so a missing marker-pdf is a soft failure by design, not a blocker.

## When to run

- **Manually** via `/paper-extension:preprocess <path-to-paper.pdf>`
- **Automatically** at the start of `/paper-extension:summarize`, `/paper-extension:extend`, `/paper-extension:present`, and `/paper-extension:run`. Each of those skills invokes preprocess when `paper.md` does not exist or its `source_sha256` frontmatter does not match the current PDF's checksum.

Users do not normally invoke this skill directly — the other pipeline stages do it for them.

## Process

### 1. Resolve paths and compute checksum

Determine the output directory from the PDF path. If the PDF is at `Paper/paper.pdf`, the output directory is `Paper/paper-extension/`. Create it if it does not exist, plus the `preprocess-logs/` and `session-logs/` subdirectories.

Compute the source checksum:

```bash
SRC_PDF="<absolute-path-to-paper.pdf>"
SRC_SHA="$(sha256sum "$SRC_PDF" | awk '{print $1}')"
```

### 2. Short-circuit if the cache is fresh

If `paper-extension/paper.md` already exists, read its YAML frontmatter and extract the `source_sha256:` line. If that value matches `$SRC_SHA`, the cache is already current — report "cache is fresh, skipping" to the user and exit. Do NOT rerun marker.

```bash
if [ -f paper-extension/paper.md ]; then
    CACHED_SHA="$(grep -E '^source_sha256:' paper-extension/paper.md | head -1 | awk '{print $2}')"
    if [ "$CACHED_SHA" = "$SRC_SHA" ]; then
        echo "paper.md cache is fresh (sha256 matches). Skipping preprocess."
        exit 0
    fi
fi
```

### 3. Verify marker_single is available (soft dependency)

```bash
if ! command -v marker_single >/dev/null 2>&1; then
    echo "Warning: marker_single not found on PATH." >&2
    echo "Install with: pip install marker-pdf" >&2
    echo "Downstream agents will fall back to reading the PDF directly." >&2
    exit 0
fi
```

Exit status is 0 here, not an error — a missing `marker_single` must not break the pipeline.

### 4. Run marker_single

```bash
marker_single "$SRC_PDF" paper-extension/preprocess-logs --output_format markdown
```

If `marker_single` exits with non-zero status, capture stderr, warn, delete any partial output, and exit 0.

### 5. Install the markdown cache

```bash
STEM="$(basename "$SRC_PDF" .pdf)"
MARKER_OUT="paper-extension/preprocess-logs/${STEM}/${STEM}.md"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [ ! -f "$MARKER_OUT" ]; then
    echo "Warning: marker did not produce expected output at $MARKER_OUT" >&2
    exit 0
fi

{
    echo "---"
    echo "source_pdf: $SRC_PDF"
    echo "source_sha256: $SRC_SHA"
    echo "preprocessed_at: $TIMESTAMP"
    echo "tool: marker-pdf"
    echo "---"
    echo ""
    cat "$MARKER_OUT"
} > paper-extension/paper.md
```

If marker extracted images, move them to `paper-extension/paper-images/`:

```bash
if [ -d "paper-extension/preprocess-logs/${STEM}/images" ]; then
    rm -rf paper-extension/paper-images
    mv "paper-extension/preprocess-logs/${STEM}/images" paper-extension/paper-images
fi
```

### 6. Sanity-check the output

Read `paper-extension/paper.md` (first ~2000 characters) and verify the frontmatter parses, the body has English text, at least one heading appears in the first 200 lines, and the file is ≥ 10 KB or ≥ 200 lines.

If the file is obviously broken (empty, < 1 KB), delete it so agents fall back to the PDF:

```bash
rm -f paper-extension/paper.md
echo "Warning: preprocess output failed sanity check. Removed paper.md; agents will fall back to PDF." >&2
```

### 7. Session log

Create `paper-extension/session-logs/YYYY-MM-DD_preprocess.md` from `~/.claude/plugins/deep-review/scripts/session-log-template.md`. Record source PDF path and SHA256, output line/char count, image count, sanity-check warnings, and marker run duration.

## Output

- `paper-extension/paper.md` — markdown cache with provenance frontmatter
- `paper-extension/paper-images/` — extracted figures (when any)
- `paper-extension/preprocess-logs/<stem>/` — raw marker output
- `paper-extension/session-logs/YYYY-MM-DD_preprocess.md` — session log

## Notes

- The cache is invalidated on SHA256 mismatch. If the user updates the PDF, the next pipeline run regenerates.
- marker-pdf's first run downloads ~2 GB of models. Subsequent papers are much faster.
- If marker-pdf is not installed, the pipeline keeps working; it just loses the speedup. Install with `pip install marker-pdf` to unlock it.

## Troubleshooting

- **`marker_single: command not found`** → `pip install marker-pdf`. First run downloads ML models (~2 GB).
- **Output is empty or garbled** → PDF may be image-only (a scan) or use exotic embedded fonts. Check raw marker output under `preprocess-logs/<stem>/`.
- **Cache always regenerates** → check `sha256sum <pdf>` matches the `source_sha256:` line in `paper.md`. Something may be rewriting the PDF between runs.
- **`paper.md` has garbled content in one section** → per-passage fallback handles this. Agents drop to the PDF for that section.
