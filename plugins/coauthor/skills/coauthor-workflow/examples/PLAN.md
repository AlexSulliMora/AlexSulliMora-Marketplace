---
project_id: example-project
status: frozen
owners: [analyst, coder, writer]
created: 2026-04-12
---

# Plan

## Goal

Estimate the effect of a 2019 minimum-wage increase on quarterly employment in affected counties, using a difference-in-differences design, and produce a short HTML report with one headline table and one event-study figure.

## Decomposition

| Slice id | Worker | Goal | Inputs | Validators | Output | Parallel-with |
|----------|--------|------|--------|------------|--------|---------------|
| s1 | analyst | Pull QCEW county-quarter panel; document coverage and missingness | SCOPE.md, data/raw/qcew/*.parquet | data/basic-checks | IMPL-analyst-s1.md | s2 |
| s2 | coder | Build clean panel: treatment indicator, controls, balanced-sample flag | s1 output, data/raw/treatment-list.csv | data/basic-checks, data/panel-balance | IMPL-coder-s2.md | s1 |
| s3 | coder | Run two-way fixed-effects DiD plus event-study with polars_reg; compare against Stata via pr.compare | s2 output | regression/pr-compare | IMPL-coder-s3.md | — |
| s4 | writer | Draft HTML report with headline DiD table (pr.regtable) and event-study coefplot | s3 output, SCOPE.md | reports/check, writer/banned-terms | IMPL-writer-s4.md | — |

## Constraints

- Polars lazy-first throughout; collect only at table/plot boundaries.
- Cluster standard errors at the county level for all DiD specifications.
- Random seed: derive from 2026-04-12 (use 20260412).
- Do not convert to pandas at any point in the pipeline.

## Success criteria

- Cleaned panel passes data/panel-balance with zero unbalanced county-quarters in the working sample.
- Headline coefficient and standard error match Stata to four decimal places via pr.compare.
- HTML report renders without error and passes reports/check.
- Event-study plot uses the tableau10 palette with shape encoding for pre/post.

## Validators referenced

- data/basic-checks v0.3.0 (plugin)
- data/panel-balance v0.1.1 (project-local at coauthor/validators/)
- regression/pr-compare v0.2.0 (plugin)
- reports/check v0.4.0 (plugin, auto-attached for .qmd → HTML)
- writer/banned-terms v0.5.0 (plugin)

## Context pointers

- /home/example/research/example-project/data/raw/qcew/
- /home/example/research/example-project/data/raw/treatment-list.csv
- /home/example/research/example-project/coauthor/SCOPE.md
- /home/example/research/example-project/coauthor/CONVENTIONS.md
