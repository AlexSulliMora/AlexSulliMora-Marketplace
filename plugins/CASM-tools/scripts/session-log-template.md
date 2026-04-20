# Session Log Template

Use this template when creating session logs for `/review-document` runs. Copy to `state/session-logs/YYYY-MM-DD_[artifact].md` (or to `[artifact-logs]/session-log.md` for long-running single-artifact reviews) and fill in the details. Update entries incrementally as they happen. Do not batch.

---

# Session Log — [artifact]

**Date:** [YYYY-MM-DD]
**Artifact:** [basename or path]
**Artifact kind:** [prose / code / slides / inline-materialized / other]
**Invocation:** [e.g. `/review-document the slides for writing only`]
**Scope:** [reviewers selected]
**Status:** [IN PROGRESS | COMPLETED | SUSPENDED | FAILED]

## Objective

[What this review is evaluating, 1-2 sentences]

## Iteration Log

[Update after each iteration. Do not batch. Write entries as they happen.]

### Tier [T] — Iteration [N]
- **Tier:** [1-5]
- **Timestamp:** [HH:MM UTC]
- **Reviewer scores:**
  - [Reviewer 1]: [score] ([PASS/FAIL])
  - [Reviewer 2]: [score] ([PASS/FAIL])
  - ...
- **Overall:** [PASS/FAIL]
- **Critical issues:** [list any CRITICAL severity items from reviewer reports, or "none"]
- **Key changes requested:** [brief summary of MAJOR feedback]

### Tier [T] — Iteration [N+1]
[Same format: add new sections as iterations proceed]

## User Review Checkpoints

[Update after each checkpoint. Do not batch. Write entries as they happen. Surgical fixes produce additional checkpoints; log every occurrence.]

### Checkpoint 1
- **Timestamp (opened):** [HH:MM UTC]
- **Timestamp (decided):** [HH:MM UTC, or "abandoned" if no decision within 48h]
- **Triggered by:** [auto-convergence at iteration N / iteration cap reached]
- **Scores at checkpoint:** [per-reviewer composite scores]
- **Items presented:** [count of MAJOR + MINOR items]
- **User decision:** [`accept` / `use <N>` / `keep original` / `fix 1,3,7` / sequence of `show` commands before deciding / `abandoned`]
- **Action:** [proceeded to Finalize / started surgical fix iteration v[N+1] / suspended]
- **Accepted items recorded to:** [path to accepted-issues.md, if accepted]
- **Installed version:** [v[N] copied to live file, or "none (keep original)"]

### Checkpoint N
[Same format: one entry per checkpoint presentation]

## Design Decisions

[Record non-obvious choices made during this review]

| Decision | Alternatives considered | Reasoning |
|---|---|---|
| [what was chosen] | [what else was considered] | [why this choice] |

## Learnings

[Tag each learning for searchability. Only record things that are surprising or non-obvious.]

- `[LEARN:reviewer]` [something learned about a specific reviewer's rubric]
- `[LEARN:process]` [something learned about the review process]
- `[LEARN:artifact]` [something non-obvious about this specific artifact]
- `[LEARN:tool]` [something about Quarto, Python, compilation, etc.]

## Verification Results

| Check | Result | Status |
|---|---|---|
| Artifact readable | [yes/no] | [PASS/FAIL] |
| Lockfile acquired cleanly | [yes/no] | [PASS/FAIL] |
| All reviewers returned parseable scorecards | [details] | [PASS/FAIL] |
| All reviewers >= 90 | [details] | [PASS/FAIL] |
| Auto-apply converged | [yes/no; rounds used] | [PASS/FAIL] |
| Thorough audit run (if requested) | [yes/no / n/a] | [PASS/FAIL / n/a] |
| User checkpoint accepted | [details; count of accepted items] | [PASS/FAIL] |

## Open Questions

- [ ] [question or unresolved issue]

## Next Steps

- [ ] [what should happen next]

## Output Files

[List all files produced by this review]

- [path]: [description]
