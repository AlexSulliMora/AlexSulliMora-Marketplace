---
id: writer/ai-tells
domain: writer
version: 0.2.0
applies_to: ["*.md", "*.qmd", "*.tex"]
---

# Writer validator: AI-tells

Mechanical checks for AI-writing patterns. No grading, no rewriting. Output is a structured report: location, pattern matched, suggested fix.

## Canonical implementation

`check.py` (in this directory) is the canonical implementation. Run:

```
python check.py [--format=text|json] <file> [<file> ...]
```

Exit code 0 if no violations, 1 otherwise. Stdlib only. The script is the source of truth; the spec below documents what it catches so a reader (or worker) can audit coverage without reading the script.

## Checks (human-readable spec)

### Banned single words

Flag every occurrence (case-insensitive, word-boundary):

- `prose`
- `delve`
- `comprehensive`
- `smoke test`: substitute `sanity check` for high-level plausibility checks, `trial run` for first-pass tests
- `leverage` as a verb (heuristic: not preceded by an article or quantifier such as `the`, `high`, `more`)
- `robust` outside statistical context. Skip the flag if the surrounding sentence contains `standard error`, `covariance`, `estimator`, `inference`, `regression`, `asymptotic`, `cluster`, or `heteroskedast`. Otherwise flag with a note that the user may keep it if statistical.

### Banned multi-word patterns

- `it's not X, it's Y` (regex bound to ~40-character X)
- `X, not Y` (regex with reasonable bounds; common stopwords filtered)

### `surface` as a verb

Heuristic: `surface` followed by a determiner, capitalized noun-like token, or `-ing/-ion/-ity/-ness` token; not preceded by an article (which would mark it as a noun).

### Throat-clearing openers

At sentence or paragraph starts: `Let me explain`, `To start`, `In summary`, `In conclusion`, `Let me`, `I'll`.

### Engagement bait

`let me know if`, `happy to`, `want me to`, `feel free to`.

### Empty emphasis qualifiers

`real`, `genuine`, `actual`, `truly`, `actually`. Flagged for human review only, since these sometimes disambiguate and should not be auto-removed.

### Hedge stacking

More than one hedge in a single clause from `might`, `could`, `possibly`, `perhaps`, `maybe`, `seem`, `seems`, `appear`, `appears`, `likely`, `arguably`, `may`.

### Long parenthetical interjections

Parenthesized text containing more than 12 words mid-sentence (not at line/paragraph start).

### Em-dash misuse

Flag any em-dash character, or the ASCII equivalent (two hyphens surrounded by spaces), when it appears in a sentence that has no prior comma or semicolon. No exception for headings (restructure the heading). No exception for list items (use a colon: `- item: elaboration on item`).

### Undefined acronyms

ALL-CAPS tokens of length 2-6 that appear without a parenthetical full-form expansion within a 200-character lookback window. Code blocks and inline code are stripped before scanning.

Skipped automatically:

- Tokens inside angle-bracket template placeholders. Anything matched by `<[^>]+>` is treated as a placeholder, and its contents are not scanned.
- Recognized date/time format components: `YYYY`, `MM`, `DD`, `HH`, `MIN`, `SS`, `TZ`, `ISO`, `UTC`, and the combined forms `YYYY-MM-DD`, `YYYY-MM`, `HH:MM:SS`.

Per-project ignore list at `<cwd>/coauthor/.acronym-ignore`: one token per line; lines starting with `#` are comments; blank lines ignored. Use this for project-internal jargon (filenames, stage labels, well-known abbreviations) that should not be flagged. The checker resolves the ignore file by walking up from the file under check until a `coauthor/.acronym-ignore` is found.

### Repetition

- Sliding 200-word window: any non-stopword appearing more than 5 times in the window.
- Identical sentence-opening trigrams used 3 or more times in the document.

### Closing summary paragraphs

Final paragraph beginning with `In summary`, `To summarize`, `In conclusion`, `Overall`, or `Taken together`.

## Pass criteria

`check.py` exits 0.

## Fail output

Text format:

```
<file>:<line>:<col> [<pattern_id>] <snippet>
  -> <suggested_fix>
```

JSON format with `--format=json` for machine consumption.

## Applicable contexts

Attach to every `writer` slice that produces a draft. Skip for code comments and one-line notes.
