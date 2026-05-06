---
id: reports/quarto-style
domain: reports
version: 0.1.0
applies_to: ["*.qmd", "*.html"]
---

# Reports validator: Quarto HTML style

Mechanical conformance checks for `.qmd` source files (and the rendered `.html`) targeting an HTML research deliverable. The source of truth for the visual conventions is `${CLAUDE_PLUGIN_ROOT}/skills/quarto-html-report/SKILL.md` and its bundled `template.qmd`, `design-notes.md`, and `checklist.md`. This validator enforces the deterministic subset; judgment-driven concerns go to the `reports` reviewer persona.

## Canonical implementation

`check.py` (in this directory) is the canonical implementation. Run:

```
python check.py [--format=text|json] <file> [<file> ...]
```

Exit code 0 if no violations, 1 otherwise. Stdlib only.

## Checks (human-readable spec)

### YAML frontmatter requirements

The first fenced YAML block in a `.qmd` file targeting HTML must contain all of:

- `embed-resources: true`
- `page-layout: full`
- `toc-depth: 2`
- `code-fold: true`

Each missing key is one violation.

### Date formatting

Every `fmt_date(...)` call must include the argument `date_style="iso"`. A `fmt_date` call without that argument is one violation per occurrence.

### great_tables wrapping

Every great_tables table emission (a function call ending in `.as_raw_html()` or a `show_table(...)` helper invocation) must occur inside a `<div class="gt-scroll">` wrapper. Heuristic: look for the surrounding HTML container in the same code chunk or in inline HTML adjacent to the call. A table emission with no `gt-scroll` ancestor is one violation.

### Missing-value convention

Every `sub_missing(` call must use `missing_text="—"` (em-dash, the agreed convention from the Quarto skill). Other missing-text values are one violation per occurrence.

### CSS rules

The embedded `<style>` block (or referenced CSS file) must contain both of:

- The literal `width: 100%` paired with `min-width: max-content` on a table-width rule.
- A sticky-thead override of the form `.gt-scroll > div { overflow: visible !important` (the inner div produced by great_tables breaks `position: sticky` without it).

Each missing rule is one violation.

### Python output wrapping

Every `<pre>` block in the rendered `.html` (or any inline `<pre>` in the `.qmd`) that contains Python output should sit inside a `wrap-pre` container, or the CSS must apply `white-space: pre-wrap` and `overflow-x: visible` to `pre` and `pre code`. A bare `<pre>` outside that wrapping with no global override is one violation.

## Pass criteria

`check.py` exits 0.

## Fail output

Text format:

```
<file>:<line>:<col> [<pattern_id>] <snippet>
  -> <suggested_fix>
```

JSON with `--format=json` for machine consumption.

## Applicable contexts

Attach to every `writer` or `coder` slice whose deliverable is a `.qmd` rendering to HTML. Skip for revealjs slides, PDF-targeted Quarto, and plain markdown. Skip when the slice predates a `<style>` block (e.g., a stub being drafted); the worker re-runs the validator once the file is shaped.
