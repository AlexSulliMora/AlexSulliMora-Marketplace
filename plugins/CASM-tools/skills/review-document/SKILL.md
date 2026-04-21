---
name: review-document
description: |
  Run the creator/reviewer parallel cascade on a deliverable artifact. Use when the user types /CASM-tools:review-document, says "review the [draft/slides/code/section]", asks for a full quality pass, or requests specific reviewers (writing, structure, math, code, simplicity, adversarial, presentation, consistency, factual, all, thorough) on a file or recently materialized inline text. The cascade operates on snapshots in the logs directory; the live file is untouched until the cascade finishes, at which point the final version is installed automatically.
argument-hint: "[scope phrase] [paths]"
allowed-tools: ["Read", "Write", "Edit", "Bash", "Grep", "Glob", "Agent"]
---

# /CASM-tools:review-document

Run the creator/reviewer parallel cascade on a named artifact. Dispatches all selected reviewers in parallel each iteration, merges their scorecards into one aggregated list, and dispatches the fixer once per iteration to apply the aggregate. The loop ends when every reviewer passes (composite ≥ 90 AND zero CRITICAL) or after 3 iterations; a final cleanup fixer pass then applies any remaining MAJOR/MINOR items before finalization. Optionally runs a thorough audit pass. Installs the final version at the live path automatically. No interactive checkpoint — the cascade is deterministic. The user's override path is a shell `cp` from the logs directory.

This skill is the user-facing surface. The state machine lives in `${CLAUDE_PLUGIN_ROOT}/scripts/loop-engine.md`; the reviewer protocol lives in `${CLAUDE_PLUGIN_ROOT}/scripts/reviewer-common.md`; the end-to-end cascade protocol lives in `${CLAUDE_PLUGIN_ROOT}/scripts/orchestrate-review.md`. Read those for details not covered here.

## Preference injection (automatic via hook)

Each reviewer's style preferences are injected automatically by the plugin's PreToolUse hook before the subagent spawns. You do not need to read, locate, or include any preferences files in the dispatch prompt.

> **Dispatch exactly the task. Do not add preferences.**
> The hook prepends the relevant style preferences to each reviewer's prompt automatically.
> If you include preference content manually, the reviewer receives it twice.
> If the hook is disabled, each reviewer's agent body carries a fallback "read preferences if not injected" pointer — the reviewer handles recovery, not the orchestrator.

## Artifact name constraint (Write-filter compatibility)

The cascade derives every versioned output filename (`<artifact>-v1.md`, `<artifact>-final.md`, `<artifact>-combined-scorecard.md`) from the artifact's basename. A Claude Code server-side filter ([issue #44657](https://github.com/anthropics/claude-code/issues/44657)) blocks the subagent Write tool on any file whose basename starts (case-insensitive) with `report`, `summary`, `findings`, or `analysis`. Until that filter is lifted, **rename any artifact with one of those prefixes before invoking the cascade** — e.g. `summary.md` → `paper-summary.md`, `analysis.md` → `draft-analysis.md`. Cascade dispatches on a blocked basename will silently fail at the reviewer fixer step.

## Quick start

Two invocation shapes cover most use:

- `/CASM-tools:review-document <path>` — auto-classifies reviewers from the file extension and runs the cascade.
- `/CASM-tools:review-document <scope-phrase> <path>` — names specific reviewers (e.g. `writing`, `all`, `thorough`), either alongside or in place of the auto-classified set.

See "Examples" below for concrete walkthroughs. Invoking `/CASM-tools:review-document <path>` on an artifact with a `REVIEW_SUSPENDED.md` file in its logs directory auto-resumes the suspended cascade.

## Argument parsing

Parse `$ARGUMENTS` in this order. The grammar is closed: no flags, only paths, scope tokens, and an optional `into <dir>` clause. Filler words (`the`, `for`, `only`, `just`, `on`, `against`, `a`) are stripped.

### 1. Extract path tokens

Any token that matches one of the following is a path:
- An absolute filesystem path (starts with `/` on Unix or `C:\` / drive letter on Windows).
- A relative path that resolves to an existing file under the session's initial cwd.
- The basename of an entry in `state/session-registry.json`.
- The basename of a file in `state/inline/`.

Collect paths into the target list. If multiple paths are provided, dispatch reviewers that support multi-artifact input (consistency-reviewer) on the set; other reviewers run once per artifact.

### 1a. Extract `into <dir>` clause (optional)

If the arguments contain the two-token sequence `into <dir>`, the `<dir>` token sets `logs_dir` for this cascade and overrides the default location. The directory is created if it does not exist. The pipeline skills (`paper-summarize`, `paper-extend`, `paper-present`) use this to route cascade output into their own per-paper log folders.

- `<dir>` can be an absolute path or a path relative to the session cwd.
- If `<dir>` already contains a `REVIEW_SUSPENDED.md`, the cascade auto-resumes from it (same semantics as the default-location resume).
- Only one `into <dir>` clause is permitted per invocation.

### 2. Scope tokens (closed grammar)

Remaining tokens form the scope phrase. Each token matches one of these:

| Token | Effect |
|---|---|
| `writing` | dispatch `writing-reviewer` |
| `structure` | dispatch `structure-reviewer` |
| `math` | dispatch `math-reviewer` |
| `code` | dispatch `code-reviewer` |
| `simplicity` | dispatch `simplicity-reviewer` |
| `adversarial` | dispatch `adversarial-reviewer` |
| `presentation` | dispatch `presentation-reviewer` |
| `consistency` | dispatch `consistency-reviewer` |
| `factual` | dispatch `factual-reviewer` |
| `all` | dispatch every reviewer, including factual |
| `thorough` | run a final audit pass after the cascade finalizes (see Thorough audit below); combines with any other scope tokens |

Unknown tokens trigger "did you mean" clarification. Example: `/CASM-tools:review-document for correctness and speed` → "Unknown scope tokens: 'correctness', 'speed'. Did you mean `code` or `simplicity`?"

### 3. Empty-scope auto-classification

If no scope tokens remain (after stripping filler and extracting paths), classify applicable reviewers from the artifact type:

| Artifact type | Default reviewers |
|---|---|
| `.py`, `.ipynb` | code, simplicity |
| `.qmd` with code blocks | code, simplicity, writing, structure, math (if math content) |
| `.qmd` with slides | writing, presentation, consistency (if paired), math (if math content) |
| `.md`, `.txt` (text) | writing, structure |
| `.tex` | writing, structure, math |
| `.pdf` (compiled slides) | presentation |
| anything in `state/inline/` | adversarial (the default for materialized chat) |
| multiple artifacts (≥ 2) | add `consistency` to whatever else was selected |

**factual-reviewer is never auto-selected.** Must be named explicitly (via `factual` or `all`).

The `thorough` token, if present, applies after the reviewer list is resolved. It does not select reviewers itself; it triggers the audit pass with whichever reviewers were selected.

### 4. Announce

Before dispatching, print a flat announcement naming the selected reviewers. The thorough audit line appears only when the `thorough` token was present.

```
cascade: <artifact-path>
  reviewers: <r1>, <r2>, <r3>, ...
  convergence cleanup: ON (automatic)
  thorough audit: ON (requested)   <-- only if `thorough` token present
```

If no reviewer applies to this artifact, error out: "no applicable reviewers for this artifact. Check scope or file type."

## Artifact resolution

1. If paths were extracted, use them as the target list.
2. For each target, check for `<logs_dir>/REVIEW_SUSPENDED.md`. If present, resume from the saved state instead of starting fresh. Announce the resume.
3. If no paths were extracted, read `state/session-registry.json` and pick the most recent entry for the current session.
4. If registry is empty or has no entry for the current session, error with recent entries as suggestions:

   ```
   No artifact in this session. Did you mean:
   - paper/slides.qmd (last written 2026-04-17 14:22)
   - analysis/event-study.py (last written 2026-04-17 13:05)
   - state/inline/inline-2026-04-17T09-30.md (materialized chat content)
   Invoke /CASM-tools:review-document <path> to pick one, or write a new artifact first.
   ```

5. If the user invoked `/CASM-tools:review-document adversarial` with no explicit path AND the last substantial turn produced chat content rather than a file Write, materialize the chat content:
   - Scan the recent message for a reviewable block (≥ 150 words of connected writing).
   - Refuse materialization if the current turn included a WebFetch or PDF read (security). Require explicit user confirmation in that case.
   - Write to `state/inline/inline-<timestamp>.md` with first line: `<!-- SOURCE: untrusted chat prose, not user-authored -->`.
   - Announce the materialization: `→ materialized inline content as state/inline/inline-2026-04-17T14-22.md`.
   - Dispatch adversarial-reviewer against the materialized file.

## Lockfile protocol

For each target artifact:

1. Compute `artifact_hash = sha256(<artifact-path>)`.
2. Attempt `flock` on `state/locks/<artifact_hash>.lock` (non-blocking).
3. On acquire failure, abort with: "Artifact is under review in another session."
4. Write lock contents: `pid: <current>\nstart_time: <ISO>\nsession_id: <current>\nartifact_hash: <hash>`.
5. On checkpoint terminal decision, suspension, or unrecoverable halt, release the lock.
6. If a lockfile exists but `flock` succeeds (OS dropped the lock because the owning process died), treat as stale and continue.

## Cascade

The full cascade is specified in `${CLAUDE_PLUGIN_ROOT}/scripts/orchestrate-review.md` and the state machine in `${CLAUDE_PLUGIN_ROOT}/scripts/loop-engine.md`. This skill's responsibility is to:

- Resolve the artifact (above).
- Acquire the lock (above).
- Announce the selected reviewers (above).
- Call the loop-engine state machine with the artifact path, reviewer list, logs directory, and `thorough` flag. Dispatch each reviewer via the Agent tool normally; the plugin's PreToolUse hook handles preferences injection before the subagent spawns. Reviewer dispatch prompts contain only the snapshot path and scorecard output path — nothing else.
- Print the terminal report (see `orchestrate-review.md` § Finalization) when the engine returns. No interactive checkpoint — the engine has already installed the final version at the live path.

### Key cascade behaviors

- **The live file is not modified during the cascade.** Baseline snapshot is `<logs_dir>/<artifact>-v1.md`. Every revision writes a new version (v2, v3, ...). Reviewers always read the latest snapshot. At cascade end, the final version is installed at the live path automatically.
- All selected reviewers run in parallel each iteration; iterations run sequentially.
- The orchestrator merges every reviewer's scorecard for an iteration into a single aggregate at `<logs_dir>/reviewer-logs/iter[N]-merged.md`. The fixer reads that single aggregate and applies every row.
- The loop runs up to 3 iterations and ends when every reviewer passes (composite ≥ 90 AND zero CRITICAL), or at iteration 3 with no CRITICAL remaining.
- After the loop exits, a single convergence-cleanup fixer dispatch applies any remaining MAJOR/MINOR items. No re-review follows.
- If `thorough` was requested, run a final parallel audit pass against the finalized version. Results save to `<logs_dir>/thorough/`. No fixes applied.
- **Revisions are produced by the `fixer` agent, not by the main session.** The orchestrator passes (source_path, target_path, scorecard_path) and the fixer applies every item in the scorecard. No mode flag. See `${CLAUDE_PLUGIN_ROOT}/agents/fixer.md`.
- Reviewers are always dispatched fresh per iteration (new Agent call, not a SendMessage to a reused reviewer) to avoid anchoring bias.
- Scorecard parse validation is strict (see loop-engine.md).

### Logs directory

Default: `docs/reviews/<artifact-basename>-<YY-MM-DD>T<HH-MM>/`, repo-root-relative. Override with the `into <dir>` clause. See `orchestrate-review.md` for the naming rules (24-hour PST, collision suffixes, lexicographic-sort property) and the internal layout (`reviewer-logs/`, `thorough/`, versioned snapshots, `-final.md`, `-combined-scorecard.md`).

## Thorough audit

When the user includes `thorough` in the scope phrase, the engine runs an additional parallel audit pass after the cascade finalizes. The audit:

- Dispatches every originally-selected reviewer once more in parallel against the finalized version.
- Saves scorecards to `<logs_dir>/thorough/<reviewer>-thorough.md`.
- Merges into `<logs_dir>/thorough/combined-scorecard.md`.
- **Does not apply any findings.** Items raised in the audit are purely informational: they tell the user whether the cascade actually converged or whether the reviewers would keep flagging issues given another turn.

The terminal report includes a brief summary of the audit with a pointer to the combined audit scorecard.

## Finalization

When the engine finishes, it installs the final version at the live path and prints a terminal report (cascade summary, final scores, thorough audit summary if any, pointer to the logs directory). There is no interactive checkpoint.

If the user wants a different version installed, they copy it manually:

```bash
cp <logs_dir>/<artifact>-v3.md <artifact_path>
```

If the user consistently disagrees with what gets flagged, the right fix is to edit the reviewer's preferences file at `${CLAUDE_PLUGIN_ROOT}/preferences/<reviewer>-style.md`, not to override individual runs. Calibration through preferences is durable and shared across future cascades.

## Failure modes

| Situation | Behavior |
|---|---|
| Scorecard parse failure (first time) | Re-dispatch that reviewer once. |
| Scorecard parse failure (second time) | Mark "failed to parse", exclude from composite, flag to user, continue. |
| Fixer returns empty / refusal | Retry once with refusal text prepended. If still empty, surface and halt cascade. |
| Fixer writes outside its `target_path` | Treat as error; revert the extra write and halt. |
| External edit to live file during cascade | Halt with prompt: "live file edited externally — restart, continue from current snapshot, or abort?" |
| Iteration cap hit with CRITICAL remaining | Escalate to the user (blocking prompt: continue / suspend / fix manually). If the user is AFK, write `REVIEW_SUSPENDED.md` and release lock; next invocation auto-resumes. |
| Convergence cleanup fixer skipped an item (row genuinely unapplicable) | Item stays in the combined scorecard as unresolved. Cascade still finalizes; the user can re-run `/review-document` after adjusting preferences or manually editing the live file. |
| Concurrent `/CASM-tools:review-document` on same artifact | Rejected by lockfile. |
| Unknown scope token | Print "Unknown scope tokens: ... Did you mean ...?" and halt. No silent best-guess. |
| Preference-injection hook disabled or fails | Reviewers fall back to reading their preferences file directly via the pointer in the agent body. No cascade regression; preferences still reach the reviewer, just via a file read instead of the dispatch prompt. |

## Examples

### Scope-only invocation

```
/CASM-tools:review-document the slides for writing only
```

1. Path tokens: "slides" → registry lookup → `paper/slides.qmd`.
2. Scope tokens: `writing` → `writing-reviewer`. (Filler `the`, `for`, `only` stripped.)
3. Announce:
   ```
   cascade: paper/slides.qmd
     reviewers: writing-reviewer
     convergence cleanup: ON (automatic)
   ```
4. Acquire lock, enter cascade; the hook injects writing preferences into the writing-reviewer dispatch automatically.

### Path-only invocation

```
/CASM-tools:review-document analysis.py
```

1. Path tokens: `analysis.py` → resolved under cwd.
2. Scope tokens: empty → auto-classify from `.py` → `code, simplicity`.
3. Announce:
   ```
   cascade: analysis.py
     reviewers: code-reviewer, simplicity-reviewer
     convergence cleanup: ON (automatic)
   ```

### Thorough audit

```
/CASM-tools:review-document thorough paper.md
```

1. Path tokens: `paper.md`.
2. Scope tokens: `thorough` (strips to audit-flag), then auto-classify from `.md` → `writing, structure`.
3. Announce:
   ```
   cascade: paper.md
     reviewers: structure-reviewer, writing-reviewer
     convergence cleanup: ON (automatic)
     thorough audit: ON (requested)
   ```
4. After the loop + convergence cleanup finalize, run one more parallel pass of structure + writing against the finalized snapshot; save to `<logs_dir>/thorough/`; no fixes.

### All reviewers

```
/CASM-tools:review-document all paper/writeup.qmd
```

1. Path tokens: `paper/writeup.qmd`.
2. Scope tokens: `all` → every reviewer including factual.
3. Announce the full reviewer list; cascade proceeds. The hook injects preferences into every reviewer's dispatch.

### Adversarial on chat content

```
/CASM-tools:review-document adversarial
```

User has just written a paragraph-long research idea in chat.

1. Scope tokens: `adversarial`.
2. No explicit path → auto-materialize the last substantial chat block (≥ 150 words) to `state/inline/inline-2026-04-17T14-22.md` with `<!-- SOURCE: untrusted chat prose, not user-authored -->`.
3. Announce materialization, then:
   ```
   cascade: state/inline/inline-2026-04-17T14-22.md
     reviewers: adversarial-reviewer
     convergence cleanup: ON (automatic)
   ```
4. Enter cascade.

### Invocation with explicit logs directory

```
/CASM-tools:review-document all paper-extension/paper-summary.md into paper-extension/paper-summary-logs/paper-summary-26-04-20T14-30
```

1. Path tokens: `paper-extension/paper-summary.md`.
2. `into <dir>`: sets `logs_dir = paper-extension/paper-summary-logs/paper-summary-26-04-20T14-30`. Directory is created if missing.
3. Scope tokens: `all`.
4. Cascade writes its version snapshots, `reviewer-logs/`, `thorough/`, final, and combined scorecard into the named directory rather than the default `docs/reviews/...` location. The pipeline skills invoke `/CASM-tools:review-document` this way so cascade artifacts live beside the paper-extension content.

### Resume a suspended review

```
/CASM-tools:review-document paper.md
```

If `<logs_dir>/REVIEW_SUSPENDED.md` exists (prior cascade halted with CRITICAL items unresolved), the skill auto-detects and resumes from the saved state; no explicit resume command is needed.

## Anti-patterns

- Do NOT dispatch reviewers serially. Every selected reviewer runs in parallel within one iteration.
- Do NOT dispatch the fixer N times per iteration (once per reviewer). The orchestrator merges all reviewer scorecards into one aggregate, and the fixer runs once per iteration against that single aggregate.
- Do NOT modify the live file during the cascade. The live file is only replaced when the engine finalizes.
- Do NOT write revisions from the main session. Revisions are produced by the `fixer` agent. Dispatching the fixer keeps the main session context clean of intermediate draft content.
- Do NOT reuse a reviewer agent across iterations via SendMessage. Each iteration dispatches a fresh reviewer Agent call so scoring does not anchor on prior scores.
- Do NOT pass a `mode` flag to the fixer. The fixer has one behavior: apply every item in the scorecard exactly. The scorecard supplies the instruction.
- Do NOT apply items from the thorough audit pass. The audit is informational only.
- Do NOT silently guess at an unknown scope token. The closed grammar is enforced so unparseable input fails loudly.
- Do NOT reintroduce an interactive checkpoint. If the user consistently disagrees with what gets flagged, they update the relevant `<reviewer>-style.md` preferences file. Per-run overrides are a shell `cp` from the logs directory; the cascade itself does not negotiate.
