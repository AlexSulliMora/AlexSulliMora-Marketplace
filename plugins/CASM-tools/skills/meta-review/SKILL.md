---
name: meta-review
description: This skill should be used when the user asks to "meta-review", "review past paper runs", "improve the paper agents", "what patterns are showing up across my papers", or wants to learn from accumulated paper-extension runs. It reads session logs and mirrored scorecards across past papers, identifies recurring failure patterns, and writes proposed agent and skill updates to ~/.paper-extensions-meta/ — never modifying live files or any per-paper directory.
argument-hint: "[optional-paper-extension-paths-or-roots]"
allowed-tools: ["Read", "Write", "Bash", "Grep", "Glob"]
---

# Meta-Review

Read accumulated paper-extensions session logs and mirrored scorecards across past papers, identify recurring failure patterns, and propose updates to creator/reviewer agents, skills, and preferences files. This skill is **read-only** with respect to live plugin files and per-paper directories — it only writes to `~/.paper-extensions-meta/`.

## Hard constraints (non-negotiable)

> **NEVER write to any file under `${CLAUDE_PLUGIN_ROOT}/` or any `paper-extension/` per-paper directory.**
>
> All outputs go under `~/.paper-extensions-meta/`. The live plugin is read-only — you read current files only to copy them as starting points for proposed replacements. Per-paper directories are read-only — you read their session logs and mirrored scorecards only as input data.
>
> The user must always be able to diff your proposals against live files and decide what to apply manually.

If you ever find yourself about to write to a path that does not begin with `~/.paper-extensions-meta/`, stop and reconsider.

## Scope of proposed changes

All live files are in one plugin. Proposals may touch any of these, but still flag the blast radius because the review cascade is used outside the paper pipeline too.

Paths below are all under `${CLAUDE_PLUGIN_ROOT}/` — abbreviated `<plugin>/` in the rest of this file.

- **Paper-pipeline creators** (paper-only — affects summarize / extend / present):
  - `<plugin>/agents/paper-summarizer.md`
  - `<plugin>/agents/extension-proposer.md`
  - `<plugin>/agents/presentation-builder.md`
- **Paper-pipeline skills** (paper-only):
  - `<plugin>/skills/{preprocess,summarize,extend,present,run,meta-review}/SKILL.md`
- **Preferences** (shared — affects every `/CASM-tools:review-document` invocation):
  - `<plugin>/preferences/{writing,structure,math,factual,consistency,presentation,simplicity,code,adversarial}-style.md`
- **Reviewer agents** (shared):
  - `<plugin>/agents/*-reviewer.md`
- **Shared scripts** (shared):
  - `<plugin>/scripts/{reviewer-common,orchestrate-review,reviewer-tiers,loop-engine}.md`

When proposing shared-scope changes, flag them explicitly — they affect every `/CASM-tools:review-document` invocation, not just paper work.

## When to run

User-invoked. Typical triggers:

- "Meta-review my recent paper runs"
- "What patterns are showing up across my paper extensions?"
- `/CASM-tools:meta-review`
- `/CASM-tools:meta-review /home/user/research/papers/`

## Process

### 1. Resolve input roots

If positional arguments were passed, treat each as an explicit root. Otherwise default to the current working directory.

For each root, enumerate `paper-extension/` directories:

```bash
find "$ROOT" -type d -name paper-extension 2>/dev/null
```

Build a deduplicated list. If empty, stop and tell the user no runs were found.

### 2. Build the input manifest

For each paper-extension directory, gather:

- Paper title (from the most recent session log's header)
- Stages completed
- Final composite scores per stage (from the combined scorecard inside each stage's cascade logs)
- Cascade logs directory paths (recorded in stage session logs — e.g. `paper-extension/summary-logs/summary-<ts>/`)
- Any outstanding items at cascade end (from the combined scorecard's "Unresolved" section)
- Most recent activity date

Write `~/.paper-extensions-meta/YYYY-MM-DD-HHMMSS/input-manifest.md` (timestamp via `date -u +%Y-%m-%d-%H%M%S`).

Format:

```markdown
# Meta-Review Input Manifest

**Run timestamp:** [YYYY-MM-DD HH:MM:SS UTC]
**Roots searched:** [list]
**Total runs found:** [N]

## Runs

### 1. [Paper title]
- **Path:** [absolute path to paper-extension/]
- **Most recent activity:** [date]
- **Stages completed:** Summarize / Extend / Present
- **Final scores:** Summarize: F=89 M=94 W=82; Extend: …; Present: …
- **Cascade logs:** summary: paper-extension/summary-logs/summary-<ts>/; extend: …; present: …
- **Unresolved at cascade end:** summary: N; extend: M; present: K
```

Report the count to the user. If N > 10, pause and ask whether to proceed with the full set or restrict scope.

### 3. Read structured signals from each run

**Per-stage session logs** (`paper-extension/session-logs/*.md`):
- Pipeline Progress final scores
- Design Decisions → context for non-default choices
- Learnings → user-recorded observations
- Cascade logs paths

**Combined scorecards** (`paper-extension/<stage>-logs/<stage>-<ts>/<stage>-combined-scorecard.md`):
- Per-reviewer composite scores at cascade end
- Items recurring across iterations within one run
- Any unresolved items from tier cleanup skips or CRITICAL-at-cap halts

**Per-iteration merged scorecards** (`paper-extension/<stage>-logs/<stage>-<ts>/reviewer-logs/tier[T]-iter[N]-merged.md`):
- Use when you need detail the combined scorecard doesn't provide (e.g. tracing which iteration first surfaced an issue).

### 4. Cluster recurring issues

Group findings. Example cluster types:

- **Reviewer-specific patterns**: "Writing reviewer flagged 'hedge stacking' on N/M runs." → creator-side fix or reviewer recalibration.
- **Iteration cap hits**: "Extend stage required ≥4 iterations on N/M runs." → extension-proposer struggles to clear the bar.
- **Score floor patterns**: "Reviewer X's first-iteration scores cluster at 78-83." → creator instruction gap.
- **Repeated CRITICAL types**: "Hallucinated content (factual) on N/M runs." → highest-priority signal.
- **Persistent unresolved items**: "Items in 'X category' appear unresolved at cascade end on N/M runs." → the fixer repeatedly couldn't apply them, or the reviewer keeps re-flagging the same underlying thing → calibration target in the preferences file.
- **Oscillation patterns**: score up-then-down → creator overshoots.

For each cluster, record: description, evidence (specific scorecard paths + iteration numbers), frequency (N/M runs), confidence (explicit qualifier: "1 of 1 — low confidence", "3 of 3 — strong signal").

Be honest about confidence. The user set no minimum sample size; label accurately.

### 5. Synthesize proposals

Write `~/.paper-extensions-meta/YYYY-MM-DD-HHMMSS/proposals.md`.

For each cluster, one entry:

```markdown
## Proposal N: [Short pattern description]

**Cluster:** [pattern]
**Confidence:** [N of M runs — explicit qualifier]
**Scope:** [paper-only | shared — see "Scope of proposed changes"]
**Evidence:** [specific scorecard paths and what was observed]
**Hypothesis:** [why this is happening — short]
**Proposed change:** [file to edit, what to add/remove/modify]
**Trade-off:** [what could go wrong]
**Touches:** [files modified]
```

Order by frequency (highest first), then by severity (CRITICAL recurrence first within the same frequency tier). Prefix shared-scope titles with `[SHARED]`.

**Preferences files are the easiest target for most calibration proposals.** If you want to tune severity thresholds, scoring weights, or what-to-flag lists, propose edits to `${CLAUDE_PLUGIN_ROOT}/preferences/<style>.md` — those are the tuning knobs by design.

### 6. Generate proposed replacement files

For each proposal whose `Touches` list includes specific files, **copy the live file as a starting point and edit the copy**. Never edit the live file.

```bash
cp "${CLAUDE_PLUGIN_ROOT}/preferences/writing-style.md" \
   "${HOME}/.paper-extensions-meta/${TIMESTAMP}/CASM-tools/preferences/writing-style.md"
```

Then edit the copy. Each output is a **full standalone replacement** — the user diffs:

```bash
diff ~/.paper-extensions-meta/.../CASM-tools/preferences/writing-style.md \
     ${CLAUDE_PLUGIN_ROOT}/preferences/writing-style.md
```

Mirror the live layout under a single `CASM-tools/` subdir:

```
~/.paper-extensions-meta/YYYY-MM-DD-HHMMSS/
├── input-manifest.md
├── proposals.md
└── CASM-tools/
    ├── preferences/         # proposed preference-file changes (most common)
    ├── agents/              # proposed reviewer and creator changes
    ├── scripts/             # proposed shared-script changes
    └── skills/              # proposed skill changes
```

Only include files actually proposed to change.

### 7. Final report

```
Meta-review complete.

Runs analyzed: N
Output: ~/.paper-extensions-meta/YYYY-MM-DD-HHMMSS/

Top clusters:
  1. [Cluster description] — [confidence] — [scope]
  2. [Cluster description] — [confidence] — [scope]
  3. [Cluster description] — [confidence] — [scope]

Proposed file changes: M ([K] paper-only, [J] shared)
  - CASM-tools/preferences/writing-style.md (shared)
  - CASM-tools/agents/paper-summarizer.md (paper-only)
  - ...

Next steps:
  1. Read proposals.md for full analysis.
  2. Diff each proposed file against the live one.
  3. Apply manually. Shared-scope changes affect every /CASM-tools:review-document, not just paper work.
```

Stop. Do not offer to apply — the user applies.

## Output structure

```
~/.paper-extensions-meta/YYYY-MM-DD-HHMMSS/
├── input-manifest.md
├── proposals.md
└── CASM-tools/             # only if any proposals exist (preferences/, agents/, scripts/, skills/)
```

## What this skill does NOT do

- Does not modify live config under `~/.claude/plugins/`.
- Does not modify per-paper `paper-extension/` directories.
- Does not auto-apply proposals.
- Does not enforce a minimum sample size. Confidence labels handle this.
- Does not invent issues. Every cluster traces back to specific evidence cited in `proposals.md`.
- Does not recommend the same change twice. Merge clusters that point to the same fix.

## Important notes

- **Re-runnable.** Each invocation gets a new timestamped subdirectory. Old outputs are preserved.
- **Idempotent on input.** Reading paper-extension directories twice produces the same analysis.
- **Preferences files are the canonical tuning surface.** Most proposals should target them, since they're designed to be edited directly by the user.
- **Shared-scope proposals have higher blast radius.** Flag them clearly so the user knows to review with more care.
- **Bash for enumeration only.** Use Bash for `find`, `cp`, `mkdir`, `date`. Use Read/Write/Grep/Glob for file content.
