---
name: paper-preprocess
description: This skill converts an academic paper PDF into a markdown cache (paper.md) using marker-pdf so downstream agents can prefer a pre-parsed text cache over re-reading the PDF on every iteration. Triggers on "preprocess paper", "convert paper to markdown", and is invoked automatically at the start of paper-summarize, paper-extend, paper-present, and paper-full-pipeline whenever paper.md does not exist or is stale relative to the source PDF.
argument-hint: "<path-to-paper.pdf>"
allowed-tools: ["Read", "Write", "Bash", "Grep", "Glob"]
---

# Preprocess Paper

Convert the paper PDF to markdown so downstream agents read a pre-parsed text cache instead of re-parsing the PDF on every iteration. The cached markdown lives at `paper-extension/paper.md` and is stamped with the source PDF's SHA256 so stale caches are detected automatically.

## Prerequisites

- A PDF file path must be provided as an argument.
- `marker_single` must be available on PATH (installed via `pip install marker-pdf`) **if the user answers `yes` to the prompt in step 0**. The first run downloads ~2 GB of models.
- Conversion on a CPU typically takes 10–20 minutes and can run longer for larger papers; on a GPU it is much faster. This is why the skill asks before running.
- If the user answers `no`, or if `marker_single` is missing, the skill exits cleanly — downstream agents fall back to reading the PDF directly, so the pipeline still works.

## When to run

- **Manually** via `/CASM-tools:paper-preprocess <path-to-paper.pdf>`
- **Automatically** at the start of `/CASM-tools:paper-summarize`, `/CASM-tools:paper-extend`, `/CASM-tools:paper-present`, and `/CASM-tools:paper-full-pipeline`. Each of those skills invokes paper-preprocess when `paper.md` does not exist or its `source_sha256` frontmatter does not match the current PDF's checksum.

Users do not normally invoke this skill directly — the other pipeline stages do it for them.

## Process

### 0. Check for a prior decision on the current PDF (short-circuit both ways)

Before prompting, compute the source PDF checksum and check for either of these pre-existing decisions tied to the current SHA256:

```bash
SRC_PDF="<absolute-path-to-paper.pdf>"
SRC_SHA="$(sha256sum "$SRC_PDF" | awk '{print $1}')"

# Case A: fresh markdown cache already exists
if [ -f paper-extension/paper.md ]; then
    CACHED_SHA="$(grep -E '^source_sha256:' paper-extension/paper.md | head -1 | awk '{print $2}')"
    if [ "$CACHED_SHA" = "$SRC_SHA" ]; then
        echo "paper.md cache is fresh (sha256 matches). Skipping preprocess — no prompt needed."
        exit 0
    fi
fi

# Case B: user previously declined preprocessing on this exact PDF
if [ -f "paper-extension/.preprocess-declined" ]; then
    DECLINED_SHA="$(cat paper-extension/.preprocess-declined)"
    if [ "$DECLINED_SHA" = "$SRC_SHA" ]; then
        echo "User previously declined preprocessing on this PDF (sha256 matches). Skipping prompt; downstream agents will read the PDF directly."
        exit 0
    fi
fi
```

Either case exits 0 with no prompt — the user has already decided for this PDF and the decision is durable until the PDF itself changes (new SHA256 invalidates both caches).

Only if both checks miss do we proceed to the prompt below.

### 0a. Ask the user whether to run marker

Use the `AskUserQuestion` tool to ask the user whether to generate a markdown cache or skip preprocessing.

Dispatch this question shape:

```
AskUserQuestion({
  questions: [{
    question: "Preprocess the paper into markdown?",
    header: "Preprocess",
    multiSelect: false,
    options: [
      {
        label: "Generate markdown",
        description: "Run marker_single to convert the PDF into paper-extension/paper.md. Reduces LLM token usage across summarize, extend, present. Requires `marker_single` (pip install marker-pdf); on CPU, conversion typically takes 10–20 minutes (longer for large papers), and the first run downloads ~2 GB of models. On GPU it is much faster."
      },
      {
        label: "Skip, read PDF directly",
        description: "Do not run marker. Downstream agents read the PDF directly on each call. Higher token usage but zero preprocessing wait time."
      }
    ]
  }]
})
```

Map the user's answer:

- `Generate markdown` → continue to step 1 below.
- `Skip, read PDF directly` → skip marker entirely. Record the decision so re-invocations on the same PDF do not re-prompt:

  ```bash
  mkdir -p paper-extension
  echo "$SRC_SHA" > paper-extension/.preprocess-declined
  ```

  Do NOT write `paper.md`. Report "skipping preprocess at user request; downstream agents will read the PDF directly." Exit 0.
- If the user selects "Other" and provides free text, interpret generously (yes/y/run/generate → run; no/n/skip → skip). If the free text is ambiguous, re-ask the question once.

Steps 1–6 only run when the user chose "Generate markdown". If `Generate markdown` is chosen, also remove any stale decline marker so the choice is unambiguous:

```bash
rm -f paper-extension/.preprocess-declined
```

### 1. Resolve paths and compute checksum

Determine the output directory from the PDF path. If the PDF is at `Paper/paper.pdf`, the output directory is `Paper/paper-extension/`. Create it if it does not exist, plus the `preprocess-logs/` and `session-logs/` subdirectories.

Compute the source checksum:

```bash
SRC_PDF="<absolute-path-to-paper.pdf>"
SRC_SHA="$(sha256sum "$SRC_PDF" | awk '{print $1}')"
```

### 2. Verify marker_single is available (soft dependency)

```bash
if ! command -v marker_single >/dev/null 2>&1; then
    echo "Warning: marker_single not found on PATH." >&2
    echo "Install with: pip install marker-pdf" >&2
    echo "Downstream agents will fall back to reading the PDF directly." >&2
    exit 0
fi
```

Exit status is 0 here, not an error — a missing `marker_single` must not break the pipeline.

### 3. Run marker_single

```bash
marker_single "$SRC_PDF" paper-extension/preprocess-logs --output_format markdown
```

If `marker_single` exits with non-zero status, capture stderr, warn, delete any partial output, and exit 0.

### 4. Install the markdown cache

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

### 5. Sanity-check the output

Read `paper-extension/paper.md` (first ~2000 characters) and verify the frontmatter parses, the body has English text, at least one heading appears in the first 200 lines, and the file is ≥ 10 KB or ≥ 200 lines.

If the file is obviously broken (empty, < 1 KB), delete it so agents fall back to the PDF:

```bash
rm -f paper-extension/paper.md
echo "Warning: preprocess output failed sanity check. Removed paper.md; agents will fall back to PDF." >&2
```

### 6. Session log

Create `paper-extension/session-logs/YYYY-MM-DD_preprocess.md` from `${CLAUDE_PLUGIN_ROOT}/scripts/session-log-template.md`. Record source PDF path and SHA256, output line/char count, image count, sanity-check warnings, and marker run duration.

## Output

- `paper-extension/paper.md` — markdown cache with provenance frontmatter
- `paper-extension/paper-images/` — extracted figures (when any)
- `paper-extension/preprocess-logs/<stem>/` — raw marker output
- `paper-extension/session-logs/YYYY-MM-DD_preprocess.md` — session log

## Notes

- The cache is invalidated on SHA256 mismatch. If the user updates the PDF, the next pipeline run regenerates (subject to the step-0 prompt).
- marker-pdf's first run downloads ~2 GB of models. Subsequent papers reuse the cached models.
- CPU conversion takes 10–20 minutes for typical papers; GPU is much faster. The step-0 prompt exists so the user can opt out when that cost doesn't match the current task.
- If marker-pdf is not installed, the pipeline keeps working; it just loses the speedup. Install with `pip install marker-pdf` to unlock it.
- The prompt in step 0 is asked on every invocation. Pipeline skills (`paper-summarize`, `paper-extend`, `paper-present`, `paper-full-pipeline`) that invoke paper-preprocess automatically will surface this prompt to the user before doing work — so the user decides per-paper whether to pay the conversion cost.

## Troubleshooting

- **`marker_single: command not found`** → `pip install marker-pdf`. First run downloads ML models (~2 GB).
- **Output is empty or garbled** → PDF may be image-only (a scan) or use exotic embedded fonts. Check raw marker output under `preprocess-logs/<stem>/`.
- **Cache always regenerates** → check `sha256sum <pdf>` matches the `source_sha256:` line in `paper.md`. Something may be rewriting the PDF between runs.
- **`paper.md` has garbled content in one section** → per-passage fallback handles this. Agents drop to the PDF for that section.
