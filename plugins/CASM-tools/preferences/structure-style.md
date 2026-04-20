# Structure Style Preferences

Scoring weights, severity calibration, and rules for the structure-reviewer. Edit this file to tune the reviewer.

## Scoring weights

| Category | What it measures | Weight |
|---|---|---|
| Logical sequence | Sections and subsections unfold in the natural order for the document's purpose | 30% |
| Paragraph composition | Paragraphs are unified, appropriately sized, and sequenced within their sections | 25% |
| Section & heading structure | Sections neither too long nor too short; headings accurately signal their content | 25% |
| Transitions | Topic shifts between sections and paragraphs carry the reader forward | 20% |

Composite = Logical sequence × 0.30 + Paragraph composition × 0.25 + Section & heading structure × 0.25 + Transitions × 0.20

A score of 90+ means the document's structure carries the reader forward on first reading, not that every paragraph is perfectly placed.

Hold the document to its own purpose. A tutorial reads differently from a reference doc; a research paper reads differently from a project README. Judge progression against the genre the document is trying to be.

## Severity calibration

### CRITICAL
- Required background or definitions placed after the content that depends on them, forcing the reader to jump forward and back.
- Structural incoherence: a section whose content does not match its heading, or whose content belongs in a different section entirely.
- Circular dependencies in presentation order (A introduces B, B introduces C, C introduces A).

### MAJOR
- Sections in an unnatural order given the document's purpose (e.g., results before methodology in a report).
- Paragraphs that should be combined (two short paragraphs covering the same idea) or split (one paragraph covering two distinct ideas).
- Missing transitions at major topic shifts.
- Headings that mislead: title says one thing, content below is about another.
- Sections so long they need subdivision, or subsections so short they should be absorbed into their parent.

### MINOR
- Small reorderings within a section.
- Heading-level imbalance (one H3 inside a section where H2 structure would be more honest).
- Paragraph topic sentences buried in the middle rather than leading.

## What NOT to flag

- Individual sentence quality: grammar, concision, word choice, transition wording — writing-reviewer's domain.
- Dead weight or YAGNI violations — simplicity-reviewer's domain.
- Factual accuracy — factual-reviewer's domain.
- Mathematical content — math-reviewer's domain.
- Code correctness — code-reviewer's domain.
- Visual layout of compiled slides — presentation-reviewer's domain.
- Cross-document consistency — consistency-reviewer's domain.

## Domain-specific rules

- When recommending combining or splitting paragraphs, name the specific boundaries: which sentences stay together, which split off.
- When recommending reordering sections, state what the new order should be.
- Bias toward small, concrete rearrangements over sweeping reorganizations. A document with good bones and abrupt transitions is fixable; proposing a full restructure usually means the diagnosis is wrong.
