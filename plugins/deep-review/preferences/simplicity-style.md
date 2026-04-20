# Simplicity Style Preferences

Scoring weights, severity calibration, and rules for the simplicity-reviewer. Edit this file to tune the reviewer.

## Scoring weights

| Category | What it measures | Weight |
|---|---|---|
| Dead weight | No unused code, parameters, imports, branches | 30% |
| Right abstraction level | Abstractions earn their keep; no premature generalization | 30% |
| Boundary discipline | Validation and error handling only at real boundaries | 20% |
| No future-proofing | No flags, shims, or hooks for unused behavior | 20% |

Composite = Dead weight × 0.30 + Right abstraction level × 0.30 + Boundary discipline × 0.20 + No future-proofing × 0.20

A score of 90+ means the artifact is as simple as the problem allows, not that it's a one-liner. Simplicity is a guideline, not a straitjacket: do not flag genuine abstractions that model real domain complexity. When uncertain, bias toward MINOR over MAJOR: false-positive simplicity flags erode user trust in this reviewer.

## Guiding principles

- YAGNI ("You Aren't Gonna Need It") — do not add capability until a real caller needs it.
- Three similar lines beat a premature abstraction.
- Validate only at system boundaries — internal code trusts its inputs.
- Default to no comments unless the code is non-obvious.

## Severity calibration

### CRITICAL (rare for this reviewer)
- Complexity that is actively harmful — e.g., a plugin mechanism whose failure mode is silent data loss, or a layer of indirection that makes the primary invariant unverifiable.

### MAJOR
- Dead code: unused function, unused class, unused parameter, unused import, unused module.
- Over-abstraction: helper that's used once, class with one instance, factory with one product, interface with one implementation.
- Premature generalization: parameter that's always passed the same value, config option that's always `True`, flag with no off-path.
- Defensive handling for impossible states: validating input that's already typed or validated upstream, catching exceptions the library doesn't raise.
- Backward-compatibility shims for APIs or callers that don't exist yet.
- Feature flags around behavior not yet used.

### MINOR
- Comments that restate the code.
- Variable names longer than needed in narrow scope.
- Multi-line expressions that compress to a single clear line without loss.
- Using a heavy dependency where a stdlib module does the job.

## What NOT to flag

- Correctness or bugs — code-reviewer's domain.
- Writing quality — writing-reviewer's domain.
- Test coverage — code-reviewer's domain.
- Style preferences unrelated to complexity — code-reviewer's domain.
- Genuinely load-bearing complexity (a class hierarchy modeling a real domain with more than one actual type).
- Missing comments — the default convention is no comments.

## Domain-specific rules

- Be concrete: cite `<file>:<line>` for each flagged complexity.
- When flagging over-abstraction, show how the code reads without the abstraction — that's the test of whether the abstraction earns its keep.
- The size-audit section at the bottom of the scorecard should show before/after line counts if removals are applied.
