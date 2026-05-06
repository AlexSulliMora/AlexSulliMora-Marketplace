---
title: Ralph-style reviewer architecture for CASM-tools
status: ready-for-planning
date: 2026-04-22
scope: deep
---

# Ralph-style reviewer architecture for CASM-tools

## Problem Frame

Reviewers in `/CASM-tools:review-document` currently run as Claude Code subagents (`plugins/CASM-tools/agents/*-reviewer.md`) dispatched inside the main session by `orchestrate-review.md` and `loop-engine.md`. Their outputs are free-form markdown scorecards parsed with prefix-match heuristics; severity and pass/fail are reconstructed by regex. This has three practical costs.

First, parsing is fragile. Scorecards occasionally drift from the expected shape and the loop engine recovers with best-effort regexes; when parsing fails silently, the convergence check produces wrong answers. Second, reviewers cannot be run in isolation outside a live Claude Code session, so debugging a single reviewer requires standing up the full cascade. Third, the cost and latency of each reviewer are invisible because subagent dispatch is bundled into the parent session's metering.

The `chenandrewy/ralph-wiggum-asset-pricing` repo (branch `ralph/run-final`) demonstrates a cleaner pattern: each reviewer is a standalone Python script that spawns `claude -p` with `--output-format json --json-schema` and writes a structured report to a predictable path. The loop is driven from a script that reads those reports. Porting CASM-tools to that shape fixes all three costs and produces machine-verifiable scorecards.

## Goal

Replace the current subagent-based reviewer cascade with a Ralph-style test harness: each reviewer is a `tests/<reviewer>.py` script that spawns a structured-output `claude -p` subprocess; all tests write `test-results/<reviewer>.json` (per-reviewer payload) plus contribute to `test-results/summary.json` (aggregate). The main Claude session owns the iteration loop as the writer: it invokes test and plan subprocesses, reads a plan file, and edits the document directly. A human-readable renderer script materializes the JSON into a markdown table for the user.

## Requirements

- **R1. Reviewers as Python test scripts.** Each reviewer is a single `.py` file under `plugins/CASM-tools/tests/`. A test is invokable as `python plugins/CASM-tools/tests/<reviewer>.py <document-path> [flags]` and succeeds or fails in isolation without a live Claude Code session.

- **R2. Structured JSON output per test.** Each test shells out to `claude -p --output-format json --json-schema '<schema>'` and writes `test-results/<reviewer>.json` with the common envelope `{verdict: "PASS"|"FAIL", score: int(0–100), reason: str, gating: bool, payload: {...}}`. `payload` may vary per reviewer (writing reviewer's `findings: [{severity, quote, fix}]`, adversarial reviewer's `unanswered_objections: [...]`, etc.).

- **R3. Aggregate summary.** After all tests finish, a runner writes `test-results/summary.json` with consistent shape across tests: `{generated_at, document, tests: [{name, verdict, score, reason, gating}], pass_rate, gating_verdict}`. `gating_verdict` is PASS only when every `gating: true` test passed.

- **R4. Main session is the writer; shell-outs per iteration.** The `/CASM-tools:review-document` skill (in the main Claude session) owns the loop. Each iteration it calls `python plugins/CASM-tools/scripts/run-tests.py <document>` (dispatch + aggregation), then `python plugins/CASM-tools/scripts/author-plan.py <document>` (synthesize a plan from results), then reads `<work>/improvement-plan.md` and edits `<document>` directly. No separate fixer agent; the main session performs edits.

- **R5. Parallel dispatch with cost isolation.** `run-tests.py` runs tests concurrently (process-pool, default `--jobs` = test count, capped by a sensible maximum). Each test is its own `claude -p` process, so per-reviewer cost, latency, and token usage are attributable via subprocess return data.

- **R6. Advisory carries over.** Each test declares `gating: true|false` in its JSON output (default `true`). Convergence gates on `summary.json.gating_verdict == "PASS"`, so advisory test findings flow into the plan but do not block the loop. Per-invocation overrides from the skill's argument grammar must still be able to demote a normally-gating test to advisory, matching the current `advisory <reviewer>` clause.

- **R7. Human-readable renderer.** `python plugins/CASM-tools/scripts/render-results.py` reads `test-results/*.json` and writes `test-results/summary-table.md` (and prints to stdout). The table shows one row per test with columns: `test`, `verdict`, `score`, `gating`, `reason`, `runtime`. Called by the loop after each iteration; not read by any agent.

- **R8. Creator agents deleted, prompts inlined.** `plugins/CASM-tools/agents/paper-summarizer.md`, `extension-proposer.md`, `presentation-builder.md`, and `fixer.md` are removed. Their prompts move into the corresponding skills (or a `plugins/CASM-tools/prompts/` directory the skills read). The main session produces v0 directly, then iterates. Paper-extend's multi-phase behavior (`candidates` / `candidates-revise` / `deep-dive` + user checkpoint) moves into the skill body.

- **R9. Reviewer agents deleted.** `plugins/CASM-tools/agents/{writing,structure,math,simplicity,adversarial,factual,consistency,code,presentation}-reviewer.md` are removed. Each is replaced by a `plugins/CASM-tools/tests/<reviewer>.py` script that carries the reviewer's prompt inline.

- **R10. Scope grammar preserved in skill args.** The existing argument grammar of `/CASM-tools:review-document` (`<scope> [advisory <reviewer>...] <path> [into <dir>]`) is preserved. The skill translates it into flags passed to `run-tests.py` (e.g., `--tests writing structure math`, `--advisory adversarial`, `--results-dir <dir>/test-results/`).

- **R11. Loop engine collapses.** `scripts/orchestrate-review.md` and `scripts/loop-engine.md` are replaced by a single concise control-flow description inside the skill body (and/or a small `scripts/review-loop.md` that the skill follows). The main session is the engine; there is no parallel-agent-dispatch bookkeeping to describe.

- **R12. Iteration state layout.** Per-run artifacts live under `<work>/test-results/` (flat, Ralph-style), with each iteration's reports atomically rotated into `<work>/history/iter-<NNN>/` before the next iteration starts. The live `<document>` path is unchanged. This replaces the current `<doc>-logs/<doc>-<timestamp>/` versioned layout.

- **R13. Paper-* skills invoke the new loop unchanged at the call site.** `paper-summarize`, `paper-extend`, and `paper-present` continue to call `/CASM-tools:review-document` via the `Skill` tool with the same `advisory adversarial` clause they currently pass. Behavior is identical from the pipeline skill's perspective; only what happens inside `review-document` changes.

- **R14. Preference injection still applies.** The PreToolUse preference-injection hook continues to inject `writing-style.md` and `structure-style.md` into dispatched Agent prompts when the skills dispatch initial drafts. When skills produce v0 as the main session (R8), the skill body reads preference files directly and includes them in its working context.

## Scope Boundaries

- Only the reviewer/fixer/creator plumbing changes. The paper pipeline's user-visible contract (inputs, outputs, scope grammar, checkpoint flow) is unchanged.
- The Ralph repo's `ralph-garage/` concept (iteration history, paper PDF archival, continual-improvement mode) is not copied over. We only adopt `tests/` + `test-results/` + `author-plan.py`.
- No change to `paper-preprocess` (marker-pdf caching step).
- No change to `presentation-reviewer`'s image-rasterization side-channel beyond wrapping it as a test. The PNG-per-slide mechanism stays.
- No change to `render-slides-to-png.sh`.

## Non-goals

- No continuous "ralph loop" that keeps iterating forever. The loop exits when `gating_verdict == PASS` or when the iteration cap is hit, matching current behavior.
- No `config-ralph.yaml`-style config file. All knobs come through skill arguments or existing plugin config.
- No Python package abstraction for tests beyond what's needed to deduplicate the common envelope writer. Shared helpers live in `plugins/CASM-tools/tests/_helpers.py`; anything else is overreach.
- No gating on numeric score thresholds. Gating is binary verdict-driven; `score` is informational and used by `author-plan.py` to prioritize fixes. The current score-threshold gating behavior is retired.
- No multi-project or user-repo-local test customization. Tests ship with the plugin.
- No rich/colored terminal renderer. Markdown table only (with stdout echo).

## Key Decisions Resolved

- **Full replacement, not coexistence.** The current agent-dispatch cascade is retired; the new test harness is the only review mechanism after migration. Rejected parallel-mode and pilot-on-one-reviewer options as accumulating maintenance cost.
- **Main session is the writer; shell-outs per iteration.** Rejected the subagent-respawn-per-iteration variant and the standalone-bash-script-owns-the-loop variant. The main session reads the plan and edits directly.
- **Creator agents inlined into skills and deleted.** Rejected keeping creators for v0 only; single writer is simpler and matches the Ralph flat-script philosophy.
- **Hybrid JSON shape.** `test-results/summary.json` is the aggregate with a consistent shape; `test-results/<test-name>.json` carries per-reviewer detail with `{verdict, score, reason, gating, payload}` envelope. Rejected strict shared schema (too restrictive for the adversarial payload) and strict per-reviewer schemas (forces branching in every consumer).
- **Advisory mode carries over via `gating` field.** Rejected dropping advisory; it solves the real problem that adversarial concerns are often research-level and unfixable by the writer.
- **Tests live at `plugins/CASM-tools/tests/`.** Rejected user-repo placement (breaks plugin self-containment) and `scripts/tests/` (over-nested).
- **Renderer is a Python script writing markdown.** Rejected Stop-hook automation (coupling) and rich-terminal output (no persisted artifact).

## Deferred to Planning

- **Exact JSON Schema definitions per reviewer.** The envelope is fixed; each reviewer's `payload` schema needs enumeration, and schemas must be co-located with the test (inline string) or in a sibling `schemas/` directory. Planning should decide.
- **Migration sequencing.** Whether to port all reviewers in one PR or in waves (e.g., writing + structure first, then adversarial, then factual + consistency + math + simplicity + code + presentation). Probably waves, but planning decides cut points.
- **Iteration cap and convergence details.** Where the cap is configured, default value, and how `REVIEW_SUSPENDED.md`-style resume semantics (if any) survive under the new flat state layout.
- **Author-plan.py prompt template.** Content of the prompt, whether it merges `payload` details or only reads `summary.json`, and how it handles advisory-only findings.
- **Fixer's edit-scope guardrails.** Whether the main session edits the document freely or is constrained (e.g., "only apply changes covered by the plan"). Ralph's `author-improve.py` is fully permissive; our current fixer has tighter scoping rules.
- **Paper-extend checkpoint integration.** How the multi-phase `candidates` / `candidates-revise` / `deep-dive` flow — currently implemented via `extension-proposer` agent phases — maps into the main-session-as-writer model. The user checkpoint (R3 of the earlier checkpoint brainstorm) still fires, but the phase switch is now a skill-body branch, not an agent dispatch parameter.
- **Preference file handling when main session is the writer.** Whether the skill inlines preference text into its own working context via explicit read, or relies on hook injection that currently targets Agent-tool dispatches.
- **Cost / quota preflight.** Whether to port Ralph's `check-claude-budget.py`. Probably out of scope for the migration itself; worth noting.
- **Test-results history rotation.** Exact mechanics of rolling `test-results/` into `history/iter-NNN/` between iterations — atomic rename, copy, or symlink.

## Success Criteria

- A researcher running `/CASM-tools:review-document all <doc>` produces identical user-facing behavior (same scope grammar, same advisory clause, same final output at the same path) as before migration, with the only differences being a new `test-results/` directory structure and a `summary-table.md` readable artifact per iteration.
- Every reviewer can be run in isolation: `python plugins/CASM-tools/tests/writing-reviewer.py <doc>` produces `test-results/writing-reviewer.json` and exits 0 on PASS / 1 on FAIL.
- `test-results/summary.json` is machine-parseable with no regex heuristics.
- The paper-* pipeline skills work end-to-end against the new `review-document` with no edits to their own bodies beyond whatever is needed to inline the former creator-agent prompts.
- Zero references to `plugins/CASM-tools/agents/*-reviewer.md`, `fixer.md`, `paper-summarizer.md`, `extension-proposer.md`, `presentation-builder.md` remain after migration.

## Sources & References

- `chenandrewy/ralph-wiggum-asset-pricing`, branch `ralph/run-final` — pattern source:
  - `tests/_test_helpers.py`, `tests/writing-intro.py` (test shape)
  - `ralph/run-tests.py` (parallel dispatch + summary.json)
  - `ralph/author-plan.py`, `ralph/author-improve.py` (plan + apply subprocesses)
  - `ralph/ralph-loop.sh` (orchestration)
- `https://code.claude.com/docs/en/headless#get-structured-output` — `claude -p --output-format json --json-schema` specification.
- `plugins/CASM-tools/skills/review-document/SKILL.md` — current cascade contract and argument grammar.
- `plugins/CASM-tools/scripts/{orchestrate-review,loop-engine}.md` — current loop mechanics (to be retired).
- `plugins/CASM-tools/agents/*-reviewer.md`, `fixer.md`, `paper-summarizer.md`, `extension-proposer.md`, `presentation-builder.md` — reviewer and creator prompts to be ported.
- `docs/plans/2026-04-22-001-feat-advisory-reviewer-non-blocking-plan.md` and `docs/brainstorms/2026-04-22-paper-extend-candidate-checkpoint-requirements.md` — recent behavior that must survive the migration.
