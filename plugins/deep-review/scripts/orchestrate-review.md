# Review Orchestration Reference

This document describes the creator/reviewer tiered cascade used by `/review-document`.

Pair with `${CLAUDE_PLUGIN_ROOT}/scripts/loop-engine.md` for the state machine details (hashing, parse failures, revision refusals, external-edit detection) and `${CLAUDE_PLUGIN_ROOT}/scripts/reviewer-tiers.md` for the scope hierarchy and tier assignments.

Within this document:
- `[artifact]` = the reviewable object's basename without extension (e.g. `slides`, `analysis`, `inline-2026-04-17T14-22`).
- `[artifact-logs]` = the review logs directory. Default location is `docs/reviews/[artifact]-YY-MM-DDTHH-MM/` relative to the repo root, where `YY-MM-DD` is the invocation date (2-digit year, month, day) and `HH-MM` is the invocation time in 24-hour PST (e.g. `docs/reviews/writing-reviewer-26-04-19T18-29/`). Increasing-granularity ordering (year → month → day → hour → minute) makes lexicographic directory sort match chronological order. The `T` separates date from time. Minute precision makes same-artifact collisions vanishingly rare; on such an exact-minute collision, append `-<N>` (e.g. `...T18-29-2/`).

## Reviewer selection

`/review-document` selects reviewers dynamically from a closed scope-token grammar defined in `${CLAUDE_PLUGIN_ROOT}/skills/review-document/SKILL.md`. No flag syntax is accepted.

- **Explicit scope phrase** (`/review-document for writing only`) — parsed by the skill into a reviewer list. Tokens matching known reviewer names (`writing`, `structure`, `math`, `code`, `simplicity`, `adversarial`, `presentation`, `consistency`, `factual`) select those reviewers. Two additional tokens modify behavior: `all` (dispatch every reviewer, including factual) and `thorough` (run a final audit pass after auto-apply).
- **Empty scope** — the skill classifies applicable reviewers from artifact type (e.g., `.py` file → `code-reviewer` + `simplicity-reviewer`; `.md` prose → `writing-reviewer` + `structure-reviewer`; `.qmd` with math → `writing-reviewer` + `structure-reviewer` + `math-reviewer`; compiled slides → `presentation-reviewer`). Selection is announced before dispatch.
- **`factual-reviewer` is never auto-selected.** It runs only when the user names it explicitly (`/review-document factual paper.md` or `/review-document all paper.md`).

## Loop Structure

Reviewers are grouped into five scope tiers (see `reviewer-tiers.md`). Each tier iterates to convergence (composite ≥ 90 AND zero CRITICAL for every reviewer in the tier) or its per-tier cap before the next tier dispatches.

**The cascade operates on snapshots in `[artifact-logs]`, not the live file.** The live file at the artifact path is copied once to `[artifact-logs]/[artifact]-v1.md` at loop start and is then read-only until the user decides at the checkpoint. Every revision during the cascade writes a new versioned snapshot (`[artifact]-v2.md`, `v3.md`, ...); reviewers always read the latest snapshot.

```
1. User invokes /review-document with scope phrase and/or paths
2. Skill resolves artifact(s), acquires lock at state/locks/<hash>.lock
3. Skill classifies reviewers from scope phrase or artifact type, announces selection grouped by tier
4. Snapshot the live file to [artifact-logs]/[artifact]-v1.md (this is the baseline). The live file is not touched again until checkpoint.
5. For tier in 1..5:
     a. applicable = intersect(tier.reviewers, selected reviewer list)
     b. If applicable is empty: skip tier, continue
     c. For iteration in 1..3 (per-tier cap):
          i.   Dispatch applicable reviewers in parallel against the latest snapshot
          ii.  Each reviewer produces a scorecard; save to [artifact-logs]/[reviewer]-tier[T]-iter[N].md
          iii. Merge the tier's scorecards → [artifact-logs]/tier[T]-iter[N]-scorecard.md
          iv.  Update session log with tier/iteration scores and CRITICAL issues
          v.   If every reviewer in this tier passes (composite ≥ 90 AND zero CRITICAL):
                 break inner loop, advance to next tier
          vi.  Main session produces the next proposed version → [artifact-logs]/[artifact]-v[next].md
          vii. Hash the latest snapshot; on external-edit mismatch to the live file (user edited it during the cascade), halt with user prompt
     d. If the tier exits the inner loop without converging AND any CRITICAL remains:
          Halt. Present the tier's final scorecard to the user and offer continue / suspend / fix-manually.
     e. MAJOR and MINOR items that remain after the cap propagate to the auto-apply phase below.
6. Auto-apply phase (default, always-on). After all tiers complete:
     a. Gather every MAJOR and MINOR item that remains outstanding across all tiers' final scorecards.
     b. If none remain: skip to step 7.
     c. For apply-round in 1..3 (auto-apply cap):
          i.   Write [artifact-logs]/surgical-fix-v[next]-request.md with every remaining item.
          ii.  Main session revises the latest snapshot to address all items. Save as [artifact-logs]/[artifact]-v[next].md.
          iii. Dispatch ALL originally-dispatched reviewers in parallel against the new snapshot (not tiered: auto-apply is a parallel pass).
          iv.  Save their scorecards to [artifact-logs]/[reviewer]-apply[R].md.
          v.   If every reviewer passes (composite ≥ 90 AND zero CRITICAL) AND no MAJOR or MINOR items remain: break; auto-apply converged.
          vi.  Else continue: new items become the fix list for the next apply round.
     d. If apply-round 3 exits with items remaining: note in combined scorecard; those items propagate to the checkpoint for the user.
7. If the user invoked with the `thorough` scope keyword:
     a. Dispatch ALL originally-dispatched reviewers in parallel against the final proposed snapshot.
     b. Save each scorecard to [artifact-logs]/thorough/[reviewer]-thorough.md.
     c. Merge into [artifact-logs]/thorough/combined-scorecard.md.
     d. **No items from the thorough pass are applied.** It is a convergence audit only.
8. Write [artifact-logs]/[artifact]-combined-scorecard.md: cascade summary, per-tier final scorecards, auto-apply rounds, and (if present) a link to the thorough scorecards.
9. Present the User Review Checkpoint (see below) with the final proposed snapshot and combined scorecard.
10. On user decision: release lock, record outcome in session log, optionally install a proposed version as the new live file.
```

The tiered cascade plus auto-apply handles in-cascade convergence. The `thorough` pass audits whether convergence is real or whether the reviewers would keep flagging issues if given another turn.

## Report File Naming

Each phase above produces files in a predictable layout. Each reviewer produces an individual report per phase:

- Tier iteration: `[artifact-logs]/[reviewer]-tier[T]-iter[N].md`
- Auto-apply round: `[artifact-logs]/[reviewer]-apply[R].md`
- Thorough audit: `[artifact-logs]/thorough/[reviewer]-thorough.md`

Merged per-phase scorecards:

- Tier iteration merge: `[artifact-logs]/tier[T]-iter[N]-scorecard.md`
- Auto-apply round merge: `[artifact-logs]/apply[R]-scorecard.md`
- Thorough merge: `[artifact-logs]/thorough/combined-scorecard.md`

Versioned proposed drafts (all revisions during the cascade):

- Baseline: `[artifact-logs]/[artifact]-v1.md` (snapshot of the live file at cascade start)
- Each revision increments: `[artifact]-v2.md`, `v3.md`, ... across tiers and auto-apply rounds in one monotonic sequence.

At the end, the final combined scorecard aggregates everything:

```
[artifact-logs]/[artifact]-combined-scorecard.md
```

Examples (assuming invocation 2026-04-19 at 18:29 PST):
- `docs/reviews/slides-26-04-19T18-29/writing-tier4-iter1.md`
- `docs/reviews/analysis-26-04-19T18-29/code-apply1.md`
- `docs/reviews/slides-26-04-19T18-29/thorough/writing-thorough.md`
- `docs/reviews/analysis-26-04-19T18-29/analysis-v4.md`

## Scorecard Merging and Final Aggregation

Within a tier iteration, merge the reviewers' scorecards into a single per-iteration document:

```markdown
# Tier [T] Scorecard — [artifact] (Iteration [N])

## Tier Status: [PASS/FAIL]
[List which reviewers in this tier passed and which failed, with composite scores]

## Critical Issues Summary
[List all CRITICAL severity items across reviewers in this tier — these must be addressed before the tier can advance]

## [Reviewer Name] Review
[Full scorecard from that reviewer]
**Individual report:** `[artifact-logs]/[reviewer]-tier[T]-iter[N].md`

[Repeat for each reviewer dispatched in this tier]
```

Auto-apply rounds use the same format with an `Apply [R] Scorecard` title.

At the end, concatenate every final scorecard into the combined scorecard:

```markdown
# Combined Scorecard — [artifact]

## Cascade summary
| Phase | Reviewers | Converged | Final iteration | CRITICAL | MAJOR | MINOR | Version |
|---|---|---|---|---|---|---|---|
| Tier 1 | structure, consistency | YES | 1 | 0 | 0 | 2 | v2 |
| Tier 2 | code | YES | 2 | 0 | 1 | 3 | v4 |
| ...
| Auto-apply round 1 | all involved (parallel) | YES | — | 0 | 0 | 0 | v6 |
| Thorough (audit only) | all involved (parallel) | — | — | 0 | 1 | 2 | — |

## Version trail
- v1: baseline snapshot of the live file at cascade start.
- v2: post-tier-1 revision. (etc.)
- v[N]: final proposed version.

## Tier [T] — Final Scorecard
[Full tier scorecard from the last iteration of tier T]

[Repeat for each tier that dispatched at least one reviewer]

## Auto-apply rounds
[Per-round summary: what was applied, what the re-review raised, whether the round converged]

## Thorough audit
[Included only if the user invoked with `thorough`. Brief summary of what the audit raised, with a pointer to `[artifact-logs]/thorough/combined-scorecard.md`. Emphasize: items in the thorough audit were NOT applied; they record what the reviewers would still flag if given another turn.]
```

## Pass/Fail Rules

The merged scorecards feed two pass/fail evaluations: **per tier** during the cascade, and **across all involved reviewers** during the auto-apply phase.

- **Tier pass:** every reviewer in that tier scores composite ≥ 90 AND zero CRITICAL items.
- **Auto-apply pass:** every originally-dispatched reviewer passes the threshold AND zero MAJOR or MINOR items remain in any scorecard. Auto-apply has a stricter bar because the phase exists to drive remaining items to zero.
- If any reviewer in the current tier fails its threshold, the tier iterates again (up to 3 times) with a revision between iterations.
- The main session receives the tier's merged scorecard as input for each in-tier revision, and the auto-apply request file for each auto-apply revision.
- CRITICAL severity items block tier advancement. A tier that hits its cap with CRITICAL remaining halts and escalates to the user.
- MAJOR and MINOR items that remain after a tier's cap do NOT block advancement. They propagate to the auto-apply phase, which applies them by default.
- Per-tier cap: 3 iterations. Auto-apply cap: 3 rounds. Thorough pass: 1 dispatch, no fixes.
- On parse failure for a reviewer's scorecard: re-dispatch that reviewer once; if the second attempt also parses poorly, mark the reviewer `failed to parse`, exclude from composite for the phase, flag to user, continue.
- On empty-or-refuse revision from the main session: retry once with the refusal reason prepended; if still empty, escalate to the user and halt the cascade.

### Severity priority within a revision

Within a single tier's revision, the main session works through the merged scorecard in severity order:

1. Address all **CRITICAL** issues first. These block tier advancement.
2. Address **MAJOR** issues next. These drag composite scores below 90 and usually need fixing for the tier to converge.
3. Address **MINOR** issues if they are easy fixes. Do not sacrifice clarity chasing minor points.

Tier scope already handles the cross-reviewer sequencing problem: structural fixes land before sentence-level ones because structure sits in an earlier tier. Within a tier, reviewers are orthogonal by construction (see `reviewer-tiers.md` for why each reviewer sits in its tier), so severity order is the only ranking needed.

## User Review Checkpoint

After the cascade (tiers + auto-apply + optional thorough) reaches a terminal state, present a human-in-the-loop checkpoint before finalizing. The live file was never touched during the cascade. At this checkpoint the user decides what to install as the new live file.

**This checkpoint is mandatory for every /review-document run.** It is not skipped even when every phase converged cleanly, because a clean cascade is still worth one final human confirmation before the live file is replaced.

### Checkpoint format

Present the user with a message using this structure:

```markdown
## Review Checkpoint — [artifact]

**Cascade converged:** [YES / NO — list any phase that hit its cap]
**Final proposed version:** [artifact]-v[N].md
**Live file status:** unchanged (snapshot-only cascade)

### Cascade summary
| Phase | Reviewers | Converged | Final iteration | CRITICAL | MAJOR | MINOR |
|---|---|---|---|---|---|---|
| Tier 1 | structure, consistency | YES | 1 | 0 | 0 | 2 |
| Tier 4 | writing | YES | 1 | 0 | 2 | 1 |
| Auto-apply 1 | structure, writing (parallel) | YES | — | 0 | 0 | 0 |
| Thorough | structure, writing (parallel) | — (audit only) | — | 0 | 1 | 0 |

### Version trail
| Version | Produced by | Notes |
|---|---|---|
| v1 | — | Baseline snapshot of the live file |
| v2 | tier 1 revision | Post-structure-pass |
| v3 | tier 4 revision | Post-writing-pass |
| v4 | auto-apply round 1 | All remaining MAJOR/MINOR items applied |

### Final Scores (on the final proposed version)
| Reviewer | Tier | Composite | Status |
|---|---|---|---|
| [Reviewer 1] | [T] | [score] | [PASS/FAIL] |
| ...

**CRITICAL remaining in final proposed version:** [count — usually zero]

### Thorough audit
[Included only if the user invoked with `thorough`. Brief summary of what the audit pass raised, with a pointer to `[artifact-logs]/thorough/combined-scorecard.md`. These items were NOT applied; they record what the reviewers would still flag on another turn.]

### Unresolved issues in the final proposed version
[Listed only if auto-apply hit its cap with items still outstanding. Grouped by source phase and reviewer, severity-sorted.]

### Your options

- **`accept`** — install the final proposed version (`[artifact]-v[N].md`) as the new live file. The live file is replaced.
- **`use <N>`** — install version N from the trail as the new live file (e.g. `use 2` installs v2). Lets you pick an earlier point in the cascade.
- **`keep original`** — do not modify the live file. Baseline (v1) remains as-is. The cascade is archived to the logs directory for reference.
- **`fix <numbers>`** — surgically revise the final proposed version to address specific items, then re-run all originally-dispatched reviewers in parallel (bypassing the tier cascade) and re-present this checkpoint.
- **`show <number>`** — print the full detail for an item (quote, citation, severity, reviewer, suggested fix). Multiple `show` calls allowed before deciding.
```

### Handling the user's response

**`accept`**
1. Copy `[artifact-logs]/[artifact]-v[final].md` over the live file at the artifact's path.
2. Write `[artifact-logs]/accepted-issues.md` capturing any outstanding items (usually none after auto-apply), the final version number, and a timestamp.
3. Release the lockfile.
4. Record in the session log: checkpoint outcome = accepted, installed version v[final].

**`use <N>`**
1. Validate that version N exists in `[artifact-logs]/`. If not, re-prompt.
2. Copy `[artifact-logs]/[artifact]-v<N>.md` over the live file.
3. Write `[artifact-logs]/accepted-issues.md` noting that version N was chosen instead of the final, with whatever issues that version carries.
4. Release the lockfile.
5. Record in the session log: checkpoint outcome = use <N>, installed version v<N>.

**`keep original`**
1. Leave the live file untouched. v1 in the logs dir equals the current live file content, so no copy is needed.
2. Write `[artifact-logs]/accepted-issues.md` noting that the user declined to install any proposed version.
3. Release the lockfile.
4. Record in the session log: checkpoint outcome = keep original.

**`fix <numbers>`** (surgical)
1. Extract the selected items from the combined scorecard.
2. Write `[artifact-logs]/surgical-fix-v[N+1]-request.md` with ONLY the selected items, prefixed with: "Address ONLY the items below. Do not re-touch unrelated content. Preserve everything else in the current version exactly as-is."
3. Main session produces a revised snapshot → `[artifact-logs]/[artifact]-v[N+1].md`. The live file is still untouched.
4. Re-run ALL originally-dispatched reviewers in parallel against the new snapshot, bypassing the tier cascade.
5. Save the new combined scorecard.
6. Re-present the checkpoint with updated scores, version trail, and whatever issues remain.
7. Loop until the user picks one of the terminal options (`accept`, `use <N>`, `keep original`).

**`show <number>`** — print the full scorecard entry for that item (quote, reference, severity, reviewer name, suggested fix), then re-present the options without doing anything else. The user may chain multiple `show` calls before deciding.

### Iteration accounting

- Version numbering is monotonic across the whole cascade: `v1` is the baseline snapshot of the live file, `v2` is the first revision, and so on through tier iterations, auto-apply rounds, and surgical-fix iterations. The thorough pass does NOT produce a new version (it reviews without revising).
- Per-tier cap: 3 iterations. Auto-apply cap: 3 rounds. These caps apply during the cascade only, not to user-driven surgical fixes.
- Surgical fix iterations at the checkpoint are uncapped. The user may fix-loop as many times as they want; they are the final authority on when to ship.
- Each surgical fix writes a new combined scorecard and a new version file.
- Session log records each checkpoint as a distinct entry, including the version the user installed (or declined to install).

### What to write to `accepted-issues.md`

Format:

```markdown
# Checkpoint outcome — [artifact]

**Artifact:** [live file path]
**Checkpoint decision:** [accept | use <N> | keep original]
**Installed version:** [v[N] that was copied to the live file, or "none (keep original)"]
**Date:** [ISO timestamp]
**Cascade converged:** [YES/NO — if NO, list which phases hit their cap]

## Final Scores at decision (on the installed version)
| Reviewer | Tier | Composite |
|---|---|---|
| ... | ... | ... |

## Outstanding items in the installed version

[Items that were not addressed in the installed version — usually none after auto-apply but may be non-empty if the user picked an earlier version with `use <N>`, or if auto-apply hit its cap.]

### Tier [T] — [Reviewer 1] — MAJOR
1. **[Location]** — [issue]. Suggested fix: [fix]. **Accepted because:** [user's note, or "no comment"]

### Tier [T] — [Reviewer 1] — MINOR
...

[Continue per source phase, then per reviewer]
```

This file is the durable record of issues the user knowingly shipped. Future review runs can read it to understand the provenance of known-issue items.

## Session Log Updates

Session-log writes happen at two points in the cascade: after each in-tier iteration, and at each user checkpoint.

### Per-iteration entry

After each in-tier iteration, update the session log under `state/session-logs/` (or `[artifact-logs]/session-log.md` for long-running single-artifact reviews) with:

- Tier number, in-tier iteration number, and timestamp.
- All reviewer composite scores and pass/fail status for the iteration.
- Any CRITICAL severity issues found.
- Summary of key changes requested.

See `${CLAUDE_PLUGIN_ROOT}/scripts/session-log-template.md` for the template.

### Per-checkpoint entry

Each checkpoint produces one entry in the session log:
- Checkpoint sequence number (first, second, third, …).
- `checkpoint_opened_at` timestamp (feeds the abandonment-detection metric).
- Number of items presented.
- User decision (`accept`, `use <N>`, `keep original`, `fix N,M,P`, or sequence of `show` before deciding).
- For `fix` decisions: which items were selected.
- For terminal decisions: link to `accepted-issues.md` and the installed version (or "none").
- Resulting action: proceeded to Finalize (terminal decision) OR started surgical fix iteration v[N+1].

## Cap exhaustion

If any tier reaches its per-tier cap (3 iterations) with CRITICAL issues remaining AND the user is not present to checkpoint:

1. Write `[artifact-logs]/REVIEW_SUSPENDED.md` capturing the full cascade state: last version, every tier scorecard produced so far, the tier that halted, reviewers that failed, CRITICAL items remaining.
2. Release the lockfile so subsequent `/review-document` invocations on other artifacts are not blocked.
3. The next `/review-document` invocation on this artifact auto-detects `REVIEW_SUSPENDED.md` in the logs directory and resumes from the saved state. No explicit resume command is needed.

Resumption picks up at the suspended tier without restarting. The user checkpoint presents the suspended state and offers options: continue the halted tier, skip to the next tier, or fix manually and re-enter.
