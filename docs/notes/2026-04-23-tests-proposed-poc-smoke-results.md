---
created: 2026-04-23
status: pending-user-execution
plan: docs/plans/2026-04-22-003-refactor-narrow-test-catalog-and-profile-grammar-plan.md
---

# Tests-Proposed PoC Smoke Results

This note records the U9 convergence smoke check from the PoC plan. The
implementation (U1–U8) is complete; this note is filled in **after the user
runs the smoke check**, since the cascade burns claude API credits and the
user should drive it interactively to see what the loop does on a real
artifact.

## How to run

### Stage 1: architecture validation on `writing` profile

Pick a small text artifact — a recent committed brainstorm or plan in
`docs/`. Suggested fixtures:

- `docs/brainstorms/2026-04-22-tests-proposed-narrow-yes-no-suite-requirements.md` (the user's own requirements doc — they already know what's good and bad about it)
- Any of the recent `docs/plans/*.md` files
- The synthetic fixture: `plugins/CASM-tools/tests/fixtures/synthetic-paper.qmd`

Run:

```
/CASM-tools:review-document writing <doc> into docs/reviews/poc-smoke-stage1-2026-04-23/ iterations 3
```

The `writing` profile runs 14 narrow tests in parallel. Observe:
- Does the cascade reach `verdict: PASS` within 3 iterations, EXHAUST cleanly, or crash?
- Do any tests fire FAIL on content the user considers fine? (false positives)
- Do any tests PASS on content the user considers problematic? (false negatives — harder to detect without spot-checking)

### Stage 2: coverage validation on `paper-source` profile

Run against the synthetic paper fixture:

```
/CASM-tools:review-document paper-source plugins/CASM-tools/tests/fixtures/synthetic-paper.qmd --references plugins/CASM-tools/tests/fixtures/references.bib --jobs 8 into docs/reviews/poc-smoke-stage2-2026-04-23/ iterations 5
```

`paper-source` runs 32 tests in parallel; `--jobs 8` caps the worker pool to
avoid hitting API rate limits. Optional follow-up: run against a real
in-progress economics paper draft if one is available in Quarto form.

## Expected outcomes per stage

| Outcome | What it means | What to do |
|---|---|---|
| Converged with no false positives | PoC validates this profile end-to-end | Record iteration count + final summary-table.md path |
| Converged with notable false positives | PoC validates with caveat | List per-test prompt tuning needs below; spawn follow-up tasks for each |
| EXHAUSTED with diagnosable cause | PoC still validates if EXHAUSTED.md shows the triage path is clear | Identify root cause (over-constrained test → relax/prune; cap too tight → raise to 10; writer limitation → escalate) |
| EXHAUSTED with INCONCLUSIVE-regression flag | Writer is gaming the loop | Tighten author-plan.py prompt and re-run |
| Loop crashes or produces incoherent output | Halt; fix before further work | Diagnose script crash; restore from prior commit if needed |

## Stage 1 results

_(fill in after running)_

- **Date run:**
- **Document:**
- **Iterations:**
- **Final verdict:**
- **Summary-table.md or EXHAUSTED.md path:**
- **False positives observed:**
- **Per-test tuning needs:**

## Stage 2 results

_(fill in after running)_

- **Date run:**
- **Document:**
- **Iterations:**
- **Final verdict:**
- **INCONCLUSIVE-count:**
- **INCONCLUSIVE-regression flagged:**
- **Summary-table.md or EXHAUSTED.md path:**
- **False positives observed:**
- **Per-test tuning needs:**

## Triage decisions

_(fill in after both stages — list any plan updates, test-prompt adjustments,
or follow-up tasks identified)_

## Plan-status update

After running both stages, update the parent plan
(`docs/plans/2026-04-22-003-refactor-narrow-test-catalog-and-profile-grammar-plan.md`)
frontmatter to `status: superseded` ONLY if both stages pass cleanly OR the
issues found are documented as deferred follow-ups. If the smoke check
reveals an architectural problem (writer gaming, persistent EXHAUSTED across
multiple representative artifacts), keep `status: active` and create a
follow-up plan to address the architectural issue.
