---
title: User checkpoint between preliminary extension ideas and deep dive
status: ready-for-planning
date: 2026-04-22
scope: lightweight
---

# User checkpoint between preliminary extension ideas and deep dive

## Problem Frame

Today, `/CASM-tools:paper-extend` dispatches the `extension-proposer` agent once and receives a complete v0 containing (1) a candidate list with feasibility and risk for each, (2) a ranking, (3) a deep dive on the agent's top-ranked candidate, and (4) any supplementary-paper requests. The review cascade then scores and polishes that full artifact. The researcher never sees the candidate list in isolation and has no natural opportunity to redirect the agent before the deep dive is written. This is the wrong sequencing for research work: the agent's top pick may not match the researcher's taste, data access, or the follow-on paper they want to write, and a mismatch surfaces only after substantial write-up effort has already been spent.

## Goal

Insert a user checkpoint between the candidate-generation step and the deep-dive step of `/CASM-tools:paper-extend`. The agent pauses with candidates and ranking in hand; the researcher picks the direction (accepting the top rank, choosing a different candidate, or asking for revisions); the agent then writes the deep dive on the chosen candidate and hands off to the review cascade as usual.

## Requirements

- R1. `extension-proposer` produces a **preliminary artifact** containing the candidate list and the agent's ranking only. It does **not** produce the deep dive in this first pass.
- R2. After the preliminary artifact is written, `/CASM-tools:paper-extend` pauses and presents the candidates and ranking to the user with a blocking prompt.
- R3. The user has three response options at the checkpoint:
    1. **Accept the top-ranked candidate.** The agent proceeds to the deep dive on candidate #1.
    2. **Pick a different candidate.** The user names a candidate (by number or title); the agent proceeds to the deep dive on that candidate.
    3. **Revise candidates.** Free-form instruction (e.g., "drop #2, add one about unemployment risk sharing", "regenerate with stronger focus on empirical identification"). The agent re-runs candidate generation with the instruction incorporated, produces a fresh preliminary artifact, and re-enters the checkpoint.
- R4. The **supplementary-paper request cycle** (existing behavior) moves to *after* the candidate is chosen. Papers are requested in service of the chosen deep dive, not speculatively against every candidate.
- R5. This checkpoint fires in **both** direct invocations of `/CASM-tools:paper-extend` and invocations via `/CASM-tools:paper-full-pipeline`. The full-pipeline skill's narrative is updated to list this as a fourth expected interruption point, alongside preprocess choice, supplementary-paper request, and CRITICAL escalation.
- R6. The preliminary artifact is written to a durable path (e.g., `paper-extension/extensions-candidates.md`) so the user's decision is grounded in a readable file rather than scroll-back. The deep-dive phase appends to or replaces this file to produce `paper-extension/extensions.md`; the cascade still reads the final combined file.
- R7. The session log records the checkpoint interaction: which candidates were proposed, the agent's ranking, the user's chosen candidate (with index), any revise instructions, and the number of revise rounds.
- R8. The existing review cascade behavior on the final `extensions.md` is unchanged (including the `advisory adversarial` clause and auto-installation at the live path).

## Scope Boundaries

- Not changing the structure of an individual candidate entry (still Idea / Type / What changes / Why interesting / Feasibility / Risk).
- Not changing the deep-dive template itself.
- Not changing `paper-summarize` or `paper-present`. The checkpoint is specific to `paper-extend`.
- Not adding a checkpoint to the review cascade itself — the review stage remains deterministic and non-interactive.

## Non-goals

- No AFK auto-accept. If the user is unavailable, the checkpoint blocks; the skill does not silently pick the top candidate and continue. (This matches the existing supplementary-paper request behavior.)
- No timeout. The checkpoint is indefinite-blocking, consistent with the other interactive points in the pipeline.
- No editor-style inline editing of candidates by the user. Revisions go through the `revise` option, which re-dispatches the agent. Direct user edits to the preliminary artifact are technically possible on the filesystem but not a supported interaction path.

## Success Criteria

- A researcher running `/CASM-tools:paper-extend` receives a candidate list and ranking before any deep-dive content is generated, and can confirm or redirect the direction before the agent commits write-up effort.
- The full pipeline still completes end-to-end on approval; the new checkpoint is the only additional pause added.
- The review cascade continues to operate on a single `extensions.md` artifact without needing to re-run on the preliminary file.

## Key Decisions Resolved

- **Checkpoint shape (Option A from brainstorm).** Candidate list + ranking only in the preliminary pass; user picks which candidate gets the deep dive. Rejected Option B (full v0 then approve/redirect — wastes deep-dive effort on redirect) and Option C (candidates only, no ranking — loses a useful signal from the agent).
- **Applies in full-pipeline too (Option A from Question 2).** The value proposition — preventing a finalized write-up on the wrong candidate — matters most in hands-off pipeline runs, so the checkpoint must fire there as well.
- **Interaction affordances.** Three verbs: accept, pick N, revise. Revise is free-form and re-enters the checkpoint after a fresh candidate pass.
- **Supplementary papers move downstream.** Requests now happen after the candidate is chosen, scoped to the chosen extension rather than every candidate.
- **Two-file intermediate state.** Preliminary artifact at `paper-extension/extensions-candidates.md`; final artifact at `paper-extension/extensions.md`. The cascade only operates on the final file, preserving the cascade's existing contract.

## Deferred to Planning

- How the agent receives the user's decision — SendMessage to the paused `extension-proposer` instance (preserving its context) versus a fresh Agent call with the chosen candidate as input. Both work; the trade-off is context reuse versus dispatch simplicity.
- Exact path and naming for the preliminary artifact (current proposal: `paper-extension/extensions-candidates.md`).
- How the revise loop is bounded — whether to cap revise rounds (e.g., 3) with an escalation after the cap, or leave uncapped and rely on the user to stop.
- How the checkpoint's blocking prompt is rendered (platform question tool, numbered options, or freeform input) — this is skill-author choice at implementation time.

## Sources & References

- `plugins/CASM-tools/skills/paper-extend/SKILL.md` — current flow (steps 3, 4, 5).
- `plugins/CASM-tools/agents/extension-proposer.md` — current agent contract and output format.
- `plugins/CASM-tools/skills/paper-full-pipeline/SKILL.md` — the "User Interaction Points" section, which needs to gain a fourth entry.
