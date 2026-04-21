# Review Orchestration Reference

This document describes the creator/reviewer parallel cascade used by `/review-document`.

Pair with `${CLAUDE_PLUGIN_ROOT}/scripts/loop-engine.md` for the state machine details (hashing, parse failures, external-edit detection, fixer dispatch contract).

Within this document:
- `[artifact]` = the reviewable object's basename without extension (e.g. `slides`, `analysis`, `inline-2026-04-17T14-22`).
- `[artifact-logs]` = the review logs directory. Default location is `docs/reviews/[artifact]-YY-MM-DDTHH-MM/` relative to the repo root, where `YY-MM-DD` is the invocation date (2-digit year, month, day) and `HH-MM` is the invocation time in 24-hour PST (e.g. `docs/reviews/writing-reviewer-26-04-19T18-29/`). Increasing-granularity ordering (year → month → day → hour → minute) makes lexicographic directory sort match chronological order. The `T` separates date from time. Minute precision makes same-artifact collisions vanishingly rare; on such an exact-minute collision, append `-<N>` (e.g. `...T18-29-2/`). The caller may override the default via the `into <dir>` scope token — pipeline skills (summarize, extend, present) pass their own log folders this way.

## Reviewer selection

`/review-document` selects reviewers dynamically from a closed scope-token grammar defined in `${CLAUDE_PLUGIN_ROOT}/skills/review-document/SKILL.md`. No flag syntax is accepted.

- **Explicit scope phrase** (`/review-document for writing only`) — parsed by the skill into a reviewer list. Tokens matching known reviewer names (`writing`, `structure`, `math`, `code`, `simplicity`, `adversarial`, `presentation`, `consistency`, `factual`) select those reviewers. Two additional tokens modify behavior: `all` (dispatch every reviewer, including factual) and `thorough` (run a final audit pass after the cascade finalizes). The `into <dir>` token overrides the default logs directory.
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
├── final-cleanup-request.md            (only if the convergence cleanup had MAJOR/MINOR items to apply)
├── reviewer-logs/
│   ├── iter[N]-[reviewer].md           (individual reviewer outputs per iteration)
│   └── iter[N]-merged.md               (per-iteration merged scorecard — input to the fixer)
└── thorough/
    ├── [reviewer]-thorough.md          (only if `thorough` requested)
    └── combined-scorecard.md
```

`REVIEW_SUSPENDED.md` is written at the top level of `[artifact-logs]/` if the cascade is halted for resumption.

## Loop Structure

All selected reviewers run in parallel against the current snapshot each iteration. The orchestrator merges every reviewer's scorecard into a single aggregated list and dispatches the fixer once per iteration against that list. The loop terminates when every reviewer passes (composite ≥ 90 AND zero CRITICAL) or when iteration 3 completes. On convergence (or at the cap with no CRITICAL remaining), a final fixer pass applies any remaining MAJOR/MINOR items before finalization. No re-review follows the convergence cleanup.

**The cascade operates on snapshots in `[artifact-logs]`, not the live file.** The live file at the artifact path is copied once to `[artifact-logs]/[artifact]-v1.md` at loop start and is then read-only until the cascade finalizes. Every revision during the cascade writes a new versioned snapshot (`[artifact]-v2.md`, `v3.md`, ...); reviewers always read the latest snapshot.

**Revisions are produced by the `fixer` agent, not the main session.** The orchestrator constructs a fixer dispatch (source_path, target_path, scorecard_path) and the fixer applies the scorecard's items to produce the next version. See `${CLAUDE_PLUGIN_ROOT}/agents/fixer.md` for the fixer contract.

```
1. User invokes /review-document with scope phrase and/or paths (optionally `into <dir>`)
2. Skill resolves artifact(s), acquires lock at state/locks/<hash>.lock, resolves logs_dir
3. Skill classifies reviewers from scope phrase or artifact type, announces selection
4. Snapshot the live file to [artifact-logs]/[artifact]-v1.md (baseline). **v1 is write-once and immutable** — nothing in the cascade ever overwrites it, not even on resume from a suspended state. Live file is untouched until finalization.
5. For iteration in 1..3:
     a. Dispatch all selected reviewers in parallel against the latest snapshot (each dispatch is a fresh Agent call, not a SendMessage to a reused reviewer — fresh dispatch avoids anchoring bias). Dispatch prompts contain only the snapshot path and scorecard output path; do not add preferences (the hook injects them automatically).
     b. Each reviewer produces a scorecard; save to [artifact-logs]/reviewer-logs/iter[N]-[reviewer].md
     c. Merge all scorecards → [artifact-logs]/reviewer-logs/iter[N]-merged.md
     d. Update session log with iteration scores and CRITICAL issues
     e. If every reviewer passes (composite ≥ 90 AND zero CRITICAL):
          break loop, go to step 6 (convergence cleanup)
     f. If iteration == 3:
          If any CRITICAL remains: halt and escalate to user.
          Else: break loop (MAJOR/MINOR will be handled in step 6).
     g. Dispatch `fixer` agent to produce the next version → [artifact-logs]/[artifact]-v[next].md (scorecard_path = the iteration's merged scorecard)
     h. Hash the latest snapshot; on external-edit mismatch to the live file (user edited it during the cascade), halt with user prompt
6. Convergence cleanup: if the final iteration's merged scorecard has any MAJOR or MINOR items remaining (no CRITICAL at this point — the CRITICAL path halts above), write [artifact-logs]/final-cleanup-request.md with those items and dispatch `fixer` once to produce the next version. No re-review — the next phase uses the cleaned snapshot as the finalized version.
7. If the user invoked with the `thorough` scope keyword:
     a. Dispatch ALL originally-dispatched reviewers in parallel against the finalized snapshot.
     b. Save each scorecard to [artifact-logs]/thorough/[reviewer]-thorough.md.
     c. Merge into [artifact-logs]/thorough/combined-scorecard.md.
     d. **No items from the thorough pass are applied.** It is a convergence audit only.
8. Write [artifact-logs]/[artifact]-combined-scorecard.md: cascade summary, per-iteration final scorecards, convergence cleanup summary, and (if present) a link to the thorough scorecards.
9. Finalize automatically (see Finalization below): install the final version at the live path and print a terminal report.
```

Cleaning up remaining MAJOR/MINOR items once globally before finalization means the final snapshot carries no outstanding items at cascade end. The `thorough` pass audits whether convergence is real or whether the reviewers would keep flagging issues if given another turn.

## Why flat rather than tiered

An earlier design dispatched reviewers in five sequential tiers (shape → content correctness → pruning → prose → adversarial), each tier with its own 3-iteration inner loop plus a tier-cleanup pass. The tiered design targeted two failure modes of a naive flat loop:

1. **Wasted rewrites.** A writing fix applied in iteration N is moot if the same revision also moves or deletes the sentence per a structure fix. Tiered dispatch avoided this by running structure before writing.
2. **Oscillation.** A writing fix and a simplicity fix can pull the same sentence in opposite directions. Tiered dispatch avoided this by running simplicity (which deletes) before writing (which reshapes).

The flat parallel design accepts these tradeoffs in exchange for a simpler loop with a smaller iteration budget (3 total iterations rather than up to 15 across five tiers). Cross-reviewer conflicts are resolved by the fixer's existing severity-priority and unapplicable-row rules: apply CRITICAL → MAJOR → MINOR, and when two rows contradict at the same location, the first wins and the second is recorded as unapplicable. If the flat design produces low-quality artifacts in practice, the user-facing escape hatch is to re-invoke with narrower reviewer scope (e.g. run `structure` first, then re-invoke with `writing`). The 3-iteration cap is a single constant that can be raised if complex artifacts consistently fail to converge.

## Report File Naming

Each phase produces files in a predictable layout. Files named below are relative to `[artifact-logs]/`.

Individual reviewer scorecards (always inside `reviewer-logs/`):

- Loop iteration: `reviewer-logs/iter[N]-[reviewer].md`
- Thorough audit: `thorough/[reviewer]-thorough.md` (the thorough pass has no iteration index)

Per-iteration merged scorecards (the inputs the fixer reads):

- Iteration merge: `reviewer-logs/iter[N]-merged.md`
- Convergence cleanup request: `final-cleanup-request.md` (at the top level of `[artifact-logs]/`)
- Thorough merge: `thorough/combined-scorecard.md`

Versioned proposed drafts (all revisions during the cascade):

- Baseline: `[artifact]-v1.md` (snapshot of the live file at cascade start)
- Each revision increments: `[artifact]-v2.md`, `v3.md`, ... across loop iterations and the convergence cleanup in one monotonic sequence.
- Final (written at finalization): `[artifact]-final.md` — a copy of whichever version the cascade installed.

Combined scorecard (at the top level of `[artifact-logs]/`):

- `[artifact]-combined-scorecard.md`

Examples (assuming invocation 2026-04-19 at 18:29 PST):
- `docs/reviews/slides-26-04-19T18-29/reviewer-logs/iter1-writing.md`
- `docs/reviews/slides-26-04-19T18-29/final-cleanup-request.md`
- `docs/reviews/slides-26-04-19T18-29/thorough/writing-thorough.md`
- `docs/reviews/analysis-26-04-19T18-29/analysis-v4.md`
- `docs/reviews/analysis-26-04-19T18-29/analysis-final.md`

## Scorecard Merging and Final Aggregation

Within a loop iteration, merge the reviewers' scorecards into a single per-iteration document at `[artifact-logs]/reviewer-logs/iter[N]-merged.md`:

```markdown
# Iteration [N] Scorecard — [artifact]

## Iteration Status: [PASS/FAIL]
[List which reviewers passed and which failed, with composite scores]

## Critical Issues Summary
[List all CRITICAL severity items across reviewers in this iteration — these must be addressed before the loop can advance]

## [Reviewer Name] Review
[Full scorecard from that reviewer]
**Individual report:** `reviewer-logs/iter[N]-[reviewer].md`

[Repeat for each reviewer dispatched in this iteration]
```

At the end, concatenate every final scorecard into the combined scorecard at `[artifact-logs]/[artifact]-combined-scorecard.md`:

```markdown
# Combined Scorecard — [artifact]

## Cascade summary
| Phase | Reviewers | Converged | CRITICAL | MAJOR | MINOR | Version after |
|---|---|---|---|---|---|---|
| Iteration 1 | writing, structure | NO | 0 | 3 | 5 | v2 |
| Iteration 2 | writing, structure | YES | 0 | 1 | 2 | v2 |
| Convergence cleanup | — (fixer only) | — | 0 | 0 | 0 | v3 |
| Thorough (audit only) | writing, structure (parallel) | — | 0 | 1 | 2 | — |

## Version trail
- v1: baseline snapshot of the live file at cascade start.
- v2: iteration 1 fixer pass.
- v3: convergence cleanup.
- v[N]: final proposed version.

## Iteration [N] — Final Scorecard
[Full merged scorecard from the last iteration of the loop, pulled from reviewer-logs/iter[N]-merged.md]

## Convergence cleanup
[Link to final-cleanup-request.md if one was written. One line per item applied.]

## Thorough audit
[Included only if the user invoked with `thorough`. Brief summary of what the audit raised, with a pointer to `thorough/combined-scorecard.md`. Emphasize: items in the thorough audit were NOT applied; they record what the reviewers would still flag if given another turn.]
```

## Pass/Fail Rules

Per-iteration pass/fail is the only evaluation during the loop:

- **Iteration pass:** every reviewer in `reviewer_list` scores composite ≥ 90 AND zero CRITICAL items.
- If any reviewer fails its threshold, the loop iterates again (up to 3 times) with a fixer dispatch between iterations.
- The fixer receives the iteration's merged scorecard as `scorecard_path` for each in-loop revision.
- CRITICAL severity items block loop advancement. A loop that hits its cap with CRITICAL remaining halts and escalates to the user.
- MAJOR and MINOR items remaining at the end of the loop are cleaned up by one final fixer dispatch (scorecard_path = `final-cleanup-request.md`) before finalization. The cleanup pass is not re-reviewed — the finalized snapshot is whatever the convergence-cleanup fixer wrote.
- 3-iteration cap. Thorough pass: 1 dispatch, no fixes.
- On parse failure for a reviewer's scorecard: re-dispatch that reviewer once; if the second attempt also parses poorly, mark the reviewer `failed to parse`, exclude from the iteration composite, flag to user, continue.
- On empty-or-refuse fixer output: retry once with the refusal reason prepended; if still empty, escalate to the user and halt the cascade.

### Severity priority within a fixer dispatch

Within a single fixer dispatch, the fixer works through the scorecard in severity order:

1. Address all **CRITICAL** issues first. These block loop advancement.
2. Address **MAJOR** issues next. These drag composite scores below 90 and usually need fixing for the loop to converge.
3. Address **MINOR** issues if they are easy fixes. Do not sacrifice clarity chasing minor points.

The flat parallel design means two reviewers can flag fixes to the same content in incompatible ways within a single iteration (e.g. a structure reviewer moves a paragraph while a writing reviewer rewrites one of its sentences). The fixer resolves contradictions by severity first (more serious wins) and then by position in the scorecard (earlier row wins). Rows that become genuinely unapplicable after a prior row's fix are recorded as `<!-- fixer note: row N unapplied — reason ... -->` at the bottom of the revision. See `agents/fixer.md` for the full contract.

The convergence-cleanup dispatch (step 6) uses the same fixer the loop uses. The fixer always applies every item in the scorecard; there is no mode flag. Because there is no re-review after cleanup, the cleanup's correctness is guaranteed by the fixer's "apply all items exactly" contract.

## Finalization

There is no interactive User Review Checkpoint. When the cascade reaches a terminal state (loop done + convergence cleanup + optional thorough + combined scorecard written), the engine finalizes automatically:

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
**Cascade converged:** [YES / NO — if NO, note whether iteration 3 hit the cap]
**Logs directory:** [artifact-logs]/

### Cascade summary
| Phase | Reviewers | Converged | CRITICAL | MAJOR | MINOR |
|---|---|---|---|---|---|
| Iteration 1 | writing, structure | NO | 0 | 3 | 5 |
| Iteration 2 | writing, structure | YES | 0 | 1 | 2 |
| Convergence cleanup | — (fixer only) | — | — | — | — |
| Thorough | writing, structure (parallel) | — (audit only) | 0 | 1 | 0 |

### Final Scores (on the installed version)
| Reviewer | Composite | Status |
|---|---|---|
| [Reviewer 1] | [score] | [PASS/FAIL] |
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

- Version numbering is monotonic across the whole cascade: `v1` is the baseline snapshot of the live file, `v2` is the first revision, and so on through loop iterations and the convergence cleanup. The thorough pass does NOT produce a new version (it reviews without revising).
- 3-iteration cap on the main loop. Convergence cleanup: one dispatch.
- Session log records one entry per loop iteration, one entry for the convergence cleanup (if any), and one finalization entry per cascade.

## Session Log Updates

Session-log writes happen at two points in the cascade: after each loop iteration, and at finalization.

### Per-iteration entry

After each loop iteration, update the session log under `state/session-logs/` (or `[artifact-logs]/session-log.md` for long-running single-artifact reviews) with:

- Iteration number and timestamp.
- All reviewer composite scores and pass/fail status for the iteration.
- Any CRITICAL severity issues found.
- Summary of key changes requested.

See `${CLAUDE_PLUGIN_ROOT}/scripts/session-log-template.md` for the template.

### Finalization entry

At cascade end, record one entry:
- Finalization timestamp.
- Final version installed and its composite scores.
- Whether the cascade converged, or whether the iteration cap was hit.
- Convergence cleanup applied (yes/no/skipped-no-items).
- Thorough audit run (yes/no) and its outstanding item count if any.
- Path to `[artifact]-final.md` and the combined scorecard.

## Cap exhaustion (CRITICAL escalation)

If iteration 3 completes with CRITICAL issues remaining:

1. Write `[artifact-logs]/REVIEW_SUSPENDED.md` capturing the full cascade state: last version, every iteration scorecard produced so far, the iteration that halted, reviewers that failed, CRITICAL items remaining, and the logs_dir path. The serialized state has no `tier` field — an old-schema suspension file (from the prior tiered engine) is not resumable and must be deleted manually.
2. Escalate to the user with a blocking prompt: continue the halted loop, suspend, or fix manually.
3. Release the lockfile.
4. The next `/review-document` invocation on this artifact auto-detects `REVIEW_SUSPENDED.md` and resumes from the saved state. No explicit resume command is needed.

This is the only user-interaction point in the cascade. It is an error-path escalation, not a routine checkpoint — it fires when a CRITICAL-severity item could not be driven to zero within the 3-iteration cap. Routine runs do not prompt the user at all.
