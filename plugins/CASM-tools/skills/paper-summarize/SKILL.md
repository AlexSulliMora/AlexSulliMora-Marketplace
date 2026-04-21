---
name: paper-summarize
description: This skill should be used when the user asks to "summarize a paper", "read and summarize", "summarize this PDF", "analyze this paper", "what does this paper say", "break down this paper", or provides a PDF path and wants a structured summary. It reads an academic economics paper, produces a structured draft via the paper-summarizer agent, and then hands the draft to /CASM-tools:review-document for the creator/reviewer quality loop.
argument-hint: "<path-to-paper.pdf>"
allowed-tools: ["Read", "Write", "Bash", "Grep", "Glob", "Agent", "Skill"]
---

# Summarize Paper

Read an academic paper from a PDF and produce a structured summary. The initial draft comes from the `paper-summarizer` agent; the quality loop is delegated to the `/CASM-tools:review-document` cascade.

## Preference injection (automatic via preference-injection hook)

The paper-summarizer's style preferences are injected automatically by the plugin's PreToolUse hook before the subagent spawns. This ensures the creator drafts against the same rules the review cascade scores against.

> **Dispatch exactly the task. Do not add preferences.**
> The hook prepends the relevant style preferences to the paper-summarizer's prompt automatically.
> If you include preference content manually, the agent receives it twice.
> If the hook is disabled, the agent's body carries a fallback "read preferences if not injected" pointer — the agent handles recovery, not the orchestrator.

## Prerequisites

- A PDF file path must be provided as an argument
- If no path is provided, prompt the user for one

## Session Logging

Maintain a lightweight session log for pipeline-level tracking (not iteration-level — that's what `/CASM-tools:review-document` logs):

1. **At start**: Create `paper-extension/session-logs/YYYY-MM-DD_summarize.md` using the template from `${CLAUDE_PLUGIN_ROOT}/scripts/session-log-template.md`.
2. **After preprocess**: Record outcome (cache-hit / regenerated / fallback).
3. **After initial draft**: Record that the paper-summarizer produced v0.
4. **After /CASM-tools:review-document returns**: Record final scores, iteration count, user checkpoint decision, cascade logs path.
5. **At end**: Update Status to COMPLETED or FAILED.

## Process

### 1. Setup output directory

If the PDF is at `Paper/paper.pdf`, create:

```
Paper/paper-extension/
Paper/paper-extension/paper-summary-logs/
Paper/paper-extension/session-logs/
```

If `paper-extension/paper-summary.md` already exists, confirm with the user before overwriting.

### 2. Preprocess paper (auto)

Invoke the `CASM-tools:paper-preprocess` skill via the Skill tool, passing the absolute PDF path. The preprocess skill will ask the user whether to generate a markdown cache (reduces LLM token usage but takes 10–20 min on CPU) or skip straight to PDF reading. Either answer is acceptable — `paper-summarizer` falls back to the PDF when `paper.md` is absent.

**When preprocess returns, continue immediately to step 3.** A cache hit, a freshly generated `paper.md`, or a skip-decision are all acceptable outcomes — none is a stopping point. Do not pause or report to the user until the full pipeline is complete.

### 3. Initial draft from paper-summarizer

Dispatch the `paper-summarizer` agent via the Agent tool. Include in the dispatch prompt:

- The absolute PDF path
- The `paper-extension/paper.md` path (if it exists) as the preferred source
- Instruction to write the draft directly to `paper-extension/paper-summary.md`

The preference-injection hook injects writing and structure style preferences into the dispatch prompt automatically.

The paper-summarizer writes v0 of the summary to the canonical live location. `/CASM-tools:review-document` will snapshot this as its v1 baseline.

### 4. Hand off to /CASM-tools:review-document

Build the cascade logs directory path using the current timestamp (24-hour PST, `YY-MM-DDTHH-MM`):

```
LOGS_DIR="paper-extension/paper-summary-logs/paper-summary-<YY-MM-DDTHH-MM>"
```

Invoke the `CASM-tools:review-document` skill via the Skill tool with scope `all` on `paper-extension/paper-summary.md` and the `into <dir>` clause pointing at that directory:

```
args: "all paper-extension/paper-summary.md into paper-extension/paper-summary-logs/paper-summary-<YY-MM-DDTHH-MM>"
```

The `all` scope enables factual-reviewer (not auto-selected) alongside writing, structure, math, simplicity, adversarial reviewers. The cascade handles iteration via the `fixer` agent and installs the final version at `paper-extension/paper-summary.md` automatically (no interactive checkpoint). All cascade artifacts — versions, `reviewer-logs/`, `thorough/`, `paper-summary-final.md`, `paper-summary-combined-scorecard.md` — land inside the named logs directory.

Record the cascade's logs directory path in the session log.

### 5. (Removed — no mirroring needed)

Because the cascade already writes into `paper-extension/paper-summary-logs/paper-summary-<timestamp>/`, no copy step is required. The meta-review skill reads directly from that location.

### 6. Finalize

Append to the session log: live summary path, final cascade scores, number of accepted outstanding items, whether cascade auto-converged or was accepted at the iteration cap.

Report to the user:

```
Summary finalized: paper-extension/paper-summary.md
Cascade logs: paper-extension/paper-summary-logs/paper-summary-<timestamp>/
Final scores: [from cascade]
Accepted outstanding items: [count]
```

## Output

- `paper-extension/paper-summary.md` — the finalized summary
- `paper-extension/paper-summary-logs/paper-summary-<timestamp>/` — full cascade trail (versions, reviewer-logs/, thorough/, paper-summary-final.md, paper-summary-combined-scorecard.md)
- `paper-extension/session-logs/YYYY-MM-DD_summarize.md` — pipeline-level log

## Error handling

- If the PDF cannot be read, report the error and stop
- If the paper-summarizer fails to produce a draft, report and stop (do not call the cascade on an empty file)
- If the cascade returns an error, surface it and stop

## Notes

- The paper-summarizer agent receives writing + structure preferences in its prompt, so its initial draft is aligned with what the cascade scores against. Its own agent body carries a fallback "read preferences if not provided" instruction for when it is dispatched directly.
- Revisions during the cascade are written by the main session, not by paper-summarizer. The summarizer only produces v0.
