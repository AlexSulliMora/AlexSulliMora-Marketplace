# Reviewer scope hierarchy

Reviewers run in tiers, highest scope first. Each tier reviews the document after the prior tier's revision has been applied.

A structural reorganization lands before a writing reviewer sees the document, so the writing reviewer never flags a sentence that was going to move anyway.

## Why tiered rather than flat parallel

The earlier design dispatched all reviewers in parallel against the same draft and iterated until every reviewer scored composite ≥ 90. Universal re-scoring after each revision handled cross-reviewer conflicts, but two failure modes remained:

1. **Wasted rewrites.** A writing fix applied in iteration N is moot if the same revision also moves or deletes the sentence per a structure fix, so the rewrite happens anyway.
2. **Oscillation.** A writing fix and a simplicity fix can pull the same sentence in opposite directions. Universal re-scoring catches the conflict but may not resolve it before the 10-iteration cap.

Tiered review addresses both: each tier reviews the draft with upstream fixes already applied.

## Tiers

| Tier | Scope | Reviewers | Why here |
|---|---|---|---|
| 1 | Document shape | `structure`, `presentation`, `consistency` | Fixes that move, merge, split, or delete whole sections or slides. Every downstream fix is premature until shape is settled. |
| 2 | Content correctness | `factual`, `math`, `code` | Fixes to specific claims. Runs after shape so each claim is reviewed in its final location. |
| 3 | Substance pruning | `simplicity` | Deletion of dead weight. Runs before prose polish so writing does not reshape text that is about to be deleted. |
| 4 | Prose quality | `writing` | Sentence-level reshaping of the text that survived pruning. |
| 5 | Adversarial stress | `adversarial` | Final pass. Asks what could still go wrong after the scope-bounded reviewers have had their say. |

Within a tier, reviewers run in parallel. Across tiers, execution is sequential.

## Flow

Each tier iterates until it converges or hits its per-tier cap, then the next tier begins.

```
for tier in 1..5:
    applicable = intersect(tier.reviewers, reviewer_list)
    if applicable is empty:
        continue

    for iteration in 1..3:  # per-tier cap
        dispatch applicable in parallel against current draft
        collect scorecards, write logs_dir/tier[N]-iter[M]-scorecard.md

        if every reviewer in this tier passes (composite ≥ 90 AND zero CRITICAL):
            break  # tier converged, advance

        main session revises based on the tier's merged scorecard

    if tier exits loop without converging AND any CRITICAL remains:
        halt and present the tier's final scorecard to the user
        (user chooses: continue to next tier anyway, suspend, or fix manually)

    # MAJOR and MINOR items that remain after the cap propagate to the final scorecard.

write logs_dir/[artifact]-combined-scorecard.md (final scorecard from each tier, concatenated)
present final draft and combined scorecard at the user checkpoint
```

Convergence rules:

- **Tier convergence condition:** every reviewer in the tier scores composite ≥ 90 AND has zero CRITICAL items.
- **Per-tier cap:** 3 iterations. Chosen so five tiers fit within a budget comparable to the old 10-iteration flat loop. Adjust by editing this file if the cap proves wrong.
- **CRITICAL at cap:** halt and present to the user. CRITICAL items block tier advancement because they mislead readers or break the document.
- **MAJOR / MINOR at cap:** propagate to the combined scorecard. The user handles them at the checkpoint (`accept`, `use <N>`, `keep original`, `fix <numbers>`, `show <number>`). Most MAJOR/MINOR items from the tiers are resolved earlier by the auto-apply phase and rarely reach the user checkpoint.
- **Empty tiers:** if no reviewer in a tier is in `reviewer_list` or if all of the tier's reviewers no-op (composite = 100, zero issues) on the first dispatch, the tier advances without revision.

## Ordering choices

The tier order above is not arbitrary:

- **Structure before content.** A structure fix such as "delete §5" invalidates every content fix in §5. Running structure first avoids that waste. Content fixes do not invalidate structure; a corrected claim does not change where the section sits.
- **Simplicity before writing.** Simplicity deletes; writing reshapes. Polishing a paragraph that later gets deleted is wasted work. Reshaping what remains after pruning is not.
- **Adversarial last.** Adversarial asks what could still go wrong. That question lands better on a document that has already passed the scope-bounded reviewers.
- **Consistency with structure, not content.** Consistency reviews cross-document agreement. Fixing a consistency issue often requires reorganizing one document to match another, which is a structural operation.

## Surgical fixes

The cascade above describes default execution. One exception is worth naming explicitly.

When the user selects `fix <numbers>` at the checkpoint, the tiered cascade does not re-run. Instead, dispatch only the reviewers whose items were selected, in parallel, as in the pre-tiered design. Tiered dispatch is a first-pass optimization; surgical fixes respect the user's chosen scope.

## New reviewers

When adding a new reviewer to the `/review-document` grammar, assign it a tier in this file before merging. Unknown reviewers are treated as tier 5 (after adversarial) as a fallback, but an explicit assignment is always preferred.
