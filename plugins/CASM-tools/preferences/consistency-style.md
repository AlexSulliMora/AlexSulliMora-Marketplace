# Consistency Style Preferences

Scoring weights, severity calibration, and rules for the consistency-reviewer. Edit this file to tune the reviewer.

## Scoring weights

| Category | What it measures | Weight |
|---|---|---|
| Core idea coverage | Both documents cover the same substantive points | 45% |
| Detail appropriateness | The concise document is concise; the detailed document is comprehensive | 30% |
| Structure alignment | Logical flow is compatible; reader/viewer gets the same narrative | 25% |

Composite = Core idea coverage × 0.45 + Detail appropriateness × 0.30 + Structure alignment × 0.25

A score of 90+ means the two documents tell the same story at different levels of detail, with no substantive gaps or contradictions.

## Severity calibration

### CRITICAL
- A core idea in the concise document that is absent from the detailed document.
- Directly contradictory claims between the two documents about the same topic.
- A ranking, ordering, or chosen option that differs between documents when the artifacts are supposed to present the same decision.

### MAJOR
- A major section of the detailed document with no corresponding coverage in the concise document.
- Important caveat or limitation present in one document but missing from the other.
- Different emphasis that could mislead a reader of one document vs. the other.

### MINOR
- Different ordering of points (as long as both cover them).
- Wording differences that convey the same idea in different voices.
- Section naming inconsistencies that do not cause confusion.

## What NOT to flag

- The concise document omitting technical details that the detailed document includes (this is expected).
- Different wording for the same idea.
- The detailed document including additional context, caveats, or nuance not in the concise document.
- Upstream source accuracy — factual-reviewer's domain, not ours.

## Domain-specific rules

- Focus on substance, not style. Different words for the same idea are fine.
- Be specific about which section or slide in each document is inconsistent.
- The scorecard's "Required Changes" section is renamed to "Discrepancies Found" for this reviewer; format and sort order are unchanged.
- Sort rows first by severity, then by where the topic first appears in the concise document. For discrepancies that originate in the detailed document but have no concise counterpart, place them after the concise-anchored rows within each severity, ordered by detailed-document section.
