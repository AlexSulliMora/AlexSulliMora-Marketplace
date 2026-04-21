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

### Iteration [N]
- **Timestamp:** [HH:MM UTC]
- **Reviewer scores:**
  - [Reviewer 1]: [score] ([PASS/FAIL])
  - [Reviewer 2]: [score] ([PASS/FAIL])
  - ...
- **Overall:** [PASS/FAIL]
- **Critical issues:** [list any CRITICAL severity items from reviewer reports, or "none"]
- **Key changes requested:** [brief summary of MAJOR feedback]

### Iteration [N+1]
[Same format: add new sections as iterations proceed]

### Convergence cleanup
- **Timestamp:** [HH:MM UTC]
- **Items applied:** [count of MAJOR/MINOR items applied, or "skipped — no outstanding items"]

## Finalization

- **Timestamp:** [HH:MM UTC when the cascade installed the final version]
- **Final version:** [v[N] copied to live file]
- **Final file:** [path to `<artifact>-final.md`]
- **Combined scorecard:** [path to `<artifact>-combined-scorecard.md`]
- **Final composite scores:** [per-reviewer composite at cascade end]
- **Cascade converged:** [YES / NO — if NO, note that the iteration cap was hit]
- **Thorough audit run:** [yes/no; if yes, outstanding item count]
- **User-interaction events:** [none, OR "CRITICAL escalation at iteration N — user chose X"]

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
| All reviewers meet threshold (default 80, or the `threshold <N>` override) | [details] | [PASS/FAIL] |
| Convergence cleanup applied (or skipped with no outstanding MAJOR/MINOR) | [yes / skipped] | [PASS/FAIL] |
| Thorough audit run (if requested) | [yes/no / n/a] | [PASS/FAIL / n/a] |
| User checkpoint accepted | [details; count of accepted items] | [PASS/FAIL] |

## Open Questions

- [ ] [question or unresolved issue]

## Next Steps

- [ ] [what should happen next]

## Output Files

[List all files produced by this review]

- [path]: [description]
