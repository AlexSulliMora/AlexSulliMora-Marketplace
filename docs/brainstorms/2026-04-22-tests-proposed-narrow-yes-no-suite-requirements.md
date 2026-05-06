---
created: 2026-04-22
status: ready-for-planning
scope: standard-to-deep
parent_brainstorm: 2026-04-22-ralph-style-reviewer-architecture-requirements.md
---

# Tests-Proposed: Narrow Yes/No Test Suite

## Problem Frame

The current `tests/` suite is nine generic reviewer-type tests (writing, structure, math, simplicity, adversarial, factual, consistency, code, presentation), each scoring an artifact 0–100 and gating on `score >= 80 AND zero CRITICAL`. The prompts are short and reviewer-shaped, with `findings` arrays that share a uniform schema across reviewers.

Inspiration from `chenandrewy/ralph-wiggum-asset-pricing` (`ralph/run-final` branch) shows a different model. ~30 narrow tests, each asking a single sharp yes/no question with a step-by-step procedure, typed claim categories (`[ARITHMETIC]`, `[VERBAL]`, `[REFERENCE]`, `[FIGURE/TABLE]`), section-by-section sub-verdicts, and per-test pass rules. The Ralph tests target one specific paper at known file paths, but the underlying patterns (specificity, granularity, single-question framing) translate to CASM-tools' generic loop.

The user wants a clean rewrite of the suite under `plugins/CASM-tools/tests/` that adopts these Ralph patterns. The legacy `tests/` and `preferences/` folders have been deleted on the `ralph-approach` branch; the new design is the replacement, not a parallel.

## Goal

Produce a complete catalog and per-test specification for the rewritten test suite under `plugins/CASM-tools/tests/`. **This is a proof-of-concept iteration**: the goal is to validate that narrow yes/no Ralph-style tests outperform the scored generic reviewers that previously lived at this path. A later iteration will redesign around per-section test routing or staged document creation (outline → math → writing, each stage gated by its own narrow tests). The PoC should not foreclose either future path.

The suite should:

- Replace generic reviewer scoring with narrow yes/no tests, each asking one sharp question.
- Adopt Ralph-style prescriptive procedures and section/region-labeled findings.
- Cover paper-pipeline outputs (summary, extension, slides + writeup), generic writing/code review, and an experimental academic paper-source profile that matches Ralph's own scope.
- Replace the legacy reviewer suite that previously lived at `plugins/CASM-tools/tests/`. That folder and the dependent `plugins/CASM-tools/preferences/` folder have already been deleted on the `ralph-approach` branch; the new design rebuilds the directory from scratch under the same path. The branch's pipeline is non-functional until the new suite ships.

## Workflow Assumption

Every artifact in scope is authored as Markdown or Quarto (`.md`, `.qmd`) and, where compilation is needed, rendered to PDF or HTML via Quarto. Tests must not assume LaTeX-source idioms (`\section{}`, `\printbibliography`, raw `\begin{align}`-only math, `paper.tex`). Math may use Quarto's `$...$` and `$$...$$` (which Quarto passes through to LaTeX or MathJax depending on output), but tests reading the source treat it as Markdown / Quarto, not LaTeX. The `--references <bib>` input is BibTeX as referenced from a Quarto YAML header, not a standalone LaTeX bibliography.

This narrows the input set relative to the live `tests/` suite, which still accepts `.tex` artifacts via the auto-classification table in `skills/review-document/SKILL.md`. Dropping `.tex` is a deliberate scope narrowing for the new suite; the user does not maintain LaTeX-source workflows and the old auto-classification table will be retired alongside the rest of the legacy harness.

## Scope Boundaries

In scope:
- The full catalog of narrow tests (names, sharp questions, pass rules, payload outline).
- Profile definitions (artifact type → test list, plus required inputs).
- The implied changes to the `/CASM-tools:review-document` grammar and harness behavior, described well enough that planning can size the work.
- Output schema design (envelope + per-test typed payload + section/region labels).

Out of scope:
- Implementing tests, the harness changes, or the renderer changes (planning will handle).
- Tuning per-test wording for production use (each test prompt will be drafted in implementation).
- Backward compatibility shims between old and new schemas. The new schema replaces the old one; tests under `tests/` are migrated to the new envelope or deleted.
- Coexistence of the new suite with the legacy reviewers or `preferences/`. Both are gone on `ralph-approach`. The new suite is the only test surface this branch will have once it ships.

## Scope Posture

The new suite replaces the live `tests/` suite rather than coexisting with it. Three commitments follow:

1. **Shared infra is rewritten in place.** `scripts/run-tests.py`, `scripts/render-results.py`, `tests/_helpers.py`, and `skills/review-document/SKILL.md` are modified to serve the new schema, dispatcher, and profile grammar. The Implied Loop Changes section below lists the surface area; this is the migration plan, not contradiction with an additivity claim.
2. **The `preferences/` folder is gone.** The legacy tests loaded per-style files from `plugins/CASM-tools/preferences/` because each `claude -p` subprocess was isolated from the user's `~/.claude/rules/`. New tests are narrow enough to be self-contained: each prompt inlines the one or two style rules its single sharp question depends on. No `preferences/` directory exists or will exist on `ralph-approach`.
3. **Retention requires positive justification.** Tests, helpers, or skill paths from the old suite stay only when their continued use is independently justified — not by default. The migration deletes; it does not preserve.

## Resolved Decisions

### D1. Test shape: narrow yes/no, no scores

Each test asks one sharp question, returns `{verdict: PASS|FAIL, reason: str, payload: {...}}`. No `score` field. No `--advisory` flag.

**Rationale:** The previous architecture's adversarial reviewer was a competent local-minimum detector, but the narrow fixer couldn't escape the minimum (gradient-descent analogy: correct gradient, step too small). With the main session now acting as Ralph-style writer, every test can hard-gate because the writer is empowered to restructure in response. Scores added implicit slack that the writer has stopped needing.

### D2. Selection by profile

Profiles map artifact types to test lists. Invocation: `/CASM-tools:review-document <profile> <doc-path> [profile-specific clauses]`. Each profile declares the inputs it needs.

**Profiles:**

| Profile | Artifact type | Required inputs | Optional inputs |
|---|---|---|---|
| `writing` | Generic text article (`.md`, `.qmd`) | `<doc-path>` | — |
| `paper-summary` | Output of paper-summarize | `<doc-path>`, `--source-paper <pdf>` | — |
| `extension-proposal` | Output of paper-extend | `<doc-path>`, `--source-paper <pdf>` | — |
| `slides` | Compiled slide deck (`.html` from revealjs, or `.pdf`) | `<doc-path>`, `--screenshots-dir <dir>` | `--source-paper <pdf>` |
| `presentation-writeup` | `.qmd` writeup paired with slides | `<doc-path>` | `--paired-slides <path>` |
| `code` | Source files | `<doc-path>` | — |
| `paper-source` (experimental) | Academic paper draft (`.qmd` rendering to PDF via Quarto) | `<doc-path>` | `--spec <md>`, `--references <bib>` |

**Rationale:** Profiles per artifact type handle multi-input cleanly (resolved once per invocation, passed to all member tests), and "groups by category" was rejected because it forces a 1-to-1 between human concepts and test files when many tests are useful across multiple categories.

**Hybrid artifacts (deferred to a later iteration).** A single `.qmd` can simultaneously be a writeup with embedded math, a paper-source draft that doubles as the presentation writeup, or a writing artifact with one heavy theory section. The current PoC design does not handle this — the user picks one profile per invocation; if the artifact needs more, run again. The systematic resolution belongs to a later iteration that will either auto-route tests to document sections or stage document creation (outline → math derivations → writing, each stage passing its own narrow tests).

### D3. Output: envelope + typed payload + section labels

Envelope stays `{verdict, reason, payload}` (drop `score`, drop `gating` since every test gates by D1, keep `verdict`/`reason`). Each test owns its payload schema. Findings carry section/region labels (line numbers, slide numbers, function names — whatever's natural for the artifact type).

Example payload for `narrative-section-fulfillment`:

```json
{
  "sections": [
    {"name": "Introduction", "lines": "1-45", "contract": "...", "deliverables": "...", "status": "FULFILLED"},
    {"name": "Method", "lines": "46-120", "contract": "...", "deliverables": "...", "status": "UNFULFILLED", "explanation": "..."}
  ],
  "cross_references": [
    {"location": "line 87", "target": "Section 4.2", "resolves": true}
  ]
}
```

The renderer learns each schema's display rule (table per test type) so the human-readable summary stays specific.

### D4. Profile-level inputs

Multi-input handled at profile resolution time, not per-test. The skill grammar surfaces what each profile needs. Tests inside a profile receive all profile inputs uniformly.

**Rationale:** Per-test CLI flags would proliferate as tests grow; profile-level inputs keep the user-facing grammar small and let related tests share inputs (e.g., every `paper-source` test gets the spec and bib paths).

### D5. Coverage scope: expand with Ralph categories

The catalog covers Ralph-inspired categories (theory, narrative, factcheck, element) alongside writing, structure, math, code, slides, adversarial, consistency. The current nine reviewer categories are not treated as a constraint.

## Test Catalog

44 narrow tests across 11 categories. Each test owns its sharp question and pass rule.

### Writing (text quality, applies to any text artifact)

| ID | Sharp question | Pass rule |
|---|---|---|
| `writing-hedge-stacking` | Are there any sentences that pile multiple hedges (e.g., "might possibly somewhat tend to")? | PASS iff zero such sentences. |
| `writing-engagement-bait` | Does the artifact close with bait phrases ("Let me know if", "Want me to", "Happy to")? | PASS iff zero bait closings in the conclusion or final paragraphs. |
| `writing-em-dash-discipline` | Are em dashes used only when the surrounding sentence already carries a comma or semicolon? | PASS iff every em dash sits in a sentence with at least one other separator. |
| `writing-not-x-pattern` | Does the artifact use "X, not Y" / "it's not Y, it's X" patterns? | PASS iff fewer than two such constructions, none in the abstract or intro. |
| `writing-empty-emphasis` | Does the artifact lean on empty intensifiers ("real", "genuine", "actual", "truly", "literally") where they don't disambiguate? | PASS iff every flagged use does disambiguating work. |
| `writing-throat-clearing` | Does the artifact open sections with scaffolding ("This section discusses X", "Let me explain", "To start")? | PASS iff zero throat-clearing openers. |
| `writing-banned-words` | Does the artifact use "prose" or "surface" (as a verb)? | PASS iff zero hits. (The "surface" check tolerates noun usage.) |
| `writing-sentence-necessity` | Does every sentence earn its place, or are there sentences that could be cut without losing meaning? | PASS iff fewer than 3 cut-able sentences flagged across the artifact. |

### Structure

| ID | Sharp question | Pass rule |
|---|---|---|
| `structure-section-flow` | Does each section follow naturally from the prior, or does the order require justification? | PASS iff every adjacent-section transition reads as inevitable. |
| `structure-paragraph-composition` | Are paragraphs the right size for their content, or are they fragmented or run-on? | PASS iff zero paragraphs flagged as fragmented (single sentence on a multi-sentence idea) or run-on (single paragraph covering multiple ideas). |
| `structure-heading-signal` | Do headings actually signal what's below, or are they generic? | PASS iff every heading mentions its specific subject (not "Discussion", "Results"). |
| `structure-progression` | Does the artifact carry the reader forward, or does it loop back / repeat itself? | PASS iff zero passages identified as repeating an earlier point without adding to it. |

### Math

| ID | Sharp question | Pass rule |
|---|---|---|
| `math-derivation-gaps` | Are intermediate steps shown the first time a technique appears? | PASS iff every novel derivation has its key intermediate steps; standard manipulations may be elided. |
| `math-notation-consistency` | Is notation consistent throughout (same symbol means same thing)? | PASS iff zero notation collisions. |
| `math-assumption-explicitness` | Are all load-bearing assumptions stated at or before the result that depends on them? | PASS iff every assumption used in a result is explicit. |
| `math-estimator-properties` | Do claimed estimator properties (consistency, normality, identification) hold under the assumed DGP? | PASS iff every claimed property is consistent with the stated assumptions. |

### Theory (Ralph-inspired)

| ID | Sharp question | Pass rule |
|---|---|---|
| `theory-clarity` | Are key model expressions in display math, and are new in-text assumptions at or near paragraph starts? | PASS iff every critical expression is in display math AND new assumptions are introduced in setup paragraphs (not buried mid-paragraph). |
| `theory-unmodeled-channels` | Does the artifact treat unmodeled channels with appropriate caution? | PASS iff every channel discussed but not modeled is flagged with appropriate hedging. |
| `theory-intuition` | Are propositions and key formulas explained in terms of the mathematical objects they involve? | PASS iff every proposition / key formula has an intuitive explanation grounded in the math, not just verbal restatement. |

### Narrative (Ralph-inspired)

| ID | Sharp question | Pass rule |
|---|---|---|
| `narrative-section-fulfillment` | Does each section deliver what its title and opening framing promise? | PASS iff every section is FULFILLED. |
| `narrative-cross-references` | Do internal cross-references resolve to content that actually exists? | PASS iff every cross-reference resolves. |
| `narrative-claim-strength` | Are verbal claims supported by the evidence the artifact provides (no claim stronger than its support)? | PASS iff every flagged claim is appropriately calibrated. |
| `narrative-abstract-body-alignment` | Are the central claims in the abstract / intro actually delivered by the body? | PASS iff every abstract or intro claim is delivered. |

### Factcheck (Ralph-inspired)

| ID | Sharp question | Pass rule |
|---|---|---|
| `factcheck-arithmetic` | Are stated numbers reproducible from the formulas and parameters literally present in the artifact? | PASS iff zero arithmetic errors among checkable numbers. Returns `INCONCLUSIVE` for any number whose inputs (parameter values, intermediate quantities) are not literally in the artifact, e.g., values referenced by citation; INCONCLUSIVE counts as PASS for gating but is reported for visibility. Numbers backed by external sources fall under `factcheck-references` or `factcheck-against-source`, not here. |
| `factcheck-references` | Do citations exist, and do they say what the artifact claims they say? | PASS iff every citation resolves to a real source AND no citation is misrepresented. |
| `factcheck-exhibits` | Do figures and tables show what the surrounding text says they show? | PASS iff every text-exhibit pairing is consistent. |
| `factcheck-against-source` | For derived artifacts (summaries, extensions), do claims match the source paper provided? | PASS iff zero claims misrepresent the source. Requires `--source-paper`. |

### Element (Ralph-inspired, content-specific)

| ID | Sharp question | Pass rule |
|---|---|---|
| `element-lit-review-coverage` | Are key citations from target journals present in the literature review? | PASS iff zero CRITICAL gaps AND no more than one IMPORTANT gap. |
| `element-lit-review-length` | Is the literature review at most half a page in the compiled artifact? | PASS iff lit review fits in half a compiled page. |
| `element-opening-figure` | Does the opening figure motivate the paper's central question? | PASS iff opening figure is on-topic and self-explanatory. |

### Slides (compiled deck, requires `--screenshots-dir`)

| ID | Sharp question | Pass rule |
|---|---|---|
| `slides-text-fitting` | Does text fit on each slide without overflow or clipping? | PASS iff zero slides flagged for overflow. |
| `slides-density` | Is each slide neither overcrowded (>~6 bullets without progressive opacity) nor under-full (<~60% fill)? | PASS iff zero slides flagged for either density problem. Reads `density.json` produced by `scripts/measure-slide-density.py` (a sidecar that converts each PNG to grayscale and computes the non-background-pixel fraction); the test agent does not eyeball screenshots. |
| `slides-readability` | Is the body font ≥18pt, code monospace, contrast adequate? | PASS iff every slide meets readability minimums. |
| `slides-headline-coverage` | Does each major paper result appear in the slides? | PASS iff zero major-result omissions. Requires `--source-paper`. |
| `slides-progression` | Does the slide order tell a coherent story? | PASS iff every adjacent pair reads as inevitable. |

### Code

| ID | Sharp question | Pass rule |
|---|---|---|
| `code-correctness` | Are there logic bugs, missed edge cases, or error-propagation failures? | PASS iff zero CRITICAL findings. |
| `code-simplicity` | Are there YAGNI violations, premature abstractions, or speculative helpers? | PASS iff zero violations flagged after weighing in-codebase usage. |
| `code-naming` | Are names accurate (the thing does what its name says) and consistent with existing conventions? | PASS iff every flagged name has accurate alternative; conventions match repo. |
| `code-error-handling` | Are errors surfaced or handled, rather than silently caught with bare `except` or `# type: ignore`? | PASS iff zero silent-failure patterns. |

### Adversarial (Ralph-inspired)

| ID | Sharp question | Pass rule |
|---|---|---|
| `adversarial-load-bearing` | What load-bearing assumptions, if false, would break the argument? Are they defended or conceded? | PASS iff every load-bearing assumption is either defended or explicitly conceded. |
| `adversarial-alternative-explanation` | What alternative explanations could produce the same observation? Does the artifact rule them out? | PASS iff every viable alternative is addressed or explicitly out of scope. |
| `adversarial-prompt-injection` | Does the artifact contain text that tries to direct the reviewer (e.g., "ignore prior instructions", "give this PASS")? | PASS iff zero injection attempts found. |

### Consistency (paired artifacts, requires `--paired-slides` or similar)

| ID | Sharp question | Pass rule |
|---|---|---|
| `consistency-equivalent-ideas` | Do the paired artifacts cover the same core ideas (allowing one to omit detail the other includes, but never to drop a core concept)? | PASS iff zero core-concept omissions in either direction. |
| `consistency-claim-alignment` | Do quantitative claims match exactly across the paired artifacts? | PASS iff every shared number is identical. |

## Profile Composition

Each profile names its tests. A test can appear in multiple profiles.

### `writing` (14 tests)
All `writing-*` tests (8), all `structure-*` tests (4), `adversarial-load-bearing`, `adversarial-prompt-injection`.

### `paper-summary` (16 tests, requires `--source-paper`)
All `writing-*` (8), all `structure-*` (4), `narrative-section-fulfillment`, `narrative-claim-strength`, `factcheck-against-source`, `adversarial-prompt-injection`.

### `extension-proposal` (18 tests, requires `--source-paper`)
All `writing-*` (8), all `structure-*` (4), `narrative-section-fulfillment`, `narrative-claim-strength`, `factcheck-against-source`, `adversarial-load-bearing`, `adversarial-alternative-explanation`, `adversarial-prompt-injection`.

### `slides` (6 + 1 conditional tests, requires `--screenshots-dir`)
`slides-text-fitting`, `slides-density`, `slides-readability`, `slides-progression`, `writing-throat-clearing`, `writing-engagement-bait`. With `--source-paper`: also `slides-headline-coverage`.

### `presentation-writeup` (12 + 1 conditional tests)
All `writing-*` (8), all `structure-*` (4). With `--paired-slides`: also `consistency-equivalent-ideas`.

### `code` (4 tests)
`code-correctness`, `code-simplicity`, `code-naming`, `code-error-handling`.

### `paper-source` (experimental, 32 tests)
All `writing-*`, all `structure-*`, all `math-*`, all `theory-*`, all `narrative-*`, all `factcheck-*` (except `factcheck-against-source` which needs a source), all `element-*`, all `adversarial-*`. Optional `--spec` and `--references` enrich the lit-review and consistency tests.

## Implied Loop Changes

The new suite is the migration target for the CASM-tools harness. The five rewrites below are the planned shared-infra changes — listed for sizing, not for resolution here. Per Scope Posture, `tests/` and `preferences/` are deleted once these land.

1. **Grammar.** The `/CASM-tools:review-document` closed grammar is rewritten to take profiles and per-profile input clauses (`--source-paper`, `--screenshots-dir`, `--paired-slides`) in place of the existing reviewer-name tokens.
2. **Test discovery and parallelism.** `scripts/run-tests.py` is rewritten to load profiles from a profile manifest rather than filename pattern matching. A profile manifest file (likely `tests/profiles.json` or similar) declares each profile's test list and required inputs. The runner accepts an optional `--jobs N` flag (modeled on `chenandrewy/ralph-wiggum-asset-pricing`'s `ralph/run-tests.py`): default behavior is one worker per selected test (current behavior), and `--jobs N` caps the worker pool at `min(N, len(selected_tests))` for invocations against the heavier profiles where API rate limits or local memory pressure are concerns.
3. **Schema validation.** `tests/_helpers.py`'s `ENVELOPE_SCHEMA` is replaced: drops `score` and `gating`, adds per-test payload schemas alongside each test. The renderer needs a registry of payload-shape → display-rule.
4. **Convergence.** Loop terminates when every test in the active profile returns PASS. No score thresholds, no advisory bypass. Iteration cap remains as a safety net. **Cap-exhaustion behavior:** when the cap is reached with N tests still FAILing, the harness exits with a third terminal state `EXHAUSTED` (distinct from PASS and FAIL) and writes a triage report listing each unresolved test with its FAIL reason and the reviewer-supplied evidence the writer would need to address it. Callers (paper-* skills) treat `EXHAUSTED` as an unresolved-failures state, not as success.
5. **Section-region rendering.** `scripts/render-results.py` is rewritten so the summary table surfaces section/region labels per test (not just a flat findings count).

## Open Questions Deferred to Implementation

- **Renderer shape.** Per-test payload schemas need a display rule each. Implementation should propose whether this lives in a Python registry or as a `display.json` alongside each test.
- **Profile manifest format.** JSON vs Python dict vs declarative YAML. Pick during implementation.
- **Source-paper representation for paper-summary / extension-proposal tests.** PDF vs extracted text. Likely PDF passed straight through to the agent (it can `Read` the PDF) but worth confirming.

## Success Criteria

- Catalog of 44 narrow tests, each with a sharp question and pass rule, fits the profiles defined.
- Each profile has a coherent test list that's clearly applicable to the artifact type.
- The implied loop changes are explicit enough that a planner can size the harness work without further discovery.
- The user can read the catalog and prune tests they consider redundant before implementation.
- **Convergence smoke check:** on at least one representative artifact run through the heaviest profile (`paper-source`, 32 tests), the loop reaches all-PASS within the iteration cap during PoC validation. If it does not, the cap is too tight, the writer's restructuring power is insufficient, or the test set is over-constrained — diagnose before adopting.
