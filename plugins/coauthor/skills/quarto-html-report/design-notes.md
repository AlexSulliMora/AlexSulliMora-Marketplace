# Design notes for Quarto HTML reports

The choices in `template.qmd` are not arbitrary. Each one is paired with a *why* below so judgment calls in edge cases can be made on principle rather than recipe.

## Page-level

**`page-layout: full`.** Academic tables routinely run 10+ columns. The default `article` layout pinches them. Full-width gives tables and figures room to breathe. Cost: the right-side TOC sidebar disappears in favor of a TOC at the top, which is the right tradeoff for table-heavy reports.

**`embed-resources: true`.** Produces a single self-contained HTML file. Trivially shareable; no broken stylesheet links or missing fonts when the file moves between machines. The tradeoff is a larger file (~1.5 MB instead of ~50 KB), which is fine for archival research deliverables.

**`code-fold: true`.** Code is auditable but doesn't dominate the page. Readers see narrative and tables first; reviewers expand code only when verifying something. The user's CLAUDE.md explicitly calls this out as the gold standard for archival deliverables.

**`toc: true`, `toc-depth: 2`.** Two levels covers most reports without making the TOC itself a wall of text.

## Tables (great_tables)

**Compact rows.** `table_font_size="11px"`, `data_row_padding="2px"`, `column_labels_padding="3px"` collected into a `COMPACT_OPTS` dict applied to every table. Default great_tables spacing is generous and academic tables look right with tight rows. Match the visual density of journal tables.

**Single-line rows.** `white-space: nowrap !important` on every `<td>` and `<th>`. Wrapping rows breaks visual scanning. If the table is too wide for the page, that's what horizontal scroll is for. Never let a long industry name wrap onto two lines.

**ISO dates.** `date_style="iso"` in `fmt_date`. Unambiguous and locale-free. The reader doesn't need to wonder if "10/03/1999" is March or October.

**Spanned headers when comparing two versions of the same metric.** `tab_spanner(label="...", columns=[...])` groups paired columns. Saves horizontal space and signals "these are the same thing, two ways to compute it" without repeating the metric name twice. The inner column labels become "GSY" / "repl" or "pub" / "ours" rather than "12m raw (GSY)" / "12m raw (repl)".

**Shorten verbose category names.** Even with full-width pages, names like "Non-Metallic and Industrial Metal Mining" eat horizontal space. Maintain a `DISPLAY_NAME_OVERRIDES` dict that reproduces published shorthand (e.g., journal abbreviations). Don't shorten names that are already concise.

**`sub_missing(missing_text="—")`.** Em-dash is more readable than empty cells or `nan`/`None`. Used universally in journal tables.

**Row identifier goes in the first column.** The sticky-left-column extension (when present, see Scrollable containers) targets `:first-child`. The first column must therefore be the column that anchors a row — variable name, ticker, observation ID — so it stays visible when the reader scrolls right through wide content. If a category, section, or grouping column is the natural left-most candidate, lift it to a row group instead (see next item) so the identifier slot stays free.

**Repeated category cells become row groups.** When a category column repeats the same value across many consecutive rows (e.g., 8 rows of `Banking`, then 6 rows of `Insurance`), do not render the column. Use `gt.GT(df, groupname_col="category")` or `tab_row_group_*` so the category becomes a row-group banner spanning its rows, and the column itself disappears. The banner doubles as visual panels and removes the visual noise of the repetition. Acceptable fallback: `pl.when(pl.col(c) == pl.col(c).shift()).then(pl.lit("")).otherwise(pl.col(c))` to fill only the first row of each group, used only when row groups would over-fragment the table (singleton groups for many categories). Default to row groups.

## Scrollable containers

**Wrap each great_tables in `<div class="gt-scroll">`.** Long tables need a vertical scrollbar with a sticky `<thead>`; wide tables need horizontal scroll without losing the column headers. One container handles both. The `show_table` helper does this in one line: `HTML(f'<div class="gt-scroll" style="max-height:{max_height}">{gt_obj.as_raw_html()}</div>')`.

**`max-height: 560px`.** A reasonable default — about 24 visible rows, fits on a typical viewport without dominating. Adjust per-table when content warrants it (e.g., a 40-row comparison might use `max_height="640px"`). Use `show_table(..., max_height="...")` to override per-table.

**Override great_tables' inner `<div>` with `!important`.** great_tables emits an inner div with inline `overflow-x:auto; overflow-y:auto; height:auto`. That inline overflow becomes the scroll ancestor and breaks sticky positioning on the outer container. The `.gt-scroll > div { overflow: visible !important; height: auto !important; padding: 0 !important }` rule neutralizes it so the outer `.gt-scroll` is the sole scroll context. Without `!important` the inline styles win.

**Sticky thead targets `<th>` cells, not `<tr>`.** `position: sticky` on `<tr>` is unreliable across browsers; on `<th>` it works everywhere. Two rules:

```css
.gt-scroll thead .gt_column_spanner_outer { position: sticky !important; top: 0; ... }
.gt-scroll thead .gt_col_heading        { position: sticky !important; top: 0; ... }
```

**Title and subtitle do NOT stick.** They scroll out of view as the user scrolls down, leaving only the spanner and column-label rows pinned. This is intentional — the markdown section heading above each table already labels it, and keeping all four thead rows sticky would eat too much vertical space.

**The rowspan=2 trap (spanner tables).** When using `tab_spanner`, great_tables emits the un-spanned columns (e.g., "Industry", "Date", "Match info") as `<th rowspan="2">` cells in the *same DOM row* as the spanner cells. A naive rule like `.gt-scroll:has(.gt_column_spanner_outer) thead .gt_col_heading { top: 26px }` pushes those rowspan=2 cells down by 26px along with the sub-header row, misaligning them. The fix is `:not([rowspan])` — exclude rowspan cells so they fall through to the default `top: 0`:

```css
.gt-scroll:has(.gt_column_spanner_outer) thead .gt_col_heading:not([rowspan]) {
  top: 26px;
}
```

**Width sizing: `width: 100%; min-width: max-content`.** Narrow tables fill the container (no awkward gap on the right). Wide tables don't squish columns below their natural no-wrap width — they trigger horizontal scroll on the outer container instead. Using `width: max-content` alone makes narrow tables appear as a thin band; using `width: 100%` alone lets the browser squish columns when content is wider than the container.

**Sticky row-group banner (only when `groupname_col` is in use).** When a table uses `gt.GT(df, groupname_col=...)`, great_tables emits the section banner as `<td class="gt_group_heading" colspan="N">` inside its own `<tr class="gt_group_heading_row">`. Without sticky-left the banner text scrolls off the visible area as the reader scrolls right through wide columns, so the section label disappears. Pin the banner cell at `left: 0` to keep the label visible across the full horizontal scroll:

```css
.gt-scroll .gt_table tbody .gt_group_heading_row .gt_group_heading {
  position: sticky !important;
  left: 0;
  background: white;
  z-index: 8;
}
```

`z-index: 8` is deliberately below the sticky-thead layers (11 for `.gt_col_heading`, 12 for `.gt_column_spanner_outer`) so the column-label row covers the banner during vertical scroll, and below the sticky-left first column (9 for body cells, 15 for the corresponding `<th>`) so the row identifier overpaints the banner where they would otherwise visually collide. Apply only when the table uses row groups; on tables without `groupname_col` the rule has no targets and is harmless but unnecessary.

## Printed Python output

**Wrap `<pre>` blocks** so narrative `print()` lines don't show a horizontal scrollbar. The CSS targets both `<pre>` and `<pre><code>` because Pandoc nests stdout text inside `<code>`:

```css
pre, pre code,
.cell-output pre, .cell-output-stdout pre, .cell-output-stdout pre code,
.sourceCode pre {
  white-space: pre-wrap !important;
  word-break: break-word !important;
  overflow-x: visible !important;
}
```

The `!important` is required to beat Quarto/Bootstrap defaults that set `pre { overflow: auto }`. Without it the rules apply but the parent's overflow:auto creates a scrollbar anyway.

**Fixed-width table-aligned print() output.** If a print uses column padding (`f"{x:<22}"`) and the lines fit the page, leave it as a print — wrapping table-aligned text would break the alignment. If the lines exceed viewport width even after wrapping rules, convert to a `great_tables` table.

## Code organization

**Setup chunk in `#| include: false`.** Imports, helper functions, data loading, display-name overrides. The reader doesn't need to see any of this on every render; the `code-fold: true` setting already lets reviewers expand it on demand.

**One helper: `show_table(gt_obj, max_height="560px")`.** Wraps a great_tables in `<div class="gt-scroll">` and returns `IPython.display.HTML` so Quarto renders it. Don't add per-table customization through the helper — the great_tables fluent API already does that. The helper's only job is the scroll wrapper.

**`COMPACT_OPTS` as a module-level dict.** Applied via `.tab_options(**COMPACT_OPTS)` on every table. Centralizes the compact-row settings so they don't drift across the report.

**Display-name overrides as a module-level dict.** They're a project-level convention (matching the source paper's display names), not a per-table choice. Use a single `pl.col(...).replace_strict(DISPLAY_NAME_OVERRIDES, default=pl.col("ff49_name"), return_dtype=pl.String).alias("display_name")` once and use the resulting column everywhere.

## Writing principles

**Blinders on the horse.** Use the most familiar and least-loaded framing that supports the specific point you're making, and no stronger. A curious reader who hits an unexpected technical word will follow it down, look it up, think through the implications, and stop reading the document. The cost of the digression is real: the reader leaves the page, sometimes for an hour, sometimes for good.

The example that prompted this rule: a Bayesian VAR plot used the phrase "the identity manifold" for what was, strictly, a 2-D plane in 3-D coefficient space defined by a single linear constraint. "Manifold" was technically correct but invited the reader to think about whether the joint posterior actually *is* a manifold, whether $\mathbb{R}$ vs $\mathbb{Q}$ matters for the parameter space, whether the continuous probability model is a good approximation of an inherently rational-valued data-generating process, and so on. None of that aided the argument the chart was making. "Line" or "plane" would have done the work without any digression-bait.

The rule:

- Prefer the simplest geometric or analytic description that captures the point. A linear constraint defines a line, plane, or hyperplane — no need to invoke a smooth-surface concept unless the constraint is nonlinear.
- Reach for terminology only when its extra structure is actually load-bearing. If the reader needs the concept of a tangent space, smoothness, or curvature for the next paragraph, name the manifold; if not, don't.
- Be especially watchful around words that imply continuous-real-number structure ("manifold", "diffeomorphism", "measure-zero", "Lebesgue") in econometrics writing, where the underlying data are typically rational and the continuous model is a working approximation. Readers who notice the mismatch will spend energy on it.
- Concrete beats abstract when the concrete description fits. "45-degree line", "the line $y = x$", or "$y = x + c$" is cleaner than "the identity submanifold of $\mathbb{R}^2$" even if they pick out the same set.

This is the writer's version of "don't make the reader load extra context to follow your point". The trap is that the *writer* already has the extra context, so it costs them nothing to use the loaded word; the reader pays the full cost of decoding it.

## What this skill does NOT cover

- **Polars patterns.** Use the user's lazy-first conventions from `~/.claude/rules/python-econometrics.md`.
- **Plotting.** Altair conventions live in `~/.claude/rules/visual-design.md`.
- **Regression tables.** Use `pr.regtable` per `~/.claude/rules/output-format.md`. The compact-row aesthetic in this skill is intended for descriptive tables, not regression output.
- **Slides or PDF output.** This skill is HTML-only.
