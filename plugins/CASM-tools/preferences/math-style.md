# Math Style Preferences

Scoring weights, severity calibration, and rules for the math-reviewer. Edit this file to tune the reviewer.

## Scoring weights

| Category | What it measures | Weight |
|---|---|---|
| Derivation correctness | Do stated results follow from assumptions? Are derivation steps valid? | 45% |
| Logical consistency | Are assumptions, results, and intuition mutually consistent? | 35% |
| Notation consistency | Is notation used consistently? Does it match cited sources? | 20% |

Composite = Derivation correctness × 0.45 + Logical consistency × 0.35 + Notation consistency × 0.20

A score of 90+ means the mathematics is sound and trustworthy, not that every equation is typeset identically to any source.

## Severity calibration

### CRITICAL
- A derivation step that does not follow — algebraic mistake, sign error, missing term.
- A result that cannot follow from the stated assumptions under any reasonable reading.
- A claimed estimator property (consistency, unbiasedness, asymptotic normality, identification) that is incompatible with the assumed data generating process.
- An internal inconsistency that produces a misleading numerical result.

### MAJOR
- Skipped derivation steps where an error could hide; request the missing steps.
- Notation used inconsistently within the artifact (same symbol for two objects, two symbols for one object, subscripts that drift).
- Missing corrections for the assumed DGP (robust or clustered standard errors, heteroskedasticity adjustments, bias corrections) that are needed but not applied.
- Internal inconsistencies across sections that do not produce a misleading number but degrade quality.
- Mismatches between the artifact and a cited upstream source (equation number, sign, functional form).

### MINOR
- Notation that works but could be cleaner.
- Derivation that is correct but unnecessarily circuitous.
- Formatting nits in equation display.

## What NOT to flag

- Notation choices that differ from the cited source but are internally consistent within the artifact.
- Grammar, phrasing, sentence concision — writing-reviewer's domain.
- Section ordering, heading structure, paragraph composition — structure-reviewer's domain.
- Factual claims about institutions, data, or history that are not mathematical — factual-reviewer's domain.
- Code correctness in embedded code blocks — code-reviewer's domain.
- A mathematical issue in the cited upstream source itself: note it, but do not penalize the artifact for faithfully reproducing it.

## Domain-specific rules

- For extension proposals, assess plausibility of conjectures but acknowledge that results of an unsolved model cannot be fully verified.
- When citing a math issue, reference the specific PDF page/equation number in the source (if any), not an extracted markdown line number — automated extraction garbles equations.
