# Writing Style Preferences

Scoring weights, severity calibration, and style rules for the writing-reviewer. Edit this file to tune the reviewer's behavior — changes apply on the next /deep-review:review-document invocation.

## Scoring weights

| Category | What it measures | Weight |
|---|---|---|
| Grammar & mechanics | Correct spelling, punctuation, sentence structure | 25% |
| Concision | No unnecessary words, phrases, or sentences | 30% |
| Sentence necessity | Every sentence adds value; no filler | 25% |
| Clarity | Ideas communicated clearly on first reading | 20% |

Composite = Grammar × 0.25 + Concision × 0.30 + Sentence necessity × 0.25 + Clarity × 0.20

A score of 90+ means the writing is clear, concise, and professional at the level a graduate economist reads, not that it reads like a novel. Academic writing can be dense; do not penalize complexity that is necessary to convey a complex idea.

## Severity calibration

### CRITICAL
- Grammatical errors that change meaning or make a sentence unparsable.
- Hallucinated or mis-attributed quoted text when the artifact quotes a source.
- Writing so unclear that a graduate economist cannot follow the argument at all.

### MAJOR
- Em-dash overuse: reserve em dashes for true interjections in sentences that already carry commas or semicolons. Flag any em dash that does not meet this bar.
- Throat-clearing sentences: "This section discusses…". Just discuss it.
- Overly punchy writing: rows of short, punch-line-style sentences are a hallmark of poor AI writing. Respect the reader's ability to follow complex sentence structure.
- Passive voice where active is clearer.
- Hedge stacking: "it might potentially be somewhat possible" — commit or qualify once.
- Jargon without purpose: a technical term used when a plain word works as well.
- Buried main point: a paragraph whose topic sentence arrives late.
- Unclear paragraph-level transitions: topic shifts inside a section that carry the reader nowhere.
- Information repeated across sections: the same point restated in prose without earning the repetition.

### MINOR
- Redundant phrases: "in order to" → "to"; "the fact that" → "that"; "it is important to note that" → omit.
- Excessive "that": the word is usually unnecessary and can be dropped by rewording. Prefer the reworded version.
- Single-word tics (e.g., "surface" as a verb) and small stylistic inconsistencies.

## What NOT to flag

- Technical terminology that is standard in economics (do not simplify "heteroskedasticity" to "unequal variance").
- Passive voice when it is the natural construction (e.g., "The model is estimated by…" is fine in methods sections).
- Notation and mathematical expressions: those are the math reviewer's domain.
- Factual content: that is the factual reviewer's domain.
- Code or code comments: those are the code reviewer's domain.

## Domain-specific rules

- Be specific: quote the problematic text and explain why it fails.
- Do not impose personal style preferences beyond what is encoded in this file.
- Each Required Change must quote the problematic text and give an exact rewrite, not a vague "rewrite this for clarity."
