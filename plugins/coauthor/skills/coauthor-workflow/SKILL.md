---
name: coauthor-workflow
description: This skill should be used when running the coauthor research workflow — scoping, planning, dispatching workers, reviewing, and finalizing a research project. Triggered by `/scope`, `/plan`, `/work`, `/review`, `/finalize`, and `/rename`.
---

# Coauthor workflow

Run a research workflow with one document artifact per stage and a standing team of named worker agents. The orchestrator (Claude Code's main instance) acts as project manager; named workers (`analyst`, `coder`, `writer`, `researcher`, `reviewer`) do reading, editing, building, and reviewing.

Operating principles, standing-team conventions, and audit-log behavior live in the canonical CLAUDE.md (auto-loaded).

## When to use this workflow

Use it when at least one of these holds:

- The work involves three or more worker slices (file edits, model runs, draft sections).
- The work spans multiple sessions, so durable artifacts matter.
- Worker discretion materially shapes the deliverable and needs to be checked.

For one-shot edits, single fact-checks, conversational answers, or quick lookups, stay inline. Do not invoke the workflow.

## Project layout

Per-project artifacts live under the project's working directory (cwd). The user works in `~/research/<project-dir>/` (a specific project directory rather than its parent). Assume invocation from inside a project directory; do not read sibling project folders.

```
<cwd>/coauthor/
├── SCOPE.md
├── PLAN.md
├── IMPL-<worker>.md
├── REVIEW-<persona>.md
├── CONVENTIONS.md
├── notes.md
└── validators/
```

Derive `project_id` from the cwd basename (no date suffix) and preserve it in frontmatter for cross-references and the global index. Use cwd, not `project_id`, for directory resolution. The global index at `~/.claude/coauthor/INDEX.md` carries one line per project: `<project_id> | <absolute path> | <status> | <created date>`.

Two `CLAUDE.md` files matter: a canonical operating-rules file at `${CLAUDE_PLUGIN_ROOT}/CLAUDE.md` (marker `<!-- coauthor-canonical-rules v1 -->`), and a project-context file at `<cwd>/.claude/CLAUDE.md` carrying name, description, question, data, method, standing team, active validators. `/scope` either copies the canonical to a parent directory or writes an `@import` line into the project file; see `references/scope-procedure.md` for the full routing logic.

## Stage 1: Scope (combined setup + scoping)

Entry: `/scope <one-line project description>` or `/scope @<path-to-spec.md>`. Actor: orchestrator with the user. Merges what was previously `/init` plus the scoping conversation.

Summary:

- Validate cwd; refuse home, root, or other non-project directories.
- Resolve canonical path and walk ancestors for the marker; install to parent or `@import` if absent.
- Scaffold `<cwd>/.claude/`, `<cwd>/coauthor/`, `<cwd>/coauthor/audit/`, `<cwd>/coauthor/validators/`; copy templates; register in the global index.
- Run the scoping conversation with `AskUserQuestion`; freeze SCOPE.md after sign-off.

Full Stage 1 procedure: see `references/scope-procedure.md`.

Do not dispatch workers in this stage. Scoping is the orchestrator's job because it requires the user's domain judgment.

## Stage 2: Plan

Entry: `/plan [project_id]`. Actor: orchestrator with the user.

1. Refuse if SCOPE is not frozen.
2. Decompose the work into slices. Each slice is one worker × one deliverable. Available workers: `analyst`, `coder`, `writer`, `researcher`, `reviewer`.
3. For each slice, write: the worker, the goal, the inputs (file paths, prior IMPL files, data sources), the success criteria, the validators that apply.
4. Mark slices that can run in parallel.
5. Reference validators by id from `validators/` (plugin-level) or `<cwd>/coauthor/validators/` (project-local).
6. Use `AskUserQuestion` for clarifications about scope edges, validator selection, or worker assignment. One structured question per call. Do not restate the user's input.
7. Instantiate `templates/PLAN.md` at `<cwd>/coauthor/PLAN.md`. After user sign-off, set `status: frozen`.
8. Update `<cwd>/.claude/CLAUDE.md`: populate the `Standing team` and `Active validators` sections.

Planning is also orchestrator-only. Do not let workers plan their own work.

See `examples/PLAN.md` for a populated example.

## Stage 3: Work

Entry: `/work [project_id] [slice|all] [--no-review]`. Actor: orchestrator dispatching workers, then dispatching the reviewer personas in parallel.

1. For each slice, dispatch one Agent call with a precise brief: goal, inputs, success criteria, attached validators, output path (`<cwd>/coauthor/IMPL-<worker>.md`).
2. Send independent slices in one message (parallel). Run dependent slices serially.
3. Workers run every applicable validator (executable scripts directly; procedural validators by dispatching the relevant sub-worker) before declaring an IMPL artifact complete, and attach the structured pass/fail results into `IMPL-<worker>.md` (or reference a sibling validator log). Failed validators stay inside the worker's loop; only artifacts with all validators green return to the orchestrator.
4. When a worker flags ambiguity, forward their question to the user, then resume the worker via SendMessage.
5. Each IMPL.md follows `templates/IMPL.md`: what I did, key decisions, deviations from plan, files touched, validator results, follow-ups. See `examples/IMPL.md`.
6. **Auto-review.** Once all PLAN-specified workers for this `/work` invocation have returned IMPL files, dispatch the five core reviewer personas (`methodology`, `robustness`, `literature`, `framing`, `replicability`) in a single parallel message; each writes `REVIEW-<persona>.md` per Stage 3a. Conditionally include the `reports` persona in the same parallel dispatch when an HTML report artifact (a `.qmd` rendering to HTML) is in PLAN's deliverables; skip it otherwise. Wait for all dispatched personas to return, then present a consolidated digest to the user: a one-line link per REVIEW file plus a single severity-sorted list of blocker/major findings cross-cutting all personas. Skip the auto-review entirely if the user passed `--no-review` to `/work` or included that literal flag in the surrounding prompt.
7. **Auto-compile audit transcript.** As the final step, run `python3 ${CLAUDE_PLUGIN_ROOT}/hooks/compile_audit.py` to refresh `<cwd>/coauthor/audit/transcript.html`. The user can inspect the transcript during active work without waiting for `/finalize`. Non-blocking: log to stderr and continue if the script exits nonzero.

Auto-attach validators: any slice whose deliverable is a `.qmd` rendering to HTML picks up `validators/reports/check.py` in addition to whatever validators PLAN already lists. The check enforces the deterministic subset of `${CLAUDE_PLUGIN_ROOT}/skills/quarto-html-report/SKILL.md`.

Treat validators as mechanical. They check what is grep-able, runnable, or otherwise objective. Style, clarity, argument quality, and methodological soundness belong to review, never to validators. Validation is not a separate user-invokable stage; it lives entirely inside the worker loop.

## Stage 3a: Review (manual override)

Entry: `/review <persona|all> [project_id]`. Actor: `reviewer` agent in a named persona. Use only to re-run a persona after fixes (or all five with `/review all`); the default review pass already runs at the end of `/work`.

Personas:

- **methodology:** checks identification, estimator–assumption fit, inference, specification choice.
- **robustness:** checks alternative specifications, sample restrictions, sensitivity to functional form, outlier handling.
- **literature:** checks citation accuracy, prior-art coverage, framing fit with related work.
- **framing:** checks whether the question, evidence, and claims line up; whether the headline result answers the stated question.
- **replicability:** checks code reproducibility, data provenance, environment pinning, seed handling.
- **reports:** checks the rendered HTML report against the judgment-driven items in `${CLAUDE_PLUGIN_ROOT}/skills/quarto-html-report/SKILL.md` (sticky-thead behaviour, max-height, display-name shortening, Python-output wrapping, visual density). Available only when an HTML report artifact is in PLAN's deliverables; the mechanical conformance items are caught upstream by `validators/reports/check.py`.

The reviewer reads SCOPE, PLAN, every IMPL, CONVENTIONS, and writes `<cwd>/coauthor/REVIEW-<persona>.md` from `templates/REVIEW.md`. Output is severity-sorted findings with quoted text, specific problem, suggested fix, plus brief commendations. Run multiple personas in parallel; each is a separate Agent call. A repeat pass on the same persona writes `REVIEW-<persona>-N.md`. As the final step, run `python3 ${CLAUDE_PLUGIN_ROOT}/hooks/compile_audit.py` to refresh `<cwd>/coauthor/audit/transcript.html`; non-blocking on failure.

## Stage 4: Finalize

Entry: `/finalize [project_id]`. Actor: orchestrator with the user. The orchestrator handles user-facing prompts directly via `AskUserQuestion`; do not dispatch agents in this stage.

Merges what were previously the separate `/compound` and `/audit` commands.

1. **Validator promotion audit.** For each file under `<cwd>/coauthor/validators/`, generate a `promote` / `skip` recommendation with a one-line rationale grounded in how the validator was used during the project (which slices it ran on, how often it caught issues, whether it generalises), then ask the user via `AskUserQuestion` for the decision. Append one line per item to `~/.claude/coauthor/promotion-log.md` (append-only):

   ```
   - <ISO date> | <project_id> | <validator path> | recommendation: promote|skip | rationale: <one line> | decision: promote|skip
   ```

   For `promote` decisions, copy the validator to `validators/<domain>/` with a bumped `version` and a provenance note in the body. Edit existing library validators in place with a version bump.

2. **Memory graduation.** For each candidate durable lesson surfaced from REVIEW files, IMPL deviations, or CONVENTIONS additions, draft a one-paragraph memory entry and ask the user via `AskUserQuestion` to approve, edit, or skip. On approval, write the entry to `~/.claude/projects/-home-sulli/memory/feedback_<topic>.md` and append a one-line link to that directory's `MEMORY.md`. On first run, create the directory and seed `MEMORY.md` with a header before appending.

3. **Audit transcript.** Run `python3 ${CLAUDE_PLUGIN_ROOT}/hooks/compile_audit.py` to produce `<cwd>/coauthor/audit/transcript.html`: a self-contained file with embedded CSS, no JS, a sticky stage-grouped sidebar TOC, collapsible dispatches, and an "Orphan dispatches" section. Missing references render as inline warnings. If `<cwd>/coauthor/audit/` is absent the script exits 1.

4. **Index update.** Edit `~/.claude/coauthor/INDEX.md` to set this project's status to `finalized`.

The log-recommendation-then-decide flow is an interim setup: it lets the user audit the orchestrator's judgment without silent decisions. Skipping `/finalize` means a project's lessons stay project-local; the validator library and the memory file are how the next project starts warmer.

## Project maintenance

Entry: `/rename <new-name>`. Renames the current project's directory and rewrites the `project_id` frontmatter field in `SCOPE.md`, `PLAN.md`, every `IMPL-*.md`, every `REVIEW-*.md`, `CONVENTIONS.md`, and `<cwd>/.claude/CLAUDE.md` (where it also updates the `Name:` field). Then `mv`s `<cwd>` to `<parent>/<new-name>` and updates the matching line in `~/.claude/coauthor/INDEX.md`. Leave audit logs (`audit/coauthor.md`, per-worker logs, `transcript.html`) and the global `promotion-log.md` untouched on the audit-trail principle. The slash command cannot change the shell's cwd, so the user must `cd` into the new directory and start a new session afterwards.

## Document lifecycle rules

- **SCOPE.md, PLAN.md:** frozen after user agreement. Amend only via explicit unfreeze (set status back to `draft`, edit, refreeze).
- **IMPL-<worker>.md:** append-only within a slice. On a second pass on the same slice, write a new dated section; do not overwrite the prior pass.
- **REVIEW-<persona>.md:** one file per review pass. A second methodology review on the same project writes `REVIEW-methodology-2.md`.
- **CONVENTIONS.md:** update as we learn. Workers read it before each task. Treat it as the project's living style guide.
- **notes.md:** orchestrator scratch space. Validation reports, decisions, side observations.
- **Project-context `CLAUDE.md`:** drop at `/scope`. Fill project-context section at scope-freeze; standing-team and active-validators sections at plan-freeze.

## References

- `references/scope-procedure.md`: full Stage 1 procedure.
- `references/validator-design.md`: how to write a new validator.
- `references/persona-briefs.md`: full briefs for each reviewer persona.
- `examples/PLAN.md`, `examples/IMPL.md`: populated artifacts.
