---
description: Dispatch workers per the frozen PLAN.md. Supports parallel and serial dispatch; one slice per agent call. Auto-runs all five reviewer personas after IMPL files return.
argument-hint: [project_id] [slice-id|all] [--no-review]
allowed-tools: Read, Agent, Bash
---

Load `skills/coauthor-workflow/SKILL.md` and follow the **Stage 3: Work** procedure.

Inputs:
- `$ARGUMENTS`: optional `project_id` and slice selector. Defaults: cwd-resolved project, all slices not yet completed. If a `project_id` is given, resolve its directory via `~/.claude/coauthor/INDEX.md`. The literal flag `--no-review` (anywhere in the arguments or in the surrounding prompt) skips the auto-review step.
- Read `<project_dir>/coauthor/PLAN.md`, `<project_dir>/coauthor/SCOPE.md`, `<project_dir>/coauthor/CONVENTIONS.md`.

Dispatch rules:
- **One slice per Agent call.** No multi-task briefs.
- **Parallelize independent slices** in a single message.
- Brief each worker with: goal, inputs (file paths), success criteria, attached validators, where to write `<project_dir>/coauthor/IMPL-<worker>.md`.
- Workers run every applicable validator (executable scripts directly; procedural validators via the appropriate sub-worker) before declaring an IMPL artifact complete, and attach the structured pass/fail results into `IMPL-<worker>.md` (or reference a sibling validator log). Failed validators stay inside the worker's loop; only artifacts with all validators green return.
- Auto-attach the `reports/quarto-style` validator (`validators/reports/check.py`) to any slice whose deliverable is a `.qmd` rendering to HTML, in addition to whatever validators PLAN already lists.
- Validation is internal to `/work`. There is no separate `/validate` stage.

Auto-review:
- After all PLAN-specified workers return their IMPL notes for this `/work` invocation, dispatch the five core reviewer personas (`methodology`, `robustness`, `literature`, `framing`, `replicability`) in a single parallel message. Each reviewer is one Agent call following `commands/review.md` semantics; output goes to `<project_dir>/coauthor/REVIEW-<persona>.md`.
- Conditionally include the `reports` persona in that same parallel dispatch when an HTML report artifact (a `.qmd` rendering to HTML) is in PLAN's deliverables. Skip it otherwise.
- Wait for all dispatched personas to return. Then present a consolidated digest to the user: a one-line link to each per-persona REVIEW file plus a single severity-sorted list of blocker/major findings cross-cutting all personas. Do not act on findings; the user decides what enters the next iteration.
- Skip auto-review entirely if the user passed `--no-review` or included that literal flag in the surrounding prompt.

`/review <persona>` (or `/review all`) remains the manual override for re-running a specific persona after fixes; see `commands/review.md`.

After all slices return (and after the auto-review digest, if not skipped), summarize what landed on disk and which slices have IMPL files.

## Compile audit transcript

As the final step of `/work`, after the consolidated digest has been shown to the user, run:

```
python3 ${CLAUDE_PLUGIN_ROOT}/hooks/compile_audit.py
```

This refreshes `<cwd>/coauthor/audit/transcript.html` so the user can inspect dispatch decisions during active work without waiting for `/finalize`. The script is idempotent and fast. Non-blocking: if it exits nonzero (e.g., the audit directory does not exist), log the error to stderr and continue. Do not fail the parent command on a transcript-compile failure.
