---
title: Treat adversarial reviewer as advisory in paper-* pipelines
type: feat
status: active
date: 2026-04-22
---

# Treat adversarial reviewer as advisory in paper-* pipelines

## Overview

Change the `paper-summarize`, `paper-extend`, and `paper-present` skills so the cascade finalizes even when the adversarial reviewer is the only reviewer that has not passed. The adversarial reviewer stress-tests research assumptions and often raises concerns that cannot be resolved by textual edits alone; today its unresolved CRITICAL items block convergence and can halt the whole paper pipeline. The fix is to introduce an "advisory" reviewer classification in `/CASM-tools:review-document`, teach the loop engine to exclude advisory reviewers from the pass-gate and from the CRITICAL-halt check, and have the three paper-* skills opt the adversarial reviewer into advisory mode.

## Problem Frame

Today `review-document` enforces a single convergence rule: every reviewer in `reviewer_list` must pass (composite ≥ threshold, zero CRITICAL) for the loop to exit cleanly, and any CRITICAL still open at the iteration cap triggers a blocking checkpoint (`halt_cascade_and_checkpoint` in `plugins/CASM-tools/scripts/loop-engine.md` step 4g). When paper-* skills dispatch with scope `all`, adversarial reviewer concerns on a summary or an extension proposal ("this paper's identification rests on an assumption the authors never defend") are treated identically to a writing or math CRITICAL, even though the fixer cannot resolve them without inventing research claims. The practical effect is that paper pipelines hit the cap with unresolved adversarial CRITICALs, suspend, and require manual intervention, even when the remainder of the deliverable is ready to ship.

The user wants the paper-* pipelines to keep running the adversarial pass (so its scorecard remains visible to the researcher) but to stop letting it gate convergence. This generalizes naturally: a reviewer that the caller marks as advisory contributes findings but not a pass requirement.

## Requirements Trace

- R1. `/CASM-tools:review-document` accepts a mechanism for marking specific reviewers as advisory for that invocation.
- R2. Advisory reviewers still run every iteration and still write scorecards into `reviewer-logs/`; their items are still merged into the per-iteration aggregate the fixer applies.
- R3. Convergence check (loop-engine step 4f) passes when every **non-advisory** reviewer passes, regardless of advisory reviewer scores.
- R4. Cap-check halt (loop-engine step 4g) fires only when a **non-advisory** reviewer still has a CRITICAL; advisory CRITICALs never suspend the cascade.
- R5. `paper-summarize`, `paper-extend`, and `paper-present` invoke `/CASM-tools:review-document` with adversarial marked advisory, so the pipeline finalizes whether or not adversarial passes.
- R6. The terminal cascade report and the combined scorecard clearly label which reviewers ran in advisory mode so users can see at a glance that adversarial findings are informational, not gating.
- R7. Behavior outside the paper-* skills is unchanged by default: invoking `/CASM-tools:review-document` without the new token preserves existing semantics for every reviewer.

## Scope Boundaries

- This plan does not change any reviewer's internal scoring rubric or style preferences.
- This plan does not change the fixer's behavior: advisory reviewer items still land in the merged scorecard and the fixer still applies every row exactly. "Advisory" is purely a pass-gate classification, not a fixer filter.
- This plan does not touch the `thorough` audit pass.
- This plan does not promote or demote reviewers based on artifact type; classification is caller-driven only.

### Deferred to Separate Tasks

- Allowing users to mark any reviewer advisory on a one-off invocation beyond the paper-* skills is a natural follow-on but not required for this change; the grammar hook is added here, and the paper-* skills are the first consumers.

## Context & Research

### Relevant Code and Patterns

- `plugins/CASM-tools/skills/review-document/SKILL.md` — argument parsing grammar (closed, additive tokens with "Unknown scope token" strictness), plus announcement block and examples. The new `advisory <reviewer>` clause follows the same shape as the existing `into <dir>`, `threshold <N>`, and `iterations <N>` clauses.
- `plugins/CASM-tools/scripts/loop-engine.md` — canonical state machine. Steps 4f and 4g are the only convergence gates; all advisory logic lives there. The engine already carries per-reviewer state (parse failures set), so adding a per-reviewer advisory set is a natural extension.
- `plugins/CASM-tools/scripts/orchestrate-review.md` — end-to-end cascade protocol (includes finalization report and combined scorecard sections). Needs a small annotation for advisory reviewers.
- `plugins/CASM-tools/skills/paper-summarize/SKILL.md`, `paper-extend/SKILL.md`, `paper-present/SKILL.md` — all three build the same shape of `args` string and hand it to `/CASM-tools:review-document`. The `all adversarial` → `all advisory adversarial` substitution is the only change they need.
- `plugins/CASM-tools/skills/paper-full-pipeline/SKILL.md` — no direct invocation of `/CASM-tools:review-document`; it only calls the three paper-* skills. Narrative text mentions adversarial CRITICAL-cap escalation; that sentence needs to reflect the new posture.

### Institutional Learnings

- The existing `REVIEW_SUSPENDED.md` schema note in loop-engine.md ("suspended under old schema, delete REVIEW_SUSPENDED.md and restart") is the working precedent for how the engine rejects stale state when its shape changes. Any new field added to the resume payload (such as `advisory_reviewers`) needs the same guard.

### External References

- None required. This is an internal engine/grammar change; no external library or framework docs are relevant.

## Key Technical Decisions

- **Advisory is a per-invocation classification, not a per-reviewer property.** A reviewer is not "advisory by nature"; the caller decides. This keeps the grammar additive and keeps existing `/CASM-tools:review-document` invocations untouched.
- **Advisory does not remove items from the fixer's input.** The adversarial reviewer's items still enter the merged scorecard so the fixer attempts any that can be addressed (e.g. sharpening a claim, adding a caveat). Only the pass-gate arithmetic changes. This keeps a single fixer contract and avoids a parallel "advisory fixer" path.
- **Cap check uses non-advisory CRITICAL only.** An advisory reviewer's CRITICAL is informational; letting it halt the cascade would defeat the purpose of marking it advisory in the first place.
- **Grammar: `advisory <reviewer>` as a repeatable clause, not a suffix on the scope token.** `advisory adversarial` parses cleanly in the existing filler-stripped token stream; `adversarial?` or `adversarial:advisory` would require grammar surgery.
- **The announcement block and the combined scorecard label advisory reviewers explicitly.** Users should never have to cross-reference arguments to know whether a reviewer's score was gating.

## Open Questions

### Resolved During Planning

- **Should advisory findings feed the fixer?** Yes. Keeping one merged scorecard and one fixer dispatch preserves the engine's current surgical simplicity; the cost is one extra fixer pass's worth of attempts on items that may not be mechanically fixable, which is cheap compared to an alternative pathway.
- **Should `all` imply any advisory defaults?** No. `all` remains "every reviewer, all gating." The paper-* skills opt in explicitly via the new token.

### Deferred to Implementation

- The exact wording of the advisory annotation in the combined scorecard footer and in the terminal report — to be settled when writing those sections rather than pre-specified here.

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

Grammar extension in `review-document/SKILL.md` — one new clause, parsed in the same pass as `into <dir>`:

```
advisory <reviewer-token>
```

- Repeatable (e.g. `advisory adversarial advisory presentation`).
- `<reviewer-token>` must be a reviewer name already present in the resolved reviewer list; otherwise error: "advisory target '<tok>' is not in the selected reviewer list".
- Produces a set `advisory_reviewers ⊆ reviewer_list` passed to the loop engine alongside `threshold`, `iterations`, and `thorough`.

Convergence logic change in `loop-engine.md` step 4 (pseudo-code sketch, not a literal diff):

```
gating_reviewers = reviewer_list - advisory_reviewers

# step 4f — convergence check
if every r in gating_reviewers passes (composite ≥ threshold AND zero CRITICAL):
    break loop

# step 4g — cap check
if iteration == max_iterations:
    if any r in gating_reviewers has CRITICAL:
        halt_cascade_and_checkpoint(...)
    else:
        break loop
```

Announcement (skill-level) gains one line when advisory is non-empty:

```
cascade: <artifact>
  reviewers: writing-reviewer, structure-reviewer, math-reviewer, adversarial-reviewer, ...
  advisory: adversarial-reviewer
  threshold: 80 (default)
  iterations: 3 (default)
  ...
```

## Implementation Units

- [ ] **Unit 1: Extend the review-document grammar with an `advisory <reviewer>` clause**

**Goal:** Parse the new repeatable clause out of `$ARGUMENTS`, validate each target against the resolved reviewer list, and pass `advisory_reviewers` to the loop engine. Update the announcement block so advisory reviewers are labeled.

**Requirements:** R1, R6, R7

**Dependencies:** None.

**Files:**
- Modify: `plugins/CASM-tools/skills/review-document/SKILL.md`

**Approach:**
- Add a new section `### 1d. Extract advisory <reviewer> clause (optional)` after the existing `1c. iterations` section, mirroring the style of the existing clause sections.
- Specify that `advisory` is a repeatable two-token sequence: each occurrence names exactly one reviewer token (matching the existing scope token table, e.g. `writing`, `math`, `adversarial`). Multiple reviewers require multiple `advisory` clauses.
- Resolve advisory targets against the final reviewer list (the list produced after scope-token expansion and `all` / auto-classification). Error loudly if an advisory target is not selected: `"advisory target '<tok>' is not in the selected reviewer list"`.
- Update the `### 4. Announce` block to print an `advisory:` line listing advisory reviewer names whenever the set is non-empty. Omit the line entirely when the set is empty so existing invocations look unchanged.
- Update the Argument parsing summary sentence at the top of the grammar section to mention the new clause alongside `into`, `threshold`, and `iterations`.
- Add one new worked example under `## Examples` showing a paper-pipeline-style invocation: `all adversarial-advisory paper-extension/paper-summary.md into ...` paired with its announcement output. Use the exact syntax decided above.

**Patterns to follow:**
- `plugins/CASM-tools/skills/review-document/SKILL.md` sections 1a, 1b, 1c (the existing optional-clause sections are the template).
- The `Unknown scope tokens: ...` error phrasing for the validation failure message.

**Test scenarios:**
- Happy path: `/CASM-tools:review-document all advisory adversarial paper-summary.md` → parser extracts `advisory_reviewers = {adversarial-reviewer}`, announcement includes the new `advisory:` line.
- Happy path (multiple): `/CASM-tools:review-document all advisory adversarial advisory presentation slides.qmd` → `advisory_reviewers = {adversarial-reviewer, presentation-reviewer}`.
- Error path: `/CASM-tools:review-document writing advisory adversarial draft.md` → adversarial is not in the selected reviewer list, error matches the spec message.
- Error path: `/CASM-tools:review-document all advisory bogus paper.md` → unknown reviewer token, error matches existing unknown-token phrasing.
- Edge case: No `advisory` clauses at all → behavior identical to today, announcement does not include the `advisory:` line.

**Verification:**
- A walk through the grammar section shows the new clause fits the existing parsing order and produces a set that can be handed to the engine.
- The announcement example in the skill file matches the output shape the engine will print.

- [ ] **Unit 2: Teach the loop engine to treat advisory reviewers as non-gating**

**Goal:** Accept an `advisory_reviewers` input set. Exclude those reviewers from the convergence check (step 4f) and from the cap-check CRITICAL halt (step 4g). Advisory reviewers still dispatch, still merge into the per-iteration scorecard, and still feed the fixer.

**Requirements:** R2, R3, R4, R7

**Dependencies:** Unit 1 (so the grammar actually sources the set), but the engine change can be specified and reviewed independently.

**Files:**
- Modify: `plugins/CASM-tools/scripts/loop-engine.md`

**Approach:**
- Add `advisory_reviewers` to the `## Inputs` section, documented as "subset of `reviewer_list` whose pass/fail status does not gate convergence; default: empty set."
- In the `## State` table, add one row: `advisory_reviewers` — the carried set, used by the convergence and cap checks.
- In `## Main cascade` step 4f, change the condition from "every reviewer in `reviewer_list` passes" to "every reviewer in `reviewer_list \ advisory_reviewers` passes." Leave the merge and dispatch logic untouched: advisory reviewers still run and still merge.
- In step 4g, change the CRITICAL-remaining test to check only reviewers in `reviewer_list \ advisory_reviewers`. Document that advisory CRITICALs are informational and will appear in the combined scorecard.
- Extend the `REVIEW_SUSPENDED.md` schema note (step 2 and the Recovery actions row about "Old-schema REVIEW_SUSPENDED.md") so a suspended file missing the `advisory_reviewers` field is treated as pre-advisory (default: empty set, no halt). This preserves forward compatibility with suspended cascades from before this change.

**Patterns to follow:**
- The existing way `reviewer_parse_failures` is carried as a set in state and referenced in convergence arithmetic.
- The "Old-schema" rejection note already in place for the prior tiered design — use the same pattern for the new `advisory_reviewers` resume field.

**Test scenarios:**
- Happy path: all gating reviewers pass, advisory reviewer fails with CRITICAL → convergence check at 4f succeeds, loop exits, cascade finalizes. Advisory reviewer's CRITICAL appears in the combined scorecard but does not trigger suspension.
- Edge case: only advisory reviewers are selected (`reviewer_list == advisory_reviewers`, `gating_reviewers == ∅`) → 4f's "every gating reviewer passes" is vacuously true on iteration 1; the loop exits immediately. Document this as intentional (the caller explicitly said "nothing is gating").
- Error path: gating reviewer has CRITICAL at cap → halt_cascade_and_checkpoint fires exactly as today, regardless of advisory reviewer status.
- Integration: advisory reviewer's items appear in `iter[N]-merged.md` and are applied by the fixer just like any other reviewer's items. No filtering at the merge step.
- Edge case: resume from an old `REVIEW_SUSPENDED.md` written before this change (no `advisory_reviewers` field) → engine defaults to empty set, behavior is identical to current.

**Verification:**
- Walking through the state machine with `reviewer_list = {writing, math, adversarial}`, `advisory_reviewers = {adversarial}`, and a scenario where adversarial has CRITICAL while writing and math pass: the loop exits at 4f after one iteration.
- Walking through the cap case with the same `advisory_reviewers` set and only an advisory CRITICAL remaining at the cap: the cascade finalizes rather than halting.

- [ ] **Unit 3: Surface advisory status in the combined scorecard and terminal report**

**Goal:** Ensure downstream consumers (users, meta-review) can tell at a glance that an adversarial section of the scorecard was advisory. No logic change, only annotation.

**Requirements:** R6

**Dependencies:** Unit 2 (the engine knows the advisory set).

**Files:**
- Modify: `plugins/CASM-tools/scripts/orchestrate-review.md`

**Approach:**
- In the Finalization / combined scorecard section, add a brief convention: reviewers marked advisory for the cascade are tagged `(advisory)` next to their name in the per-iteration table and in the summary header. Their composite score is still included in the table but the advisory tag makes clear it was not gating.
- In the terminal report specification, add one line noting advisory reviewers after the reviewer list (parallel to the `advisory:` line in the skill announcement).
- Leave the wording intentionally minimal; the goal is visibility, not a new report schema.

**Patterns to follow:**
- The existing `thorough audit` annotation style in the terminal report is the closest precedent: compact, only present when relevant.

**Test scenarios:**
- Integration: an advisory adversarial run produces a combined scorecard where adversarial's table rows and summary header carry the `(advisory)` tag; the terminal report shows the new line.
- Edge case: no advisory reviewers → combined scorecard and terminal report look identical to today (no dangling labels).

**Verification:**
- A reader of the combined scorecard can identify without reading the invocation logs which reviewers were gating.

- [ ] **Unit 4: Opt adversarial into advisory mode in the three paper-* skills**

**Goal:** The paper-summarize, paper-extend, and paper-present skills pass `advisory adversarial` when invoking `/CASM-tools:review-document`. Pipeline documentation is updated to describe the new posture.

**Requirements:** R5

**Dependencies:** Unit 1 (grammar exists), Unit 2 (engine honors it).

**Files:**
- Modify: `plugins/CASM-tools/skills/paper-summarize/SKILL.md`
- Modify: `plugins/CASM-tools/skills/paper-extend/SKILL.md`
- Modify: `plugins/CASM-tools/skills/paper-present/SKILL.md`
- Modify: `plugins/CASM-tools/skills/paper-full-pipeline/SKILL.md`

**Approach:**
- In `paper-summarize/SKILL.md` step 4, change the `args` string from `"all paper-extension/paper-summary.md into ..."` to `"all paper-extension/paper-summary.md advisory adversarial into ..."`. Update the prose paragraph describing the cascade to note that adversarial findings are advisory: they still appear in the combined scorecard but do not gate convergence.
- Apply the same args change and prose note in `paper-extend/SKILL.md` step 5.
- Apply the same args change and prose note in `paper-present/SKILL.md` step 5 (both artifacts; the advisory token follows the same ordering rule regardless of how many paths are passed).
- In `paper-full-pipeline/SKILL.md`, update the framing paragraph so the "CRITICAL escalation" sentence acknowledges that adversarial CRITICALs no longer trigger suspension in this pipeline; only the non-adversarial reviewers can drive a pipeline to halt at the cap.

**Patterns to follow:**
- The existing `into <dir>` clause usage pattern in these same skill files is the template for how to position the new token in the `args` string.

**Test scenarios:**
- Integration: run paper-summarize end-to-end on a paper where adversarial raises a CRITICAL that cannot be surgically resolved (e.g. a core identification concern). Expect the cascade to finalize, the final summary to install at the live path, and the adversarial CRITICAL to appear in the combined scorecard with the `(advisory)` tag.
- Integration: run paper-extend end-to-end on a paper where adversarial raises a MAJOR concern but every other reviewer passes. Expect the cascade to exit via 4f on the first clean iteration, regardless of adversarial's score.
- Edge case: a user invokes `paper-summarize` and also wants adversarial to gate (overriding the default). Document in each skill's `## Notes` section that advanced users can call `/CASM-tools:review-document all <path>` directly to get the old gating behavior; the paper-* skills intentionally default to advisory adversarial.

**Verification:**
- Reading each skill's dispatch section confirms the new args string and the prose note on advisory adversarial.
- A dry run (read-through) of paper-full-pipeline shows the updated narrative matches the new halt criteria.

## System-Wide Impact

- **Interaction graph:** The only coupling that changes is between review-document's grammar parser, the loop engine's convergence checks, and the orchestrate-review report. All other reviewer-facing and fixer-facing contracts are unchanged.
- **Error propagation:** Advisory reviewer CRITICALs no longer propagate into cascade suspension. Non-advisory CRITICAL propagation is byte-for-byte unchanged.
- **State lifecycle risks:** `REVIEW_SUSPENDED.md` gains an `advisory_reviewers` field; cascades suspended before this change resume with an empty set and behave identically to today. A cascade suspended after this change that is resumed by a pre-upgrade engine build would be a downgrade scenario, which is out of scope.
- **API surface parity:** The other skill surfaces (meta-review consumers, downstream readers of combined-scorecard.md) gain the `(advisory)` tag but no schema break; nothing was removed, only annotated.
- **Integration coverage:** The most important integration test is paper-summarize end-to-end with a real adversarial-failing paper; unit-level engine walkthroughs are necessary but not sufficient because the fixer/merge seam is where accidental filtering would most easily leak in.
- **Unchanged invariants:** Fixer contract (apply every row exactly, never write outside `target_path`), reviewer dispatch contract (fresh per iteration, two-field prompt), thorough audit semantics (informational, no fixes), lockfile protocol, hash guard against external edits.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Users invoke `/CASM-tools:review-document` with `advisory <tok>` and misspell a reviewer name, assuming silent no-op | Grammar validates advisory targets against the resolved reviewer list and errors loudly with the existing unknown-token phrasing. |
| Advisory adversarial items end up silently dropped from the fixer's scope, defeating the fix-what-can-be-fixed intent | Unit 2 explicitly leaves the merge step untouched; the only change is the pass-gate arithmetic. The test scenarios call this out. |
| Users forget that advisory adversarial is the default in paper-* skills and expect a halt | Each skill's dispatch section prints the advisory line in the announcement and calls it out in prose. The meta-review skill already reads the combined scorecard, so historical signals remain visible. |
| Pre-change `REVIEW_SUSPENDED.md` files cause an engine error on resume | Loop-engine spec explicitly documents that missing `advisory_reviewers` defaults to empty set (forward-compatible). |
| Old-style `REVIEW_SUSPENDED.md` that carries a `tier` field is still rejected as today | Unchanged: the existing "suspended under old schema" guard is not modified by this plan. |

## Documentation / Operational Notes

- Each of the four paper-* skill files gets a short prose note near its cascade dispatch section describing the advisory-adversarial posture, so future maintainers do not assume adversarial is a gating reviewer for paper deliverables.
- No user-facing changelog is required beyond the README-level touch inside the skill files themselves, but if the plugin carries a CHANGELOG it should gain one line.

## Sources & References

- Primary reference: `plugins/CASM-tools/scripts/loop-engine.md` (steps 4f, 4g, inputs, state, resume guard).
- Primary reference: `plugins/CASM-tools/skills/review-document/SKILL.md` (grammar sections 1a–1c as templates).
- Orchestration reference: `plugins/CASM-tools/scripts/orchestrate-review.md` (finalization and combined scorecard sections).
- Consumers: `plugins/CASM-tools/skills/paper-summarize/SKILL.md`, `paper-extend/SKILL.md`, `paper-present/SKILL.md`, `paper-full-pipeline/SKILL.md`.
- Related prior plan: `docs/plans/2026-04-20-refactor-flat-parallel-review-cascade-plan.md` (the current cascade shape) and `docs/plans/2026-04-20-fix-prevent-orchestrator-preference-injection-plan.md` (for the dispatch-prompt discipline the new grammar must not violate).
