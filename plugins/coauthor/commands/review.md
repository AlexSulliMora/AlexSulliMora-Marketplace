---
description: Manual override for re-running a specific reviewer persona (or all five) after fixes. Auto-review at end of /work is the default path.
argument-hint: <persona|all> [project_id]
allowed-tools: Read, Agent, Bash
---

Load `skills/coauthor-workflow/SKILL.md` and follow the **Stage 3a: Review (manual override)** procedure.

`/work` already dispatches all five reviewer personas automatically when its workers finish. Use `/review` only to re-run a single persona after addressing its findings, or to re-run the full sweep with `/review all`.

Inputs:
- `$ARGUMENTS`: required persona, one of `methodology`, `robustness`, `literature`, `framing`, `replicability`, `reports`, or the literal `all`. Optional `project_id` (default: cwd-resolved project). The `reports` persona only makes sense when an HTML report artifact is in PLAN's deliverables; it is skipped from `all` otherwise.

Preconditions:
- All planned IMPL files exist under `<project_dir>/coauthor/`.
- Workers have run their attached validators internally (backpressure inside `/work`) and all validators pass.

Actions:
1. If persona is `all`, dispatch the five core reviewer personas in parallel in a single message, plus `reports` if and only if an HTML report artifact is in PLAN's deliverables; otherwise dispatch the named one. Each call uses `agents/reviewer.md` with the persona name in the brief.
2. The reviewer reads SCOPE, PLAN, all IMPL files, and CONVENTIONS, then writes `<project_dir>/coauthor/REVIEW-<persona>.md` from `templates/REVIEW.md`. A repeat pass on the same persona writes `REVIEW-<persona>-N.md` per the lifecycle rule.
3. Return a one-paragraph digest plus the path(s) to the review file(s). Do not act on findings here; the user decides what enters the next iteration.

## Compile audit transcript

As the final step of `/review`, after the persona's REVIEW file is written, run:

```
python3 ${CLAUDE_PLUGIN_ROOT}/hooks/compile_audit.py
```

This refreshes `<cwd>/coauthor/audit/transcript.html` so the user can inspect dispatch decisions immediately. Non-blocking: if the script exits nonzero, log the error to stderr and continue. Do not fail the parent command on a transcript-compile failure.
