---
title: "refactor: Prefix paper-pipeline skills and outputs with `paper-` to work around Write-filter bug"
type: refactor
date: 2026-04-20
---

# refactor: Prefix paper-pipeline skills and outputs with `paper-`

## Context

Claude Code's subagent Write tool silently rejects `.md` files whose basenames start (case-insensitive) with `report`, `summary`, `findings`, or `analysis` ([issue #44657](https://github.com/anthropics/claude-code/issues/44657)). The restriction is server-side with no opt-out. The CASM-tools paper pipeline writes its canonical summary to `paper-extension/summary.md`, and the review cascade derives every downstream filename from that basename — so `summary-v1.md`, `summary-final.md`, `summary-combined-scorecard.md`, etc. all trip the filter. The paper-summarizer agent and all subagent-driven revisions in the summarize stage are currently broken.

Secondary motivation: the five paper-pipeline skills (`summarize`, `extend`, `present`, `preprocess`, `run`) don't share a prefix, so they don't cluster visually in autocomplete. Renaming them with a `paper-` prefix fixes both issues — the blocked-name problem for the `summarize` artifact chain, and the discoverability problem for the pipeline.

**Intended outcome:** subagents in the paper pipeline can write their outputs again; all five pipeline skills group under `/CASM-tools:paper-*` in autocomplete.

## Problem Statement

Two problems, one plan:

1. **Write-filter breakage.** Any filename whose basename starts with the four blocked prefixes is rejected for subagents. In the current plugin only one artifact chain is directly affected: the `paper-extension/summary.md` artifact and its cascade-derived children. Every other output filename is safe (checked exhaustively — `extensions.md`, `paper.md`, `YYYY-MM-DD_*.md` session logs, `input-manifest.md`, `proposals.md` all pass the filter).

2. **Skill naming inconsistency.** The five paper-pipeline skills use ad-hoc names that don't group in autocomplete. A shared `paper-` prefix fixes that while also matching the artifact-rename convention needed to unblock the Write tool.

The nested-colon grouping (`compound-engineering:workflows:plan`) is undocumented and not part of the Agent Skills open standard, so the flat prefix approach is the right move.

## Proposed Solution

Two coordinated changes applied together:

### A. Rename five skills with `paper-` prefix

| Old directory | New directory | Rationale |
|---|---|---|
| `skills/summarize/` | `skills/paper-summarize/` | verb form preserved |
| `skills/extend/` | `skills/paper-extend/` | verb form preserved |
| `skills/present/` | `skills/paper-present/` | verb form preserved |
| `skills/preprocess/` | `skills/paper-preprocess/` | verb form preserved |
| `skills/run/` | `skills/paper-full-pipeline/` | "run" alone is too generic; "full-pipeline" names what it orchestrates |

Not renamed (intentionally): `skills/review-document/` and `skills/meta-review/`. These are generic-purpose skills, not paper-pipeline-specific.

For each renamed skill, update:
- The SKILL.md `name:` frontmatter field
- All cross-references to the old slash-command name throughout the plugin

### B. Rename the `summary.md` artifact to `paper-summary.md`

The `paper-extension/summary.md` path is the single blocked file in the repo. The review cascade derives all its versioned and final outputs from this basename, so renaming the artifact auto-propagates through the cascade:

| Old path | New path |
|---|---|
| `paper-extension/summary.md` | `paper-extension/paper-summary.md` |
| `paper-extension/summary-logs/summary-<ts>/` | `paper-extension/paper-summary-logs/paper-summary-<ts>/` |
| `paper-extension/summary-logs/summary-<ts>/summary-v{N}.md` | `paper-extension/paper-summary-logs/paper-summary-<ts>/paper-summary-v{N}.md` |
| `…/summary-final.md` | `…/paper-summary-final.md` |
| `…/summary-combined-scorecard.md` | `…/paper-summary-combined-scorecard.md` |

All five derivative basenames now start with `paper-` and clear the filter.

No change needed for any other output filename. The filename audit (see below) confirmed `extensions.md`, session logs, meta-review outputs, `paper.md`, and all cascade filenames that don't derive from the summary artifact are already safe.

### C. Out-of-scope, worth noting

The `skills/review-document/` cascade is generic: a user who invokes `/CASM-tools:review-document all analysis.md` would hit the same filter (the artifact basename `analysis` is blocked). That's a user-input problem, not a paper-pipeline problem, and is not in scope here. Document an inline note in `review-document/SKILL.md` warning users that artifact basenames starting with `report`/`summary`/`findings`/`analysis` will fail until the upstream bug is fixed.

## Technical Considerations

- **Mechanical edit scope.** This is pure text editing plus five `git mv` operations. No logic changes, no schema changes, no hook changes.
- **Plugin manifest.** `plugins/CASM-tools/.claude-plugin/plugin.json` does not enumerate skill directories — Claude Code discovers skills by folder scan. Only the prose description in `plugin.json` needs a mention-update. Confirmed via filename audit.
- **Nested namespacing.** Keeping all skills flat under `skills/` (not introducing subfolders like `skills/paper/summarize/`) is deliberate — nested-colon invocation is undocumented and not part of the Agent Skills spec.
- **Historical plan docs.** `docs/plans/2026-04-20-fix-prevent-orchestrator-preference-injection-plan.md` references old skill names (`summarize/SKILL.md`, etc.) as historical record. Leave as-is — it's a frozen artifact of its own decision.
- **Git-rename hygiene.** Use `git mv` rather than delete+create to preserve file history across the rename.

## Acceptance Criteria

### Skill renames (Change A)

- [x] `skills/summarize/` renamed to `skills/paper-summarize/` via `git mv`; `name:` frontmatter updated; all `/CASM-tools:summarize` slash-command references updated to `/CASM-tools:paper-summarize`; all prose mentions of "the summarize skill" updated.
- [x] `skills/extend/` renamed to `skills/paper-extend/`; same treatment.
- [x] `skills/present/` renamed to `skills/paper-present/`; same treatment.
- [x] `skills/preprocess/` renamed to `skills/paper-preprocess/`; same treatment.
- [x] `skills/run/` renamed to `skills/paper-full-pipeline/`; same treatment, with particular care for the ambiguous word "run" (only update where it references the skill, not where it means "execute").

### Filename rename (Change B)

- [x] Every reference to `paper-extension/summary.md` (live artifact path) updated to `paper-extension/paper-summary.md`.
- [x] Every reference to `paper-extension/summary-logs/...` updated to `paper-extension/paper-summary-logs/...`.
- [x] Every cascade-derived filename pattern (`summary-v{N}.md`, `summary-final.md`, `summary-combined-scorecard.md`) updated with the `paper-` prefix.
- [x] The paper-summarizer agent's dispatch instruction in `skills/paper-summarize/SKILL.md` tells it to write to `paper-extension/paper-summary.md`.
- [x] Example usage in `skills/review-document/SKILL.md:294` updated to show a `paper-summary.md`-flavored example.

### Out-of-scope note (Change C)

- [x] `skills/review-document/SKILL.md` gains a short note warning that artifact basenames starting with `report`/`summary`/`findings`/`analysis` will fail the Write-filter and should be renamed before invoking the cascade.

### Verification

- [x] Grep for `/CASM-tools:summarize|extend|present|preprocess|run\b` across the repo returns zero hits (except in the historical plan document).
- [x] Grep for `paper-extension/summary\.md` across the repo returns zero hits (except in the historical plan document).
- [x] Grep for `summary-logs|summary-v|summary-final|summary-combined` across `plugins/CASM-tools/` returns zero hits.
- [x] Every renamed skill's SKILL.md `name:` field matches its new directory name.
- [ ] A test run of `/CASM-tools:paper-summarize <some-pdf>` dispatches `paper-summarizer`, which successfully writes to `paper-extension/paper-summary.md` (primary validation that the Write filter no longer trips). **Deferred — requires live PDF + pipeline execution; static checks all pass.**

## Files to Modify

**Renamed (5 directories via `git mv`):**
- [plugins/CASM-tools/skills/summarize/](plugins/CASM-tools/skills/summarize/) → `skills/paper-summarize/`
- [plugins/CASM-tools/skills/extend/](plugins/CASM-tools/skills/extend/) → `skills/paper-extend/`
- [plugins/CASM-tools/skills/present/](plugins/CASM-tools/skills/present/) → `skills/paper-present/`
- [plugins/CASM-tools/skills/preprocess/](plugins/CASM-tools/skills/preprocess/) → `skills/paper-preprocess/`
- [plugins/CASM-tools/skills/run/](plugins/CASM-tools/skills/run/) → `skills/paper-full-pipeline/`

**Edited (skill rename + filename rename both apply):**
- [plugins/CASM-tools/skills/summarize/SKILL.md](plugins/CASM-tools/skills/summarize/SKILL.md) — heaviest: `name:` field, many `summary.md`/`summary-logs/` references, self-referential prose
- [plugins/CASM-tools/skills/extend/SKILL.md](plugins/CASM-tools/skills/extend/SKILL.md) — `name:` field, cross-refs to `paper-summarize`, `paper-preprocess`, `summary.md`
- [plugins/CASM-tools/skills/present/SKILL.md](plugins/CASM-tools/skills/present/SKILL.md) — `name:` field, cross-refs, `summary.md`
- [plugins/CASM-tools/skills/preprocess/SKILL.md](plugins/CASM-tools/skills/preprocess/SKILL.md) — `name:` field, cross-refs to other four
- [plugins/CASM-tools/skills/run/SKILL.md](plugins/CASM-tools/skills/run/SKILL.md) — `name:` field, cross-refs to all four, `summary.md` and `summary-logs/` references

**Edited (filename rename only):**
- [plugins/CASM-tools/skills/review-document/SKILL.md:294](plugins/CASM-tools/skills/review-document/SKILL.md) — example uses `summary.md`; update + add filter-warning note
- [plugins/CASM-tools/skills/meta-review/SKILL.md](plugins/CASM-tools/skills/meta-review/SKILL.md) — references `paper-extension/summary-logs/` in lines 73, 95

**Edited (skill rename only):**
- [plugins/CASM-tools/agents/paper-summarizer.md:7,35](plugins/CASM-tools/agents/paper-summarizer.md) — dispatch description
- [plugins/CASM-tools/agents/extension-proposer.md:7,35](plugins/CASM-tools/agents/extension-proposer.md) — dispatch description
- [plugins/CASM-tools/agents/presentation-builder.md:7,30,22,42,227](plugins/CASM-tools/agents/presentation-builder.md) — dispatch description, `summary.md` → `paper-summary.md`
- [plugins/CASM-tools/agents/factual-reviewer.md:8](plugins/CASM-tools/agents/factual-reviewer.md) — example command uses `summary.md`
- [plugins/CASM-tools/.claude-plugin/plugin.json:4](plugins/CASM-tools/.claude-plugin/plugin.json) — prose description mentions old skill names
- [README.md:5,41](README.md) — enumerates old skill names

## Verification (end-to-end)

After implementation:

1. **Static grep pass** — run the three greps in Verification above and confirm zero hits (ignoring `docs/plans/2026-04-20-fix-prevent-orchestrator-*`).

2. **Skill discovery** — confirm Claude Code autocomplete surfaces `/CASM-tools:paper-summarize`, `paper-extend`, `paper-present`, `paper-preprocess`, `paper-full-pipeline` grouped together.

3. **End-to-end pipeline smoke test** — on a small test PDF:
   - Run `/CASM-tools:paper-preprocess <pdf>` → produces `paper-extension/paper.md` (unchanged filename).
   - Run `/CASM-tools:paper-summarize <pdf>` → paper-summarizer agent writes `paper-extension/paper-summary.md` without Write-tool rejection; cascade produces `paper-extension/paper-summary-logs/paper-summary-<ts>/paper-summary-v{N}.md` and `paper-summary-final.md`, `paper-summary-combined-scorecard.md`.
   - Run `/CASM-tools:paper-extend <pdf>` → reads `paper-summary.md`; writes `extensions.md` (unchanged).
   - Run `/CASM-tools:paper-present <pdf>` → reads both and produces slides/writeup.

4. **Regression guard** — `/CASM-tools:review-document` on a non-blocked artifact (e.g. `draft.md`) still works; no reviewer agents blocked.

## References

### Internal
- Cross-reference map and filename audit: produced during research phase; all 10+ touch points enumerated in "Files to Modify".
- Prior related plan: [`docs/plans/2026-04-20-fix-prevent-orchestrator-preference-injection-plan.md`](docs/plans/2026-04-20-fix-prevent-orchestrator-preference-injection-plan.md) (historical; not edited by this plan).

### External
- [claude-code issue #44657](https://github.com/anthropics/claude-code/issues/44657) — root cause of the Write-filter bug.
- [Agent Skills open standard](https://agentskills.io) — confirms single-level namespacing is the portable convention.
- [Claude Code skills docs](https://code.claude.com/docs/en/skills.md) — flat `skills/<name>/SKILL.md` layout.
