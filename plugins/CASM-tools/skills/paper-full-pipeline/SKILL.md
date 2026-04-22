---
name: paper-full-pipeline
description: This skill should be used when the user asks to "run the full paper pipeline", "analyze and extend this paper", "do everything for this paper", or wants to execute all three stages (paper-summarize, paper-extend, paper-present) end-to-end on an academic paper PDF with minimal manual intervention.
argument-hint: "<path-to-paper.pdf> [summary only | extension only] [ppt | pdf]"
allowed-tools: ["Read", "Write", "Bash", "Grep", "Glob", "Agent", "Skill"]
---

# Run Full Paper Pipeline

Execute the complete paper analysis pipeline: paper-preprocess, paper-summarize, paper-extend, and paper-present. Each stage invokes the corresponding `CASM-tools:*` skill, which delegates its review loop to `/CASM-tools:review-document`.

## Prerequisites

- A PDF file path must be provided as an argument
- Quarto must be installed on PATH (for the present stage)
- Optional: `marker-pdf` for preprocessing, `pdftoppm`/`decktape`/`libreoffice` for screenshot rendering

## Argument Parsing

Pass through to `CASM-tools:paper-present`:
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
paper-extension/paper-summary-logs/
paper-extension/extensions-logs/
paper-extension/presentation-logs/
paper-extension/writeup-logs/
paper-extension/session-logs/
```

Announce:

> Starting full pipeline for [paper name]. Four stages: paper-preprocess, paper-summarize, paper-extend, paper-present. Each review stage hands its draft to `/CASM-tools:review-document`, which runs the cascade and installs the final version automatically. The adversarial reviewer runs in advisory mode across all three review stages, so its research-level concerns stay visible in the scorecard without blocking convergence. The review cascades themselves are non-interactive, but the extend stage pauses once at a candidate checkpoint so the researcher can steer direction before the agent commits deep-dive effort. I will pause only if: (a) preprocess needs the up-front generate-markdown-or-skip choice, (b) the extend stage reaches its candidate checkpoint (accept / pick / revise), (c) the extension-proposer requests supplementary papers during the deep-dive phase, or (d) a non-advisory reviewer hits the iteration cap with CRITICAL items unresolved.

### 2. Stage 0: Preprocess (auto)

Invoke `CASM-tools:paper-preprocess` via the Skill tool. The preprocess skill will prompt the user once to choose whether to convert the PDF to markdown (reduces downstream token usage; ~10–20 min on CPU, requires `marker_single` from `pip install marker-pdf`) or skip and let agents read the PDF directly. Record outcome (markdown generated / user declined / cache-hit / fallback) in the pipeline log.

**The user will only be prompted here, not again in stages 1–3.** Either outcome produces a durable per-SHA decision:

- `Generate markdown` → writes `paper-extension/paper.md` with `source_sha256` frontmatter.
- `Skip, read PDF directly` → writes `paper-extension/.preprocess-declined` containing the current SHA256.

Later invocations of paper-preprocess (directly or via paper-summarize/paper-extend/paper-present) detect either marker and silently short-circuit on the same PDF. Stages 2 and 3 (`paper-extend`, `paper-present`) additionally skip the paper-preprocess call entirely when `paper.md` already exists. The prompt only re-fires if the source PDF itself changes (new SHA256).

### 3. Stage 1: Summarize

Invoke `CASM-tools:paper-summarize` via the Skill tool. Wait for it to return (includes its delegation to `/CASM-tools:review-document` and automatic finalization).

After return, read the final state from `paper-extension/session-logs/YYYY-MM-DD_summarize.md` and the combined scorecard inside `paper-extension/paper-summary-logs/paper-summary-<ts>/paper-summary-combined-scorecard.md`. Report final scores, convergence, and any unresolved-item count.

### 4. Stage 2: Extend (skipped if scope = summary only)

If scope is `summary only`, skip to Stage 3.

Otherwise, invoke `CASM-tools:paper-extend` via the Skill tool. If the extension-proposer pauses for supplementary paper requests, the extend skill handles the user interaction. Report final state.

### 5. Stage 3: Present

Invoke `CASM-tools:paper-present` via the Skill tool, passing through the scope and format options from `/CASM-tools:paper-full-pipeline`. Report final state.

### 6. Final Report

```markdown
# Pipeline Complete: [Paper Title]

## Stage Results
| Stage | Cascade Logs | Final Scores | Unresolved Items | Status |
|---|---|---|---|---|
| Preprocess | — | N/A | — | [GENERATED/DECLINED/CACHE-HIT/FALLBACK] |
| Summarize | paper-extension/paper-summary-logs/paper-summary-<ts>/ | [scores] | [count] | [CONVERGED/CAP-HIT] |
| Extend    | paper-extension/extensions-logs/extensions-<ts>/ | [scores] | [count] | [CONVERGED/CAP-HIT/SKIPPED] |
| Present   | paper-extension/presentation-logs/cascade-<ts>/ | [scores] | [count] | [CONVERGED/CAP-HIT] |

## Live Outputs
- `paper-extension/paper.md` (when preprocess succeeded)
- `paper-extension/paper-summary.md`
- `paper-extension/extensions.md` (unless scope = summary only)
- `paper-extension/presentation.qmd` → compiled [html/pptx/pdf]
- `paper-extension/writeup.qmd` → `writeup.html` + `writeup.pdf`

## Warnings
[Any stages that hit the iteration cap, any reviewers that did not pass]
```

## User Interaction Points

The pipeline is designed to run end-to-end without prompting. The only interactions:

1. **Preprocess choice** (stage 0, at most once): generate markdown via `marker_single` or skip. Decision is durable per-SHA, so stages 1–3 do not re-prompt.
2. **Candidate checkpoint** (stage 2, always): the extend stage pauses after generating candidate extensions and ranking, before producing the deep dive. The researcher can accept the agent's top-ranked candidate, pick a different one, or request a revised candidate list. Revise rounds are uncapped. This checkpoint exists because the deep dive commits substantial write-up effort to a single direction; letting the agent pick unilaterally risks finalizing a write-up the researcher would have redirected.
3. **Supplementary paper requests** (stage 2 deep-dive phase only): after the candidate is chosen, the extension-proposer may pause with a list of papers it wants, scoped to the chosen direction. Provide PDFs or tell the agent to proceed without them.
4. **CRITICAL escalation** (error path): if the cascade hits its iteration cap with CRITICAL items unresolved on a **gating** reviewer, `/CASM-tools:review-document` blocks with continue/suspend/fix-manually. Because the adversarial reviewer runs in advisory mode for all three review stages, adversarial CRITICALs never trigger this path — the cascade finalizes and the adversarial findings appear in the combined scorecard tagged `(advisory)` for later review. This escalation only fires when writing, structure, math, simplicity, factual, consistency, code, or presentation reviewers cannot be driven to zero CRITICAL within the iteration cap, which does not happen on routine runs.

No interactive checkpoints at the end of each review stage. Each cascade installs its final version automatically. If the user wants a different version, they copy it from the cascade's logs directory manually.

## Notes

- Each cascade writes its logs directly into `paper-extension/<stage>-logs/<stage>-<timestamp>/` (via the `into <dir>` token). No mirroring step. `/CASM-tools:meta-review` reads from those locations.
- The pipeline is not resumable mid-stage, but each stage's output is durable. If interrupted after paper-summarize, resume with `/CASM-tools:paper-extend <pdf>` directly.
