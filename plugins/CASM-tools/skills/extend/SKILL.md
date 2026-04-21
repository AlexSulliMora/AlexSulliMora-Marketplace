---
name: extend
description: This skill should be used when the user asks to "extend this paper", "propose extensions", "suggest research extensions", "what extensions could be made", or wants ideas for extending a summarized paper. It generates research extension proposals via the extension-proposer agent, then hands the draft to /CASM-tools:review-document for the creator/reviewer quality loop.
argument-hint: "<path-to-paper.pdf>"
allowed-tools: ["Read", "Write", "Bash", "Grep", "Glob", "Agent", "Skill"]
---

# Extend Paper

Propose research extensions to a summarized paper. The initial candidate list and deep-dive come from the `extension-proposer` agent; the quality loop is delegated to `/CASM-tools:review-document`.

## Preference injection (automatic via preference-injection hook)

The CASM-tools plugin's `PreToolUse` hook intercepts the `extension-proposer` dispatch and prepends `writing-style.md` + `structure-style.md` preferences to the prompt. Dispatch the creator normally — the hook does the rest. The creator's body carries a fallback file-read pointer if the hook is disabled.

## Prerequisites

- A PDF file path must be provided as an argument
- A finalized summary must exist at `paper-extension/summary.md`
- If no summary exists, instruct the user to run `/CASM-tools:summarize` first

## Session Logging

1. **At start**: Create `paper-extension/session-logs/YYYY-MM-DD_extend.md` using the template from `${CLAUDE_PLUGIN_ROOT}/scripts/session-log-template.md`.
2. **After preprocess**: Record outcome.
3. **After initial draft**: Record that the extension-proposer produced v0.
4. **After paper requests**: Record which supplementary papers were requested, which the user provided.
5. **After /CASM-tools:review-document returns**: Record final scores, iteration count, checkpoint decision, cascade logs path.
6. **At end**: Update Status.

## Process

### 1. Verify inputs

Check the PDF and `paper-extension/summary.md` both exist. Create `paper-extension/extensions-logs/` if missing.

### 2. Preprocess paper (auto)

If `paper-extension/paper.md` already exists (from a prior summarize or preprocess run on this paper), **skip this step entirely** — do not invoke preprocess. The downstream extension-proposer will read the existing `paper.md` cache, and re-prompting the user about preprocessing would be redundant.

If `paper.md` does NOT exist, invoke `CASM-tools:preprocess` via the Skill tool. The preprocess skill self-short-circuits when a prior decision (generate or skip) is recorded against the current PDF's SHA256, so it will only prompt the user when there is genuinely no recorded choice yet. Proceed regardless of outcome.

### 3. Initial draft from extension-proposer

Dispatch the `extension-proposer` agent via the Agent tool. Include:

- The absolute PDF path
- The `paper-extension/paper.md` path (if it exists)
- The `paper-extension/summary.md` path
- Instruction to write the draft directly to `paper-extension/extensions.md`

The preference-injection hook injects writing + structure preferences into the dispatch prompt automatically.

### 4. Handle supplementary paper requests

The extension-proposer may pause to request supplementary papers. When it does:

- Present the list of requested papers with the agent's justifications
- Wait for the user to provide PDF paths
- Send supplementary PDFs back to the agent to continue
- It is acceptable if the user cannot provide all requested papers — the agent proceeds with what is available
- Log the request/response outcome in the session log

### 5. Hand off to /CASM-tools:review-document

Build the cascade logs directory path using the current timestamp (24-hour PST, `YY-MM-DDTHH-MM`):

```
LOGS_DIR="paper-extension/extensions-logs/extensions-<YY-MM-DDTHH-MM>"
```

Invoke `CASM-tools:review-document` via the Skill tool with scope `all` on `paper-extension/extensions.md` and the `into <dir>` clause:

```
args: "all paper-extension/extensions.md into paper-extension/extensions-logs/extensions-<YY-MM-DDTHH-MM>"
```

The cascade handles iteration via the `fixer` agent and installs the final version at `paper-extension/extensions.md` automatically (no interactive checkpoint). All cascade artifacts land inside the named logs directory.

### 6. (Removed — no mirroring needed)

The cascade already writes into the named logs directory; meta-review reads directly from there.

### 7. Finalize

Append to the session log: live extensions path, final cascade scores, accepted-item count, list of supplementary papers requested + provided.

Report to the user:

```
Extensions finalized: paper-extension/extensions.md
Cascade logs: paper-extension/extensions-logs/extensions-<timestamp>/
Final scores: [from cascade]
Accepted outstanding items: [count]
Supplementary papers requested: [N], provided: [M]
```

## Output

- `paper-extension/extensions.md`
- `paper-extension/extensions-logs/extensions-<timestamp>/` — full cascade trail (versions, reviewer-logs/, thorough/, extensions-final.md, extensions-combined-scorecard.md)
- `paper-extension/session-logs/YYYY-MM-DD_extend.md`

## Notes

- The extension-proposer uses Claude's training knowledge to identify related work. It does NOT search the web.
- Extensions should propose directions, not solve models or run regressions.
- For theoretical papers, focus on assumption relaxation that changes economic intuition — not complexity for its own sake.
- For empirical papers, focus on new settings, complementary papers, or mechanism tests.
