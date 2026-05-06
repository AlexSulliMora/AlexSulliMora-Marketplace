---
description: Close out a project. Audit project-local validators for promotion, write durable learnings to a per-project learnings file, compile the audit transcript, and mark the project finalized in the global index.
argument-hint: [project_id]
allowed-tools: Bash, Read, Write, Edit, AskUserQuestion
---

Load `skills/coauthor-workflow/SKILL.md` and follow the **Stage 4: Finalize** procedure.

Inputs:
- `$ARGUMENTS`: optional `project_id`. Default: cwd-resolved project, falling back to the most recent project in `~/.claude/coauthor/INDEX.md` whose reviews are completed.
- Read SCOPE, PLAN, every IMPL, every REVIEW, CONVENTIONS, and `<project_dir>/coauthor/validators/`.

The orchestrator handles user-facing prompts directly via `AskUserQuestion`. Do not dispatch agents in this stage.

## a. Validator promotion audit

Enumerate every file under `<cwd>/coauthor/validators/`. For each, generate a recommendation (`promote` or `skip`) with a one-line rationale grounded in how the validator was used during the project: which slices it ran on, how often it caught issues, whether it generalises beyond the current project.

Then issue a **single** `AskUserQuestion` call presenting all candidates as a multi-select question. Format the prompt so each option lists the validator path, the recommendation, and the one-line rationale, e.g.:

```
Select validators to PROMOTE to the global library. Anything left unselected will be recorded as `skip`.

[ ] validators/data/range-checks.py — rec: promote — caught 3 issues across s1,s3; generalises to any panel-data project
[ ] validators/writer/local-style.md — rec: skip — project-specific terminology only
...
```

Collect the user's selections. For each candidate, the decision is `promote` if selected, `skip` otherwise.

Append one line per candidate to `~/.claude/coauthor/promotion-log.md` (append-only):

```
- <ISO date> | <project_id> | <validator path> | recommendation: promote|skip | rationale: <one line> | decision: promote|skip
```

For `promote` decisions: copy the validator to `validators/<domain>/` with a bumped `version` field and a provenance note in the body. Edits to existing library validators happen in place with a version bump.

## b. Learnings file

Durable lessons from this project go to `~/.claude/coauthor/learnings/<project-name>.md`, where `<project-name>` is the cwd basename (the same value used as `project_id`). The file is append-only across runs and tabular.

1. Run `mkdir -p ~/.claude/coauthor/learnings/` before writing.
2. Surface candidate lessons from REVIEW files, IMPL deviations, and CONVENTIONS additions. For each candidate, classify the category as one of: `methodology`, `robustness`, `literature`, `framing`, `replicability`, `reports`, `tooling`, `workflow`. Identify the source artifact path (e.g., `REVIEW-methodology.md`).
3. Ask the user via `AskUserQuestion` to approve, edit, or skip each draft lesson. Keep each `learning` to one line.
4. If `~/.claude/coauthor/learnings/<project-name>.md` does not exist, create it with this header:

   ```markdown
   # Learnings: <project-name>

   | date       | category       | learning                                       | source artifact          |
   |------------|----------------|------------------------------------------------|--------------------------|
   ```

5. Append one row per approved lesson:

   ```
   | YYYY-MM-DD | <category>     | <one-line lesson>                              | <source artifact>        |
   ```

   Use today's ISO date. Do not rewrite existing rows.

## c. Audit transcript

Run the compilation script and report the output path:

```
python3 ${CLAUDE_PLUGIN_ROOT}/hooks/compile_audit.py
```

The script reads `<cwd>/coauthor/audit/coauthor.md` and per-worker log files, joins dispatch references by exact timestamp, and writes a self-contained `<cwd>/coauthor/audit/transcript.html` with embedded CSS, no JS, a sticky stage-grouped sidebar TOC, and collapsible dispatch sections. Orphan worker log entries appear in a final "Orphan dispatches" section. Missing references render as inline warnings. If the audit directory does not exist, the script prints an error and exits 1.

## d. Index update

Edit `~/.claude/coauthor/INDEX.md`: set this project's status to `finalized`.

Promotion is the finalizing step. Skipping it means the next project starts cold. Logging recommendations alongside decisions lets the user audit the orchestrator's judgment over time.
