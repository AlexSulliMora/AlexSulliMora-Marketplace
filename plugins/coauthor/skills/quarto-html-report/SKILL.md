---
name: quarto-html-report
description: Build a polished Quarto-to-HTML research report with great_tables tables that match the user's academic-paper aesthetic — full-width page, compact rows, ISO dates, sticky thead with vertical and horizontal scroll, spanned headers for paired-metric comparisons, and wrapped Python output. Use when producing a `.qmd` that compiles to HTML for a research deliverable, replication report, or any document that combines narrative prose with formatted tables built from polars + great_tables. Skip for plain markdown reports, Quarto revealjs slides, or PDF-targeted Quarto output (different layout concerns).
---

# Quarto HTML report

This skill builds Quarto reports that match the user's preferences for academic-paper-style HTML deliverables. It is a starter template plus a small body of hard-won knowledge about what breaks visually in Quarto + great_tables and how to verify the output.

## Triggers

- The user asks for a `.qmd` that compiles to HTML.
- The user asks for an HTML report combining narrative prose and formatted tables.
- The user asks for a replication report, side-by-side comparison of values, or any tabular research deliverable rendered to HTML.
- An existing `.qmd` is being polished and needs the visual conventions documented here.

## When NOT to use

- Plain Markdown notes with no Quarto rendering.
- Quarto `revealjs` slide decks (different YAML, different CSS, different layout).
- Quarto PDF output (different page-size and CSS concerns).
- Any deliverable where the user has explicitly opted into a different visual style.

## Process

1. **Read the design notes once.** The choices in the template are not arbitrary — see `design-notes.md` for the why behind every CSS rule, frontmatter setting, and helper. Read it so you can make judgment calls when the template doesn't quite fit.

2. **Copy the template** at `template.qmd` as the starting point for the new report. Keep the YAML header, the `<style>` block, and the setup chunk verbatim unless there's a project-specific reason to change them. Replace the placeholder section with the actual report content.

3. **Build the report content** following the user's general rules — Polars-first, `pr.regtable` for regressions, GreatTables for formatted tables, ISO dates, no helper functions for one-time operations.

4. **Render with `quarto render`** and verify visually. Don't infer visual quality from the `.qmd` source. Use the bundled Chromium at `~/.cache/puppeteer/chrome/linux-*/chrome-linux*/chrome` to take screenshots and `Read` them — the multimodal Read tool accepts PNG files directly, which is the only reliable way to verify sticky thead, scrollbars, and width behavior.

5. **Walk the checklist** at `checklist.md` before declaring the report done. The checklist is short and every item has caught a real bug at least once.

## File map

- `template.qmd` — starter document with YAML, embedded CSS, and the `show_table` helper. Drop content into the placeholder section.
- `design-notes.md` — design rationale. Read once; consult when the template needs adapting.
- `checklist.md` — pre-finalize checks with verification commands.

## Common failure modes (fast reference)

- **Sticky thead doesn't stick**: great_tables emits an inner `<div>` with inline `overflow-x:auto; overflow-y:auto; height:auto`. The inline overflow becomes the scroll ancestor, breaking `position: sticky` on the outer wrapper. Fix: `.gt-scroll > div { overflow: visible !important; height: auto !important }`.
- **Spanner-table headers misaligned**: the un-spanned columns are `<th rowspan="2">` cells in the same DOM row as spanner cells. A blanket `top: 26px` rule pushes them down with the sub-headers. Fix: `:not([rowspan])` exclusion.
- **Narrow tables don't fill page width**: `width: max-content` shrinks the table to its content. Fix: `width: 100%; min-width: max-content`.
- **`<pre>` shows a horizontal scrollbar**: Quarto/Bootstrap default sets `overflow: auto` on `<pre>`. Fix: `white-space: pre-wrap !important; overflow-x: visible !important` on both `pre` and `pre code`.
- **Dates render as `m_day_year`** instead of ISO: forgot `date_style="iso"` on `fmt_date`.
- **Lime border diagnostic**: if visual issues persist and you suspect CSS isn't applying, set `.gt-scroll { border: 4px solid lime !important; background: #fffaef !important }` and re-render. If lime doesn't show, the class isn't matching — there's a parsing error or the wrapper isn't applied. Remove the diagnostic before final.

## Visual verification command

```bash
CHROME=$(ls -1 ~/.cache/puppeteer/chrome/linux-*/chrome-linux*/chrome 2>/dev/null | head -1)
"$CHROME" --headless=new --disable-gpu --no-sandbox \
  --password-store=basic --use-mock-keychain \
  --user-data-dir=/tmp/chrome-headless-quarto \
  --window-size=1800,8000 --virtual-time-budget=4000 \
  --screenshot=/tmp/report_shot.png "file://$PWD/<report>.html"
```

The `--password-store=basic`, `--use-mock-keychain`, and isolated `--user-data-dir` flags are mandatory on Linux. Without them headless Chrome tries to talk to libsecret / GNOME keyring on first launch and pops a desktop password dialog (it does this even in headless mode and even when no cookies will be stored). The dialog blocks the screenshot and confuses the user with a request that has nothing to do with the task.

Then crop with PIL into ~1400-pixel-tall slices at 50% scale and `Read` each. Sticky behavior is best verified by temporarily injecting a scroll-on-load `<script>` (see `checklist.md`).
