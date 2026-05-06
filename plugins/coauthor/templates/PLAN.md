---
project_id: <cwd-basename>
status: draft   # draft | frozen
owners: [analyst, coder, writer, researcher, reviewer]
created: <YYYY-MM-DD>
---

# Plan

## Goal

The deliverable this plan produces. One or two sentences.

## Decomposition

One row per slice. Each slice is one worker × one deliverable.

| Slice id | Worker | Goal | Inputs | Validators | Output | Parallel-with |
|----------|--------|------|--------|------------|--------|---------------|
| s1 | analyst | ... | SCOPE.md, data/raw/*.parquet | data/basic-checks | IMPL-analyst.md | s2 |
| s2 | coder | ... | data/clean.parquet | regression/pr-compare | IMPL-coder.md | s1 |
| ... |

## Constraints

Methodological commitments, deadlines, resource limits the workers must respect.

## Success criteria

What done looks like at the project level. One bulleted list.

## Validators referenced

List validator ids with their version. Project-local validators in `<project_dir>/validators/` take precedence over plugin-level ones.

## Context pointers

Absolute paths to data, code, prior drafts. Workers read these as part of every brief.
