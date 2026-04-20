# Adversarial Style Preferences

Scoring weights, severity calibration, and rules for the adversarial-reviewer. Edit this file to tune how demanding the adversarial pass is.

## Scoring weights

| Category | What it measures | Weight |
|---|---|---|
| Assumption robustness | Load-bearing assumptions are evidenced or acknowledged | 35% |
| Inference validity | Conclusions follow from premises; no gaps | 30% |
| Alternative explanations | Rival explanations considered and addressed | 20% |
| Falsifiability | Failure conditions defined, abandonment criteria present | 15% |

Composite = Assumption robustness × 0.35 + Inference validity × 0.30 + Alternative explanations × 0.20 + Falsifiability × 0.15

A score of 90+ means the argument's load-bearing assumptions are defensible and its inferences are tight, not that no objection remains.

## Severity calibration

### CRITICAL
- A load-bearing assumption asserted without evidence that, if false, breaks the core argument.
- An inference with no supporting evidence where the opposite conclusion is consistent with the same observations.
- A plan with no falsification / abandonment criterion where failure would be invisible until expensive.
- A claim that is internally contradictory.

### MAJOR
- Assumptions or inferences that are plausible but under-argued.
- Absent counterfactuals: "we'd expect X" without "vs. the baseline of Y."
- Cherry-picked supporting cases where selection bias is visible.
- Undefined key terms that the argument turns on.

### MINOR
- Minor unexamined implications.
- Small unstated tradeoffs.
- Hedging that hides a crisper claim.

## What NOT to flag

- Writing quality — writing-reviewer's domain.
- Mathematical derivation errors — math-reviewer's domain.
- Code correctness — code-reviewer's domain.
- Stylistic preferences dressed up as substance.
- Objections that require information the author couldn't reasonably have.

## Objection format (domain-specific)

Every objection in the Required Changes table uses this three-part structure in the Issue cell:

1. The objection (1-2 sentences).
2. A concession (best steelman of the artifact's rebuttal).
3. The sharper form that survives the concession.

## Domain-specific rules

- Be demanding but not gratuitously contrarian. An objection that doesn't admit a concession is probably not a real objection.
- Hold the argument to its own stated bar: don't demand evidence for claims the argument hasn't made.
- In synthetic-artifact mode (materialized chat prose), review the argument, not the chat-level ergonomics. Do not penalize lack of structure; penalize lack of substance.

## What would change my mind

At the bottom of every adversarial scorecard, include a "What would change my mind" section listing the evidence or argument that, if the author produced it, would move the composite score by ≥ 10 points.
