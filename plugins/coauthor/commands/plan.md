---
description: Translate a frozen SCOPE.md into a worker decomposition (PLAN.md). Orchestrator-only; does not dispatch workers.
argument-hint: [project_id]
allowed-tools: Read, Write, Edit, Bash, AskUserQuestion
---

Load `skills/coauthor-workflow/SKILL.md` and follow the **Stage 2: Plan** procedure.

Inputs:
- `$ARGUMENTS` is the optional `project_id`. If omitted, treat the cwd as the project directory and read its `coauthor/SCOPE.md`. If a `project_id` is given, resolve its directory via `~/.claude/coauthor/INDEX.md`. `project_id` equals the cwd basename (no date suffix).
- Read `<project_dir>/coauthor/SCOPE.md` (must be frozen) and `<project_dir>/coauthor/CONVENTIONS.md` if present.

Preconditions:
1. Refuse if `<project_dir>/coauthor/` does not exist. Print: "Run /scope first."
2. Refuse if SCOPE.md is not frozen. Ask the user to run `/scope` to completion.

Actions:
1. Decompose the work into slices, one per worker dispatch. Each slice is a single deliverable (one IMPL.md). Available workers: `analyst`, `coder`, `writer`, `researcher`, `reviewer`.
2. Use `AskUserQuestion` for clarification questions about scope edges, validator selection, or worker assignment. One structured question per call. Avoid free-form text with embedded questions.
3. Do not restate the user's input. Ask only the questions you need answered, or write directly to PLAN.md.
4. Select validators from `validators/` to attach to each slice. Reference by id.
5. Instantiate `templates/PLAN.md` at `<project_dir>/coauthor/PLAN.md`. Ask the user to read it before freezing. Once they sign off, set `status: frozen`.
6. Update `<project_dir>/CLAUDE.md`: populate the `Standing team` and `Active validators` sections from the plan. Leave operating principles and response-style sections untouched.
7. Update `~/.claude/coauthor/INDEX.md`: set this project's status to `planned`.

The plan is the contract workers execute against. Be specific about file paths, success criteria, and validators. Flag ambiguity to the user rather than guess.
