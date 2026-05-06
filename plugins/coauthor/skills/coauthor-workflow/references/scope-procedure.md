# Stage 1 procedure: scope

Entry: `/scope <one-line project description>` or `/scope @<path-to-spec.md>`. The second form is a bare or `@`-prefixed path to an existing `.md` file whose contents seed SCOPE.md. Actor: orchestrator with the user. This stage merges what was previously `/init` plus the scoping conversation.

## 1. Validate cwd

Resolve via `pwd`. Refuse if cwd is `$HOME`, `/`, `~/.claude`, `~/Downloads`, `~/Documents`, or anywhere else without a sensible project context. Print the resolved cwd and the reason; ask the user to `cd` into a project directory and retry.

## 2. Resolve canonical path and walk ancestors

Compute `${CLAUDE_PLUGIN_ROOT}/CLAUDE.md` (falling back to `$HOME/.claude/plugins/coauthor/CLAUDE.md` if the env var is unset); expand any leading `~` to `$HOME`. Then walk from cwd up to `$HOME` (inclusive), checking each ancestor's `CLAUDE.md` for the marker line `<!-- coauthor-canonical-rules v1 -->`. If a marker-bearing file is found, the canonical is already in scope via Claude Code's directory walk; record `install_choice=ancestor` and skip the install prompt.

## 3. Canonical-install prompt

If no ancestor canonical was found, ask via `AskUserQuestion` with one structured question and three options.

- **Install at parent directory**: copy the canonical to a chosen ancestor's `CLAUDE.md`; default chosen is the parent of cwd, with an "Elsewhere" sub-option to pick a different ancestor.
- **Import in this project's CLAUDE.md**: write `@<canonical absolute path>` as the first line of `<cwd>/CLAUDE.md`.
- **Skip**: rules unloaded; not recommended.

Record the result as `install_choice` in {`parent`, `import`, `skip`}. For `parent`, copy the canonical to `<chosen>/CLAUDE.md` only if that file does not already exist; if it does, refuse and ask the user to merge by hand.

## 4. Scaffolding

Derive `project_id` from cwd basename. Create `<cwd>/.claude/`, `<cwd>/coauthor/`, `<cwd>/coauthor/audit/`, `<cwd>/coauthor/validators/`. Copy `templates/CONVENTIONS.md` to `<cwd>/coauthor/CONVENTIONS.md`. The project-context `CLAUDE.md` destination is `<cwd>/.claude/CLAUDE.md`.

If a project `CLAUDE.md` already exists at either `<cwd>/.claude/CLAUDE.md` or the legacy `<cwd>/CLAUDE.md`, leave it alone and print a notice describing what to add by hand given `install_choice` (an `@<canonical>` first line for `import`; nothing for `parent`/`ancestor`/`skip`). Otherwise copy `templates/project-CLAUDE.md` to `<cwd>/.claude/CLAUDE.md` and branch on `install_choice`:

- For `import`, replace the `<!-- COAUTHOR-IMPORT-LINE -->` marker line and the placeholder `@<absolute path to plugin canonical CLAUDE.md>` line with a single `@<canonical absolute path>` line.
- For `parent`, `ancestor`, or `skip`, delete the marker line, the placeholder `@<...>` line, and the trailing blank line, so the project file starts at `# Project context`.

In all branches, fill `Name` from cwd basename and `One-line description` from `$ARGUMENTS`. If the file-input branch was taken, move the resolved spec to `<cwd>/.claude/specs/<basename>` (semantic move: copy then delete original; abort if the destination already exists; skip if the source already lives under `<cwd>/.claude/`). Register the project in `~/.claude/coauthor/INDEX.md` with status `scoping`. The first write under `<cwd>/.claude/` may trigger a single permission prompt under default Claude Code settings; that is expected and one-time.

## 5. Scoping conversation

Copy `templates/SCOPE.md` to `<cwd>/coauthor/SCOPE.md` with `status: draft`. If `$ARGUMENTS` is a description, use `AskUserQuestion` for clarifications, one structured question per call, covering question precision, in/out scope, rough method, data, constraints, and definition of done. If `$ARGUMENTS` is a markdown-file reference of the form `@<path>` or a bare `.md` path that exists, read it, map its content into SCOPE.md sections by heading match, put unmatched content under a final `## Notes from input file` section, then ask only about template sections the file did not cover. Do not restate input.

## 6. Freeze

Write agreed answers into SCOPE.md as the conversation proceeds. Once filled, show the path and ask the user to read it before freezing. After sign-off, set `status: frozen` in SCOPE.md, fill the `Question`, `Data`, and `Method summary` placeholders in `<cwd>/.claude/CLAUDE.md`, and update `~/.claude/coauthor/INDEX.md`.

Do not dispatch workers in this stage. Scoping is the orchestrator's job because it requires the user's domain judgment.
