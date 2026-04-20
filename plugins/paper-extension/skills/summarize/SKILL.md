---
name: summarize
description: This skill should be used when the user asks to "summarize a paper", "read and summarize", "summarize this PDF", "analyze this paper", "what does this paper say", "break down this paper", or provides a PDF path and wants a structured summary. It reads an academic economics paper, produces a structured draft via the paper-summarizer agent, and then hands the draft to /deep-review:review-document for the creator/reviewer quality loop.
argument-hint: <path-to-paper.pdf>
allowed-tools: ["Read", "Write", "Bash", "Grep", "Glob", "Agent", "Skill"]
---

# Summarize Paper

Read an academic paper from a PDF and produce a structured summary. The initial draft comes from the `paper-summarizer` agent; the quality loop is delegated to the `/deep-review:review-document` cascade.

## Preference injection (automatic via deep-review hook)

The deep-review plugin registers a `PreToolUse` hook that intercepts Agent dispatches to known creator agents (`paper-summarizer`, `extension-proposer`, `presentation-builder`) and prepends the relevant style preferences from `~/.claude/plugins/.../deep-review/preferences/` to the dispatch prompt. `paper-summarizer` receives `writing-style.md` + `structure-style.md` automatically, so the creator drafts against the same rules the review cascade scores against.

Dispatch the creator normally — the hook does the rest. The creator agent's body also carries a fallback "read preferences file directly if not injected" pointer for the case where deep-review is not installed or the hook is disabled.

## Prerequisites

- A PDF file path must be provided as an argument
- If no path is provided, prompt the user for one

## Session Logging

Maintain a lightweight session log for pipeline-level tracking (not iteration-level — that's what `/deep-review:review-document` logs):

1. **At start**: Create `paper-extension/session-logs/YYYY-MM-DD_summarize.md` using the template from `~/.claude/plugins/deep-review/scripts/session-log-template.md`.
2. **After preprocess**: Record outcome (cache-hit / regenerated / fallback).
3. **After initial draft**: Record that the paper-summarizer produced v0.
4. **After /deep-review:review-document returns**: Record final scores, iteration count, user checkpoint decision, cascade logs path.
5. **At end**: Update Status to COMPLETED or FAILED.

## Process

### 1. Setup output directory

If the PDF is at `Paper/paper.pdf`, create:

```
Paper/paper-extension/
Paper/paper-extension/summary-logs/
Paper/paper-extension/session-logs/
```

If `paper-extension/summary.md` already exists, confirm with the user before overwriting.

### 2. Preprocess paper (auto)

Invoke the `paper-extension:preprocess` skill via the Skill tool, passing the absolute PDF path. Idempotent — short-circuits on a fresh cache. Proceed regardless of outcome.

### 3. Initial draft from paper-summarizer

Dispatch the `paper-summarizer` agent via the Agent tool. Include in the dispatch prompt:

- The absolute PDF path
- The `paper-extension/paper.md` path (if it exists) as the preferred source
- Instruction to write the draft directly to `paper-extension/summary.md`

The deep-review hook injects `writing-style.md` and `structure-style.md` preferences into the dispatch prompt automatically.

The paper-summarizer writes v0 of the summary to the canonical live location. `/deep-review:review-document` will snapshot this as its v1 baseline.

### 4. Hand off to /deep-review:review-document

Invoke the `deep-review:review-document` skill via the Skill tool with scope `all` on `paper-extension/summary.md`:

```
args: "all paper-extension/summary.md"
```

The `all` scope enables factual-reviewer (not auto-selected) alongside writing, structure, math, simplicity, adversarial reviewers. The cascade handles iteration, User Review Checkpoint, and installing the accepted version at `paper-extension/summary.md`.

Record the cascade's logs directory path in the session log.

### 5. Mirror cascade artifacts for meta-review

After the cascade returns, mirror its key artifacts into `paper-extension/summary-logs/`:

```bash
CASCADE_DIR="docs/reviews/summary-<timestamp>"   # resolved from announcement
cp "$CASCADE_DIR/combined-scorecard.md" paper-extension/summary-logs/summary-scorecard.md 2>/dev/null || true
cp "$CASCADE_DIR/accepted-issues.md"    paper-extension/summary-logs/accepted-issues.md   2>/dev/null || true
```

### 6. Finalize

Append to the session log: live summary path, final cascade scores, number of accepted outstanding items, whether cascade auto-converged or was accepted at the iteration cap.

Report to the user:

```
Summary finalized: paper-extension/summary.md
Cascade logs: docs/reviews/summary-<timestamp>/
Final scores: [from cascade]
Accepted outstanding items: [count]
```

## Output

- `paper-extension/summary.md` — the finalized summary
- `paper-extension/summary-logs/summary-scorecard.md` — cascade scorecard mirror
- `paper-extension/summary-logs/accepted-issues.md` — cascade accepted-issues mirror
- `paper-extension/session-logs/YYYY-MM-DD_summarize.md` — pipeline-level log
- `docs/reviews/summary-<timestamp>/` — full cascade iteration trail

## Error handling

- If the PDF cannot be read, report the error and stop
- If the paper-summarizer fails to produce a draft, report and stop (do not call the cascade on an empty file)
- If the cascade returns an error, surface it and stop

## Notes

- The paper-summarizer agent receives writing + structure preferences in its prompt, so its initial draft is aligned with what the cascade scores against. Its own agent body carries a fallback "read preferences if not provided" instruction for when it is dispatched directly.
- Revisions during the cascade are written by the main session, not by paper-summarizer. The summarizer only produces v0.
