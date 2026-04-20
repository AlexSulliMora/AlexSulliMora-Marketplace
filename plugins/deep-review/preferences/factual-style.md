# Factual Style Preferences

Scoring weights, severity calibration, and rules for the factual-reviewer. Edit this file to tune the reviewer.

## Scoring weights

| Category | What it measures | Weight |
|---|---|---|
| Accuracy | Do claims match the source? Are results correctly stated? | 40% |
| Completeness | Are all key elements covered? Is anything important missing? | 35% |
| Citation quality | Are claims attributed to the right sections/results? Is context preserved? | 25% |

Composite = Accuracy × 0.40 + Completeness × 0.35 + Citation quality × 0.25

A score of 90+ means the artifact is factually reliable with essentially no misrepresentations or significant omissions.

## Severity calibration

### CRITICAL
- Hallucinated content — information in the artifact not present in the source.
- A claim that reverses or materially misrepresents what the source says.
- An attribution that points to the wrong paper, author, or section.

### MAJOR
- Overstates or understates a finding.
- Attributes a result to the wrong mechanism.
- Omits a key qualification or caveat the source includes.
- Omits a core element of the source that the artifact's stated scope implies it should cover.

### MINOR
- Minor paraphrase that drifts from the source without misrepresenting it.
- Missing ancillary detail that does not affect the artifact's contribution.
- Citation reference that is correct but less granular than it could be.

## What NOT to flag

- Mathematical derivations or notation consistency — math-reviewer's domain.
- Grammar, concision, sentence-level quality — writing-reviewer's domain.
- Section ordering, paragraph composition, heading structure — structure-reviewer's domain.
- Code correctness in embedded code blocks — code-reviewer's domain.
- Dead weight or unnecessary complexity — simplicity-reviewer's domain.
- Minor omitted details that do not matter for understanding the source's contribution.

## Domain-specific rules

- If uncertain whether a claim is accurate, flag it as "Uncertain — verify [specific thing]" rather than marking it wrong.
- Cite the authoritative source (PDF page or section) in the Source citation column, not a derived markdown line number.
- When reviewing a document against a markdown cache of its source PDF: use the markdown for speed, drop to the PDF for any claim involving equations, tables, numerical results, figure captions, or footnotes.
