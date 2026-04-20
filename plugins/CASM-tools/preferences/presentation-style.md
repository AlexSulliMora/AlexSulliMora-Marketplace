# Presentation Style Preferences

Scoring weights, severity calibration, and style rules for the presentation-reviewer AND the presentation-builder creator. Edit this file to tune both — changes propagate to reviewer scoring and to the builder's initial drafts.

## Scoring weights

| Category | What it measures | Weight |
|---|---|---|
| Text fitting | All content fits within slide bounds, no overflow | 20% |
| Layout readability | Clear hierarchy, appropriate spacing, logical flow | 20% |
| Space utilization | Slide area well-used, no excessive empty space, appropriate font sizing | 20% |
| Cross-slide consistency | Uniform numbered structures, bullets, emphasis, notation across the deck | 15% |
| Font/color readability | Readable fonts, sufficient contrast, consistent sizing | 15% |
| Visual hierarchy | Information organized effectively, not cluttered | 10% |

Composite = Text fitting × 0.20 + Layout readability × 0.20 + Space utilization × 0.20 + Cross-slide consistency × 0.15 + Font/color readability × 0.15 + Visual hierarchy × 0.10

A score of 90+ means the presentation is polished and ready to deliver, not that it wins a design award.

## Severity calibration

### CRITICAL
- Text literally clipped at a slide boundary in the rendered PNG.
- Equation running off the slide edge.
- Content cut off so a reader cannot understand a slide.
- A slide whose content does not match its title.

### MAJOR
- Font sizes too small to read from a projector.
- Missing slide titles where the structure implies one.
- Dense slides (6+ bullets) without progressive opacity (Revealjs only).
- Slides with content occupying less than ~60% of the vertical area — flag with specific recommendation (increase font size, increase spacing, OR consolidate with an adjacent related slide).
- Inconsistent formatting between slides (see Cross-slide consistency below).
- A slide that a speaker would need speaker notes for but has none.

### MINOR
- Small spacing or alignment nits.
- Consistent-but-suboptimal font sizing.
- Color choices that could have more contrast but are still readable.

## What NOT to flag

- Content accuracy — factual-reviewer's domain.
- Writing quality — writing-reviewer's domain.
- Color scheme preferences when contrast is adequate.
- Template or theme choices when they meet readability standards.
- Dense slides that properly use progressive opacity.
- Slides that intentionally use minimal content for emphasis (e.g., a single key takeaway or quote).

## Style rules

### Slide design standards (builder and reviewer both hold these)

- Body text minimum 18pt equivalent (in Revealjs terms).
- No horizontal scrolling, no content cut off at slide edges.
- Equations get breathing room; they are not crammed between text.
- The gap between a slide title (`##`) and the first content element is at least 0.5em.
- Use `##` for slide titles throughout. No stray `#` or `###` as slide titles.

### Dense slide handling (6+ bullet points)

- Slides with 6 or more bullet points should NOT be split into multiple slides. Instead, use progressive opacity in Revealjs (`::: {.incremental .dense-bullets}`) so bullets start dimmed (30%), become full opacity when current, and semi-fade after advancing.
- For PowerPoint and Beamer formats, a standard `::: {.incremental}` reveal is acceptable for dense slides (progressive opacity CSS is not available in those formats).
- Reviewer: flag 6+-bullet slides that lack progressive opacity in Revealjs.
- Builder: always wrap 6+-bullet lists in the progressive-opacity block.

### Evidence-based fullness judgments — PNGs, not source text

Every fullness judgment must cite the specific PNG filename observed. Source text length alone is not a valid basis.

- "Over-full": content bunches against edges, clips, or reads as crowded in the PNG.
- "Under-full": content occupies clearly less than 60% of the vertical slide area.
- Do not flag slides that intentionally use minimal content for emphasis.

#### Over-full slides: remedy hierarchy

"Split this slide" is a last resort. Work down this list and stop at the first remedy that applies:

1. For slides with 6+ bullets (Revealjs), wrap in `::: {.incremental .dense-bullets}`. For pptx/beamer, `::: {.incremental}` is acceptable. Flag 6+-bullet slides that lack this in Revealjs.
2. Reduce font size with `{style="font-size: 0.9em"}`.
3. Reword bullets to be shorter, or collapse two bullets into one.
4. Move a sub-point into speaker notes (`::: {.notes}`).
5. Recommend splitting only when 1-4 are inapplicable AND the PNG shows content clipped at the slide boundary; cite the PNG and describe the overflow.

#### Under-full slides and the anti-oscillation rule

Before recommending any split, list slides that look under-full. For every under-full slide, EITHER (a) recommend font-size/spacing increases, OR (b) recommend consolidating with an adjacent related slide (naming the specific merge target). You may not simultaneously recommend splits on some slides and leave under-full slides unaddressed — that pattern is what produces oscillation.

### Cross-slide consistency

Check consistency in:

- Numbered structures (`Proposition N:`, `Lemma N:`, `Theorem N:`, `Corollary N:`, `Assumption N:`, `Definition N:`, `Remark N:`, `Example N:`, `Hypothesis N:`, `Claim N:`). Same punctuation, numbering, casing across all slides.
- Equation labeling (all or none of the substantive equations numbered).
- Bullet markers (no mixing `-`, `*`, `+` across slides for the same bullet level).
- Emphasis conventions (bold, italic, inline code, color applied the same way throughout).
- Citation style: pick one of `[Smith 2020]`, `(Smith, 2020)`, `Smith (2020)` and use it throughout.
- Notation conventions (bold vectors `\mathbf{x}`, hat/star/bar conventions consistent across slides).
- Box styling (if propositions are in boxed divs on one slide, every proposition is boxed).

When flagging a consistency issue, list every affected slide. File once under the lowest-numbered affected slide.

### Builder output conventions (presentation-builder creator)

- Default Revealjs YAML: `theme: serif`, `slide-number: true`, `transition: fade`, `width: 1050`, `height: 700`, `margin: 0.1`, `fontsize: 24pt`.
- Include the progressive-opacity CSS block in the YAML header for Revealjs.
- Maximum ~40 words per bullet point.
- Propositions, theorems, lemmas, and other substantial results in boxed divs.
- Speaker notes (`::: {.notes}`) for complex slides.
- No "TODO" or placeholder slides in output; complete the draft.
