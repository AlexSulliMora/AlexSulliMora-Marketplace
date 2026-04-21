---
name: present
description: This skill creates a slide presentation and a companion writeup from a summarized/extended paper. Supports scope options ("summary only" for paper summary, "extension only" for extension deep-dive) and output formats (revealjs HTML default, ppt, pdf). Triggers on "create a presentation", "build slides", "present this paper", "/CASM-tools:present summary only", "/CASM-tools:present extension only", "/CASM-tools:present ppt", "/CASM-tools:present pdf".
argument-hint: "<path-to-paper.pdf> [summary only | extension only] [ppt | pdf]"
allowed-tools: ["Read", "Write", "Bash", "Grep", "Glob", "Agent", "Skill"]
---

# Present Paper

Create a slide presentation and manuscript writeup from a finalized summary and extensions document. The initial drafts come from the `presentation-builder` agent; the quality loop is delegated to `/CASM-tools:review-document`.

## Preference injection (automatic via preference-injection hook)

The presentation-builder's style preferences are injected automatically by the plugin's PreToolUse hook before the subagent spawns. The builder and presentation-reviewer share the same presentation style preferences, so initial draft output and reviewer scoring stay aligned.

> **Dispatch exactly the task. Do not add preferences.**
> The hook prepends the relevant style preferences automatically.
> If you include preference content manually, the agent receives it twice.
> If the hook is disabled, the agent's body carries a fallback pointer.

The post-cascade screenshot-based presentation-review pass (step 6 below) also receives its preferences via the hook.

## Prerequisites

- A PDF file path must be provided as an argument
- Finalized outputs must exist:
  - `paper-extension/summary.md`
  - `paper-extension/extensions.md` (required for full and extension-only scope; not for summary only)
- Quarto must be installed and available on PATH (check with `quarto --version`)
- For Revealjs: Node.js (`npx`) or `decktape` on PATH (for screenshot rendering)
- For PowerPoint: `libreoffice` or `soffice` on PATH
- `pdftoppm` from poppler-utils (all formats)

## Argument Parsing

Parse (case-insensitive):

**Scope**: `summary only` / `extension only` / default (full)
**Format**: `ppt` or `pptx` / `pdf` (Beamer) / default (Revealjs HTML)

## Session Logging

1. **At start**: Create `paper-extension/session-logs/YYYY-MM-DD_present.md` using `${CLAUDE_PLUGIN_ROOT}/scripts/session-log-template.md`. Record objective, scope, format, paper details.
2. **After preprocess**: Record outcome.
3. **After initial draft + compile + screenshot**: Record both `.qmd` files produced and compiled, screenshot count.
4. **After /CASM-tools:review-document returns**: Record final scores, iteration count, checkpoint decision, cascade logs path.
5. **After post-cascade screenshot review (if run)**: Record outcome.
6. **At end**: Update Status.

## Process

### 1. Verify inputs and set up directories

```
paper-extension/presentation-logs/
paper-extension/presentation-logs/screenshots/
paper-extension/writeup-logs/
```

### 2. Preprocess paper (auto)

If `paper-extension/paper.md` already exists (from a prior summarize/extend/preprocess run on this paper), **skip this step entirely** — do not invoke preprocess. The presentation-builder will read the existing `paper.md` cache, and re-prompting the user about preprocessing would be redundant.

If `paper.md` does NOT exist, invoke `CASM-tools:preprocess` via the Skill tool. The preprocess skill self-short-circuits when a prior decision (generate or skip) is recorded against the current PDF's SHA256, so it will only prompt the user when there is genuinely no recorded choice yet.

**When preprocess returns, continue immediately to step 3.** A cache hit, a freshly generated `paper.md`, a skip-decision, or the step being skipped entirely (because `paper.md` already existed) are all acceptable outcomes — none is a stopping point. Do not pause or report to the user until the full pipeline is complete.

### 3. Initial drafts from presentation-builder

Dispatch the `presentation-builder` agent via the Agent tool. Include:

- The absolute PDF path
- The `paper-extension/paper.md` path (if it exists)
- Paths to `summary.md` and (if applicable) `extensions.md`
- The **scope** option (full / summary only / extension only)
- The **format** option (revealjs / pptx / beamer)
- Instruction to write drafts to `paper-extension/presentation.qmd` and `paper-extension/writeup.qmd`

The preference-injection hook injects writing + structure + presentation preferences into the dispatch prompt automatically.

### 4. Compile and render screenshots

Compile both files based on format.

**Revealjs (default):**
```bash
quarto render paper-extension/presentation.qmd --to revealjs
quarto render paper-extension/writeup.qmd --to html
quarto render paper-extension/writeup.qmd --to pdf
```

**PowerPoint:**
```bash
quarto render paper-extension/presentation.qmd --to pptx
quarto render paper-extension/writeup.qmd --to html
quarto render paper-extension/writeup.qmd --to pdf
```

**PDF (Beamer):**
```bash
quarto render paper-extension/presentation.qmd --to beamer
quarto render paper-extension/writeup.qmd --to html
quarto render paper-extension/writeup.qmd --to pdf
```

If compilation fails, surface the error, have the builder fix the source, recompile. Do not proceed to review until both files compile.

Render per-slide screenshots:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/render-slides-to-png.sh \
    paper-extension/presentation.[html|pptx|pdf] \
    paper-extension/presentation-logs/screenshots/current
```

The script lives in this plugin (it's reviewer infrastructure, used by presentation-reviewer to rasterize slides for visual review).

### 5. Hand off to /CASM-tools:review-document

Build the cascade logs directory path using the current timestamp (24-hour PST, `YY-MM-DDTHH-MM`):

```
LOGS_DIR="paper-extension/presentation-logs/cascade-<YY-MM-DDTHH-MM>"
```

Invoke `CASM-tools:review-document` via the Skill tool with scope `all` on both artifacts and the `into <dir>` clause:

```
args: "all paper-extension/presentation.qmd paper-extension/writeup.qmd into paper-extension/presentation-logs/cascade-<YY-MM-DDTHH-MM>"
```

Passing both paths triggers consistency-reviewer automatically. The `all` scope includes factual, writing, structure, math, simplicity, adversarial, consistency, and presentation reviewers. All cascade artifacts land inside the named logs directory.

**Known limitation:** the cascade does not forward a screenshot directory to presentation-reviewer, so its cascade-internal review falls back to source-based review. Step 6 below addresses this with a post-cascade screenshot pass.

When the cascade's main session writes a revision, recompile and re-render screenshots at `paper-extension/presentation-logs/screenshots/current/` so the convention path always reflects the latest version.

### 6. Screenshot-based presentation review (post-cascade)

After `/CASM-tools:review-document` returns with an accepted version, dispatch `presentation-reviewer` manually via the Agent tool with the screenshot directory explicitly in the prompt. The preference-injection hook injects presentation style preferences automatically; you only need to provide inputs and task in the prompt.

```
Agent(
  subagent_type: "presentation-reviewer",
  description: "Screenshot review of final deck",
  prompt: "You are dispatched as the presentation-reviewer against paper-extension/presentation.qmd.

## Inputs
- Source: paper-extension/presentation.qmd
- Compiled: paper-extension/presentation.[html|pptx|pdf]
- Screenshots: paper-extension/presentation-logs/screenshots/current/

Read every PNG with the Read tool. Produce a scorecard at paper-extension/presentation-logs/screenshot-review.md."
)
```

Show the scorecard to the user. If CRITICAL or MAJOR issues were found, ask whether to:

- `accept` — keep the current deck, log as accepted
- `fix <numbers>` — hand back to `presentation-builder` for surgical fix, recompile, re-screenshot, re-run this step

This step is optional — the user can skip it if they don't need visual-grade review.

### 7. (Removed — no mirroring needed)

The cascade already writes into `paper-extension/presentation-logs/cascade-<timestamp>/`; meta-review reads directly from there.

### 8. Finalize

Recompile final accepted versions to ensure outputs are fresh. Report to the user with paths and final scores.

## Output

**Revealjs (default):** `presentation.qmd`, `presentation.html`, `writeup.qmd`, `writeup.html`, `writeup.pdf`
**PowerPoint:** `presentation.qmd`, `presentation.pptx`, `writeup.qmd`, `writeup.html`, `writeup.pdf`
**Beamer:** `presentation.qmd`, `presentation.pdf`, `writeup.qmd`, `writeup.html`, `writeup.pdf`

All formats also produce:

- `paper-extension/presentation-logs/` — scorecard mirrors, screenshot-review.md, `screenshots/current/`
- `paper-extension/session-logs/YYYY-MM-DD_present.md`

## Compilation Troubleshooting

- **YAML parse error**: Check for unquoted special characters in title/author fields
- **Unclosed div**: Ensure every `:::` has a matching close
- **LaTeX error (PDF/Beamer)**: Check equation syntax; escape special characters
- **Missing blank lines**: Quarto requires blank lines before/after fenced code blocks and div blocks
- **PPTX limitations**: No custom CSS, progressive opacity, or fine-grained layout control
- **Beamer limitations**: Beamer themes control styling; custom CSS does not apply
