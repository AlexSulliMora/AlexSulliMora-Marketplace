---
name: paper-extend
description: This skill should be used when the user asks to "extend this paper", "propose extensions", "suggest research extensions", "what extensions could be made", or wants ideas for extending a summarized paper. It generates candidate extensions via the extension-proposer agent, pauses for the researcher to pick a direction, then produces the deep dive and hands it to /CASM-tools:review-document for the creator/reviewer quality loop.
argument-hint: "<path-to-paper.pdf>"
allowed-tools: ["Read", "Write", "Bash", "Grep", "Glob", "Agent", "Skill", "AskUserQuestion"]
---

# Extend Paper

Propose research extensions to a summarized paper. The `extension-proposer` agent runs in two phases with a user checkpoint in between: first it generates candidates and ranking, then the researcher picks the direction, then the agent writes the deep dive on the chosen candidate. The quality loop is delegated to `/CASM-tools:review-document`. The checkpoint prevents the agent from committing a full write-up to the wrong candidate — the researcher's taste, data access, and follow-on plans often push away from the agent's top pick.

## Preference injection (automatic via preference-injection hook)

The extension-proposer's style preferences are injected automatically by the plugin's PreToolUse hook before the subagent spawns.

> **Dispatch exactly the task. Do not add preferences.**
> The hook prepends the relevant style preferences automatically.
> If you include preference content manually, the agent receives it twice.
> If the hook is disabled, the agent's body carries a fallback pointer — the agent handles recovery, not the orchestrator.

## Prerequisites

- A PDF file path must be provided as an argument
- A finalized summary must exist at `paper-extension/paper-summary.md`
- If no summary exists, instruct the user to run `/CASM-tools:paper-summarize` first

## Session Logging

1. **At start**: Create `paper-extension/session-logs/YYYY-MM-DD_extend.md` using the template from `${CLAUDE_PLUGIN_ROOT}/scripts/session-log-template.md`.
2. **After preprocess**: Record outcome.
3. **After candidates phase**: Record that the extension-proposer produced the preliminary candidate list, how many candidates, and the agent's top-ranked pick.
4. **At each checkpoint interaction**: Record the user's decision (accept top / pick #N / revise with instruction) and the round number. The revise loop is uncapped, so this entry may appear multiple times.
5. **After deep-dive phase**: Record which candidate was chosen (index + title), how it was chosen (top pick, user override, post-revise), and that the extension-proposer produced v0 of the final extensions file.
6. **After paper requests**: Record which supplementary papers were requested, which the user provided.
7. **After /CASM-tools:review-document returns**: Record final scores, iteration count, cascade logs path.
8. **At end**: Update Status.

## Process

### 1. Verify inputs

Check the PDF and `paper-extension/paper-summary.md` both exist. Create `paper-extension/extensions-logs/` if missing.

### 2. Preprocess paper (auto)

If `paper-extension/paper.md` already exists (from a prior summarize or preprocess run on this paper), **skip this step entirely** — do not invoke preprocess. The downstream extension-proposer will read the existing `paper.md` cache, and re-prompting the user about preprocessing would be redundant.

If `paper.md` does NOT exist, invoke `CASM-tools:paper-preprocess` via the Skill tool. The paper-preprocess skill self-short-circuits when a prior decision (generate or skip) is recorded against the current PDF's SHA256, so it will only prompt the user when there is genuinely no recorded choice yet.

**When preprocess returns, continue immediately to step 3.** A cache hit, a freshly generated `paper.md`, a skip-decision, or the step being skipped entirely (because `paper.md` already existed) are all acceptable outcomes — none is a stopping point. Do not pause or report to the user until the full pipeline is complete.

### 3. Candidate generation (phase: candidates)

Dispatch the `extension-proposer` agent via the Agent tool with `phase: candidates`. Include in the dispatch prompt:

- `phase: candidates`
- The absolute PDF path
- The `paper-extension/paper.md` path (if it exists)
- The `paper-extension/paper-summary.md` path
- Instruction to write the preliminary artifact directly to `paper-extension/extensions-candidates.md` and to produce candidates + ranking only, no deep dive, no supplementary-paper requests yet

The preference-injection hook injects writing + structure preferences into the dispatch prompt automatically.

When the agent returns, read `paper-extension/extensions-candidates.md` and continue to the checkpoint.

### 4. Candidate checkpoint

Present the candidates and ranking to the user with a blocking prompt via `AskUserQuestion` (falling back to a numbered-options message when the platform question tool is not available). The prompt enumerates each candidate with its title and the agent's ranking position, and offers three response options:

- **Accept top pick** — proceed to the deep dive on the agent's #1 candidate.
- **Pick a different candidate** — the user names a candidate by index or title.
- **Revise** — the user supplies a free-form instruction (e.g., "drop #2, add one about unemployment risk sharing", "regenerate with stronger focus on empirical identification"). The skill re-dispatches `extension-proposer` with `phase: candidates-revise`, the revise instruction, and the path to the existing `paper-extension/extensions-candidates.md`. The agent writes a fresh candidates file replacing the old one; the skill then re-enters this checkpoint.

The revise loop is uncapped: the researcher can iterate as many rounds as they need. Each round records an entry in the session log. The user can cancel the whole skill run by ending the conversation or signaling stop; do not invent a timeout or silent auto-accept.

`AskUserQuestion` is used whether the skill was invoked directly or through `/CASM-tools:paper-full-pipeline`. This checkpoint is the fourth expected interaction point in the full-pipeline flow; the pipeline skill's narrative reflects that.

When the user accepts a candidate (top or user-chosen), record the chosen index + title in the session log and continue to step 5.

### 5. Deep dive (phase: deep-dive)

Dispatch the `extension-proposer` agent again via the Agent tool with `phase: deep-dive`. Include in the dispatch prompt:

- `phase: deep-dive`
- The chosen candidate: index + title, and whether it was the agent's top pick, a user override, or selected after N revise rounds
- The absolute PDF path
- The `paper-extension/paper.md` path (if it exists)
- The `paper-extension/paper-summary.md` path
- The `paper-extension/extensions-candidates.md` path (the agent reads candidates + ranking from here and copies them into the final file)
- Instruction to write the final artifact to `paper-extension/extensions.md` combining candidates + ranking + deep dive + optional requested-papers section

The agent may pause during this phase to request supplementary papers scoped to the chosen direction. Handle the request as before:

- Present the list with the agent's justifications
- Wait for the user to provide PDF paths
- Send supplementary PDFs back to the agent to continue
- It is acceptable if the user cannot provide all requested papers — the agent proceeds with what is available
- Log the request/response outcome in the session log

When the agent returns, `paper-extension/extensions.md` exists with the full draft and the cascade can begin.

### 6. Hand off to /CASM-tools:review-document

Build the cascade logs directory path using the current timestamp (24-hour PST, `YY-MM-DDTHH-MM`):

```
LOGS_DIR="paper-extension/extensions-logs/extensions-<YY-MM-DDTHH-MM>"
```

Invoke `CASM-tools:review-document` via the Skill tool with scope `all`, the `advisory adversarial` clause, and the `into <dir>` clause:

```
args: "all advisory adversarial paper-extension/extensions.md into paper-extension/extensions-logs/extensions-<YY-MM-DDTHH-MM>"
```

The `advisory adversarial` clause marks the adversarial reviewer as non-gating. Its scorecard still merges into the per-iteration aggregate so the fixer applies any mechanically addressable items, but its pass/fail status does not gate convergence. Research extension proposals in particular attract adversarial CRITICALs that are speculative or cannot be resolved without new evidence; letting them gate convergence would stall finalization on issues the fixer cannot close. The cascade handles iteration via the `fixer` agent and installs the final version at `paper-extension/extensions.md` automatically (no interactive checkpoint). All cascade artifacts land inside the named logs directory, with adversarial findings tagged `(advisory)` in the combined scorecard for later review.

### 7. (Removed — no mirroring needed)

The cascade already writes into the named logs directory; meta-review reads directly from there.

### 8. Finalize

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

- `paper-extension/extensions-candidates.md` — preliminary candidate list + ranking (the artifact the checkpoint reads from). Overwritten on each revise round.
- `paper-extension/extensions.md` — final candidates + ranking + deep dive, produced after the candidate is chosen and fed to the review cascade.
- `paper-extension/extensions-logs/extensions-<timestamp>/` — full cascade trail (versions, reviewer-logs/, thorough/, extensions-final.md, extensions-combined-scorecard.md).
- `paper-extension/session-logs/YYYY-MM-DD_extend.md` — pipeline-level log including the checkpoint decision trail.

## Notes

- The extension-proposer uses Claude's training knowledge to identify related work. It does NOT search the web.
- Extensions should propose directions, not solve models or run regressions.
- The candidate checkpoint (step 4) is the feature's value: it prevents the agent from spending deep-dive effort on a direction that doesn't fit the researcher's taste, data access, or follow-on plans. The revise loop is uncapped for the same reason — iterating on candidates is cheap, iterating on a finished deep dive is not.
- Supplementary-paper requests happen in the deep-dive phase only, scoped to the chosen candidate. This is a change from the pre-checkpoint flow, where the agent could request papers against every candidate.
- For theoretical papers, focus on assumption relaxation that changes economic intuition — not complexity for its own sake.
- For empirical papers, focus on new settings, complementary papers, or mechanism tests.
- The adversarial reviewer runs in advisory mode by default in this pipeline. Its findings remain visible in the combined scorecard but do not gate convergence. Advanced users who want adversarial to gate convergence can invoke `/CASM-tools:review-document all paper-extension/extensions.md` directly without the `advisory adversarial` clause.
