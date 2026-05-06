---
title: "refactor: narrow yes/no test catalog + profile grammar for CASM-tools"
type: refactor
status: active
date: 2026-04-22
origin: docs/brainstorms/2026-04-22-tests-proposed-narrow-yes-no-suite-requirements.md
parent_plan: docs/plans/2026-04-22-002-refactor-ralph-style-reviewer-architecture-plan.md
---

# refactor: narrow yes/no test catalog + profile grammar for CASM-tools

## Overview

Replace the nine-reviewer-shape test suite (already deleted on `ralph-approach`) with a 44-test catalog of narrow Ralph-style yes/no tests organized into 7 profiles. Refactor the existing harness scripts (`run-tests.py`, `render-results.py`, `author-plan.py`) to a new envelope (drop `score`, drop `gating`), a profile-based dispatch model (`<profile> <doc> [profile-clauses]`), and an EXHAUSTED terminal state with a triage report. Add a `--jobs N` parallelism cap (Ralph pattern) and a sidecar `measure-slide-density.py` script that produces the input the `slides-density` test reads. Update the four paper-* skill call sites to the new grammar.

The parent plan (`2026-04-22-002-refactor-ralph-style-reviewer-architecture-plan.md`) shipped the Ralph architecture itself: subprocess-isolated tests, main-session-as-writer, parallel dispatch, state rotation, hook retirement, creator-agent inlining. That foundation stays. This plan replaces only the parts the requirements doc redesigned: the test layer, the skill grammar, the envelope shape, and the cap-exhaustion terminal state.

## Problem Frame

The parent-plan harness ships nine reviewer-shape Python tests, each scoring 0–100 and gating on `score >= 80 AND zero CRITICAL`. Those nine tests have been deleted on `ralph-approach` (commit pending) because the reviewer-per-artifact-type model has known weaknesses: scores absorb signal that hard verdicts would expose, the nine reviewer categories don't fit hybrid Quarto artifacts cleanly, and the `--advisory` mechanism the old fixer needed is no longer required (the Ralph writer can restructure to address adversarial findings, so every test can hard-gate).

The redesign in the requirements doc (`docs/brainstorms/2026-04-22-tests-proposed-narrow-yes-no-suite-requirements.md`) is 44 narrow yes/no tests across 11 categories, organized into 7 profiles per artifact type. Each test asks one sharp question and returns `{verdict, reason, payload}` with section/region labels in the payload. Profiles handle multi-input cleanly (`--source-paper`, `--screenshots-dir`, `--paired-slides`); the user-facing grammar collapses from `<scope> [advisory <r>...] <path> [into <dir>]` to `<profile> <doc> [profile-clauses]`. The `paper-source` profile (32 tests) is experimental and parallels Ralph's own scope.

This is a proof-of-concept iteration. A later iteration will redesign around per-section test routing or staged document creation (outline → math → writing, each stage gated by its own narrow tests). The PoC must not foreclose either future path. (See origin: `docs/brainstorms/2026-04-22-tests-proposed-narrow-yes-no-suite-requirements.md`.)

## Relationship to Parent Plan

This plan supersedes specific sections of `docs/plans/2026-04-22-002-refactor-ralph-style-reviewer-architecture-plan.md`. The parent plan stays the authoritative reference for everything not listed below.

| Parent-plan section | Status under this plan |
|---|---|
| §"Implementation Units" U2 (port 9 reviewers to `tests/*.py`) | Superseded; replaced by U7 below (44 narrow tests). |
| §"Key Technical Decisions" — envelope `{verdict, score, reason, gating, payload}` | Superseded; new envelope drops `score` and `gating`. |
| §"Key Technical Decisions" — gating is binary verdict-driven | Tightened; every test gates (no `gating: bool` field; no `--advisory` flag; convergence requires every test PASS). |
| §"Key Technical Decisions" — REVIEW_SUSPENDED.md schema 2 | Superseded; cap-exhaustion writes `EXHAUSTED.md` (no resume). |
| §"Key Technical Decisions" — `threshold <N>` deprecated parser | Tightened; parser removed entirely. |
| §"High-Level Technical Design" — scope-token grammar | Superseded; new grammar is `<profile> <doc> [--source-paper <pdf>] [--screenshots-dir <dir>] [--paired-slides <p>] [--spec <m>] [--references <b>] [into <dir>] [iterations <N>]`. |
| Auto-classification table (`.qmd` → writing+presentation+code+...) | Superseded; empty-scope falls back to `writing` for `.md`/`.qmd` and `code` for `.py`. Other artifact types require an explicit profile. |
| `meta-review` reads test-results | Carries forward; meta-review's reading logic is updated for the new envelope (U6). |

The parent plan's still-valid decisions stay verbatim: subprocess isolation, main-session-as-writer, atomic state rotation, baseline.md + git audit trail, no concurrency protection, retry policy, exit code semantics, paper-extend three-phase via `draft-candidates.py`, hook retirement, creator-agent inlining.

After U9 lands, the parent plan's frontmatter `status: active` flips to `status: superseded` (see Documentation / Operational Notes).

## Requirements Trace

From the origin requirements doc, with prefix `R` to distinguish from the parent plan's R1–R19:

- **R1.** Each test asks one sharp question and returns `{verdict: PASS|FAIL, reason: str, payload: {...}}`. No `score`, no `gating`, no `--advisory` flag. (Origin §D1.)
- **R2.** Profiles map artifact types to test lists. Invocation: `/CASM-tools:review-document <profile> <doc-path> [profile-specific clauses]`. Each profile declares its required and optional inputs. (Origin §D2.)
- **R3.** Envelope: `{verdict, reason, payload}`. Each test owns its `payload` schema. Findings carry section/region labels (lines, slide numbers, function names). (Origin §D3.)
- **R4.** Profile-level inputs resolved at the skill layer; tests inside a profile receive all profile inputs uniformly. (Origin §D4.)
- **R5.** Catalog covers Ralph-inspired categories (theory, narrative, factcheck, element) alongside writing, structure, math, code, slides, adversarial, consistency. 44 tests, 11 categories. (Origin §D5 + §"Test Catalog".)
- **R6.** Seven profiles: `writing`, `paper-summary`, `extension-proposal`, `slides`, `presentation-writeup`, `code`, `paper-source` (experimental). (Origin §"Profile Composition".)
- **R7.** New CLI surface for `run-tests.py`: profile manifest in place of filename pattern matching; optional `--jobs N` flag (Ralph `chenandrewy/ralph-wiggum-asset-pricing` `ralph/run-tests.py` pattern); profile-input flags forwarded to each test. (Origin §"Implied Loop Changes" #1, #2.)
- **R8.** Loop terminates on every-test-PASS. Iteration cap remains; cap-exhaustion is a third terminal state `EXHAUSTED` with a triage report listing each unresolved test, its FAIL reason, and reviewer-supplied evidence the writer would need to address it. Callers (paper-* skills) treat `EXHAUSTED` as unresolved-failures, not success. (Origin §"Implied Loop Changes" #4.)
- **R9.** Renderer (`render-results.py`) shows section/region labels per test type, not just a flat findings count. Per-test display rules. (Origin §"Implied Loop Changes" #5.)
- **R10.** Workflow assumption: artifacts are Markdown or Quarto (`.md`, `.qmd`); tests must not assume LaTeX-source idioms. `.tex` is dropped from the supported input set; the parent plan's `.tex` auto-classification row is removed. (Origin §"Workflow Assumption".)
- **R11.** `factcheck-arithmetic` returns `INCONCLUSIVE` for any number whose inputs are not literally in the artifact (e.g., values referenced by citation). `INCONCLUSIVE` counts as PASS for gating but is reported separately for visibility. (Origin §"Test Catalog" — Factcheck row.)
- **R12.** `slides-density` reads `density.json` from a sidecar `scripts/measure-slide-density.py` (PNG → grayscale → non-background-pixel fraction); the test agent does not eyeball screenshots. (Origin §"Test Catalog" — Slides row.)
- **R13.** PoC validates if (a) the loop reaches a coherent terminal state (PASS or EXHAUSTED with a diagnosable cause) on a small text artifact under the `writing` profile, AND (b) the loop converges or exhausts cleanly on a synthetic-paper fixture under the `paper-source` profile. Validation is "narrow yes/no tests produce useful, calibrated verdicts" — not "outperform the deleted nine-reviewer suite," which has no recorded baseline to compare against. (Origin §"Success Criteria"; reframed because the deleted suite cannot be a comparator. See U9 for staged smoke-check protocol.)

## Scope Boundaries

In scope:
- The 44 narrow test files under `plugins/CASM-tools/tests/`.
- Profile manifest under `plugins/CASM-tools/tests/profiles.json`.
- Refactor of `scripts/run-tests.py`, `scripts/render-results.py`, `scripts/author-plan.py`, `scripts/review-loop.md`, and `skills/review-document/SKILL.md` for the new envelope, profile grammar, EXHAUSTED state, and `--jobs N`.
- Sidecar `scripts/measure-slide-density.py`.
- Paper-* skill call-site updates (`paper-summarize`, `paper-extend`, `paper-present`, `paper-full-pipeline`).
- `meta-review` envelope reads if any.
- Convergence smoke check on `paper-source` profile.

Out of scope:
- Per-section test routing (deferred to a later iteration; PoC framing).
- Staged document creation (outline → math → writing, each stage gated). Deferred.
- Hybrid `.qmd` artifact handling (writeup + math + slides in one file). User picks one profile per invocation; if the artifact needs more, run again. Systematic resolution belongs to the deferred future iteration.
- Resumption of cap-exhausted cascades. `REVIEW_SUSPENDED.md` is gone with the rest of the legacy; `EXHAUSTED.md` is a terminal report only. (Recovery is git + delete logs + rerun, matching the parent plan's no-concurrency-protection stance.)
- Backward compatibility shims between old and new schemas. The new schema replaces the old one; nothing reads the old envelope after this lands.
- LaTeX-source workflows. Tests assume Quarto/Markdown only.

### Deferred to Separate Tasks

- **Per-section test routing OR staged document creation.** A future iteration redesigns the harness to either auto-route tests to document parts or stage document creation. Decisions in this plan must not foreclose either future path. (See `MEMORY.md` → `project_tests_proposed_poc_framing.md`.)
- **Tuning per-test prompt wording for production use.** Each test's Ralph-style stepwise procedure is drafted in U7; production tuning happens after the smoke check (U9) reveals where the prompts need tightening.
- **`paper-source` profile validation against a real economics paper draft.** U9 covers the smoke check; deeper validation (false-positive rate, false-negative rate against expert review) is a follow-up task.

## Context & Research

### Relevant Code and Patterns

- **Parent plan's harness scripts** — `plugins/CASM-tools/scripts/{run-tests.py,render-results.py,author-plan.py,review-loop.md}` and `skills/review-document/SKILL.md`. Refactored in U2–U6. Current state uses old envelope (`score`, `gating`, `gating_verdict`) and old grammar (scope tokens, `--advisory`, deprecated `threshold <N>` parser).
- **Parent plan's `_helpers.py` placeholder** — does not exist on disk; the parent plan's U1 was supposed to create it but was completed inline within each test file. This plan creates it for real (U1) since the new envelope and profile loader need a shared module.
- **Ralph reference patterns** — `chenandrewy/ralph-wiggum-asset-pricing`, branch `ralph/run-final`:
  - `ralph/run-tests.py` for `--jobs N` parallelism cap shape.
  - `tests/_test_helpers.py` for envelope/dispatch helpers (carrying same shape, different fields).
  - `tests/writing-intro.py`, `tests/clarity.py`, `tests/factcheck.py` for narrow-yes/no prompt structure with stepwise procedures and section/region payloads.
- **`scripts/draft-candidates.py`** — paper-extend's three-phase drafting (`candidates`, `candidates-revise`, `deep-dive`). Untouched by this plan; orthogonal concern.
- **`scripts/render-slides-to-png.sh`** — produces the PNG screenshots that `measure-slide-density.py` (U4) consumes. Untouched.
- **Paper-* skill call sites** — `skills/paper-summarize/SKILL.md` (line ~118), `skills/paper-extend/SKILL.md`, `skills/paper-present/SKILL.md`, `skills/paper-full-pipeline/SKILL.md`. All currently invoke with `all advisory adversarial <doc> into <dir>`. Updated in U8.

### Institutional Learnings

- **No legacy grandfathering** (`MEMORY.md` → `project_no_legacy_grandfathering.md`). Old envelope, old grammar, `--advisory` flag, REVIEW_SUSPENDED.md schema 2 — all retired in this plan rather than preserved alongside the new design. Retention requires positive justification.
- **Ralph-style writer escapes the local-minimum trap** (`MEMORY.md` → `project_ralph_loop_architecture_rationale.md`). The new tests can hard-gate without falling into the trap that drove the old `--advisory` mechanism, because the writer is empowered to restructure. This is why this plan drops `--advisory` entirely.
- **Don't describe preference loading in orchestrator-facing docs** (`docs/plans/2026-04-20-fix-prevent-orchestrator-preference-injection-plan.md`). Each test inlines the one or two style rules its sharp question depends on. No `preferences/` folder, no preference-injection hook (already retired).
- **Don't write subagent-Write-blocked basenames** (parent plan §"Artifact name constraint"). `tests/<name>.json` and `EXHAUSTED.md` are written by Python subprocess, bypassing the filter; safe.

### External References

- `chenandrewy/ralph-wiggum-asset-pricing`, branch `ralph/run-final` — pattern source for narrow Ralph tests, profile-shaped invocation, `--jobs N` parallelism cap.
- Claude Code headless structured output: `claude -p --output-format json --json-schema '<schema>'`; result in `.structured_output`. Already established in the parent plan; reused here with the new envelope.

## Key Technical Decisions

- **Profile manifest is JSON, co-located with tests.** `plugins/CASM-tools/tests/profiles.json` with one top-level key per profile. Each entry: `{required_inputs: [...], optional_inputs: [...], tests: [...]}`. JSON because both `run-tests.py` (Python) and the skill body (Bash-tool-driven JSON parsing via `jq` or Python one-liners) parse it. Rejected: Python dict (forces import path resolution from the skill body) and YAML (extra dependency).
- **No per-test display registry; render uniform envelope.** `render-results.py` reads `summary.json` and each per-test JSON and renders a uniform table with columns `Test | Verdict | Region | Reason | Runtime`. The `Region` column pulls section/line labels from the `payload` if present (mechanical lookup, no per-test code). Tests with rich payloads write detail to their per-test JSON for user inspection, not to the summary table. Rejected: per-test `DISPLAY_RULE` with dynamic Python imports — `plugins/CASM-tools/tests/<test-name>` is not a valid Python identifier (hyphens), and dynamic-import-on-render couples rendering to every test module's import side effects. Ralph's renderer reads only the standard envelope and works fine; we follow that pattern.
- **`_helpers.run_test()` owns argparse; tests are minimal.** Each test file is `from _helpers import run_test; main = lambda: run_test(prompt=..., payload_schema=..., test_name=...)`. `_helpers.run_test()` parses CLI args (the union of all profile-input flags + `--logs-dir`), hands the resolved values to the prompt-template renderer as kwargs, and writes the envelope. Tests reference profile inputs by name (`{source_paper_path}`, `{screenshots_dir}`) in their prompt template; absent inputs interpolate as empty strings. Tests are invoked from `tests/` (each test is `python tests/<name>.py`), so `from _helpers import ...` works without `sys.path` manipulation — same as Ralph's `from _test_helpers import ...`.
- **`--jobs N` defaults to unbounded (one worker per test).** Behavior matches the parent plan's `run-tests.py`. `--jobs N` caps the worker pool at `min(N, len(selected_tests))`. Rationale: backward compatible for the writing/code profiles (small test counts), gives the user a knob for `paper-source` (32 tests) when API rate limits or local memory pressure are concerns. Default unbounded is the right default because each test is its own subprocess and the per-test claude -p call is the long pole; CPU-bound contention is negligible.
- **EXHAUSTED replaces SUSPENDED. No resume.** When the iteration cap is reached with FAILs remaining, the harness writes `<logs_dir>/EXHAUSTED.md` (terminal triage report) and exits with status `exhausted`. The next invocation does NOT auto-resume; the user diagnoses, edits the doc, and reruns from scratch. Rationale: the requirements doc explicitly drops resume semantics (§"Implied Loop Changes" #4); resume added complexity for a workflow that was rare in practice and confusing when state drifted between cap-exhaustion and resume.
- **`INCONCLUSIVE` is allowed only for `factcheck-arithmetic`; treated as PASS for convergence with anti-gaming guards.** `_helpers.py` enforces a single allow-list (`INCONCLUSIVE_ALLOWED = {"factcheck-arithmetic"}`); any other test that emits INCONCLUSIVE is rejected as a schema-validation failure. The aggregate `verdict` in `summary.json` is PASS iff every test is PASS or INCONCLUSIVE. The summary table renders INCONCLUSIVE distinctly. **Anti-gaming guard:** `author-plan.py`'s prompt explicitly forbids the writer from converting a checkable arithmetic claim into a citation-referenced one to dodge a FAIL. INCONCLUSIVE-count is tracked iteration-over-iteration; a regression (more INCONCLUSIVE than the prior iteration) is flagged in the EXHAUSTED report and in `applied-edits.md` so the user can see if the writer is weakening the artifact rather than improving it. Rationale: hard-gating works only if the writer addresses real findings; INCONCLUSIVE without a guard becomes the path of least resistance.
- **No `--thorough` post-convergence audit pass.** The parent plan kept `thorough` as a token that runs a final audit. This plan drops it: with hard-gating tests and no `score` field, the distinction "informational thorough run" doesn't carry meaning anymore. If a user wants every test to run regardless, they pick the heaviest profile (`paper-source` for academic papers; `writing` for general text). Rationale: simpler grammar, no second-class informational pass.
- **Sidecar `measure-slide-density.py` writes `density.json` next to the screenshots.** Single source of truth: the `slides-density` test reads `<screenshots-dir>/density.json` and refuses to run (FAIL with reason "density.json not found; run measure-slide-density.py first") if absent. Rationale: separates measurement (deterministic Python on PIL) from evaluation (LLM judgment on density.json + slide content). The skill body invokes `measure-slide-density.py` once before dispatching the `slides` profile; `paper-present` integrates this into its compile step.
- **`.tex` artifacts dropped from auto-classification.** Quarto/Markdown only, per origin §"Workflow Assumption". The auto-classification table in the new SKILL.md does not include a `.tex` row. Existing `.tex` invocations error with `"file extension .tex is no longer supported; convert to .qmd or .md"`. Rationale: the user does not maintain LaTeX-source workflows; carrying the row forward is dead complexity.
- **`meta-review` updates minimally.** It reads test-results JSONs to surface them in pipeline summaries. The change is mechanical: drop reads of `score` and `gating`, accept the new `verdict ∈ {PASS, FAIL, INCONCLUSIVE}`, drop references to `gating_verdict` (use `verdict`). No structural changes.

## Open Questions

### Resolved During Planning

- **Profile manifest format.** JSON, co-located at `plugins/CASM-tools/tests/profiles.json`. Resolved above.
- **Display rules.** Dropped — `render-results.py` reads the standard envelope only. Region column extracts mechanically from the payload (tries `payload.region`, `payload.location`, `payload.lines`, then `payload.sections[0]`). No per-test Python code, no dynamic imports of hyphenated module names.
- **`--jobs N` default behavior.** Default unbounded (one worker per selected test); `--jobs N` caps at `min(N, len(tests))`. Resolved above.
- **Source-paper representation for `paper-summary` / `extension-proposal` tests.** PDF passed straight through; the test's claude -p subprocess uses its `Read` tool to load the PDF. No pre-extraction step. Origin §"Open Questions" suggested confirming this; the parent plan's pattern is to pass paths and let claude tools handle reading, so this is the consistent choice.
- **EXHAUSTED report format.** Markdown with YAML frontmatter for machine-parseable status: `terminal_state: exhausted`, `iteration_count: <N>`, `unresolved_tests: [...]`, `inconclusive_regression: <bool>`. Body is mechanically generated by the skill body from `summary.json` + per-test JSONs — one row per FAILing test with the test name, FAIL reason, and `payload.region` (or `payload.sections`, `payload.lines`) if present. **No LLM synthesis** — no "what the writer would need to address" prose. The user reads the FAIL reasons directly. Rationale: synthesis prose would require another `claude -p` invocation at cap exhaustion, adding cost and an extra failure mode for marginal value over raw FAIL reasons.
- **Conditional tests filtered by a hard-coded skill-body rule, not by manifest metadata.** Only two tests in the catalog are conditional: `slides-headline-coverage` (requires `--source-paper`) and `consistency-equivalent-ideas` (requires `--paired-slides`). The skill body inlines two `if` statements before invoking `run-tests.py`: drop these tests from the resolved test list when their required input is absent. The profile manifest lists every test unconditionally; the skill body does the filtering by passing `--skip-test <name>` (a flag added to `run-tests.py`) for each one. Rationale: two conditionals do not justify a manifest-schema extension; hard-coded rules are obvious and grep-able.
- **paper-* skills halt on EXHAUSTED.** `paper-full-pipeline` and the individual paper-* skills treat an EXHAUSTED return from `/CASM-tools:review-document` as a terminal pipeline failure: report the path to `EXHAUSTED.md` and stop. Downstream pipeline stages do not run. The user diagnoses, edits the offending artifact, and re-invokes (either the individual stage or the pipeline). Rationale: silently continuing past a failed quality gate produces compounding bad output.
- **What happens when a test in a profile is missing from `tests/`?** `run-tests.py` errors with `"profile '<name>' lists test '<missing>' which does not exist in tests/"`. No silent skip. Rationale: a profile manifest reference to a missing test is always a bug; treating it as PASS (vacuous) would let the loop converge on incomplete coverage.

### Deferred to Implementation

- **Per-test prompt wording.** The catalog gives each test its sharp question and pass rule. The Ralph-style stepwise procedure (input → procedure → output schema → pass condition) is drafted at port time, taking inspiration from `chenandrewy/ralph-wiggum-asset-pricing`'s `ralph/run-final/tests/` for shape but not literal text. Tuning happens after U9 reveals false-positive/false-negative patterns.
- **Per-test payload field names.** Structural rules are fixed: every payload is one of `{findings: [...]}`, `{sections: [...]}`, `{cross_references: [...]}`, `{citations: [...]}`, or a small composite. Field names within (e.g., `findings[i].quote`, `sections[i].name`) are decided at port time per test.
- **Region-extraction key precedence.** `render-results.py` tries `payload.region`, `payload.location`, `payload.lines`, `payload.sections[0]` in that order. Per-test prompt drafters in U7 should use one of these keys when relevant; defer the specific key choice per test to U7 drafting.
- **`measure-slide-density.py` non-background-pixel threshold.** Threshold near-white pixels at some grayscale value (e.g., > 250 of 255 = background). The implementer tunes the threshold against representative slides; default `> 240` is a starting point.
- **`tests/profiles.json` JSON schema.** A small JSON Schema for the profile manifest itself, enforced when `run-tests.py` loads it. Useful but not blocking; defer to U2.
- **`meta-review` summary-table additions for INCONCLUSIVE.** Whether to highlight `INCONCLUSIVE` test counts in pipeline-level reports. Defer; mechanical.

## Output Structure

The directory tree showing new and modified files (existing unchanged files not shown):

```
plugins/CASM-tools/
├── tests/                                     # NEW (was deleted on this branch)
│   ├── _helpers.py                            # NEW — envelope schema, profile loader, INCONCLUSIVE handling
│   ├── profiles.json                          # NEW — 7 profile definitions
│   ├── writing-hedge-stacking.py              # NEW — 8 writing tests
│   ├── writing-engagement-bait.py
│   ├── writing-em-dash-discipline.py
│   ├── writing-not-x-pattern.py
│   ├── writing-empty-emphasis.py
│   ├── writing-throat-clearing.py
│   ├── writing-banned-words.py
│   ├── writing-sentence-necessity.py
│   ├── structure-section-flow.py              # NEW — 4 structure tests
│   ├── structure-paragraph-composition.py
│   ├── structure-heading-signal.py
│   ├── structure-progression.py
│   ├── math-derivation-gaps.py                # NEW — 4 math tests
│   ├── math-notation-consistency.py
│   ├── math-assumption-explicitness.py
│   ├── math-estimator-properties.py
│   ├── theory-clarity.py                      # NEW — 3 theory tests
│   ├── theory-unmodeled-channels.py
│   ├── theory-intuition.py
│   ├── narrative-section-fulfillment.py       # NEW — 4 narrative tests
│   ├── narrative-cross-references.py
│   ├── narrative-claim-strength.py
│   ├── narrative-abstract-body-alignment.py
│   ├── factcheck-arithmetic.py                # NEW — 4 factcheck tests; arithmetic has INCONCLUSIVE
│   ├── factcheck-references.py
│   ├── factcheck-exhibits.py
│   ├── factcheck-against-source.py
│   ├── element-lit-review-coverage.py         # NEW — 3 element tests
│   ├── element-lit-review-length.py
│   ├── element-opening-figure.py
│   ├── slides-text-fitting.py                 # NEW — 5 slides tests
│   ├── slides-density.py                      #   reads density.json
│   ├── slides-readability.py
│   ├── slides-headline-coverage.py
│   ├── slides-progression.py
│   ├── code-correctness.py                    # NEW — 4 code tests
│   ├── code-simplicity.py
│   ├── code-naming.py
│   ├── code-error-handling.py
│   ├── adversarial-load-bearing.py            # NEW — 3 adversarial tests
│   ├── adversarial-alternative-explanation.py
│   ├── adversarial-prompt-injection.py
│   ├── consistency-equivalent-ideas.py        # NEW — 2 consistency tests
│   └── consistency-claim-alignment.py
├── scripts/
│   ├── run-tests.py                           # MODIFIED — profile dispatch, --jobs N, profile-input flags, new envelope
│   ├── render-results.py                      # MODIFIED — per-test display rules, new envelope
│   ├── author-plan.py                         # MODIFIED — new envelope, drop advisory rule
│   ├── review-loop.md                         # MODIFIED — verdict-based convergence, EXHAUSTED state
│   ├── measure-slide-density.py               # NEW — sidecar, PIL grayscale measurement
│   ├── draft-candidates.py                    # unchanged
│   ├── render-slides-to-png.sh                # unchanged
│   └── session-log-template.md                # MODIFIED — verdict labels updated
└── skills/
    ├── review-document/SKILL.md               # REWRITTEN — profile grammar, EXHAUSTED state, drop scope tokens / advisory / threshold
    ├── paper-summarize/SKILL.md               # MODIFIED — call site uses paper-summary profile
    ├── paper-extend/SKILL.md                  # MODIFIED — call site uses extension-proposal profile
    ├── paper-present/SKILL.md                 # MODIFIED — call sites use slides + presentation-writeup profiles; invokes measure-slide-density.py
    ├── paper-full-pipeline/SKILL.md           # MODIFIED — pipeline summary references new grammar
    └── meta-review/SKILL.md                   # MODIFIED — drops score/gating reads; accepts INCONCLUSIVE verdict
```

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

### Envelope schema (per-test JSON output)

```json
{
  "verdict": "PASS|FAIL|INCONCLUSIVE",
  "reason": "one-sentence summary of why",
  "payload": { /* test-specific shape */ }
}
```

`INCONCLUSIVE` is only valid for tests that declare it possible (currently only `factcheck-arithmetic`). The skill convergence check treats `INCONCLUSIVE` as PASS. The aggregate `summary.json.verdict` is PASS iff every test is PASS or INCONCLUSIVE.

### Profile manifest schema (`plugins/CASM-tools/tests/profiles.json`)

```json
{
  "writing": {
    "required_inputs": [],
    "optional_inputs": [],
    "tests": [
      "writing-hedge-stacking", "writing-engagement-bait", "writing-em-dash-discipline",
      "writing-not-x-pattern", "writing-empty-emphasis", "writing-throat-clearing",
      "writing-banned-words", "writing-sentence-necessity",
      "structure-section-flow", "structure-paragraph-composition",
      "structure-heading-signal", "structure-progression",
      "adversarial-load-bearing", "adversarial-prompt-injection"
    ]
  },
  "paper-summary": {
    "required_inputs": ["source-paper"],
    "optional_inputs": [],
    "tests": [ /* 16 tests per origin */ ]
  },
  "extension-proposal": {
    "required_inputs": ["source-paper"],
    "optional_inputs": [],
    "tests": [ /* 18 tests per origin */ ]
  },
  "slides": {
    "required_inputs": ["screenshots-dir"],
    "optional_inputs": ["source-paper"],
    "tests": [ /* 6 unconditional + 1 conditional */ ]
  },
  "presentation-writeup": {
    "required_inputs": [],
    "optional_inputs": ["paired-slides"],
    "tests": [ /* 12 unconditional + 1 conditional */ ]
  },
  "code": {
    "required_inputs": [],
    "optional_inputs": [],
    "tests": ["code-correctness", "code-simplicity", "code-naming", "code-error-handling"]
  },
  "paper-source": {
    "required_inputs": [],
    "optional_inputs": ["spec", "references"],
    "tests": [ /* 32 tests per origin: all writing-* (8), all structure-* (4), all math-* (4),
                 all theory-* (3), all narrative-* (4), factcheck-arithmetic, factcheck-references,
                 factcheck-exhibits (3 of 4 — factcheck-against-source excluded because paper-source
                 has no source PDF), all element-* (3), all adversarial-* (3) */ ]
  }
}
```

Conditional tests (`slides-headline-coverage`, `consistency-equivalent-ideas`) are listed in `tests` only when their required optional input was passed. The skill body filters before calling `run-tests.py`.

### New CLI grammar

```
/CASM-tools:review-document <profile> <doc-path>
                            [--source-paper <pdf>]
                            [--screenshots-dir <dir>]
                            [--paired-slides <path>]
                            [--spec <md>]
                            [--references <bib>]
                            [into <dir>]
                            [iterations <N>]
                            [--jobs <N>]
```

Filler words (`the`, `for`, `only`, `just`, `on`, `against`, `a`) still stripped. `<profile>` must be one of the seven profile names. Required inputs validated against the profile manifest before dispatch.

### Per-iteration loop changes vs parent plan

```
1. Measure: python scripts/run-tests.py <profile> <doc> --logs-dir <dir> [profile-flags] [--jobs N] [--iteration N] [--skip-test <name> ...]
2. Render:  python scripts/render-results.py <logs_dir>/test-results
3. Convergence: read summary.json; if verdict == PASS, break.
4. Cap check: if iter == max_iter, skill body writes <logs_dir>/EXHAUSTED.md mechanically from summary.json + per-test JSONs; exit (no resume).
5. Author plan: python scripts/author-plan.py <doc> <logs_dir>
6. Rotate: os.rename(test-results/, history/iter-NNN/), copy plan.md, sentinel, mkdir new test-results/.
7. Edit: main session reads plan, edits doc in place, writes applied-edits.md.
8. iter += 1.
```

Steps 1, 3, 4 changed (new CLI, new convergence, EXHAUSTED replaces SUSPENDED). Steps 2, 5, 6, 7, 8 mechanically updated for the new envelope but structurally unchanged.

### `EXHAUSTED.md` format (mechanical, no LLM synthesis)

```markdown
---
schema_version: 1
terminal_state: exhausted
iteration_count: 3
inconclusive_regression: false
generated_at: 2026-04-22T15:00:00Z
unresolved_tests:
  - narrative-section-fulfillment
  - factcheck-against-source
  - adversarial-load-bearing
---

# Cascade Exhausted — 3 unresolved tests after 3 iterations

## narrative-section-fulfillment (FAIL)

**Reason:** Section "Method" promises X but delivers Y.
**Region:** lines 46-120

## factcheck-against-source (FAIL)

**Reason:** Claim on line 87 ("X causes Y") not supported by source paper.
**Region:** line 87

(repeat per unresolved test — content extracted directly from per-test JSON envelopes; no model synthesis)
```

## Implementation Units

- [ ] **Unit 1: `_helpers.py` + profile manifest + display-rule contract**

**Goal:** Establish the foundation every other unit depends on: shared envelope schema, profile manifest format, JSON schema fragments for claude -p, the `INCONCLUSIVE` allow-list, and the centralized argparse + prompt-interpolation wrapper that every test calls.

**Requirements:** R1, R2, R3, R4, R6, R11

**Dependencies:** None.

**Files:**
- Create: `plugins/CASM-tools/tests/_helpers.py`
- Create: `plugins/CASM-tools/tests/profiles.json`
- Create: `plugins/CASM-tools/tests/test__helpers.py` (unit tests for the helper module)

**Approach:**
- `_helpers.py` exports: `ENVELOPE_SCHEMA` (JSON schema dict), `INCONCLUSIVE_ALLOWED = {"factcheck-arithmetic"}` (allow-list), `run_test(test_name, prompt_template, payload_schema, allowed_tools)` (generic dispatch wrapper), `load_profile(name)` (reads `profiles.json`, returns the profile dict), `validate_profile_inputs(profile, args)` (raises if a required input is missing).
- `run_test()` owns argparse: parses `--logs-dir`, `--iteration`, and the union of profile-input flags (`--source-paper`, `--screenshots-dir`, `--paired-slides`, `--spec`, `--references`). Interpolates the resolved values into `prompt_template` as named placeholders (`{source_paper_path}`, `{screenshots_dir}`, etc.); absent inputs interpolate as empty strings.
- `run_test()` calls `claude -p --output-format json --json-schema <merged>` where merged is `ENVELOPE_SCHEMA` with the test's `payload_schema` injected. Validates the result against `INCONCLUSIVE_ALLOWED` (rejects INCONCLUSIVE from any test not in the allow-list). Writes `<logs_dir>/test-results/<test_name>.json`. Exits 0 for PASS or INCONCLUSIVE, 1 for FAIL, 2 for infra failure.
- `profiles.json` ships with all 7 profiles populated per origin §"Profile Composition". Test lists are stable strings; U7's test names must match.
- No `DISPLAY_RULE` contract — display lives entirely in `render-results.py` reading the standard envelope (U3).

**Patterns to follow:**
- Parent plan's `tests/_helpers.py` patterns for `run_claude_subprocess` (subprocess invocation, retry-on-schema-failure, infra-failure envelope synthesis). Adapt: drop `score` and `gating` fields, add `INCONCLUSIVE` verdict path.
- Ralph repo's `tests/_test_helpers.py` for generic dispatch wrapper shape.

**Test scenarios:**
- Happy path: `_helpers.run_test(...)` with a stub claude -p (mock subprocess) returning a well-formed envelope writes `<logs_dir>/test-results/<name>.json` and exits 0.
- Edge case: `INCONCLUSIVE` verdict accepted only when the test's `payload_schema` declares it; otherwise raises.
- Error path: subprocess returns malformed JSON → retry once → if second attempt still fails, write infra-failure envelope and exit 2.
- Edge case: `load_profile("nonexistent")` raises with a clear message naming the available profiles.
- Error path: `validate_profile_inputs` raises when `paper-summary` is missing `--source-paper`, naming the missing input.
- Integration: a fixture profile with 2 tests, both passing → aggregate `summary.json.verdict == PASS`. (Integration test placed in `test__helpers.py` for now; full integration is U9.)

**Verification:**
- `_helpers.py` is importable and exports the documented surface.
- `profiles.json` parses as JSON; every profile has `required_inputs`, `optional_inputs`, `tests` keys.
- `pytest plugins/CASM-tools/tests/test__helpers.py` passes.

---

- [ ] **Unit 2: refactor `run-tests.py` for profile dispatch + `--jobs N` + profile-input flags + new envelope**

**Goal:** Replace test-list dispatch with profile-based dispatch, add `--jobs N` cap, forward profile-input flags to each test subprocess, drop `--advisory` and `--thorough`, update summary aggregation for the new envelope.

**Requirements:** R1, R2, R4, R7, R11

**Dependencies:** U1 (`_helpers.load_profile`, `validate_profile_inputs`).

**Files:**
- Modify: `plugins/CASM-tools/scripts/run-tests.py`
- Create: `plugins/CASM-tools/scripts/test_run_tests.py` (unit tests)

**Approach:**
- New CLI: `python scripts/run-tests.py <profile> <doc-path> --logs-dir <dir> [--source-paper <pdf>] [--screenshots-dir <dir>] [--paired-slides <p>] [--spec <m>] [--references <b>] [--jobs <N>] [--iteration <N>] [--skip-test <name> ...]` (`--skip-test` is repeatable; the skill body uses it to drop conditional tests when their optional input is absent — see U6 conditional rule).
- Drop `--tests`, `--advisory`, `--thorough`, `--screenshots` (the last is renamed to `--screenshots-dir` for grammar consistency).
- Resolution order: parse args → load profile via `_helpers.load_profile` → validate required inputs are present → resolve test-name → file-path mapping (each test name → `tests/<name>.py`). Conditional-test filtering happens in the skill body (U6) before this script is invoked; `run-tests.py` does not own that logic. (See conditional-filtering open question in §"Open Questions" — a follow-up decision is required on how the skill body communicates the filtered list to `run-tests.py`.)
- Worker pool: `min(args.jobs or len(tests), len(tests))`.
- Forward profile-input flags to each test subprocess via CLI: every test's argparse accepts the union of input flags, ignores those it doesn't need.
- Aggregation: `_build_summary` writes `{schema_version: 2, generated_at, document, profile, tests: [{name, verdict, reason, runtime_s, exit_code}], verdict, inconclusive_count, fail_count}`. `verdict` is PASS iff every test is PASS or INCONCLUSIVE; otherwise FAIL.
- Exit code: 0 if `verdict == PASS`, 1 otherwise.

**Patterns to follow:**
- Parent plan's `run-tests.py` parallel dispatch via `ProcessPoolExecutor`; keep that.
- Ralph `chenandrewy/ralph-wiggum-asset-pricing` `ralph/run-tests.py` for `--jobs` flag shape.

**Test scenarios:**
- Happy path: `run-tests.py code <doc.py> --logs-dir <tmp>` runs all 4 code tests in parallel, writes 4 per-test JSONs + summary.json with `verdict: PASS`. (Uses fixture tests with stub subprocess, not real claude -p.)
- Happy path: `run-tests.py paper-summary <doc.md> --source-paper <pdf> --logs-dir <tmp>` runs the 16 tests, forwards `--source-paper` to each test subprocess.
- Error path: `run-tests.py paper-summary <doc.md> --logs-dir <tmp>` (missing `--source-paper`) errors with `"profile 'paper-summary' requires --source-paper"`, exits 2.
- Error path: `run-tests.py nonexistent-profile <doc> --logs-dir <tmp>` errors with `"unknown profile 'nonexistent-profile'; available: ..."`, exits 2.
- Edge case: `run-tests.py paper-source <doc.qmd> --jobs 4 --logs-dir <tmp>` caps the worker pool at 4 even though the profile has 32 tests.
- Edge case: profile lists a test that isn't in `tests/` → errors with `"profile 'X' lists test 'Y' which does not exist in tests/"`, exits 2.
- Integration: one PASS test + one FAIL test → `summary.json.verdict == FAIL`, exit 1.
- Integration: one PASS test + one INCONCLUSIVE test → `summary.json.verdict == PASS`, `inconclusive_count == 1`, exit 0.

**Verification:**
- `python scripts/run-tests.py --help` shows the new flag set; no `--tests`, `--advisory`, `--thorough`, `--screenshots`.
- `pytest plugins/CASM-tools/scripts/test_run_tests.py` passes.

---

- [ ] **Unit 3: refactor `render-results.py` for per-test display rules + new envelope**

**Goal:** Drop `Score` and `Gating` columns. Render a uniform table from the standard envelope (no per-test code, no Python imports of test modules). Add `Region` column populated mechanically from payload keys. Render `INCONCLUSIVE` distinctly.

**Requirements:** R3, R9, R11

**Dependencies:** U1 (envelope shape). U2 (summary.json shape).

**Files:**
- Modify: `plugins/CASM-tools/scripts/render-results.py`
- Create: `plugins/CASM-tools/scripts/test_render_results.py`

**Approach:**
- Read `summary.json` and each per-test JSON. No Python imports of test modules; render purely from JSON.
- Uniform table columns: `Test | Verdict | Region | Reason | Runtime`. The `Region` column extracts from the per-test payload by trying these keys in order: `payload.region`, `payload.location`, `payload.lines`, or the first `payload.sections[i].name`/`lines` if present. If none present, `Region` is empty.
- Footer: `verdict: PASS|FAIL`, `pass_rate`, `inconclusive_count`, `iteration`, `document`, `generated_at`. No `gating_verdict`.
- INCONCLUSIVE renders with distinct marker (`INCONCL`) so the reader sees what wasn't checked.

**Patterns to follow:**
- Existing `render-results.py` table-building structure.

**Test scenarios:**
- Happy path: render summary.json with 4 PASS tests → markdown table with 4 rows, footer shows `verdict: PASS, pass_rate: 1.0, inconclusive_count: 0`.
- Happy path: render summary with 2 PASS + 1 FAIL + 1 INCONCLUSIVE → table renders all 4 rows; FAIL highlighted, INCONCLUSIVE distinct.
- Happy path: a test with `payload.sections: [{name: "Method", lines: "46-120"}, ...]` renders `Region` as `Method (46-120)`.
- Edge case: a test in summary.json has no per-test JSON on disk → render row with `infra-failure` annotation in Reason column; do not crash.
- Edge case: payload has none of the recognized region keys → `Region` is empty; do not crash.
- Integration: render against the fixture summary written by U2's integration test → output matches the documented column shape.

**Verification:**
- `python scripts/render-results.py <fixture-dir>` writes `summary-table.md` matching the expected format.
- `pytest plugins/CASM-tools/scripts/test_render_results.py` passes.

---

- [ ] **Unit 4: sidecar `measure-slide-density.py`**

**Goal:** Compute non-background-pixel fraction per slide PNG; write `density.json` next to the screenshots.

**Requirements:** R12

**Dependencies:** None (orthogonal to U1).

**Files:**
- Create: `plugins/CASM-tools/scripts/measure-slide-density.py`
- Create: `plugins/CASM-tools/scripts/test_measure_slide_density.py`

**Approach:**
- CLI: `python scripts/measure-slide-density.py <screenshots-dir>`. Reads every `*.png` in the directory (sorted), converts each to grayscale, counts pixels with grayscale value `<= 240` (i.e., not near-white), divides by total pixel count to get density fraction.
- Writes `<screenshots-dir>/density.json` with `{slide_001: 0.42, slide_002: 0.61, ...}` keyed by the PNG basename without extension.
- Uses `Pillow` (PIL); add to `pyproject.toml` if a dependency manifest exists, or use `uv run --script` inline dependency declaration.
- Does not depend on `_helpers.py`; pure utility script.

**Patterns to follow:**
- The `uv run --script` inline-script pattern used by other CASM-tools scripts.

**Test scenarios:**
- Happy path: directory with 3 PNGs (one near-blank, one densely populated, one mid) → density fractions in expected ranges (e.g., < 0.05, > 0.5, 0.2–0.4). Use synthetic PIL images as fixtures.
- Edge case: directory with no PNGs → writes `density.json: {}`; exits 0; warns to stderr.
- Edge case: directory does not exist → exits 2 with clear error.
- Edge case: a PNG is unreadable (corrupt) → skips it, warns to stderr, continues with the rest.

**Verification:**
- `python scripts/measure-slide-density.py <fixture-dir>` produces `density.json` with the expected keys and values.
- `pytest plugins/CASM-tools/scripts/test_measure_slide_density.py` passes.

---

- [ ] **Unit 5: refactor `author-plan.py` for new envelope**

**Goal:** Update the plan-authoring prompt template and input handling for the new envelope (no `score`, no `gating`, no `--advisory`).

**Requirements:** R1, R3

**Dependencies:** U2 (summary.json shape).

**Files:**
- Modify: `plugins/CASM-tools/scripts/author-plan.py`

**Approach:**
- Update PROMPT_TEMPLATE: drop "Cite verbatim ... finding's severity label" (the new envelope doesn't carry severities). Replace with: cite `test_name` + `payload` field references (e.g., `[narrative-section-fulfillment / sections[1] (Method, lines 46-120)]`) so the plan rows are traceable.
- Drop the "advisory tests get top-3 only" rule; every failing test contributes to the plan.
- Drop the rule about ordering by severity; order tests by name within failing-test list.
- Update plan output structure: drop `Gating verdict`; use `Verdict`. Drop the `## Failing advisory tests` section.
- **Anti-gaming language (load-bearing for hard-gating):** the prompt must explicitly forbid the writer from weakening the artifact to dodge a FAIL. Bans include: converting a checkable arithmetic claim into a citation-referenced one to flip `factcheck-arithmetic` FAIL → INCONCLUSIVE; deleting a claim instead of supporting it; replacing a specific number with a vague phrase. The writer must address findings by improving the artifact, not by removing the failing surface.

**Patterns to follow:**
- Existing `author-plan.py` shape (claude -p subprocess + atomic write).

**Test scenarios:**
- Happy path: feed a synthetic summary.json with 5 PASS + 3 FAIL tests + corresponding per-test JSONs → claude -p subprocess invoked with the new prompt; resulting `current-plan.md` cites each FAIL test by name + payload region.
- Edge case: every test PASS (shouldn't happen — author-plan only runs on FAIL — but defensively) → claude -p produces an empty plan; the script writes "All tests passed; no improvements needed" and exits 0.
- Error path: claude binary missing → exit 2 with clear message (already in current code).

**Verification:**
- `python scripts/author-plan.py <doc> <logs_dir>` against a fixture produces a plan that cites every failing test by name.
- Manual review of one generated plan confirms no references to `score`, `gating`, `advisory`, or `severity`.

---

- [ ] **Unit 6: rewrite `review-document` skill body + `review-loop.md` for profile grammar + EXHAUSTED state**

**Goal:** Replace the entire argument-parsing and orchestration section of the skill with profile-based grammar. Replace `REVIEW_SUSPENDED.md` with `EXHAUSTED.md` (terminal, no resume). Drop scope tokens, `advisory <reviewer>`, `threshold <N>`, and `--thorough`.

**Requirements:** R2, R4, R7, R8, R10

**Dependencies:** U2 (run-tests.py CLI shape). U5 (author-plan.py output format).

**Files:**
- Modify: `plugins/CASM-tools/skills/review-document/SKILL.md`
- Modify: `plugins/CASM-tools/scripts/review-loop.md`
- Modify: `plugins/CASM-tools/skills/review-document/state-README.md` (output layout section)
- Modify: `plugins/CASM-tools/scripts/session-log-template.md` (verdict labels)

**Approach:**
- New skill body argument parsing: extract path → extract `<profile>` (must be one of 7 names; error with "did you mean" if not) → extract optional `into <dir>`, `iterations <N>`, `--jobs <N>` → extract profile-input flags (`--source-paper`, `--screenshots-dir`, `--paired-slides`, `--spec`, `--references`) → validate profile's required inputs are present.
- **Conditional-test filtering rule (hard-coded):** the skill body knows the conditional set:
  ```
  if profile == "slides" and "--source-paper" not in args:
      filtered_tests.discard("slides-headline-coverage")
  if profile == "presentation-writeup" and "--paired-slides" not in args:
      filtered_tests.discard("consistency-equivalent-ideas")
  ```
  Pass the resulting set to `run-tests.py` via repeated `--skip-test <name>` flags (added to `run-tests.py` in U2). Two conditionals do not justify a manifest-schema extension.
- Empty-scope auto-classification simplified: `.md` / `.qmd` → `writing` profile; `.py` → `code` profile. Other artifact types require an explicit profile.
- Drop §"Reviewers with non-standard CLI" entirely. Profiles handle this uniformly via profile-input flags.
- For the `slides` profile, the skill body invokes `python scripts/measure-slide-density.py <screenshots-dir>` once before dispatching `run-tests.py`.
- **EXHAUSTED.md is mechanically generated by the skill body** (no LLM synthesis): on cap-exhaustion, read `summary.json` + per-test JSONs, produce `EXHAUSTED.md` with YAML frontmatter (`terminal_state`, `iteration_count`, `unresolved_tests`, `inconclusive_regression: <bool>`) and one body row per FAILing test (test name, FAIL reason, region from payload). Track INCONCLUSIVE-count iteration-over-iteration; set `inconclusive_regression: true` if the count rose during this cascade.
- Rewrite `review-loop.md`: convergence check is `verdict == PASS`; cap-exhaustion writes `EXHAUSTED.md` and exits (no resume); remove all advisory references.
- Rewrite §"Failure modes" table: drop advisory rows, drop suspend/resume rows, add EXHAUSTED row.
- Rewrite §"Examples" with new grammar.
- `state-README.md`: update directory-layout doc; drop `REVIEW_SUSPENDED.md`, add `EXHAUSTED.md`; drop `thorough/`.

**Patterns to follow:**
- Existing skill-body structure (sections, examples, anti-patterns); rewrite content within each.
- Parent plan's review-loop.md for rotation invariants and crash recovery (still apply).

**Test scenarios:**
- Happy path: invoke `/CASM-tools:review-document writing draft.md` → skill resolves to `writing` profile, runs the 14 writing-profile tests, converges or exhausts.
- Happy path: invoke `/CASM-tools:review-document paper-summary paper-summary.md --source-paper paper.pdf into /tmp/logs` → resolves correctly.
- Happy path: invoke `/CASM-tools:review-document slides slides.html --screenshots-dir /tmp/png` → skill invokes `measure-slide-density.py` first, then `run-tests.py`.
- Error path: invoke `/CASM-tools:review-document paper-summary paper.md` (missing `--source-paper`) → error message names the missing input; no dispatch.
- Error path: invoke `/CASM-tools:review-document everything paper.md` → "did you mean" suggests one of the 7 profiles.
- Error path: artifact is `.tex` → "file extension .tex is no longer supported; convert to .qmd or .md".
- Edge case: cap exhaustion → `EXHAUSTED.md` written with frontmatter + per-test triage; next invocation does NOT auto-resume (would start fresh).
- Integration: invoke against a fixture artifact, observe loop runs through to convergence or EXHAUSTED.

**Verification:**
- New SKILL.md has no occurrences of "scope token", "advisory", "threshold", "thorough", "gating_verdict", "REVIEW_SUSPENDED".
- `review-loop.md` references only `verdict` and `EXHAUSTED.md`.
- Smoke invocation against a tiny fixture artifact reaches PASS without errors.

---

- [ ] **Unit 7: build the 44 narrow test files**

**Goal:** Implement every test in the catalog. Each file is small (~30–60 lines): imports `_helpers`, declares the prompt template, the payload JSON schema, and the allowed-tools string, then exits via `_helpers.run_test(...)`. Following Ralph's `tests/writing-intro.py` shape.

**Requirements:** R1, R3, R5, R11 (factcheck-arithmetic INCONCLUSIVE), R12 (slides-density reads density.json)

**Dependencies:** U1 (`_helpers.run_test`, envelope schema). U4 (density.json schema for `slides-density`).

**Files:**
- Create: 44 files under `plugins/CASM-tools/tests/` (see Output Structure for the full list).
- Create: `plugins/CASM-tools/tests/test_smoke.py` (smoke fixture: for each `.py` file in `tests/` not starting with `_`, run it with `--help` and confirm exit 0; also confirm every name in `profiles.json` corresponds to a file).

**Approach:**
- Each test follows the same template (Ralph's `tests/writing-intro.py` pattern):
  ```python
  # tests/<name>.py
  from _helpers import run_test
  PROMPT_TEMPLATE = """<Ralph-style sharp question + stepwise procedure;
  may interpolate {source_paper_path}, {screenshots_dir}, etc. — empty string when absent>"""
  PAYLOAD_SCHEMA = { ... }
  ALLOWED_TOOLS = "Read,Grep,Glob"
  if __name__ == "__main__":
      raise SystemExit(run_test(
          test_name="<name>",
          prompt_template=PROMPT_TEMPLATE,
          payload_schema=PAYLOAD_SCHEMA,
          allowed_tools=ALLOWED_TOOLS,
      ))
  ```
  `_helpers.run_test()` parses CLI args (the union of profile-input flags + `--logs-dir` + `--iteration`), interpolates them into `PROMPT_TEMPLATE`, invokes `claude -p --output-format json --json-schema <merged>`, and writes the envelope. No `DISPLAY_RULE` — display is uniform across tests, handled by `render-results.py` reading the standard envelope.
- The bulk of work is **drafting the per-test prompt**: each prompt asks the sharp question from the requirements doc catalog, defines a stepwise inspection procedure, names the section/region labels to include in the payload, and states the pass condition. Reference Ralph's `tests/clarity.py`, `tests/factcheck.py`, etc. for the procedural shape (read the artifact → step through it → emit findings → decide verdict).
- Inline the one or two style rules each prompt depends on directly into the prompt (no `preferences/` directory). Keep style-rule inlining minimal: most tests need zero style rules; a few writing tests reference banned-word lists or em-dash discipline rules.
- **Scope note for `writing-em-dash-discipline` and `writing-banned-words`:** these tests target *user-authored* documents (academic papers, summaries, slide writeups). Their pass rules deliberately differ from the user's `MEMORY.md` rules for Claude's own output — for example, the catalog allows em dashes in sentences with another separator, while `MEMORY.md` bans them outright in assistant text. The test prompt must state explicitly that the catalog rule applies, not the agent-output rule, so the model does not over-flag user prose.
- `factcheck-arithmetic` declares `INCONCLUSIVE` as a possible verdict in its schema; the prompt instructs the model to return INCONCLUSIVE for any number whose inputs are not literally in the artifact.
- `slides-density` reads `<screenshots-dir>/density.json`; its prompt feeds the JSON as input and asks the model to flag slides outside `[0.05, 0.7]` density (rough thresholds; the implementer tunes against representative slides). The test does NOT call PIL itself.
- `consistency-equivalent-ideas` and `consistency-claim-alignment` accept multiple paths (passed as `--paired-slides <path>` from the profile-input flag); the test reads both artifacts.
- `factcheck-against-source`, `slides-headline-coverage` accept `--source-paper <pdf>` (passed straight through; the model uses Read to inspect the PDF).
- Allowed tools per test: most tests `Read,Grep,Glob`. `code-correctness` uses `Read,Grep,Glob,Bash(pytest:*),Bash(ruff:*),Bash(mypy:*)` (carry forward from the parent plan's allowedTools mapping). `code-simplicity` uses `Read,Grep,Glob,Bash(ruff:*),Bash(vulture:*)`.

**Patterns to follow:**
- Ralph repo's `ralph/run-final/tests/writing-intro.py`, `tests/clarity.py`, `tests/factcheck.py` — for stepwise prompt structure with section labels.
- The 44 test names in the catalog must exactly match the strings in `profiles.json` (U1).

**Test scenarios:**
- Smoke: every test file responds to `--help` with exit 0 (Ralph pattern; confirms importability + argparse wiring).
- Smoke: every test name in `profiles.json` corresponds to an existing `tests/<name>.py`.
- Manual spot-check (not automated): for one test per category, run against a known-PASS artifact and a known-FAIL artifact, verify the verdicts. (Full validation belongs to U9.)

**Verification:**
- `pytest plugins/CASM-tools/tests/test_smoke.py` passes.
- `python -c "import json; from pathlib import Path; m=json.loads(Path('plugins/CASM-tools/tests/profiles.json').read_text()); names={n for p in m.values() for n in p['tests']}; existing={p.stem for p in Path('plugins/CASM-tools/tests').glob('*.py') if not p.stem.startswith(('_','test_'))}; missing=names-existing; assert not missing, f'missing test files: {missing}'"` passes.

---

- [ ] **Unit 8: update paper-* skill call sites for the new grammar**

**Goal:** Update the four paper-* skills to invoke `/CASM-tools:review-document` with profile-based grammar. Add `measure-slide-density.py` to paper-present's slide pipeline.

**Requirements:** R2, R6, R12

**Dependencies:** U6 (skill body accepts new grammar).

**Files:**
- Modify: `plugins/CASM-tools/skills/paper-summarize/SKILL.md`
- Modify: `plugins/CASM-tools/skills/paper-extend/SKILL.md`
- Modify: `plugins/CASM-tools/skills/paper-present/SKILL.md`
- Modify: `plugins/CASM-tools/skills/paper-full-pipeline/SKILL.md`
- Modify: `plugins/CASM-tools/skills/meta-review/SKILL.md`

**Approach:**
- `paper-summarize` final step: invoke with `paper-summary <output> --source-paper <pdf> into <dir>` (was: `all advisory adversarial <output> into <dir>`).
- `paper-extend` final step: invoke with `extension-proposal <output> --source-paper <pdf> into <dir>`.
- `paper-present`:
  - Slides step: ensure `render-slides-to-png.sh` runs first (already does), then run `measure-slide-density.py <screenshots-dir>`, then invoke with `slides <slides-html> --screenshots-dir <dir> [--source-paper <pdf>] into <dir>`.
  - Writeup step: invoke with `presentation-writeup <writeup.qmd> [--paired-slides <slides-html>] into <dir>`.
- `paper-full-pipeline`: update the cascade narrative for the new grammar; update example invocations.
- `meta-review`: drop reads of `score` and `gating` from per-test JSONs; accept `verdict ∈ {PASS, FAIL, INCONCLUSIVE}`; aggregate `inconclusive_count` if surfaced in pipeline summaries.

**Patterns to follow:**
- Existing skill structure; rewrite the call-site invocation lines.

**Test scenarios:**
- Manual spot-check: each paper-* skill's example invocation block is rewritten with the new grammar; no `advisory adversarial` references remain.
- Integration: end-to-end invocation of `paper-summarize` against a fixture PDF reaches `/CASM-tools:review-document paper-summary <output> --source-paper <pdf> into <dir>` and converges or exhausts.

**Verification:**
- `grep -rn 'advisory adversarial\|all advisory\|gating_verdict' plugins/CASM-tools/skills/` returns no results.
- One paper-* skill end-to-end invocation against a tiny fixture reaches PASS or EXHAUSTED without grammar errors.

---

- [ ] **Unit 9: PoC convergence smoke check (two-stage)**

**Goal:** Validate that the loop converges meaningfully on representative artifacts. The PoC question is "do narrow yes/no tests produce useful, calibrated verdicts that the writer can act on" — not "outperform the deleted reviewers" (the deleted suite has no recorded baseline to compare against, so a head-to-head was never measurable). Two-stage smoke: first a small fixture proves the architecture, then a real paper exercises the heaviest profile.

**Requirements:** R13

**Dependencies:** U1–U8.

**Files:**
- Create: `plugins/CASM-tools/tests/fixtures/synthetic-paper.qmd` (small ~2-page synthetic Quarto draft: abstract + intro + method + 1 derivation + 1 figure reference + bibliography stub; designed to exercise paper-source's 32 tests without depending on a real paper).
- Create: `docs/reviews/poc-smoke-<YYYY-MM-DD>/` (cascade output; not committed).
- Create: `docs/notes/2026-04-22-tests-proposed-poc-smoke-results.md` (committed; written after the smoke check, summarizing convergence behavior, false-positive patterns, INCONCLUSIVE-regression observations, and per-test tuning needs).

**Approach:**
- **Stage 1 — architecture validation on `writing` profile.** Pick a small text artifact (e.g., a recent committed brainstorm or plan in `docs/`). Run `/CASM-tools:review-document writing <doc> into docs/reviews/poc-smoke-stage1-<date>/ iterations 3`. Observe whether the loop converges, exhausts cleanly, or crashes. This isolates the harness from the paper-source test surface.
- **Stage 2 — coverage validation on `paper-source` profile.** Run against `tests/fixtures/synthetic-paper.qmd` first (cheap, controlled). If that converges or exhausts cleanly, optionally re-run against the user's own WIP paper draft (if one exists in Quarto). Run: `/CASM-tools:review-document paper-source <draft.qmd> --jobs 8 into docs/reviews/poc-smoke-stage2-<date>/ iterations 5`.
- Observe per stage: iterations to convergence, which tests fired FAIL repeatedly, INCONCLUSIVE counts, INCONCLUSIVE regressions, false-positive patterns.
- Outcome (per stage):
  - **Converged with no/few false positives:** stage validates.
  - **Converged with notable false positives:** validates with caveat; list per-test tuning needs.
  - **EXHAUSTED with diagnosable cause:** PoC still validates as long as `EXHAUSTED.md` shows the triage path is clear (over-constrained test → relax/prune; cap too tight → raise to 10; writer limitation → escalate).
  - **EXHAUSTED with INCONCLUSIVE-regression flag:** writer is gaming the loop; tighten author-plan.py prompt and re-run.
  - **Loop crashes or produces incoherent output:** halt and escalate; fix before further work.

**Test scenarios:** none (this unit is itself a verification step).

**Verification:**
- `tests/fixtures/synthetic-paper.qmd` exists and renders cleanly via `quarto render`.
- The smoke-check note exists at `docs/notes/2026-04-22-tests-proposed-poc-smoke-results.md` summarizing both stages.
- For each stage: the note attaches the final `summary-table.md` (or `EXHAUSTED.md`) and lists triage decisions or follow-up tuning tasks.

## System-Wide Impact

- **Interaction graph:** the four paper-* skills, the meta-review skill, and the `/CASM-tools:review-document` skill all change argument shape. No external system depends on the old grammar (no GitHub Actions, no shared CI, no other plugins consume CASM-tools test outputs). The user's own paper-pipeline workflow is the entire downstream.
- **Error propagation:** a profile-input validation failure at the skill body fails fast (before dispatch) with a clear message. A test subprocess infra-failure is captured in `summary.json` and continues; the loop converges or exhausts on remaining tests. EXHAUSTED is a terminal state; the user diagnoses, edits, and reruns.
- **State lifecycle risks:** the rotation invariants from the parent plan still apply (atomic `os.rename` of `test-results/` → `history/iter-NNN/` BEFORE edits, with `.iteration-complete` sentinel). Crash between rotation and edits → next invocation re-applies the plan idempotently; the live doc + git is the recovery substrate.
- **API surface parity:** there is no parallel API surface. The skill is the only entry point; tests are invoked only by `run-tests.py`. The paper-* skills are the only consumers of the skill.
- **Integration coverage:** U2's integration test (one PASS + one FAIL fixture) and U9's smoke check are the integration points. Unit tests in U1–U6 cover their respective scripts; integration is tested end-to-end through one paper-* invocation in U8 and through the smoke check in U9.
- **Unchanged invariants:**
  - Subprocess isolation per test (parent plan).
  - Main session as writer; edits live document in place (parent plan).
  - Atomic state rotation; baseline.md + git as audit trail (parent plan).
  - No concurrency protection; user responsibility (parent plan).
  - Hook retirement: no `inject-preferences.py`; no preferences folder (parent plan + this branch's deletion).
  - Creator-agent inlining (parent plan; paper-* skills already produce v0 inline).

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| 44 test prompts drafted unevenly; some too strict, some too loose, leading to false positives or false negatives in the loop | U9's smoke check explicitly looks for false-positive patterns; per-test prompt tuning is a deferred-to-separate-task item that fires after U9's results are in. The implementer is encouraged to draft conservatively (prefer false-negative on edge cases over false-positive). |
| `author-plan.py` struggles to synthesize from 44 tests' worth of payloads when many fail at once | author-plan.py reads only failing tests; the prompt instructs it to be concrete and short. If plans become unmanageably long, follow-up: add per-plan-row severity hints in payload schemas. |
| `paper-source` profile (32 parallel claude -p subprocesses) hits API rate limits or local memory pressure | The `--jobs N` flag exists. Default for `paper-source` invocations: cap at 8 (set by skill body, not test default). Implementer adjusts if smoke check shows rate-limit errors. |
| Convergence on `paper-source`: 32 tests = more failure surface than 9; loop may cycle without converging | U9 is two-stage: stage 1 validates the harness on `writing` profile first; stage 2 runs `paper-source` against a synthetic fixture, then optionally a real paper. Triage paths (relax test, raise iteration cap, prune) documented in U9. |
| Writer games hard-gating by weakening the artifact (e.g., flipping FAIL → INCONCLUSIVE on `factcheck-arithmetic`) | `_helpers.INCONCLUSIVE_ALLOWED` allow-lists only `factcheck-arithmetic`; `author-plan.py` prompt explicitly forbids the anti-pattern; INCONCLUSIVE-count tracked iteration-over-iteration, regression flagged in `EXHAUSTED.md`. |
| Per-test arithmetic checking is LLM-based and inherently noisier than the `slides-density` sidecar | Asymmetry accepted for PoC: arithmetic claims aren't structured the way pixel grids are, so a `measure-arithmetic.py` sidecar would require the writer to maintain a manifest, defeating the test's point. If U9 reveals the INCONCLUSIVE rate is too high to be useful, follow-up considers extraction-and-compute. |
| `EXHAUSTED.md` lacks resume; user has to start from scratch on cap exhaustion | Per origin §"Implied Loop Changes" #4 and Key Technical Decisions: this is intentional. Resume added complexity for a workflow that was rare; if it bites in practice, follow-up plan can re-add. |
| `.tex` artifacts no longer supported; some user workflows may break | Per origin §"Workflow Assumption": user does not maintain LaTeX-source workflows. If this turns out to be wrong, follow-up plan can re-add `.tex` support to specific profiles. |

## Documentation / Operational Notes

- **Parent plan supersession.** After U9 completes, edit `docs/plans/2026-04-22-002-refactor-ralph-style-reviewer-architecture-plan.md`'s frontmatter to `status: superseded`, and add a top-of-document note: `> Superseded in part by docs/plans/2026-04-22-003-refactor-narrow-test-catalog-and-profile-grammar-plan.md (2026-04-22). The Ralph architecture (subprocess isolation, main-session-as-writer, state rotation, hook retirement, creator-agent inlining) shipped per this plan and stays. The reviewer-shape test catalog, scope-token grammar, envelope, and SUSPENDED state described here were redesigned by plan 003.`
- **Pre-implementation commit.** Before U1 begins, commit the staged deletions (`tests/`, `preferences/`) currently sitting in the working tree, plus the requirements doc + this plan, with one commit message describing both. This puts the branch in a clean state from which U1 begins.
- **Memory updates.** The four memory files referenced in this plan (`feedback_word_prose_banned.md`, `project_ralph_loop_architecture_rationale.md`, `project_no_legacy_grandfathering.md`, `project_tests_proposed_poc_framing.md`) stay accurate as written. No updates needed.
- **No external rollout.** This plan ships entirely within `ralph-approach`; no production deploy, no migration of user data, no PR to anyone else's repo.

## Sources & References

- **Origin requirements doc:** `docs/brainstorms/2026-04-22-tests-proposed-narrow-yes-no-suite-requirements.md`
- **Parent plan:** `docs/plans/2026-04-22-002-refactor-ralph-style-reviewer-architecture-plan.md`
- **Sibling parent brainstorm:** `docs/brainstorms/2026-04-22-ralph-style-reviewer-architecture-requirements.md`
- **Ralph reference repo:** `chenandrewy/ralph-wiggum-asset-pricing`, branch `ralph/run-final`:
  - `tests/_test_helpers.py`, `tests/clarity.py`, `tests/factcheck.py`, `tests/writing-intro.py`
  - `ralph/run-tests.py` (`--jobs N` pattern)
- **Memory:**
  - `MEMORY.md` → `feedback_word_prose_banned.md` (writing rules for any user-facing output)
  - `MEMORY.md` → `project_ralph_loop_architecture_rationale.md` (why hard-gating works in Ralph architecture)
  - `MEMORY.md` → `project_no_legacy_grandfathering.md` (no parallel-mode preservation)
  - `MEMORY.md` → `project_tests_proposed_poc_framing.md` (PoC framing, deferred future iterations)
- **Related plans:**
  - `docs/plans/2026-04-22-001-feat-advisory-reviewer-non-blocking-plan.md` (advisory mechanism — retired by this plan)
  - `docs/plans/2026-04-20-fix-prevent-orchestrator-preference-injection-plan.md` (preference-loading guidance — applies)
  - `docs/plans/2026-04-20-refactor-flat-parallel-review-cascade-plan.md` (delete-don't-archive principle)
- **Recent commits on `ralph-approach` (parent plan execution):**
  - `e8c442a feat(casm-tools): ralph harness scaffolding (U1)`
  - `ed450c6 feat(casm-tools): port 9 reviewer agents to tests/*.py (U2)` — superseded by this plan's U7
  - `e4c1f25 refactor(casm-tools): rewrite review-document skill for Ralph harness (U3)` — partially superseded by this plan's U6
  - `38862fb`, `a1617ea`, `23ac5b7` — creator-agent inlining (still applies)
  - `52c9643`, `e0bb429`, `2ef7a3b` — final cleanup, hook retirement, state machinery removal (still applies)
