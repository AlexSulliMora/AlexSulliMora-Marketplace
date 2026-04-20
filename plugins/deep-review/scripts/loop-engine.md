# Loop engine

This document specifies the state machine `/review-document` runs, extracted from the skill surface so the skill can own user interaction (parse, announce, render checkpoint) while the engine owns cascade mechanics (hash, dispatch, parse, aggregate, recover).

Pair with `${CLAUDE_PLUGIN_ROOT}/scripts/orchestrate-review.md` for the user-facing protocol, `${CLAUDE_PLUGIN_ROOT}/scripts/reviewer-tiers.md` for the scope hierarchy, and `${CLAUDE_PLUGIN_ROOT}/scripts/reviewer-common.md` for the scorecard contract.

The cascade never modifies the live file at `artifact_path`. The live file is snapshotted to `v1` at the start and left alone until the user's checkpoint decision installs some version (possibly `v1`, possibly a later one, possibly nothing). Reviewers always read the latest snapshot from `logs_dir`. Revisions are written by the main session to new versioned snapshots.

## Inputs

- `artifact_path` — absolute path to the live file under review.
- `reviewer_list` — list of agent names to dispatch (e.g. `["writing-reviewer", "code-reviewer"]`).
- `tier_assignment` — map from reviewer name to tier number, loaded from `${CLAUDE_PLUGIN_ROOT}/scripts/reviewer-tiers.md`.
- `logs_dir` — path to the review logs directory. Default: `docs/reviews/<artifact-basename>-<YY-MM-DD>T<HH-MM>/` relative to the repo root, where time is 24-hour PST. See `orchestrate-review.md` for the full naming rule.
- `thorough` — boolean. When true, the engine runs a final parallel audit pass after auto-apply, saving results to `logs_dir/thorough/` without applying any findings.
- `session_id` — from hook context; recorded in the lock and session log.

## State

| Field | Purpose |
|---|---|
| `phase` | `tier` / `auto_apply` / `thorough` / `checkpoint`. |
| `tier` | Current tier number (1..5). Only meaningful during the `tier` phase. |
| `iteration` | Current in-tier iteration (1..3). Resets at each new tier. |
| `apply_round` | Current auto-apply round (1..3). Only meaningful during `auto_apply`. |
| `version` | Monotonic snapshot version. `v1` is the baseline (live file at cascade start); every revision increments by 1. |
| `current_snapshot_path` | `logs_dir/[artifact]-v[version].md`. Reviewers read this. |
| `live_file_hash` | SHA256 of the live file at cascade start. If it changes during the cascade, halt with an external-edit warning. |
| `lockfile_path` | `state/locks/<artifact_hash_at_acquire>.lock`. |
| `tier_scorecard_paths` | Map: tier number → `logs_dir/tier[T]-iter[N]-scorecard.md` for the last iteration of that tier. |
| `apply_scorecard_paths` | List: round number → `logs_dir/apply[R]-scorecard.md`. |
| `thorough_scorecard_path` | `logs_dir/thorough/combined-scorecard.md` (only if `thorough=true`). |
| `combined_scorecard_path` | `logs_dir/[artifact]-combined-scorecard.md`. Written once at cascade end. |
| `reviewer_parse_failures` | Set of reviewer names whose scorecards failed to parse (excluded after one retry). |

## Main cascade

```
1. acquire_lock(artifact_path)
   - Attempt flock on lockfile. If already held → return "artifact under review, retry later."
   - Write {pid, start_time, session_id, live_file_hash} into lockfile.

2. Check for `logs_dir/REVIEW_SUSPENDED.md`. If present, auto-resume from the saved state (reviewers, tier, iteration, version) rather than starting fresh. Announce: "Resuming suspended review from [timestamp]."

3. tier_assignment = load_tiers(${CLAUDE_PLUGIN_ROOT}/scripts/reviewer-tiers.md)

4. Snapshot baseline:
     live_file_hash = sha256(artifact_path)
     copy artifact_path → logs_dir/[artifact]-v1.md
     version = 1
     current_snapshot_path = logs_dir/[artifact]-v1.md

5. Tier cascade:
     for tier in 1..5:
       a. applicable = [r for r in reviewer_list if tier_assignment[r] == tier]
       b. if applicable is empty: continue to next tier

       c. for iteration in 1..3:
            i.   If sha256(artifact_path) != live_file_hash:
                   halt("live file edited externally during cascade. options: restart, continue from current snapshot, abort")
            ii.  Dispatch all `applicable` in parallel against `current_snapshot_path`.
                 Each reviewer writes logs_dir/[reviewer]-tier[tier]-iter[iteration].md.
            iii. Collect scorecards, validate, handle parse failures per Recovery actions.
            iv.  Merge → logs_dir/tier[tier]-iter[iteration]-scorecard.md.
            v.   Update session log.
            vi.  If every reviewer in `applicable` passes (composite ≥ 90 AND zero CRITICAL):
                   tier_scorecard_paths[tier] = current path
                   break inner loop
            vii. If iteration == 3:
                   tier_scorecard_paths[tier] = current path
                   if any CRITICAL remains:
                     halt_cascade_and_checkpoint(reason="tier [tier] exhausted cap with CRITICAL items")
                   else:
                     break inner loop  # MAJOR/MINOR propagate to auto-apply
            viii. Main session revises `current_snapshot_path` using the tier's merged scorecard → logs_dir/[artifact]-v[version+1].md.
                  version += 1
                  current_snapshot_path = logs_dir/[artifact]-v[version].md
                  if revision is empty or refused: retry once with refusal text prepended. If still empty, halt.
            ix.  continue inner loop

       d. end of tier

6. Auto-apply phase:
     a. outstanding = collect_major_and_minor_items(tier_scorecard_paths)
     b. if outstanding is empty: skip to step 7

     c. for apply_round in 1..3:
          i.   Write logs_dir/surgical-fix-v[version+1]-request.md containing every item in `outstanding`, prefixed with the standard surgical-fix instruction.
          ii.  Main session revises `current_snapshot_path` addressing all items → logs_dir/[artifact]-v[version+1].md.
               version += 1
               current_snapshot_path = logs_dir/[artifact]-v[version].md
          iii. Dispatch ALL originally-dispatched reviewers in parallel against `current_snapshot_path` (not tiered).
               Each reviewer writes logs_dir/[reviewer]-apply[apply_round].md.
          iv.  Merge → logs_dir/apply[apply_round]-scorecard.md.
          v.   apply_scorecard_paths[apply_round] = current path.
          vi.  If every reviewer passes AND no MAJOR or MINOR items remain:
                 break  # auto-apply converged
          vii. Else outstanding = new items from this round's scorecards; continue.

     d. If apply_round == 3 with items remaining: note in combined scorecard; items propagate to checkpoint.

7. Thorough phase (only if `thorough=true`):
     a. mkdir logs_dir/thorough/
     b. Dispatch ALL originally-dispatched reviewers in parallel against `current_snapshot_path`.
        Each reviewer writes logs_dir/thorough/[reviewer]-thorough.md.
     c. Merge → logs_dir/thorough/combined-scorecard.md.
     d. **Do not apply any findings.** The thorough pass is a convergence audit only.

8. Write logs_dir/[artifact]-combined-scorecard.md:
     - Cascade summary table (phase, reviewers, converged, final iteration, CRITICAL/MAJOR/MINOR, version produced).
     - Version trail.
     - Per-tier final scorecards.
     - Auto-apply round summaries.
     - Thorough audit section (if ran): brief summary + pointer to logs_dir/thorough/combined-scorecard.md.

9. user_checkpoint(state):
     Render cascade summary, version trail, final scores, thorough audit (if any), and unresolved items (if any).
     Options:
       - `accept` → install current_snapshot_path at artifact_path, write accepted-issues.md, release_lock(), return ACCEPTED.
       - `use <N>` → install logs_dir/[artifact]-v<N>.md at artifact_path, write accepted-issues.md, release_lock(), return USE_N.
       - `keep original` → leave artifact_path untouched, write accepted-issues.md, release_lock(), return KEEP_ORIGINAL.
       - `fix <n>` → construct surgical-fix-request → main session revises `current_snapshot_path` → save new version → re-dispatch all originally dispatched reviewers in parallel → re-render checkpoint.
       - `show <n>` → print entry, re-render options, no state change.

10. Cap exhaustion with CRITICAL remaining AND user not present:
      write logs_dir/REVIEW_SUSPENDED.md with full state (phase, tier or apply_round, version, reviewer_list, thorough flag).
      release_lock()
      On next `/review-document` invocation for this artifact, the skill detects the suspended file and auto-resumes.

11. release_lock()
```

The sections below enumerate the error conditions, validation rules, utilities, and data formats referenced by the cascade above.

## Recovery actions

| Event | Action |
|---|---|
| Lock acquire fails | Return "artifact under review. Another session holds the lock." |
| External edit to live file during cascade (hash mismatch) | Halt with user prompt: "live file edited externally — restart, continue from current snapshot, or abort?" |
| Reviewer scorecard parse failure (first time) | Re-dispatch that reviewer once with the same input. |
| Reviewer scorecard parse failure (second time) | Mark reviewer "failed to parse", exclude from phase composite, flag to user, continue. |
| Main session revision returns empty/refusal | Retry once with refusal reason prepended. If still empty, surface to user and halt. |
| Tier cap hit with CRITICAL remaining | Halt cascade, suspend or checkpoint. User decides whether to continue the halted tier, skip to auto-apply anyway, or fix manually. |
| Auto-apply cap hit with items remaining | Proceed to checkpoint with items in the combined scorecard as "unresolved in final proposed version." User can `fix <n>` at the checkpoint. |
| Loop crashes mid-iteration | Lockfile TTL is advisory (OS lock drops on process death). On next invocation, if lockfile exists but flock succeeds, treat as stale and resume from last saved state. |

## Parse validation

Enforced before accepting any reviewer's output. All checks must pass:

1. Exactly one `## Scores` heading in the scorecard.
2. Scores table contains a row with `**Composite**` in the category column.
3. Composite numeric value equals (weighted sum of category scores), tolerant to ±0.5 rounding.
4. Exactly one `## Required Changes` heading (or its reviewer-specific rename, e.g. `## Discrepancies Found` for consistency-reviewer).
5. The Required Changes table has exactly the columns `#`, `Severity`, `Location`, `Issue`, `Source citation`, `Fix` in that order.
6. The Severity column of every body row is exactly `CRITICAL`, `MAJOR`, or `MINOR` — no Unicode homoglyphs, no surrounding whitespace, no lowercase variants.
7. Rows are sorted first by severity (CRITICAL → MAJOR → MINOR), then by source location within each severity.
8. No fenced code blocks inside the `## Required Changes` section (they can hide malformed content).
9. No duplicate `## Scores` or `## Required Changes` sections.

Failure handling:

- **Steps 1–6 (hard).** Mark the whole scorecard unparseable.
- **Steps 7–9 (soft).** Warn but accept; the orchestrator reorders rows or skips malformed ones rather than failing the reviewer.

## Hash computation

```python
import hashlib
def artifact_hash(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()
```

For binary artifacts (compiled slides, PDFs), hash the source file (`.qmd`, `.tex`), not the compiled output — the source is what gets revised.

## Lock file format

```
pid: 12345
start_time: 2026-04-17T14:22:00Z
session_id: abc123
artifact_hash: sha256:deadbeef...
```

The OS flock is the enforcement primitive. The file contents are diagnostic only: a future `/review-document` invocation on the same artifact reads them to report what is blocking.

## Surgical fix request format

When the user selects `fix <numbers>` at a checkpoint:

```markdown
# Surgical fix request — [artifact] — v[N+1]

**Instruction:** The user has asked you to address ONLY the items below. Do not re-touch unrelated content. Do not introduce changes beyond what is requested. Preserve everything else in the current version exactly as-is.

## Items to fix

| # | Severity | Location | Issue | Source citation | Fix |
|---|---|---|---|---|---|
| [copied verbatim from the combined scorecard, preserving row order] | | | | | |
```

This file is written to `logs_dir/surgical-fix-v[N+1]-request.md` and passed to the main session as input for direct revision.
