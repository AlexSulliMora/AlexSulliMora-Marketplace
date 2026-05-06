---
description: Rename the current coauthor project's directory and update all frontmatter references atomically. After the rename, the user must `cd` into the new directory; the command itself cannot change the shell's cwd.
argument-hint: <new-name>
allowed-tools: Bash, Read, Edit
---

Rename the current coauthor project. `$ARGUMENTS` is the new project_id.

## a. Validate cwd is a coauthor project

Resolve cwd via `pwd`. If `<cwd>/coauthor/` does not exist, abort with a clear error: the current directory is not a coauthor project; `cd` into one and retry.

## b. Validate the new name

Let `new_name` be `$ARGUMENTS` after stripping surrounding whitespace. Reject and abort with a specific message if any of the following hold:

1. `new_name` is empty.
2. `new_name` contains a path separator (`/` or `\`), parentheses, spaces, or any character outside `[a-z0-9_-]`. Lowercase letters, digits, hyphens, and underscores only.
3. `new_name` equals the current cwd basename (no-op rename).
4. The destination `<dirname of cwd>/<new_name>` already exists as a file or directory.

Print which check failed; do not partially proceed.

## c. Compute paths

- `old_id` = basename of cwd.
- `new_id` = `new_name`.
- `old_path` = absolute cwd.
- `parent` = dirname of cwd.
- `new_path` = `<parent>/<new_id>`.

## d. Update frontmatter at the original path before moving

All edits happen at stable paths under `old_path` so the directory move in step (e) is the only filesystem change once edits are done.

Use the `Edit` tool on each of the following files when present (skip silently if a file does not exist; do not create stubs):

- `<old_path>/coauthor/SCOPE.md`
- `<old_path>/coauthor/PLAN.md`
- Every `<old_path>/coauthor/IMPL-*.md`
- Every `<old_path>/coauthor/REVIEW-*.md`
- `<old_path>/coauthor/CONVENTIONS.md`
- `<old_path>/.claude/CLAUDE.md`

In each file replace the frontmatter line `project_id: <old_id>` with `project_id: <new_id>`. In `<old_path>/.claude/CLAUDE.md` also replace the `Name:` field in the project-context section: `- **Name:** <old_id>` with `- **Name:** <new_id>`.

Use Bash `ls <old_path>/coauthor/` to enumerate the IMPL and REVIEW files; iterate over each match and run an `Edit` per file.

Do not touch any file under `<old_path>/coauthor/audit/` (the audit logs are historical) or `~/.claude/coauthor/promotion-log.md` (audit-trail principle).

## e. Move the directory

```bash
mv <old_path> <new_path>
```

If `mv` fails, abort and print the error. Do not attempt rollback of the frontmatter edits; the directory still exists at `old_path` with updated frontmatter, which is the recoverable state.

## f. Update the global INDEX

Edit `~/.claude/coauthor/INDEX.md`. Find the line whose first column is `<old_id>` and whose second column is `<old_path>`; rewrite it with the new project_id and new absolute path, preserving status and created date. Use a single `Edit` call with the full old line as `old_string` and the rewritten line as `new_string` so the match is unambiguous.

## g. Tell the user

Print the message:

```
Renamed `<old_id>` → `<new_id>`. Now run `cd <new_path>` and start a new session if you want to continue working in this project.
```

Note that the current shell's cwd is now stale; commands that read cwd (including any further coauthor commands in this session) will fail until the user `cd`s into `<new_path>`.

## What this command does NOT update

- `<new_path>/coauthor/audit/coauthor.md`, the per-worker logs, and `transcript.html`. Audit logs reference historical timestamps and prompts; rewriting them would falsify the record.
- `~/.claude/coauthor/promotion-log.md`. Stale `<old_id>` references stay; the log is append-only by design.
- Validator promotion records that have already graduated to the global library.
