# Validator design

A validator is a mechanical, objective check against an artifact. It produces a structured report; it does not grade, rewrite, or opine.

## Anatomy

```yaml
---
id: <domain>/<short-name>
domain: writer | data | regression | derivation
version: 0.1.0
applies_to: [SCOPE.md, IMPL-*.md, *.qmd, ...]
---
```

Body sections:

- **Checks.** What patterns, properties, or invariants the validator enforces. Be specific and grep-able where possible.
- **How to run.** A shell command, a Python snippet, or an explicit procedural checklist for a worker.
- **Pass criteria.** What clean output looks like.
- **Fail output.** What a failure report contains: location (file path, line), pattern matched, suggested fix.
- **Applicable contexts.** When the validator should and should not be attached.

## Promotion pipeline

Project-local validators live in `<cwd>/coauthor/validators/`. During `/finalize`, the orchestrator generates a promote/skip recommendation per validator with one-line rationale; the user supplies the final decision; both are logged to `~/.claude/coauthor/promotion-log.md`. On promotion: copy to `validators/<domain>/`, bump version, add a provenance note in the body identifying the originating project.

## What is in scope

Mechanical, objective checks: regex-able patterns, schema validity, null rates, numerical convergence checks, citation existence, file presence.

## What is out of scope

Anything requiring substantive judgment about meaning: clarity, argument tightness, framing fit, methodological soundness. Those belong in `/review`.
