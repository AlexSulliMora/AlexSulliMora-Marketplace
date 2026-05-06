# Validator library

Mechanical, objective checks attached to PLAN slices. Workers run them internally before declaring a slice done. Validators do not grade or rewrite; they produce structured pass/fail reports.

## Domains

- `writer/`: writing validators (AI-tells, banned words, em-dash misuse, undefined acronyms).
- `data/`: schema, null rates, key uniqueness, range bounds.
- `regression/`: numerical cross-checks (`pr.compare()` against known references).
- `derivation/`: data-generating-process simulations that confirm an estimator converges to the true parameter.
- `reports/`: Quarto-HTML style conformance for `.qmd` files rendering to HTML report deliverables. Source of truth for the visual conventions: `${CLAUDE_PLUGIN_ROOT}/skills/quarto-html-report/SKILL.md`.

## Anatomy

Each validator is a markdown file with frontmatter:

```yaml
---
id: <domain>/<short-name>
domain: <writer|data|regression|derivation|reports>
version: <semver>
applies_to: [glob1, glob2]
---
```

Body sections: **Checks**, **How to run**, **Pass criteria**, **Fail output**, **Applicable contexts**.

## Promotion pipeline

1. New checks start in `<cwd>/coauthor/validators/` for one project.
2. During `/compound`, the orchestrator generates a promote/skip recommendation per validator with one-line rationale; the user supplies the final decision; both are appended to `~/.claude/coauthor/promotion-log.md`.
3. On promotion: copy here, bump version, add a provenance note in the body identifying the originating project.
4. Existing validators get edited in place; bump version on each change.

## Selection during `/plan`

The orchestrator attaches validators to each slice based on the slice's deliverable type:

- Writing slice → `writer/ai-tells` (run via `writer/check.py`).
- Data ingestion slice → `data/basic-checks`.
- Regression slice → `regression/pr-compare`.
- Derivation slice → `derivation/dgp-simulation`.
- Quarto HTML report slice (any `.qmd` rendering to HTML) → `reports/quarto-style` (run via `reports/check.py`).

Project-local validators take precedence over library validators with the same id.

## What is in scope

Mechanical, grep-able, runnable, or schema-checkable.

## What is out of scope

Substantive judgment about meaning, clarity, argument quality, methodological soundness. Those go to `/review`.
