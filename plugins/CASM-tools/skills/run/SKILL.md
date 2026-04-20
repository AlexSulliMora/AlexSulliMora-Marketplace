---
name: run
description: This skill should be used when the user asks to "run the full paper pipeline", "analyze and extend this paper", "do everything for this paper", or wants to execute all three stages (summarize, extend, present) end-to-end on an academic paper PDF with minimal manual intervention.
argument-hint: "<path-to-paper.pdf> [summary only | extension only] [ppt | pdf]"
allowed-tools: ["Read", "Write", "Bash", "Grep", "Glob", "Agent", "Skill"]
---

# Run Full Paper Pipeline

Execute the complete paper analysis pipeline: preprocess, summarize, extend, and present. Each stage invokes the corresponding `CASM-tools:*` skill, which delegates its review loop to `/CASM-tools:review-document`.

## Prerequisites

- A PDF file path must be provided as an argument
- Quarto must be installed on PATH (for the present stage)
- Optional: `marker-pdf` for preprocessing, `pdftoppm`/`decktape`/`libreoffice` for screenshot rendering

## Argument Parsing

Pass through to `CASM-tools:present`:
- `summary only` / `extension only` → presentation scope
- `ppt` / `pdf` → presentation format

If `summary only` is specified, the extend stage is skipped.

## Session Logging

Maintain a single pipeline-level session log:

1. **At start**: Create `paper-extension/session-logs/YYYY-MM-DD_full-pipeline.md` using `${CLAUDE_PLUGIN_ROOT}/scripts/session-log-template.md`.
2. **After each stage**: Update the Pipeline Progress table with stage status, final scores, cascade logs path.
3. **After paper requests**: Record papers requested during extend and which were provided.
4. **At end**: Update Status, Verification Results, Learnings.

Per-stage skills maintain their own stage-level logs. The pipeline-level log is the top-of-tree rollup; it should point at the per-stage logs, not duplicate them.

## Process

### 1. Setup

Verify the PDF exists. Create the output directory structure:

```
paper-extension/
paper-extension/preprocess-logs/
paper-extension/summary-logs/
paper-extension/extensions-logs/
paper-extension/presentation-logs/
paper-extension/writeup-logs/
paper-extension/session-logs/
```

Announce:

> Starting full pipeline for [paper name]. Four stages: preprocess, summarize, extend, present. Each review stage hands its draft to `/CASM-tools:review-document`, which presents its own User Review Checkpoint. You will see three checkpoints total. I will also pause if the extension-proposer requests supplementary papers.

### 2. Stage 0: Preprocess (auto)

Invoke `CASM-tools:preprocess` via the Skill tool. Record outcome (success / cache-hit / fallback) in the pipeline log.

### 3. Stage 1: Summarize

Invoke `CASM-tools:summarize` via the Skill tool. Wait for it to return (includes its delegation to `/CASM-tools:review-document` and the cascade's User Review Checkpoint).

After return, read the final state from `paper-extension/session-logs/YYYY-MM-DD_summarize.md` and `paper-extension/summary-logs/summary-scorecard.md`. Report final scores, convergence, and accepted-item count.

### 4. Stage 2: Extend (skipped if scope = summary only)

If scope is `summary only`, skip to Stage 3.

Otherwise, invoke `CASM-tools:extend` via the Skill tool. If the extension-proposer pauses for supplementary paper requests, the extend skill handles the user interaction. Report final state.

### 5. Stage 3: Present

Invoke `CASM-tools:present` via the Skill tool, passing through the scope and format options from `/CASM-tools:run`. Report final state.

### 6. Final Report

```markdown
# Pipeline Complete: [Paper Title]

## Stage Results
| Stage | Cascade Logs | Final Scores | Outstanding Items | Status |
|---|---|---|---|---|
| Preprocess | — | N/A | — | [SUCCESS/FALLBACK/CACHE-HIT] |
| Summarize | docs/reviews/summary-<ts>/ | [scores] | [count] | [CONVERGED/CAP-ACCEPTED] |
| Extend    | docs/reviews/extensions-<ts>/ | [scores] | [count] | [CONVERGED/CAP-ACCEPTED/SKIPPED] |
| Present   | docs/reviews/presentation-<ts>/ | [scores] | [count] | [CONVERGED/CAP-ACCEPTED] |

## Live Outputs
- `paper-extension/paper.md` (when preprocess succeeded)
- `paper-extension/summary.md`
- `paper-extension/extensions.md` (unless scope = summary only)
- `paper-extension/presentation.qmd` → compiled [html/pptx/pdf]
- `paper-extension/writeup.qmd` → `writeup.html` + `writeup.pdf`

## Warnings
[Any stages that hit the iteration cap, any reviewers that did not pass]
```

## User Interaction Points

1. **Supplementary paper requests** (stage 2 only): the extension-proposer pauses with a list. Provide PDFs or tell the agent to proceed without them.
2. **Three User Review Checkpoints** — one at the end of each review stage. At each, choose `accept`, `use <N>`, `keep original`, `fix <numbers>`, or `show <number>`. A stage does not finalize until the user decides.

If a stage hits the cascade's iteration cap, the checkpoint still fires with the best-available version.

## Notes

- Each cascade logs its full iteration trail under `docs/reviews/<artifact>-<timestamp>/`. The per-stage skills mirror the final combined scorecard and accepted-issues into `paper-extension/<stage>-logs/` so `/CASM-tools:meta-review` can find them.
- The pipeline is not resumable mid-stage, but each stage's output is durable. If interrupted after summarize, resume with `/CASM-tools:extend <pdf>` directly.
