# Loop engine

This document specifies the state machine `/review-document` runs. The skill owns user-facing announcements and final reporting. The engine owns cascade mechanics (hash, dispatch, parse, aggregate, recover). Revisions are produced by the `fixer` agent.

Pair with `${CLAUDE_PLUGIN_ROOT}/scripts/orchestrate-review.md` for the end-to-end protocol and `${CLAUDE_PLUGIN_ROOT}/scripts/reviewer-common.md` for the scorecard contract.

The cascade does not modify the live file at `artifact_path` during the loop. The live file is snapshotted to `v1` at start and left untouched until the cascade finishes, at which point the final proposed version is installed at the live path. Reviewers always read the latest snapshot from `logs_dir`. Revisions are written by the `fixer` agent to new versioned snapshots.

## Inputs

- `artifact_path` — absolute path to the live file under review.
- `reviewer_list` — list of agent names to dispatch (e.g. `["writing-reviewer", "code-reviewer"]`).
- `logs_dir` — path to the review logs directory. Default: `docs/reviews/<artifact-basename>-<YY-MM-DD>T<HH-MM>/` relative to the repo root, where time is 24-hour PST. May be overridden by the caller (e.g. the pipeline skills pass their own log folders via the `into <dir>` token). See `orchestrate-review.md` for the full naming rule.
- `threshold` — integer in [0, 100]. Per-reviewer composite score required to pass. Default: `80`. Set via the `threshold <N>` scope token.
- `max_iterations` — integer in [1, 10]. Maximum number of loop iterations before hitting the cap. Default: `3`. Set via the `iterations <N>` scope token.
- `thorough` — boolean. When true, the engine runs a final parallel audit pass after the cascade finalizes, saving results to `logs_dir/thorough/` without applying any findings.
- `session_id` — from hook context; recorded in the lock and session log.

## Directory layout inside `logs_dir`

```
<logs_dir>/
├── <artifact>-final.md                 (copy of the installed version, written at cascade end)
├── <artifact>-v1.md                    (baseline snapshot of the live file)
├── <artifact>-v2.md                    (each revision increments the version)
├── <artifact>-v3.md
├── ...
├── <artifact>-combined-scorecard.md    (written once at cascade end)
├── final-cleanup-request.md            (only if the convergence cleanup had MAJOR/MINOR items to apply)
├── reviewer-logs/
│   ├── iter[N]-<reviewer>.md           (individual reviewer scorecards per iteration)
│   └── iter[N]-merged.md               (per-iteration merged scorecard — input to the fixer)
└── thorough/
    ├── <reviewer>-thorough.md          (only if `thorough=true`)
    └── combined-scorecard.md
```

`REVIEW_SUSPENDED.md` is written at the top level of `logs_dir` if the cascade is halted for resumption.

## State

| Field | Purpose |
|---|---|
| `phase` | `loop` / `cleanup` / `thorough` / `finalize`. |
| `iteration` | Current iteration (1..`max_iterations`). Only meaningful during the `loop` phase. |
| `version` | Monotonic snapshot version. `v1` is the baseline (live file at cascade start); every revision increments by 1. |
| `current_snapshot_path` | `logs_dir/[artifact]-v[version].md`. Reviewers read this. |
| `final_scorecard_path` | `logs_dir/reviewer-logs/iter[N]-merged.md` for the last iteration run. Input to the convergence-cleanup fixer dispatch. Set when the loop exits. |
| `live_file_hash` | SHA256 of the live file at cascade start. If it changes during the cascade, halt with an external-edit warning. |
| `lockfile_path` | `state/locks/<artifact_hash_at_acquire>.lock`. |
| `thorough_scorecard_path` | `logs_dir/thorough/combined-scorecard.md` (only if `thorough=true`). |
| `combined_scorecard_path` | `logs_dir/[artifact]-combined-scorecard.md`. Written once at cascade end. |
| `reviewer_parse_failures` | Set of reviewer names whose scorecards failed to parse (excluded after one retry). |

## Main cascade

```
1. acquire_lock(artifact_path)
   - Attempt flock on lockfile. If already held → return "artifact under review, retry later."
   - Write {pid, start_time, session_id, live_file_hash} into lockfile.

2. Check for `logs_dir/REVIEW_SUSPENDED.md`. If present, validate the saved state's shape matches the current engine (no `tier` field from the prior tiered design). If the shape is the old tiered format, halt with "suspended under old schema, delete REVIEW_SUSPENDED.md and restart." Otherwise, auto-resume from the saved state (reviewers, iteration, version) rather than starting fresh. Announce: "Resuming suspended review from [timestamp]."

3. Snapshot baseline (only on fresh start — skipped on resume):
     mkdir -p logs_dir/reviewer-logs
     if logs_dir/[artifact]-v1.md already exists (resume case): do NOT overwrite. v1 is the immutable original, captured on the cascade's first run. Just restore `live_file_hash` and `current_snapshot_path` from the suspended state.
     else (fresh case):
       live_file_hash = sha256(artifact_path)
       copy artifact_path → logs_dir/[artifact]-v1.md
       version = 1
       current_snapshot_path = logs_dir/[artifact]-v1.md

**v1 is write-once.** After it is written on the cascade's first start, nothing in the engine ever writes to that path again. The fixer's `target_path` is always `v[next]`; reviewers never write to version paths at all; resume is read-only against v1. If the user wants to always retrieve the original, v1 in the logs directory is the canonical record.

4. Reviewer loop:
     phase = loop
     for iteration in 1..max_iterations:
       a. If sha256(artifact_path) != live_file_hash:
            halt("live file edited externally during cascade. options: restart, continue from current snapshot, abort")
       b. Dispatch all reviewers in `reviewer_list` in parallel against `current_snapshot_path`.
          Each reviewer writes logs_dir/reviewer-logs/iter[iteration]-[reviewer].md.
          Each dispatch is a fresh Agent call (not a SendMessage to a reused reviewer) to avoid anchoring bias.
       c. Collect scorecards, validate, handle parse failures per Recovery actions.
       d. Merge → logs_dir/reviewer-logs/iter[iteration]-merged.md.
       e. Update session log.
       f. If every reviewer in `reviewer_list` passes (composite ≥ `threshold` AND zero CRITICAL):
            final_scorecard_path = logs_dir/reviewer-logs/iter[iteration]-merged.md
            break loop
       g. If iteration == max_iterations:
            final_scorecard_path = logs_dir/reviewer-logs/iter[iteration]-merged.md
            if any CRITICAL remains:
              halt_cascade_and_checkpoint(reason="iteration cap exhausted with CRITICAL items remaining")
            else:
              break loop  # MAJOR/MINOR handled by the cleanup step below
       h. Dispatch `fixer` agent to apply the iteration's merged scorecard:
          - source_path = current_snapshot_path
          - target_path = logs_dir/[artifact]-v[version+1].md
          - scorecard_path = logs_dir/reviewer-logs/iter[iteration]-merged.md
          After the fixer returns:
            version += 1
            current_snapshot_path = logs_dir/[artifact]-v[version].md
          If the fixer returns empty or refuses: retry once with the refusal text prepended to its prompt. If still empty, halt.
       i. continue loop

5. Convergence cleanup (post-loop):
     phase = cleanup
     a. outstanding = MAJOR/MINOR items in final_scorecard_path (CRITICAL must already be zero to reach here).
     b. If outstanding is empty: skip cleanup, continue to step 6.
     c. Write logs_dir/final-cleanup-request.md with every item in `outstanding`, prefixed with the standard surgical-fix instruction.
     d. Dispatch `fixer`:
          - source_path = current_snapshot_path
          - target_path = logs_dir/[artifact]-v[version+1].md
          - scorecard_path = logs_dir/final-cleanup-request.md
        After the fixer returns:
          version += 1
          current_snapshot_path = logs_dir/[artifact]-v[version].md
     e. No re-review. The convergence cleanup is a trusted surgical pass.

6. Thorough phase (only if `thorough=true`):
     phase = thorough
     a. mkdir logs_dir/thorough/
     b. Dispatch ALL reviewers in `reviewer_list` in parallel against `current_snapshot_path`.
        Each reviewer writes logs_dir/thorough/[reviewer]-thorough.md.
     c. Merge → logs_dir/thorough/combined-scorecard.md.
     d. **Do not apply any findings.** The thorough pass is a convergence audit only.

7. Write logs_dir/[artifact]-combined-scorecard.md:
     - Cascade summary table (per iteration, the convergence cleanup, and the thorough pass if ran).
     - Version trail.
     - Per-iteration final scorecards (pulled from logs_dir/reviewer-logs/iter[N]-merged.md).
     - Convergence cleanup summary (if any items were applied).
     - Thorough audit section (if ran): brief summary + pointer to logs_dir/thorough/combined-scorecard.md.

8. Finalize:
     phase = finalize
     a. copy current_snapshot_path → logs_dir/[artifact]-final.md
     b. copy current_snapshot_path over artifact_path (install the final version at the live path)
     c. Report to the user: final version number, final scores, cascade summary, logs_dir path. If the user wants an earlier version installed instead, they copy it from logs_dir manually.
     d. release_lock()
     e. return DONE.

9. Cap exhaustion with CRITICAL remaining:
      write logs_dir/REVIEW_SUSPENDED.md with full state (iteration, version, reviewer_list, threshold, max_iterations, thorough flag, logs_dir).
      Escalate to the user with a blocking prompt: continue the halted loop, suspend, or fix manually. This is an error-path escalation, not a routine checkpoint — it only fires when a CRITICAL-severity item could not be driven to zero within the configured iteration cap.
      release_lock()
      On next `/review-document` invocation for this artifact, the skill detects the suspended file and auto-resumes.
```

The sections below enumerate the error conditions, validation rules, utilities, and data formats referenced by the cascade above.

## Reviewer dispatch prompt format

A reviewer dispatch prompt contains exactly two things:

1. The path to the current snapshot (`current_snapshot_path`) — the file to score.
2. The path where the reviewer must write its scorecard (`logs_dir/reviewer-logs/iter[N]-[reviewer].md`).

Do not add preferences, protocol instructions, or scoring rubrics to the dispatch prompt. The hook prepends style preferences automatically before the subagent spawns; the scoring protocol is in the reviewer's agent body. A dispatch prompt that adds preference content will cause the reviewer to receive it twice.

## Fixer dispatch contract

Every fixer dispatch passes these three paths in the prompt (plain prose, not JSON — the agent parses the task description):

- `source_path` — absolute path to the version the fixer must read.
- `target_path` — absolute path where the next version must be written. The fixer owns this file.
- `scorecard_path` — absolute path to the scorecard: a merged iteration scorecard during the loop, or the convergence-cleanup request after the loop exits. The behavior is the same either way: apply every row.

There is no `mode` field. The fixer always applies every item in the scorecard exactly; the scorecard itself carries the full instruction. The fixer must never write anywhere except `target_path`. See `${CLAUDE_PLUGIN_ROOT}/agents/fixer.md` for the full contract.

## Recovery actions

| Event | Action |
|---|---|
| Lock acquire fails | Return "artifact under review. Another session holds the lock." |
| External edit to live file during cascade (hash mismatch) | Halt with user prompt: "live file edited externally — restart, continue from current snapshot, or abort?" |
| Reviewer scorecard parse failure (first time) | Re-dispatch that reviewer once with the same input. |
| Reviewer scorecard parse failure (second time) | Mark reviewer "failed to parse", exclude from iteration composite, flag to user, continue. |
| Fixer returns empty/refusal | Retry once with refusal reason prepended. If still empty, surface to user and halt. |
| Fixer writes to a path other than `target_path` | Treat the extra write as an error. Revert the extra write (from git or the pre-dispatch state) and halt. |
| Iteration cap hit with CRITICAL remaining | Halt cascade, suspend or checkpoint. User decides whether to continue the halted loop, finalize anyway, or fix manually. The cap is whatever `max_iterations` was set to (default 3). |
| Old-schema `REVIEW_SUSPENDED.md` detected on resume (contains `tier` field from the prior tiered engine) | Halt with "suspended under old schema, delete REVIEW_SUSPENDED.md and restart." |
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

## Convergence cleanup request format

After the loop exits with convergence (or with no CRITICAL at the cap), remaining MAJOR/MINOR items from `final_scorecard_path` are written to `logs_dir/final-cleanup-request.md` and dispatched to the fixer before finalization.

```markdown
# Convergence cleanup request — [artifact] — v[N+1]

**Instruction:** Apply every item below exactly as the Fix cell specifies. Preserve everything else in the current version byte-for-byte.

## Items to fix

| # | Severity | Location | Issue | Source citation | Fix |
|---|---|---|---|---|---|
| [copied verbatim from the final iteration scorecard's remaining MAJOR/MINOR rows] | | | | | |
```
