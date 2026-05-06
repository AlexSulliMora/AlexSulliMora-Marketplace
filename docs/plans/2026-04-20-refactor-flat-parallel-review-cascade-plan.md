---
title: Refactor review-document cascade to flat parallel review with consolidated fixer dispatch
type: refactor
status: active
date: 2026-04-20
---

# Refactor review-document cascade to flat parallel review with consolidated fixer dispatch

## Overview

Replace the five-tier sequential cascade in `/CASM-tools:review-document` with a flat parallel loop. All selected reviewers run in parallel against the current snapshot; the orchestrator merges every reviewer's scorecard into a single aggregated list and dispatches the fixer once per iteration against that list. The loop terminates when all reviewers pass (composite >= 90 AND zero CRITICAL) or after 3 iterations. On convergence, the orchestrator dispatches a final fixer pass to apply remaining MAJOR/MINOR items. `thorough` keeps its current semantics: an informational audit pass after finalization with no fixes applied.

The cascade is entirely doc-driven — no executable state machine code exists — so this refactor is a coordinated rewrite of the four documents in `plugins/CASM-tools/scripts/` and the SKILL text that point at them, plus small follow-on edits in downstream consumers.

## Problem Frame

Today's cascade runs five sequential tiers, each with its own 3-iteration inner loop plus a tier-cleanup fixer pass. This was chosen to resolve cross-reviewer conflicts by ordering (structure before writing, simplicity before writing, etc.) and to avoid wasted rewrites when an upstream fix invalidates a downstream one. Total maximum work per cascade: up to 15 reviewer iterations plus 5 cleanup dispatches plus one thorough audit.

The user wants a simpler shape: one parallel pass, one consolidated fix, up to 3 iterations total, plus one final cleanup on convergence. This trades tier-ordered conflict resolution for a flatter, faster loop with lower context cost per run. `thorough` continues to exist as an audit-only convergence check.

## Requirements Trace

- R1. All selected reviewers run in parallel against the current snapshot in every iteration (no tiers).
- R2. The orchestrator merges all reviewer scorecards from an iteration into one aggregated required-changes list; the fixer reads that single aggregate and applies every item.
- R3. The iteration loop terminates when every reviewer passes (composite >= 90 AND zero CRITICAL), or when iteration 3 completes, whichever comes first.
- R4. On convergence, the orchestrator dispatches the fixer once more with the final iteration's remaining MAJOR/MINOR items as the scorecard, then finalizes.
- R5. When iteration 3 completes with any CRITICAL remaining, the cascade halts and escalates per today's `REVIEW_SUSPENDED.md` protocol (same as today's per-tier cap-with-CRITICAL behavior).
- R6. `thorough` continues to mean "run all originally-selected reviewers once more in parallel against the finalized version, save to `thorough/`, apply no fixes". Behavior unchanged.
- R7. Downstream consumers that read the review logs (meta-review skill, session-log template) must keep working with the new directory layout.

## Scope Boundaries

- This refactor does not change the reviewer agent contracts (scorecard format, scoring rubric, "never fix content" rule, preference-injection hook). Those sit in `reviewer-common.md` and the individual reviewer agents and stay as-is except for the inert `tier:` frontmatter field noted below.
- This refactor does not change the fixer's per-dispatch contract (source_path, target_path, scorecard_path → apply every row). Only the upstream merging changes.
- This refactor does not touch the `state/` layout (session registry, inline materialization, lockfiles).
- This refactor does not add a rollback or compatibility shim for cascades suspended under the old schema. A cascade suspended by the old tiered engine that hasn't been resumed by the time this lands must be discarded — the `REVIEW_SUSPENDED.md` format changes. This is a cold-start breaking change, acceptable because suspensions are rare and short-lived.
- `paper-summarize`, `paper-extend`, `paper-present`, and `paper-full-pipeline` invoke `/CASM-tools:review-document` via the `into <dir>` clause and do not read the log layout themselves. They need no changes.

## Context & Research

### Relevant Code and Patterns

Primary files that define the cascade (all doc-driven):

- `plugins/CASM-tools/scripts/loop-engine.md` — the state machine spec (hash, dispatch, parse, aggregate, recover). Currently tier-structured.
- `plugins/CASM-tools/scripts/orchestrate-review.md` — end-to-end narrative: directory layout, loop structure, pass/fail rules, finalization, session-log updates. Currently tier-structured.
- `plugins/CASM-tools/scripts/reviewer-tiers.md` — defines the five tiers and the reviewer-to-tier mapping. Deletable under the new design.
- `plugins/CASM-tools/skills/review-document/SKILL.md` — user-facing surface (scope-token grammar, artifact resolution, tier-grouped announcement, examples). Tier terminology is woven through.
- `plugins/CASM-tools/scripts/session-log-template.md` — template uses per-tier iteration entries.
- `plugins/CASM-tools/scripts/reviewer-common.md` — shared reviewer protocol. Already tier-agnostic; no changes needed.

Secondary consumers and dependencies:

- `plugins/CASM-tools/skills/meta-review/SKILL.md` — reads scorecards from `reviewer-logs/tier[T]-iter[N]-merged.md`. Needs path update.
- `plugins/CASM-tools/agents/fixer.md` — core contract is tier-agnostic; only its examples and one descriptive sentence reference tier-cleanup.
- `plugins/CASM-tools/agents/{writing,structure,math,code,simplicity,adversarial,presentation,consistency,factual}-reviewer.md` — each carries an inert `tier: N` frontmatter field. No hook parses it (`hooks/inject-preferences.py` maps by subagent_type name only). Deletable.

The preference-injection hook is tier-agnostic: it maps subagent_type → preferences filename. No changes needed.

### Patterns to Preserve

- Snapshot versioning remains monotonic: `v1` = baseline (write-once), `v2..vN` = revisions, `final` = copy of the installed version.
- Version names stay `<artifact>-v<N>.md`. Only the reviewer-log subdirectory naming changes.
- Fixer contract: exactly three input paths (`source_path`, `target_path`, `scorecard_path`), writes only `target_path`, applies every row. Unchanged.
- External-edit detection via `live_file_hash` at every iteration boundary. Unchanged.
- Lock protocol via `state/locks/<artifact_hash>.lock`. Unchanged.
- Parse validation on reviewer scorecards. Unchanged.
- `into <dir>` clause behavior. Unchanged.
- Auto-resume from `REVIEW_SUSPENDED.md` after a CRITICAL-at-cap halt. Semantics unchanged, but the serialized state shape is smaller (no tier field, no `tier_scorecard_paths` map).

## Key Technical Decisions

- **Merge location: orchestrator-side, not fixer-side.** The user's phrasing ("have the fixer read all reviewer outputs at once, consolidate them") literally suggests the fixer ingests N scorecards. This plan keeps the merge in the orchestrator (producing a single `iter[N]-merged.md` that the fixer reads) because (a) the resulting behavior is identical, (b) the fixer's current "one scorecard in, apply every row" contract stays narrow and testable, (c) parse failures and conflict resolution already live on the orchestrator side for the tiered design. If the user wants the fixer to do the merging itself, the fixer agent body would need a new merge protocol — flag this for user override at plan approval.

- **Conflict handling relies on fixer severity priority + unapplicable-row skip.** The tiered design avoided same-sentence conflicts by ordering (structure before writing, simplicity before writing). The flat design loses this. Conflicts are resolved by the fixer's existing rules: apply CRITICAL → MAJOR → MINOR; when two rows contradict at the same location, the first-applied wins and the second is recorded as unapplicable. This is a real regression in conflict-resolution quality but is what the user's design implies. Flagged in Risks.

- **One global 3-iteration cap replaces the previous per-tier cap.** Maximum reviewer iterations per cascade drops from up to 15 to 3. For routine artifacts this is fine; for complex artifacts that historically needed late-tier iterations to converge, this will produce more CRITICAL-at-cap halts. Flagged in Risks.

- **Convergence still runs one more fixer pass.** Even when every reviewer passes (composite >= 90, zero CRITICAL), remaining MAJOR/MINOR items are applied by a final cleanup fixer dispatch before finalization. No re-review after that cleanup. This mirrors the spirit of today's tier-cleanup passes, applied once globally instead of once per tier.

- **Cap-with-CRITICAL halt preserves current escalation.** At iteration 3 with any CRITICAL remaining: halt, write `REVIEW_SUSPENDED.md` capturing the flat state (iteration, version, reviewer_list, thorough flag, logs_dir), release lock, prompt the user. Next invocation auto-resumes. Same ergonomics as today.

- **Log directory layout drops the tier dimension.** New names:
  - `reviewer-logs/iter[N]-<reviewer>.md` (was `reviewer-logs/tier[T]-iter[N]-<reviewer>.md`)
  - `reviewer-logs/iter[N]-merged.md` (was `reviewer-logs/tier[T]-iter[N]-merged.md`)
  - `final-cleanup-request.md` at the top of `logs_dir` (replaces the per-tier `tier[T]-cleanup-request.md`)
  - `<artifact>-final.md`, `<artifact>-v<N>.md`, `<artifact>-combined-scorecard.md`, `thorough/<reviewer>-thorough.md`, `thorough/combined-scorecard.md` stay the same.

- **`reviewer-tiers.md` is deleted, not archived.** The doc's content (tier rationale, ordering choices, tier table) has no function under the new design. Keeping it invites confusion for future readers. The historical motivation is captured briefly in the new `orchestrate-review.md` under a "Why flat rather than tiered" note so the design history is not lost.

- **Reviewer agent `tier: N` frontmatter is removed.** Inert metadata; unused by any hook or orchestrator. Keeping it after deleting `reviewer-tiers.md` would be a broken reference. Safe to remove.

- **The thorough audit hook stays simple.** The audit has always been "run every originally-selected reviewer once in parallel against the final version; save scorecards; apply nothing". That stays literally the same; only the phrase "after all tiers finish" becomes "after the cascade finalizes" in the docs.

## Open Questions

### Resolved During Planning

- Q: Should `thorough` become an opt-in escape hatch back to the tiered cascade? — No. The user confirmed `thorough` keeps today's audit-only semantics attached to the new flat flow.
- Q: What happens at iteration cap with CRITICAL remaining? — Halt + escalate + `REVIEW_SUSPENDED.md`, same as today's per-tier cap.
- Q: Is there always a final fixer pass on convergence? — Yes. Apply remaining MAJOR/MINOR; no re-review.
- Q: Where does consolidation live (orchestrator vs fixer)? — Orchestrator. The fixer contract stays narrow; the merged scorecard is its input. See Key Technical Decisions.
- Q: Is `reviewer-tiers.md` deleted or archived? — Deleted. A short historical note lands in `orchestrate-review.md`.

### Deferred to Implementation

- The exact wording of the "Why flat rather than tiered" historical note in `orchestrate-review.md`. Keep short, name the tradeoff (simpler loop, lost tier-ordered conflict resolution, lower iteration budget), and link to this plan as the change's origin.
- Whether the per-iteration session-log entry format should carry a new field for "items applied this iteration" (the fixer's effective change count). Current template has "Key changes requested" which can serve. Decide while writing Unit 4.
- Whether iteration 3 with CRITICAL halt should write a distinct `REVIEW_SUSPENDED_v2.md` filename to signal the new format, or reuse `REVIEW_SUSPENDED.md` and rely on content-shape validation on resume. Decide while writing Unit 1.

## Implementation Units

- [ ] **Unit 1: Rewrite cascade mechanics for flat parallel loop (loop-engine.md + orchestrate-review.md)**

**Goal:** Specify the new flat parallel algorithm authoritatively across the two cascade docs. The state machine (loop-engine) and the end-to-end narrative (orchestrate-review) must stay in sync, so they land in one atomic change.

**Requirements:** R1, R2, R3, R4, R5, R6

**Dependencies:** None.

**Files:**
- Modify: `plugins/CASM-tools/scripts/loop-engine.md`
- Modify: `plugins/CASM-tools/scripts/orchestrate-review.md`

**Approach:**

In `loop-engine.md`:
- Drop `tier_assignment` from Inputs. Keep `artifact_path`, `reviewer_list`, `logs_dir`, `thorough`, `session_id`.
- Replace the Directory layout block with the new layout (`iter[N]-<reviewer>.md`, `iter[N]-merged.md`, `final-cleanup-request.md`, unchanged version names).
- Rewrite State table: drop `tier` and `tier_scorecard_paths`; keep `phase` (now `loop` / `cleanup` / `thorough` / `finalize`), `iteration`, `version`, `current_snapshot_path`, `live_file_hash`, `lockfile_path`, `reviewer_parse_failures`. Add `final_scorecard_path` pointing to the last iteration's merged scorecard (input to the convergence-cleanup fixer).
- Rewrite the Main cascade pseudocode as a single loop:
  1. acquire_lock, check suspend, snapshot baseline to v1 (write-once).
  2. For iteration in 1..3:
     - Hash-check the live file; halt on external-edit.
     - Dispatch all reviewers in `reviewer_list` in parallel against `current_snapshot_path`; each writes `reviewer-logs/iter[N]-<reviewer>.md`.
     - Collect scorecards, validate, handle parse failures per existing recovery table.
     - Merge into `reviewer-logs/iter[N]-merged.md`.
     - Update session log.
     - If every reviewer passes (composite >= 90 AND zero CRITICAL): set `final_scorecard_path` and break.
     - If iteration == 3 and any CRITICAL remains: halt via `halt_cascade_and_checkpoint`.
     - Else if iteration == 3 (no CRITICAL): set `final_scorecard_path` and break.
     - Else: dispatch fixer (source = current_snapshot_path, target = v[version+1], scorecard = `iter[N]-merged.md`); increment version; continue.
  3. Convergence cleanup (always runs after the loop, unless the halt path fired):
     - outstanding = MAJOR/MINOR rows in `final_scorecard_path`.
     - If outstanding is empty: skip cleanup.
     - Else: write `final-cleanup-request.md` using the same template as today's tier-cleanup request; dispatch fixer once; increment version. No re-review.
  4. Thorough phase (only if `thorough=true`): unchanged semantics — dispatch all reviewers in parallel against the final snapshot, save under `thorough/`, merge, apply nothing.
  5. Write `<artifact>-combined-scorecard.md` in the new format (see orchestrate-review below).
  6. Finalize: copy final snapshot to `<artifact>-final.md` and over `artifact_path`; release lock.
- Update the Recovery actions table: drop per-tier references; keep all other rows.
- Update Fixer dispatch contract section: unchanged prose, update one sentence that calls the scorecard a "merged tier scorecard" to say "merged iteration scorecard or the convergence-cleanup request".
- Update Tier cleanup request format section: rename to "Convergence cleanup request format"; change filename to `final-cleanup-request.md`; header becomes `# Convergence cleanup request — [artifact] — v[N+1]`.
- Resolve the deferred question on `REVIEW_SUSPENDED.md`: reuse the name; on resume, detect shape by presence of the old `tier` field and error with "suspended under old schema, discard and restart" if detected. Document this in Recovery actions.

In `orchestrate-review.md`:
- Rewrite the introductory paragraph and the "Loop Structure" section to describe the new single-loop algorithm.
- Replace the directory-layout diagram with the new layout.
- Replace the Loop Structure pseudocode with the narrative-level version of the state machine above (cross-reference loop-engine.md for mechanics).
- Add a new short section "Why flat rather than tiered" recording the tradeoff: simpler loop, reduced maximum iteration budget, loss of tier-ordered conflict resolution relied on fixer severity priority. Link this plan file.
- Rewrite the Combined Scorecard format: replace per-tier rows in the cascade summary with per-iteration rows plus one convergence-cleanup row plus one thorough row. Version trail still monotonic.
- Rewrite the Terminal report format with the same per-iteration + cleanup + thorough shape.
- Rewrite the Pass/Fail Rules section: drop "tier pass"; use "iteration pass" (every reviewer in `reviewer_list` scores composite >= 90 AND zero CRITICAL); retain the CRITICAL-at-cap halt behavior.
- Rewrite Iteration accounting: version numbering monotonic across the loop iterations and the convergence cleanup; thorough pass does not produce a new version. Session log records one entry per iteration plus one cleanup entry plus one finalization entry.
- Rewrite Cap exhaustion section to describe the single global 3-iteration cap.
- Remove the Report File Naming subsections that reference `tier[T]-*` naming; replace with the `iter[N]-*` naming.
- Remove the "Severity priority within a fixer dispatch" section's trailing paragraph about tier scope handling cross-reviewer sequencing; the new flat design leans on severity alone.

**Patterns to follow:**
- Keep every "unchanged" invariant from Context & Research (snapshot versioning, fixer contract, external-edit detection, lock protocol, parse validation, `into <dir>`, thorough semantics).
- Match the prose register and section ordering of the current docs; this is a minimal-diff rewrite where possible.

**Test scenarios:**
- Test expectation: none -- pure documentation refactor. Verification is via a manual integration invocation in Unit 4's verification step (dispatch `/review-document` against a small artifact after all four units land and confirm the log directory, combined scorecard, and terminal report match the new shape).

**Verification:**
- `loop-engine.md` describes exactly one nested loop (iterations 1..3 with an inner dispatch + fixer step), a convergence-cleanup block, a thorough block, and a finalize block. No `for tier in 1..5` remains.
- `orchestrate-review.md` contains zero literal references to "tier 1", "tier 2", etc., outside the "Why flat rather than tiered" historical note.
- The directory-layout diagrams in both files are byte-identical to each other.
- A reader following only these two files can answer: what file does the fixer read each iteration? where does the convergence-cleanup scorecard live? what is the combined scorecard's cascade-summary row shape? under what condition does the cascade halt?

- [ ] **Unit 2: Update review-document SKILL.md to surface the flat parallel flow to users**

**Goal:** Bring the skill's user-facing documentation into alignment with the new cascade mechanics. Every tier-shaped announcement, example, cascade-behavior bullet, and anti-pattern needs updating.

**Requirements:** R1, R3, R5, R6

**Dependencies:** Unit 1. The SKILL cites `loop-engine.md` and `orchestrate-review.md` and must match their new shape.

**Files:**
- Modify: `plugins/CASM-tools/skills/review-document/SKILL.md`

**Approach:**
- Update the frontmatter `description`: replace "tiered cascade" with "parallel review cascade" or similar; drop the "tier" word.
- Update the intro paragraph ("Run the creator/reviewer tiered cascade..."): describe the flat parallel + convergence-cleanup + optional thorough model in one sentence, matching the new mechanics.
- Remove the reference to `${CLAUDE_PLUGIN_ROOT}/scripts/reviewer-tiers.md` from the introduction. Replace with a two-reference pointer to `orchestrate-review.md` and `loop-engine.md`.
- Update the scope-token table row for `thorough`: replace "run a final audit pass after all tiers finish" with "run a final audit pass after the cascade finalizes".
- Rewrite the Announce section:
  - Replace the tier-grouped multi-line announcement block with a single-line flat list: `cascade: <artifact-path>\n  reviewers: <r1>, <r2>, ...\n  thorough audit: ON (requested)   <-- only if present`.
  - Rewrite the "If no tier has an applicable reviewer" error to "If no reviewer applies to this artifact".
- Rewrite the Cascade section's "Key cascade behaviors" bullets to describe:
  - All selected reviewers dispatched in parallel each iteration.
  - Orchestrator merges all scorecards into one aggregate; fixer reads the aggregate.
  - Loop ends on all-pass or at iteration 3.
  - On convergence, a single fixer dispatch applies remaining MAJOR/MINOR before finalization.
  - `thorough` runs the audit after finalization.
- Rewrite the Cascade section's other bullets to drop tier-specific claims (e.g. the current "Tiers run sequentially; reviewers within a tier run in parallel" bullet becomes "Reviewers within an iteration run in parallel; iterations run sequentially; each iteration ends with one fixer dispatch").
- Rewrite each example in the Examples section:
  - Drop tier-grouped announcement output; use the new flat list format.
  - Keep the same invocation strings and same artifacts.
  - The "Thorough audit" example keeps the `thorough` token; announcement adds the single `thorough audit: ON` line.
  - The "Path-only invocation" example loses tier-specific lines and becomes `cascade: analysis.py\n  reviewers: code-reviewer, simplicity-reviewer`.
- Rewrite the Failure modes table:
  - Replace "Tier cap hit with CRITICAL remaining" with "Iteration cap hit with CRITICAL remaining".
  - Replace "Tier cleanup fixer skipped an item" with "Convergence cleanup fixer skipped an item".
- Rewrite Anti-patterns:
  - Drop the two anti-patterns that are now moot: "Do NOT dispatch reviewers across tiers in parallel" and "Do NOT dispatch reviewers within a single tier serially".
  - Keep the remaining anti-patterns as-is (live-file modification, main-session revisions, reviewer SendMessage reuse, mode flag, thorough-apply, unknown scope, interactive checkpoint).
  - Add one new anti-pattern: "Do NOT dispatch the fixer N times per iteration (once per reviewer). The aggregate scorecard is the fixer's single input per iteration."
- Update the Artifact resolution section if it references tier-specific behavior; preserve the auto-resume detection.

**Patterns to follow:**
- Preserve the closed scope-token grammar unchanged — no new tokens, no removed tokens.
- Preserve every sentence about preference injection, artifact-name constraints, lockfile protocol, and `into <dir>` semantics verbatim.

**Test scenarios:**
- Test expectation: none -- documentation update. Verified manually in Unit 4's integration check.

**Verification:**
- The SKILL.md file contains zero literal occurrences of `tier-cleanup`, `reviewer-tiers.md`, or `tier 1 (shape)`-style announcement lines.
- A user reading only SKILL.md can answer: how many iterations will my cascade run at most? where is the final version installed? how do I trigger the informational audit? what happens if the reviewers can't drive a CRITICAL to zero?
- The examples still produce output matching the new announcement format.

- [ ] **Unit 3: Delete reviewer-tiers.md, strip `tier:` frontmatter from reviewer agents, clean up fixer.md**

**Goal:** Remove every surviving tier artifact from the codebase so there are no broken references.

**Requirements:** R1 (by removing the only source of tier metadata)

**Dependencies:** Unit 1 and Unit 2. Nothing should still cite `reviewer-tiers.md` or the `tier:` frontmatter after those units land.

**Files:**
- Delete: `plugins/CASM-tools/scripts/reviewer-tiers.md`
- Modify: `plugins/CASM-tools/agents/fixer.md`
- Modify: `plugins/CASM-tools/agents/writing-reviewer.md`
- Modify: `plugins/CASM-tools/agents/structure-reviewer.md`
- Modify: `plugins/CASM-tools/agents/math-reviewer.md`
- Modify: `plugins/CASM-tools/agents/code-reviewer.md`
- Modify: `plugins/CASM-tools/agents/simplicity-reviewer.md`
- Modify: `plugins/CASM-tools/agents/adversarial-reviewer.md`
- Modify: `plugins/CASM-tools/agents/presentation-reviewer.md`
- Modify: `plugins/CASM-tools/agents/consistency-reviewer.md`
- Modify: `plugins/CASM-tools/agents/factual-reviewer.md`

**Approach:**
- Run `git rm plugins/CASM-tools/scripts/reviewer-tiers.md`.
- Grep for any remaining references to `reviewer-tiers.md` and `reviewer-tiers` across the plugin directory; expect zero hits after Units 1-2.
- In each reviewer agent frontmatter, remove the `tier: N` line. Preserve every other frontmatter field (`name`, `description`, `model`, `color`, `tools`) exactly.
- In `fixer.md`:
  - Replace the `<example>` block body "Apply the tier 1 scorecard to slides-v1.md" → "Apply iteration 3's merged scorecard to slides-v3.md".
  - Replace the `<example>` block body "Run cleanup for tier 4" → "Run the convergence cleanup pass".
  - Replace the matching assistant lines to remove the "tier" word.
  - In the Inputs section, rewrite the sentence about the scorecard_path to read: "May be a merged iteration scorecard (during the loop) or the convergence-cleanup request (once the loop exits). The behavior is the same either way: apply every row."

**Patterns to follow:**
- Preserve all other content in the reviewer agent bodies verbatim. Frontmatter edits are scoped to removing a single line each.
- The fixer agent's core contract prose (non-negotiables, Output, Process steps) stays unchanged.

**Test scenarios:**
- Test expectation: none -- mechanical deletion and frontmatter stripping. Validation is "no grep hits for `tier:` or `reviewer-tiers` in the plugin tree after the unit lands".

**Verification:**
- `rg 'reviewer-tiers' plugins/CASM-tools` returns no hits.
- `rg '^tier: ' plugins/CASM-tools/agents` returns no hits.
- `rg 'tier[\s\[]' plugins/CASM-tools/scripts plugins/CASM-tools/skills plugins/CASM-tools/agents` returns only the historical note in `orchestrate-review.md` and any incidental uses (e.g. word like "tier" in an example that is not about cascade tiers).
- Each reviewer agent still has a complete frontmatter block with `name`, `description`, `model`, `color`, `tools`.
- The `fixer.md` file still defines the three-input contract and the non-negotiables.

- [ ] **Unit 4: Update downstream consumers (meta-review log paths, session log template) and run an integration check**

**Goal:** Keep the meta-review skill and the session log template in sync with the new log layout. Run one manual end-to-end invocation of `/review-document` on a small artifact to confirm the new cascade produces the expected files.

**Requirements:** R7

**Dependencies:** Units 1, 2, 3.

**Files:**
- Modify: `plugins/CASM-tools/skills/meta-review/SKILL.md`
- Modify: `plugins/CASM-tools/scripts/session-log-template.md`

**Approach:**

In `meta-review/SKILL.md`:
- Update the reference list `- <plugin>/scripts/{reviewer-common,orchestrate-review,reviewer-tiers,loop-engine}.md` to drop `reviewer-tiers`.
- Update the "Per-iteration merged scorecards" path: `paper-extension/<stage>-logs/<stage>-<ts>/reviewer-logs/tier[T]-iter[N]-merged.md` → `paper-extension/<stage>-logs/<stage>-<ts>/reviewer-logs/iter[N]-merged.md`.
- Update the bullet "Any unresolved items from tier cleanup skips or CRITICAL-at-cap halts" → "Any unresolved items from the convergence cleanup or CRITICAL-at-cap halts".
- The sentence using "severity tier" as a figurative grouping ("CRITICAL recurrence first within the same frequency tier") is fine — it refers to severity grouping, not cascade tiers. Leave as-is.

In `session-log-template.md`:
- Replace the two `### Tier [T] — Iteration [N]` section templates with a single `### Iteration [N]` section template.
- Drop the `**Tier:** [1-5]` bullet; keep all other bullets.
- Update the Verification Results row "All tier cleanups applied" → "Convergence cleanup applied (or skipped with no outstanding MAJOR/MINOR)".
- Update the Finalization row phrasing about "which tiers hit their cap" → "or indicate iteration cap was hit".

Integration check (last step of this unit):
- Pick a small text artifact in a scratch location.
- Invoke `/CASM-tools:review-document <path>` with a scope that selects 2 reviewers.
- Verify the created `logs_dir` contains:
  - `<artifact>-v1.md`, `<artifact>-v2.md`, ..., `<artifact>-final.md`
  - `reviewer-logs/iter1-<r1>.md`, `reviewer-logs/iter1-<r2>.md`, `reviewer-logs/iter1-merged.md`
  - possibly further `iter2-*`, `iter3-*` if the loop ran more than once
  - `final-cleanup-request.md` if the convergence pass fired
  - `<artifact>-combined-scorecard.md` at the top level
- Verify the terminal report uses iteration rows, not tier rows.
- Verify the live file was replaced at cascade end.
- Verify there is no `tier[T]-iter[N]-*` file anywhere in the logs directory.

**Patterns to follow:**
- Preserve the session log template's entry cadence ("Update after each iteration. Do not batch.")
- Keep every unaffected field in the template intact (Objective, Design Decisions, Learnings, Open Questions, Next Steps, Output Files).

**Test scenarios:**
- Test expectation: none -- documentation update. The integration check above is the verification, not a test scenario per se.

**Verification:**
- `rg 'tier\[T\]|tier 1|tier 5|reviewer-tiers' plugins/CASM-tools/skills/meta-review plugins/CASM-tools/scripts/session-log-template.md` returns no hits.
- After the integration check, all expected files are present and no tier-named files exist in the logs directory.

## System-Wide Impact

- **Interaction graph:** `paper-summarize`, `paper-extend`, `paper-present`, and `paper-full-pipeline` invoke `/CASM-tools:review-document` via the `into <dir>` clause. They only care about the final installed version and the combined scorecard path, both of which keep their names. No changes required in those skills.
- **Error propagation:** CRITICAL-at-cap halts remain the only user-interaction point. The `REVIEW_SUSPENDED.md` file's content shape changes but the filename and surface semantics do not.
- **State lifecycle risks:** A cascade suspended under the old tiered schema becomes unresumable under the new engine. The recovery path: on detecting old-schema suspended state, error with a clear message telling the user to delete the `REVIEW_SUSPENDED.md` and re-invoke. This is a one-time cost and affects only users with an actively-suspended review at the time of the refactor.
- **API surface parity:** The scope-token grammar is unchanged. Every existing invocation string (`/review-document thorough paper.md`, `/review-document all paper/writeup.qmd into <dir>`, `/review-document adversarial`, etc.) continues to work.
- **Integration coverage:** The integration check in Unit 4 verifies end-to-end behavior on a real artifact; unit-level testing is not available for a doc-driven orchestrator.
- **Unchanged invariants:** Reviewer agent scorecard format, fixer's three-path contract + "apply every row" non-negotiables, preference-injection hook, lockfile + external-edit detection, artifact-name filter, `into <dir>` clause, scope-token grammar, auto-resume detection, v1 write-once property.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Loss of tier-ordered conflict resolution. Flat parallel lets structure-type fixes and writing-type fixes land in the same fixer pass, where they may contradict. | The fixer's existing severity priority (CRITICAL → MAJOR → MINOR) and unapplicable-row rule handle contradictions but with lower quality than tier ordering did. Document this in the "Why flat rather than tiered" note. If it produces bad artifacts in practice, the escape hatch is a user re-invocation with a narrower reviewer scope (e.g. `/review-document structure paper.md` then `/review-document writing paper.md`). |
| Reduced iteration budget. Old max was 15 reviewer-iterations (5 tiers × 3). New max is 3. Complex artifacts may hit CRITICAL-at-cap more often. | The cap-halt escalation lets the user continue manually or split the work. If complex artifacts become unworkable, the cap is a single constant in `loop-engine.md` that can be raised. |
| Cascade suspended under old schema is not auto-resumable. | Detect old-shape `REVIEW_SUSPENDED.md` at resume and error with a clear migration message ("delete this file and re-invoke"). Users in the middle of a suspended review at refactor time are rare. |
| Meta-review skill path references (unit 4) are missed and break silently on next run. | Unit 4 verification greps explicitly for the old path patterns in the meta-review directory. |
| Reviewer dispatch payload grows: more reviewers in one parallel batch. The PreToolUse hook injects preferences into each and these are independent, so no compounding in prompt size, but parallel dispatch of N reviewers against the same snapshot uses N × snapshot-size input tokens per iteration. | Unchanged from today — parallelism within a tier already did this. The new design widens the batch slightly but not per-reviewer cost. |
| Combined scorecard output loses the per-tier breakdown that some users may find useful for diagnosing where problems concentrate. | The per-iteration breakdown in the new combined scorecard provides an equivalent slice ("iteration 1 flagged CRITICAL shape issues, iteration 2 flagged MAJOR writing issues"). Document the translation in `orchestrate-review.md`'s new combined-scorecard section. |

## Documentation / Operational Notes

- The refactor is a breaking change to the `REVIEW_SUSPENDED.md` on-disk format. Note this in a commit message and in the PR description.
- The reviewer-tiers.md file's historical rationale (why tiered was chosen originally) should be captured in one short paragraph in `orchestrate-review.md` so future readers can understand the prior design. The paragraph should name the two failure modes the tiered design was targeting (wasted rewrites, oscillation) and note the tradeoff the new design accepts.

## Sources & References

- Current cascade spec: `plugins/CASM-tools/scripts/loop-engine.md`, `plugins/CASM-tools/scripts/orchestrate-review.md`, `plugins/CASM-tools/scripts/reviewer-tiers.md`
- Current skill surface: `plugins/CASM-tools/skills/review-document/SKILL.md`
- Fixer contract: `plugins/CASM-tools/agents/fixer.md`
- Reviewer protocol (unchanged): `plugins/CASM-tools/scripts/reviewer-common.md`
- Preference-injection hook (unchanged): `plugins/CASM-tools/hooks/inject-preferences.py`
- Downstream consumer: `plugins/CASM-tools/skills/meta-review/SKILL.md`
