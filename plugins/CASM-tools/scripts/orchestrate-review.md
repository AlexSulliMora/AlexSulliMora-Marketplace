# Review Orchestration Reference

This document describes the creator/reviewer tiered cascade used by `/review-document`.

Pair with `${CLAUDE_PLUGIN_ROOT}/scripts/loop-engine.md` for the state machine details (hashing, parse failures, external-edit detection, fixer dispatch contract) and `${CLAUDE_PLUGIN_ROOT}/scripts/reviewer-tiers.md` for the scope hierarchy and tier assignments.

Within this document:
- `[artifact]` = the reviewable object's basename without extension (e.g. `slides`, `analysis`, `inline-2026-04-17T14-22`).
- `[artifact-logs]` = the review logs directory. Default location is `docs/reviews/[artifact]-YY-MM-DDTHH-MM/` relative to the repo root, where `YY-MM-DD` is the invocation date (2-digit year, month, day) and `HH-MM` is the invocation time in 24-hour PST (e.g. `docs/reviews/writing-reviewer-26-04-19T18-29/`). Increasing-granularity ordering (year → month → day → hour → minute) makes lexicographic directory sort match chronological order. The `T` separates date from time. Minute precision makes same-artifact collisions vanishingly rare; on such an exact-minute collision, append `-<N>` (e.g. `...T18-29-2/`). The caller may override the default via the `into <dir>` scope token — pipeline skills (summarize, extend, present) pass their own log folders this way.

## Reviewer selection

`/review-document` selects reviewers dynamically from a closed scope-token grammar defined in `${CLAUDE_PLUGIN_ROOT}/skills/review-document/SKILL.md`. No flag syntax is accepted.

- **Explicit scope phrase** (`/review-document for writing only`) — parsed by the skill into a reviewer list. Tokens matching known reviewer names (`writing`, `structure`, `math`, `code`, `simplicity`, `adversarial`, `presentation`, `consistency`, `factual`) select those reviewers. Two additional tokens modify behavior: `all` (dispatch every reviewer, including factual) and `thorough` (run a final audit pass after all tiers finish). The `into <dir>` token overrides the default logs directory.
- **Empty scope** — the skill classifies applicable reviewers from artifact type (e.g., `.py` file → `code-reviewer` + `simplicity-reviewer`; `.md` prose → `writing-reviewer` + `structure-reviewer`; `.qmd` with math → `writing-reviewer` + `structure-reviewer` + `math-reviewer`; compiled slides → `presentation-reviewer`). Selection is announced before dispatch.
- **`factual-reviewer` is never auto-selected.** It runs only when the user names it explicitly (`/review-document factual paper.md` or `/review-document all paper.md`).

## Directory layout

Every cascade writes into `[artifact-logs]/` with this structure:

```
[artifact-logs]/
├── [artifact]-final.md                 (at cascade end — a copy of the installed version)
├── [artifact]-v1.md                    (baseline snapshot)
├── [artifact]-v2.md
├── [artifact]-v3.md
├── ...
├── [artifact]-combined-scorecard.md    (at cascade end)
├── tier[T]-cleanup-request.md          (one per tier that exits with remaining MAJOR/MINOR)
├── reviewer-logs/
│   ├── tier[T]-iter[N]-[reviewer].md   (individual reviewer outputs per tier iteration)
│   └── tier[T]-iter[N]-merged.md       (per-iteration merged tier scorecard — input to the fixer)
└── thorough/
    ├── [reviewer]-thorough.md          (only if `thorough` requested)
    └── combined-scorecard.md
```

`REVIEW_SUSPENDED.md` is written at the top level of `[artifact-logs]/` if the cascade is halted for resumption.

## Loop Structure

Reviewers are grouped into five scope tiers (see `reviewer-tiers.md`). Each tier iterates to convergence (composite ≥ 90 AND zero CRITICAL for every reviewer in the tier) or its per-tier cap. Any MAJOR/MINOR items remaining at the end of the tier's inner loop are cleaned up by one final fixer dispatch **before** the next tier runs — so each tier advances on a snapshot that has no outstanding items at its scope.

**The cascade operates on snapshots in `[artifact-logs]`, not the live file.** The live file at the artifact path is copied once to `[artifact-logs]/[artifact]-v1.md` at loop start and is then read-only until the user decides at the checkpoint. Every revision during the cascade writes a new versioned snapshot (`[artifact]-v2.md`, `v3.md`, ...); reviewers always read the latest snapshot.

**Revisions are produced by the `fixer` agent, not the main session.** The orchestrator constructs a fixer dispatch (source_path, target_path, scorecard_path, mode) and the fixer applies the scorecard's items to produce the next version. See `${CLAUDE_PLUGIN_ROOT}/agents/fixer.md` for the fixer contract.

```
1. User invokes /review-document with scope phrase and/or paths (optionally `into <dir>`)
2. Skill resolves artifact(s), acquires lock at state/locks/<hash>.lock, resolves logs_dir
3. Skill classifies reviewers from scope phrase or artifact type, announces selection grouped by tier
4. Snapshot the live file to [artifact-logs]/[artifact]-v1.md (baseline). **v1 is write-once and immutable** — nothing in the cascade ever overwrites it, not even on resume from a suspended state. Live file is untouched until finalization.
5. For tier in 1..5:
     a. applicable = intersect(tier.reviewers, selected reviewer list)
     b. If applicable is empty: skip tier, continue
     c. For iteration in 1..3 (per-tier cap):
          i.   Dispatch applicable reviewers in parallel against the latest snapshot (each dispatch is a fresh Agent call, not a SendMessage to a reused reviewer — fresh dispatch avoids anchoring bias).
          ii.  Each reviewer produces a scorecard; save to [artifact-logs]/reviewer-logs/tier[T]-iter[N]-[reviewer].md
          iii. Merge the tier's scorecards → [artifact-logs]/reviewer-logs/tier[T]-iter[N]-merged.md
          iv.  Update session log with tier/iteration scores and CRITICAL issues
          v.   If every reviewer in this tier passes (composite ≥ 90 AND zero CRITICAL):
                 break inner loop, go to step 5.e (cleanup)
          vi.  If iteration == 3:
                 If any CRITICAL remains: halt and escalate to user.
                 Else: break inner loop (MAJOR/MINOR will be handled in step 5.e).
          vii. Dispatch `fixer` agent to produce the next version → [artifact-logs]/[artifact]-v[next].md (scorecard_path = the merged tier scorecard)
          viii. Hash the latest snapshot; on external-edit mismatch to the live file (user edited it during the cascade), halt with user prompt
     d. If the tier exits the inner loop without converging AND any CRITICAL remains:
          Halt. Present the tier's final scorecard to the user and offer continue / suspend / fix-manually.
     e. Tier cleanup (pre-advance): if the tier's final scorecard has any MAJOR or MINOR items remaining (no CRITICAL at this point — the CRITICAL path halts above), write [artifact-logs]/tier[T]-cleanup-request.md with those items and dispatch `fixer` once to produce the next version. No re-review within this tier — the next tier reads the cleaned snapshot, and its reviewers catch any regression the cleanup introduced.
6. If the user invoked with the `thorough` scope keyword:
     a. Dispatch ALL originally-dispatched reviewers in parallel against the final proposed snapshot.
     b. Save each scorecard to [artifact-logs]/thorough/[reviewer]-thorough.md.
     c. Merge into [artifact-logs]/thorough/combined-scorecard.md.
     d. **No items from the thorough pass are applied.** It is a convergence audit only.
7. Write [artifact-logs]/[artifact]-combined-scorecard.md: cascade summary, per-tier final scorecards, tier cleanup summaries, and (if present) a link to the thorough scorecards.
8. Finalize automatically (see Finalization below): install the final version at the live path and print a terminal report.
9. On user decision: release lock, record outcome in session log, write [artifact-logs]/[artifact]-final.md, optionally install a proposed version as the new live file.
```

Cleaning up remaining MAJOR/MINOR items within each tier means the final snapshot carries no outstanding items at cascade end. The `thorough` pass audits whether convergence is real or whether the reviewers would keep flagging issues if given another turn.

## Report File Naming

Each phase produces files in a predictable layout. Files named below are relative to `[artifact-logs]/`.

Individual reviewer scorecards (always inside `reviewer-logs/`):

- Tier iteration: `reviewer-logs/tier[T]-iter[N]-[reviewer].md`
- Thorough audit: `thorough/[reviewer]-thorough.md` (the thorough pass has no tier/iter index)

Per-phase merged scorecards (the inputs the fixer reads):

- Tier iteration merge: `reviewer-logs/tier[T]-iter[N]-merged.md`
- Tier cleanup request: `tier[T]-cleanup-request.md` (at the top level of `[artifact-logs]/`)
- Thorough merge: `thorough/combined-scorecard.md`

Versioned proposed drafts (all revisions during the cascade):

- Baseline: `[artifact]-v1.md` (snapshot of the live file at cascade start)
- Each revision increments: `[artifact]-v2.md`, `v3.md`, ... across tier iterations and tier-cleanup dispatches in one monotonic sequence.
- Final (written at checkpoint): `[artifact]-final.md` — a copy of whichever version the user installed.

Fixer dispatch request files (at the top level of `[artifact-logs]/`):

- Tier cleanup: `tier[T]-cleanup-request.md` (one per tier that exited with remaining MAJOR/MINOR).

Combined scorecard (at the top level of `[artifact-logs]/`):

- `[artifact]-combined-scorecard.md`

Examples (assuming invocation 2026-04-19 at 18:29 PST):
- `docs/reviews/slides-26-04-19T18-29/reviewer-logs/tier4-iter1-writing.md`
- `docs/reviews/slides-26-04-19T18-29/tier1-cleanup-request.md`
- `docs/reviews/slides-26-04-19T18-29/thorough/writing-thorough.md`
- `docs/reviews/analysis-26-04-19T18-29/analysis-v4.md`
- `docs/reviews/analysis-26-04-19T18-29/analysis-final.md`

## Scorecard Merging and Final Aggregation

Within a tier iteration, merge the reviewers' scorecards into a single per-iteration document at `[artifact-logs]/reviewer-logs/tier[T]-iter[N]-merged.md`:

```markdown
# Tier [T] Scorecard — [artifact] (Iteration [N])

## Tier Status: [PASS/FAIL]
[List which reviewers in this tier passed and which failed, with composite scores]

## Critical Issues Summary
[List all CRITICAL severity items across reviewers in this tier — these must be addressed before the tier can advance]

## [Reviewer Name] Review
[Full scorecard from that reviewer]
**Individual report:** `reviewer-logs/tier[T]-iter[N]-[reviewer].md`

[Repeat for each reviewer dispatched in this tier]
```

At the end, concatenate every final scorecard into the combined scorecard at `[artifact-logs]/[artifact]-combined-scorecard.md`:

```markdown
# Combined Scorecard — [artifact]

## Cascade summary
| Phase | Reviewers | Converged | Final iteration | CRITICAL | MAJOR | MINOR | Version after |
|---|---|---|---|---|---|---|---|
| Tier 1 reviewers | structure, consistency | YES | 1 | 0 | 0 | 2 | v1 |
| Tier 1 cleanup | — (fixer only) | — | — | 0 | 0 | 0 | v2 |
| Tier 2 reviewers | code | YES | 2 | 0 | 1 | 3 | v3 |
| Tier 2 cleanup | — (fixer only) | — | — | 0 | 0 | 0 | v4 |
| ...
| Thorough (audit only) | all involved (parallel) | — | — | 0 | 1 | 2 | — |

## Version trail
- v1: baseline snapshot of the live file at cascade start.
- v2: tier 1 cleanup.
- v[N]: final proposed version.

## Tier [T] — Final Scorecard
[Full tier scorecard from the last iteration of tier T, pulled from reviewer-logs/tier[T]-iter[N]-merged.md]

## Tier [T] — Cleanup
[Link to tier[T]-cleanup-request.md if one was written. One line per item applied.]

[Repeat per tier]

## Thorough audit
[Included only if the user invoked with `thorough`. Brief summary of what the audit raised, with a pointer to `thorough/combined-scorecard.md`. Emphasize: items in the thorough audit were NOT applied; they record what the reviewers would still flag if given another turn.]
```

## Pass/Fail Rules

Per-tier pass/fail is the only evaluation:

- **Tier pass:** every reviewer in that tier scores composite ≥ 90 AND zero CRITICAL items.
- If any reviewer in the current tier fails its threshold, the tier iterates again (up to 3 times) with a fixer dispatch between iterations.
- The fixer receives the tier's merged scorecard as `scorecard_path` for each in-tier revision.
- CRITICAL severity items block tier advancement. A tier that hits its cap with CRITICAL remaining halts and escalates to the user.
- MAJOR and MINOR items remaining at the end of the tier's inner loop are cleaned up by one final fixer dispatch (scorecard_path = `tier[T]-cleanup-request.md`) before the next tier begins. The cleanup pass is not re-reviewed within the current tier — the next tier's reviewers pick up regressions.
- Per-tier cap: 3 iterations. Thorough pass: 1 dispatch, no fixes.
- On parse failure for a reviewer's scorecard: re-dispatch that reviewer once; if the second attempt also parses poorly, mark the reviewer `failed to parse`, exclude from composite for the phase, flag to user, continue.
- On empty-or-refuse fixer output: retry once with the refusal reason prepended; if still empty, escalate to the user and halt the cascade.

### Severity priority within a fixer dispatch

Within a single tier's revision, the fixer works through the merged scorecard in severity order:

1. Address all **CRITICAL** issues first. These block tier advancement.
2. Address **MAJOR** issues next. These drag composite scores below 90 and usually need fixing for the tier to converge.
3. Address **MINOR** issues if they are easy fixes. Do not sacrifice clarity chasing minor points.

Tier scope already handles the cross-reviewer sequencing problem: structural fixes land before sentence-level ones because structure sits in an earlier tier. Within a tier, reviewers are orthogonal by construction (see `reviewer-tiers.md` for why each reviewer sits in its tier), so severity order is the only ranking needed.

The tier-cleanup dispatch (step 5.e) uses the same fixer the iteration loop uses. The fixer always applies every item in the scorecard; there is no mode flag. Because there is no re-review within the tier, the cleanup advance is guaranteed by the fixer's "apply all items exactly" contract, not by a mode tag.

## Finalization

There is no interactive User Review Checkpoint. When the cascade reaches a terminal state (all tiers done + optional thorough + combined scorecard written), the engine finalizes automatically:

1. Copy `[artifact-logs]/[artifact]-v[final].md` → `[artifact-logs]/[artifact]-final.md` (a permanent record of the installed version).
2. Copy `[artifact-logs]/[artifact]-v[final].md` over the live file at `artifact_path` (install).
3. Print a terminal report: final version number, cascade summary, final scores, and the path to `[artifact-logs]/[artifact]-combined-scorecard.md`.
4. Release the lockfile.

If the user wants an earlier version installed instead, they copy it from `[artifact-logs]/` manually — the directory retains every version (`v1` through `v[final]`), the combined scorecard, and every reviewer log. No `accept`, `use <N>`, `keep original`, `fix <numbers>`, or `show <number>` verbs exist; the cascade is deterministic and the user's override path is a shell `cp`.

The design principle: the fixer applies every item the reviewers flag. If the user consistently disagrees with what gets flagged, they update the reviewer's preferences file at `${CLAUDE_PLUGIN_ROOT}/preferences/<reviewer>-style.md`, not an individual run's output. This keeps the calibration visible, durable, and shared across future cascades.

### Terminal report format

```markdown
## Review complete — [artifact]

**Installed version:** [artifact]-v[N].md (copied to [artifact_path])
**Final file:** [artifact]-final.md
**Cascade converged:** [YES / NO — if NO, list which tiers hit their cap]
**Logs directory:** [artifact-logs]/

### Cascade summary
| Phase | Reviewers | Converged | Final iteration | CRITICAL | MAJOR | MINOR |
|---|---|---|---|---|---|---|
| Tier 1 reviewers | structure, consistency | YES | 1 | 0 | 0 | 2 |
| Tier 1 cleanup | — (fixer only) | — | — | — | — | — |
| Tier 4 reviewers | writing | YES | 2 | 0 | 1 | 0 |
| Tier 4 cleanup | — (fixer only) | — | — | — | — | — |
| Thorough | structure, writing (parallel) | — (audit only) | — | 0 | 1 | 0 |

### Final Scores (on the installed version)
| Reviewer | Tier | Composite | Status |
|---|---|---|---|
| [Reviewer 1] | [T] | [score] | [PASS/FAIL] |
| ...

### Thorough audit
[Included only if the user invoked with `thorough`. Brief summary + pointer to `thorough/combined-scorecard.md`. Items NOT applied.]

### Want a different version?
Every intermediate version is in `[artifact-logs]/`. Copy one over the live file:

```bash
cp [artifact-logs]/[artifact]-v3.md [artifact_path]
```
```

### Iteration accounting

- Version numbering is monotonic across the whole cascade: `v1` is the baseline snapshot of the live file, `v2` is the first revision, and so on through tier iterations and tier-cleanup dispatches. The thorough pass does NOT produce a new version (it reviews without revising).
- Per-tier cap: 3 iterations. Tier cleanup: one dispatch per tier.
- Session log records one entry per in-tier iteration and one finalization entry per cascade.

## Session Log Updates

Session-log writes happen at two points in the cascade: after each in-tier iteration, and at finalization.

### Per-iteration entry

After each in-tier iteration, update the session log under `state/session-logs/` (or `[artifact-logs]/session-log.md` for long-running single-artifact reviews) with:

- Tier number, in-tier iteration number, and timestamp.
- All reviewer composite scores and pass/fail status for the iteration.
- Any CRITICAL severity issues found.
- Summary of key changes requested.

See `${CLAUDE_PLUGIN_ROOT}/scripts/session-log-template.md` for the template.

### Finalization entry

At cascade end, record one entry:
- Finalization timestamp.
- Final version installed and its composite scores.
- Whether the cascade converged, or which tiers hit their cap.
- Thorough audit run (yes/no) and its outstanding item count if any.
- Path to `[artifact]-final.md` and the combined scorecard.

## Cap exhaustion (CRITICAL escalation)

If any tier reaches its per-tier cap (3 iterations) with CRITICAL issues remaining:

1. Write `[artifact-logs]/REVIEW_SUSPENDED.md` capturing the full cascade state: last version, every tier scorecard produced so far, the tier that halted, reviewers that failed, CRITICAL items remaining, and the logs_dir path.
2. Escalate to the user with a blocking prompt: continue the halted tier, suspend, or fix manually.
3. Release the lockfile.
4. The next `/review-document` invocation on this artifact auto-detects `REVIEW_SUSPENDED.md` and resumes from the saved state. No explicit resume command is needed.

This is the only user-interaction point in the cascade. It is an error-path escalation, not a routine checkpoint — it fires when a CRITICAL-severity item could not be driven to zero within the per-tier cap. Routine runs do not prompt the user at all.
