---
title: "fix: Prevent orchestrator from manually injecting preference file contents"
type: fix
date: 2026-04-20
---

# fix: Prevent orchestrator from manually injecting preference file contents

## Overview

An orchestrator running a skill (e.g. `review-document`, `summarize`) manually copied the contents of preference files into subagent dispatch prompts, duplicating what the `inject-preferences.py` PreToolUse hook was already doing. The result: each dispatched reviewer or creator agent received its preferences twice. This plan fixes the conditions that made that possible.

## Problem Statement

The current SKILL.md files describe the preference injection hook in enough detail that an orchestrator can — and apparently does — reason its way into replicating the hook's behavior manually:

1. **`review-document/SKILL.md` lines 16–20** names the preferences directory (`${CLAUDE_PLUGIN_ROOT}/preferences/<name>-style.md`) and explains that the hook prepends file contents to dispatch prompts. An orchestrator reading this can infer exactly how to replicate the injection itself.

2. **`summarize/SKILL.md` lines 12–16 and 59–61** similarly reveals the preferences directory path and the per-agent file mapping.

3. **The prohibition** ("Do NOT manually include preferences blocks in the reviewer dispatch prompt") exists in `review-document/SKILL.md` but appears at line 318 — after 300 lines of other content and buried in a 10-item anti-patterns list. It is easy to read the preference injection section, internalize "preferences need to be in the prompt", and never reach the prohibition.

4. **The fallback mechanism** ("read preferences file directly if not injected") in each agent's body further reinforces the idea that preferences are the caller's problem to arrange.

The anti-pattern rule was right but poorly positioned. The fix is to close the gap between where the hook is described and where the prohibition lives, remove unnecessary implementation details from orchestrator-facing docs, and give the orchestrator a concrete positive example of what a correct dispatch prompt looks like.

## Proposed Solution

Three complementary changes, applied to all relevant SKILL.md files:

### A. Promote and strengthen the prohibition (primary fix)

Move the "Do NOT manually inject preferences" rule from the anti-patterns list to immediately after the preference injection description, formatted as a stand-alone warning block. Remove it from the anti-patterns list (no duplicate). Rewrite it as an explicit positive/negative pair:

```
> **Dispatch exactly the task. Do not add preferences.**
> The hook prepends preference file contents automatically before the subagent spawns.
> If you include preference content manually, the agent receives it twice.
> A correct dispatch prompt contains only: the artifact path, the logs directory path,
> and a one-sentence task description. Nothing else.
```

### B. Remove implementation details from orchestrator-facing descriptions (reduces replicate-ability)

The orchestrator does not need to know the preferences directory path or the per-agent file mapping. Those are the hook's concern. Rewrite the preference injection section in each SKILL.md to describe the *effect* (preferences are injected) without the *mechanism* (where the files live or what gets read).

Before (current `review-document/SKILL.md` lines 16–18):
> "Style preferences... live under `${CLAUDE_PLUGIN_ROOT}/preferences/<name>-style.md`. A `PreToolUse` hook... intercepts every Agent tool dispatch... and prepends the relevant preferences file contents..."

After:
> "Each reviewer's style preferences are injected automatically by the plugin's PreToolUse hook before the subagent spawns. You do not need to read or include any preferences files."

### C. Add an explicit dispatch template (gives a positive example)

Add a "## Dispatch format" or "## What goes in a dispatch prompt" subsection to the cascade/loop-engine documentation that shows concrete, minimal dispatch prompts. An orchestrator that has a clear positive example is less likely to improvise:

```markdown
## Dispatch prompt format

Every reviewer dispatch contains exactly three things:
1. The path to the current snapshot (`current_snapshot_path`)
2. The path to the reviewer's output file in the logs directory
3. A one-sentence description of what to review

Preferences, protocol instructions, and scoring rubrics are already in the agent's body
and in the hook-injected prefix. Do not add them to the dispatch prompt.
```

Apply the same treatment to fixer and creator agent dispatch descriptions.

## Technical Considerations

- All three changes are documentation-only. No code changes to the hook script or agent bodies.
- The fallback in each agent's body ("read preferences file if not injected by hook") stays unchanged — it protects against hook failure, not orchestrator behavior.
- The changes must be applied consistently across all skills that describe Agent dispatches with hook injection: `review-document`, `summarize`, `extend`, `present`.
- `orchestrate-review.md` and `loop-engine.md` describe dispatch in prose; both should receive the dispatch template (Change C) and any cross-references updated.

## Acceptance Criteria

- [x] `review-document/SKILL.md`: preference injection section describes effect only (no file paths); prohibition appears immediately after that section as a bold warning block; prohibition removed from anti-patterns list; dispatch template added near cascade section.
- [x] `summarize/SKILL.md`: same treatment — preference injection section revised, prohibition added inline, file path removed.
- [x] `extend/SKILL.md`: same treatment.
- [x] `present/SKILL.md`: same treatment.
- [x] `scripts/orchestrate-review.md`: dispatch format note added near reviewer dispatch instructions.
- [x] `scripts/loop-engine.md`: reviewer dispatch prompt format section added before fixer dispatch contract.
- [x] No file path to the preferences directory remains in any SKILL.md or orchestration script that an orchestrating session reads.
- [x] An orchestrator reading the revised SKILL.md from top to bottom encounters the prohibition **before** it has the information to replicate the hook.

## Dependencies & Risks

- **No runtime risk.** All changes are documentation. The hook, agent bodies, and fallback mechanism are untouched.
- **Fallback still works.** Agents that are dispatched directly (not through the hook) still have the "read preferences if not injected" fallback in their body.
- **Risk of over-restriction.** If the dispatch template is too prescriptive it might break legitimate cases where extra context in a dispatch prompt is warranted (e.g., the fixer's scorecard path, the paper-summarizer's paper path). Keep the template illustrative, not a rigid schema.

## References

### Internal References

- Hook script: [`plugins/CASM-tools/hooks/inject-preferences.py`](../../plugins/CASM-tools/hooks/inject-preferences.py)
- Primary skill: [`plugins/CASM-tools/skills/review-document/SKILL.md:16`](../../plugins/CASM-tools/skills/review-document/SKILL.md) (preference injection section) and [`:318`](../../plugins/CASM-tools/skills/review-document/SKILL.md) (current anti-pattern location)
- Summarize skill: [`plugins/CASM-tools/skills/summarize/SKILL.md:12`](../../plugins/CASM-tools/skills/summarize/SKILL.md)
- Loop engine: [`plugins/CASM-tools/scripts/loop-engine.md:156`](../../plugins/CASM-tools/scripts/loop-engine.md) (fixer dispatch contract)
- Orchestration reference: [`plugins/CASM-tools/scripts/orchestrate-review.md:59`](../../plugins/CASM-tools/scripts/orchestrate-review.md)
- Preferences directory: `plugins/CASM-tools/preferences/` (nine `*-style.md` files)
