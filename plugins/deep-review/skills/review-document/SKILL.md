---
name: review-document
description: |
  Run the creator/reviewer tiered cascade on a deliverable artifact. Use when the user types /deep-review:review-document, says "review the [draft/slides/code/section]", asks for a full quality pass, or requests specific reviewers (writing, structure, math, code, simplicity, adversarial, presentation, consistency, factual, all, thorough) on a file or recently materialized inline text. The cascade operates on snapshots in the logs directory; the live file is never touched until the user's checkpoint decision.
argument-hint: "[scope phrase] [paths]"
disable-model-invocation: true
allowed-tools: ["Read", "Write", "Edit", "Bash", "Grep", "Glob", "Agent"]
---

# /deep-review:review-document

Run the creator/reviewer tiered cascade on a named artifact. Groups selected reviewers into scope tiers, dispatches each tier in parallel after the previous tier converges (or hits its cap), auto-applies any remaining MAJOR/MINOR items, optionally runs a thorough audit pass, and raises a mandatory user checkpoint before the live file is modified.

This skill is the user-facing surface. The tier definitions live in `${CLAUDE_PLUGIN_ROOT}/scripts/reviewer-tiers.md`; the state machine lives in `${CLAUDE_PLUGIN_ROOT}/scripts/loop-engine.md`; the reviewer protocol lives in `${CLAUDE_PLUGIN_ROOT}/scripts/reviewer-common.md`; the cascade and checkpoint protocol lives in `${CLAUDE_PLUGIN_ROOT}/scripts/orchestrate-review.md`. Read those for details not covered here.

## Preference injection (automatic via hook)

Style preferences (scoring weights, severity calibration, what-to-flag lists) for each reviewer live under `${CLAUDE_PLUGIN_ROOT}/preferences/<name>-style.md`. A `PreToolUse` hook (`${CLAUDE_PLUGIN_ROOT}/hooks/inject-preferences.py`, registered in this plugin's `plugin.json`) intercepts every Agent tool dispatch whose `subagent_type` matches a known reviewer and prepends the relevant preferences file contents to the `prompt` field before the subagent spawns.

You do not need to include preferences content manually in the dispatch prompt. Dispatch each reviewer normally — the hook handles injection. If the hook is disabled or fails to resolve its preferences directory, each reviewer agent's body carries a fallback "read preferences file if not already injected" pointer, so the reviewer still scores against the current preferences.

## Quick start

Two invocation shapes cover most use:

- `/deep-review:review-document <path>` — auto-classifies reviewers from the file extension and runs the cascade.
- `/deep-review:review-document <scope-phrase> <path>` — names specific reviewers (e.g. `writing`, `all`, `thorough`), either alongside or in place of the auto-classified set.

See "Examples" below for concrete walkthroughs. Invoking `/deep-review:review-document <path>` on an artifact with a `REVIEW_SUSPENDED.md` file in its logs directory auto-resumes the suspended cascade.

## Argument parsing

Parse `$ARGUMENTS` in this order. The grammar is closed: no flags, only paths and scope tokens. Filler words (`the`, `for`, `only`, `just`, `on`, `against`, `a`) are stripped.

### 1. Extract path tokens

Any token that matches one of the following is a path:
- An absolute filesystem path (starts with `/` on Unix or `C:\` / drive letter on Windows).
- A relative path that resolves to an existing file under the session's initial cwd.
- The basename of an entry in `state/session-registry.json`.
- The basename of a file in `state/inline/`.

Collect paths into the target list. If multiple paths are provided, dispatch reviewers that support multi-artifact input (consistency-reviewer) on the set; other reviewers run once per artifact.

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
| `thorough` | run a final audit pass after auto-apply (see Thorough audit below); combines with any other scope tokens |

Unknown tokens trigger "did you mean" clarification. Example: `/deep-review:review-document for correctness and speed` → "Unknown scope tokens: 'correctness', 'speed'. Did you mean `code` or `simplicity`?"

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

Before dispatching, print a tier-grouped announcement. Each line lists the reviewers that will run in that tier (parallel within the tier). Tiers with no applicable reviewers are omitted.

```
cascade: <artifact-path>
  tier 1 (shape):      <tier-1 reviewers applicable>
  tier 2 (content):    <tier-2 reviewers applicable>
  tier 3 (pruning):    <tier-3 reviewers applicable>
  tier 4 (text):       <tier-4 reviewers applicable>
  tier 5 (adversarial):<tier-5 reviewers applicable>
  auto-apply: ON (default)
  thorough audit: ON (requested)   <-- only if `thorough` token present
```

If no tier has an applicable reviewer, error out: "no applicable reviewers for this artifact. Check scope or file type."

See `${CLAUDE_PLUGIN_ROOT}/scripts/reviewer-tiers.md` for the tier → reviewer mapping.

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
   Invoke /deep-review:review-document <path> to pick one, or write a new artifact first.
   ```

5. If the user invoked `/deep-review:review-document adversarial` with no explicit path AND the last substantial turn produced chat content rather than a file Write, materialize the chat content:
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
- Load tier assignments from `${CLAUDE_PLUGIN_ROOT}/scripts/reviewer-tiers.md`.
- Announce reviewer selection grouped by tier (above).
- Call the loop-engine state machine with the artifact path, reviewer list, tier assignment, logs directory, and `thorough` flag. Dispatch each reviewer via the Agent tool normally; the plugin's PreToolUse hook handles preferences injection before the subagent spawns.
- Render the user checkpoint when the engine returns a terminal state.
- Dispatch the checkpoint decision back into the engine.

### Key cascade behaviors

- **The live file is never modified during the cascade.** Baseline snapshot is `<logs_dir>/<artifact>-v1.md`. Every revision writes a new version (v2, v3, ...). Reviewers always read the latest snapshot.
- Tiers run sequentially; reviewers within a tier run in parallel.
- Each tier iterates to convergence (composite ≥ 90 AND zero CRITICAL for every in-tier reviewer) or hits its 3-iteration cap.
- After tiers complete, auto-apply runs by default: gathers remaining MAJOR/MINOR items, revises, re-reviews in parallel. Up to 3 rounds.
- If `thorough` was requested, run a final parallel audit pass against the final proposed version. Results save to `<logs_dir>/thorough/`. No fixes applied.
- Revision between iterations is written by the main session directly.
- Scorecard parse validation is strict (see loop-engine.md).

### Logs directory

Default: `docs/reviews/<artifact-basename>-<YY-MM-DD>T<HH-MM>/`, repo-root-relative. See `orchestrate-review.md` for the naming rules (24-hour PST, collision suffixes, lexicographic-sort property).

## Thorough audit

When the user includes `thorough` in the scope phrase, the engine runs an additional parallel audit pass after the auto-apply phase converges or caps out. The audit:

- Dispatches every originally-selected reviewer once more in parallel against the final proposed version.
- Saves scorecards to `<logs_dir>/thorough/<reviewer>-thorough.md`.
- Merges into `<logs_dir>/thorough/combined-scorecard.md`.
- **Does not apply any findings.** Items raised in the audit are purely informational: they tell the user whether the cascade actually converged or whether the reviewers would keep flagging issues given another turn.

The checkpoint displays a brief summary of the audit with a pointer to the combined audit scorecard.

## User checkpoint

Render the checkpoint format from `${CLAUDE_PLUGIN_ROOT}/scripts/orchestrate-review.md` § "User Review Checkpoint". Five action verbs: `accept`, `use <N>`, `keep original`, `fix <numbers>`, `show <number>`. Parse the user's reply against exact verb match; unknown replies trigger re-prompt.

- `accept` → install `<logs_dir>/<artifact>-v[final].md` as the new live file. Write `<logs_dir>/accepted-issues.md`. Release lock.
- `use <N>` → install `<logs_dir>/<artifact>-v<N>.md` as the new live file. Write accepted-issues.md. Release lock.
- `keep original` → live file untouched. Write accepted-issues.md noting the user declined. Release lock.
- `fix <numbers>` → build `<logs_dir>/surgical-fix-v[N+1]-request.md`, main session revises the latest snapshot, re-run ALL originally-dispatched reviewers in parallel (not tiered), re-present checkpoint.
- `show <number>` → print full scorecard entry, re-present options.

## Failure modes

| Situation | Behavior |
|---|---|
| Scorecard parse failure (first time) | Re-dispatch that reviewer once. |
| Scorecard parse failure (second time) | Mark "failed to parse", exclude from composite, flag to user, continue. |
| Main session revision returns empty / refusal | Retry once with refusal text prepended. If still empty, surface and halt cascade. |
| External edit to live file during cascade | Halt with prompt: "live file edited externally — restart, continue from current snapshot, or abort?" |
| Tier cap hit with CRITICAL remaining, user AFK | Write `REVIEW_SUSPENDED.md`, release lock. Next invocation auto-resumes. |
| Auto-apply cap hit with items remaining | Proceed to checkpoint with items in the combined scorecard as unresolved. User can `fix <n>` or accept. |
| Concurrent `/deep-review:review-document` on same artifact | Rejected by lockfile. |
| Unknown scope token | Print "Unknown scope tokens: ... Did you mean ...?" and halt. No silent best-guess. |
| Preference-injection hook disabled or fails | Reviewers fall back to reading their preferences file directly via the pointer in the agent body. No cascade regression; preferences still reach the reviewer, just via a file read instead of the dispatch prompt. |

## Examples

### Scope-only invocation

```
/deep-review:review-document the slides for writing only
```

1. Path tokens: "slides" → registry lookup → `paper/slides.qmd`.
2. Scope tokens: `writing` → `writing-reviewer`. (Filler `the`, `for`, `only` stripped.)
3. Announce:
   ```
   cascade: paper/slides.qmd
     tier 4 (text): writing-reviewer
     auto-apply: ON (default)
   ```
4. Acquire lock, enter cascade; the hook injects writing preferences into the writing-reviewer dispatch automatically. Present checkpoint.

### Path-only invocation

```
/deep-review:review-document analysis.py
```

1. Path tokens: `analysis.py` → resolved under cwd.
2. Scope tokens: empty → auto-classify from `.py` → `code, simplicity`.
3. Announce:
   ```
   cascade: analysis.py
     tier 2 (content):  code-reviewer
     tier 3 (pruning):  simplicity-reviewer
     auto-apply: ON (default)
   ```

### Thorough audit

```
/deep-review:review-document thorough paper.md
```

1. Path tokens: `paper.md`.
2. Scope tokens: `thorough` (strips to audit-flag), then auto-classify from `.md` → `writing, structure`.
3. Announce:
   ```
   cascade: paper.md
     tier 1 (shape): structure-reviewer
     tier 4 (text):  writing-reviewer
     auto-apply: ON (default)
     thorough audit: ON (requested)
   ```
4. After cascade + auto-apply, run one more parallel pass of structure + writing against the final snapshot; save to `<logs_dir>/thorough/`; no fixes.

### All reviewers

```
/deep-review:review-document all paper/writeup.qmd
```

1. Path tokens: `paper/writeup.qmd`.
2. Scope tokens: `all` → every reviewer including factual.
3. Announce the full tier layout; cascade proceeds. The hook injects preferences into every reviewer's dispatch.

### Adversarial on chat content

```
/deep-review:review-document adversarial
```

User has just written a paragraph-long research idea in chat.

1. Scope tokens: `adversarial`.
2. No explicit path → auto-materialize the last substantial chat block (≥ 150 words) to `state/inline/inline-2026-04-17T14-22.md` with `<!-- SOURCE: untrusted chat prose, not user-authored -->`.
3. Announce materialization, then:
   ```
   cascade: state/inline/inline-2026-04-17T14-22.md
     tier 5 (adversarial): adversarial-reviewer
     auto-apply: ON (default)
   ```
4. Enter cascade.

### Resume a suspended review

```
/deep-review:review-document paper.md
```

If `<logs_dir>/REVIEW_SUSPENDED.md` exists (prior cascade halted with CRITICAL items unresolved), the skill auto-detects and resumes from the saved state; no explicit resume command is needed.

## Anti-patterns

- Do NOT dispatch reviewers across tiers in parallel. The cascade's purpose is to let each tier see the upstream tier's revisions already applied.
- Do NOT dispatch reviewers within a single tier serially. Within a tier, reviewers are orthogonal and parallel is correct.
- Do NOT modify the live file during the cascade. The live file is only replaced at the checkpoint on the user's terminal decision.
- Do NOT re-run only the failing reviewer on a surgical fix. Surgical fixes re-run ALL originally-dispatched reviewers in parallel to catch regressions.
- Do NOT apply items from the thorough audit pass. The audit is informational only.
- Do NOT silently guess at an unknown scope token. The closed grammar is enforced so unparseable input fails loudly.
- Do NOT skip the user checkpoint even when every phase converges cleanly. The checkpoint is mandatory; it is the only point at which the live file can be modified.
- Do NOT manually include preferences blocks in the reviewer dispatch prompt. The PreToolUse hook handles injection. If you paste preferences manually on top of the hook injection, the reviewer sees two copies.
