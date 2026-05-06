---
description: Set up a coauthor project and run the scoping conversation. Validates cwd, walks ancestors for an existing canonical CLAUDE.md, prompts for canonical install if absent, drops project scaffolding, then opens a structured scoping conversation and freezes SCOPE.md.
argument-hint: <one-line project description> | @<path-to-spec.md>
allowed-tools: Read, Write, Edit, Bash, AskUserQuestion
---

Load `skills/coauthor-workflow/SKILL.md` and follow the **Stage 1: Scope** procedure. This command performs project setup (cwd validation, canonical-rules install, scaffolding) and then runs the scoping conversation.

Inputs:
- `$ARGUMENTS` takes one of two forms. A one-line project description is the default. Alternatively, a markdown-file reference of the form `@<path>` or a bare path ending in `.md` that resolves to an existing file: its contents seed SCOPE.md.
- Project directory is the current working directory (cwd). Per-project artifacts live in `<cwd>/coauthor/`.
- `project_id` is the cwd basename. No date suffix.

## Argument detection

Before running the actions below, classify `$ARGUMENTS`:

1. Strip a single leading `@` if present.
2. If the stripped string ends in `.md` and resolves to an existing file (relative paths resolved against cwd; `~` expanded), treat it as a **file input**. Resolve to an absolute path.
3. Otherwise treat it as a **one-line description** (current behaviour).

The file-input branch only changes step (c) below; the cwd validation and scaffolding are identical.

## Preconditions

1. Resolve cwd via `pwd`. Refuse if cwd is `$HOME`, `/`, `~/.claude`, `~/Downloads`, `~/Documents`, or anywhere else without a sensible project context. Print the resolved cwd and the reason; ask the user to `cd` into a project directory (typically `~/research/<project-dir>/`) and retry.

## Actions

### a. Resolve the canonical operating-rules path and check ancestors

Compute the absolute path to the plugin's canonical `CLAUDE.md`:

```bash
canonical="${CLAUDE_PLUGIN_ROOT}/CLAUDE.md"
canonical="${canonical/#\~/$HOME}"
```

If `${CLAUDE_PLUGIN_ROOT}` is not set, fall back to `$HOME/.claude/plugins/coauthor/CLAUDE.md`.

Then walk from cwd up to `$HOME` (inclusive), checking each ancestor's `CLAUDE.md` and `.claude/CLAUDE.md` for the marker line `<!-- coauthor-canonical-rules v1 -->`. Both locations are checked because Claude Code loads memory from either path during its ancestor walk, and the user may have placed the canonical at either one:

```bash
dir="$(pwd)"
found=""
while :; do
  for cand in "$dir/CLAUDE.md" "$dir/.claude/CLAUDE.md"; do
    if [ -f "$cand" ] && grep -qF '<!-- coauthor-canonical-rules v1 -->' "$cand"; then
      found="$cand"
      break 2
    fi
  done
  [ "$dir" = "$HOME" ] && break
  [ "$dir" = "/" ] && break
  dir="$(dirname "$dir")"
done
```

If `found` is non-empty, a canonical is already in scope via Claude Code's tree walk. Skip the install prompt; set `install_choice=ancestor` and proceed.

### b. Canonical-install prompt

If no ancestor canonical was found, ask the user via `AskUserQuestion` (one structured question, three options) where the operating rules should come from:

- **Install at parent directory.** Copy `<canonical>` to `<parent>/CLAUDE.md`, where `<parent>` defaults to the parent of cwd. Claude Code's directory walk will auto-load it for any project under that parent. Recommended when the user expects multiple coauthor projects under the same research root.
- **Import in this project's CLAUDE.md.** Do not copy. Write `@<canonical absolute path>` as the first line of `<cwd>/CLAUDE.md` so the rules load via `@import` for this project only. Note: the path is absolute; if the plugin moves, the line must be updated by hand.
- **Skip canonical install.** Operating rules will not load. Not recommended; the workflow assumes the canonical is in scope.

For "Install at parent", offer a sub-prompt via `AskUserQuestion` with two options: accept the default `<parent of cwd>`, or choose "Elsewhere" to enter a different ancestor directory (must be an existing ancestor of cwd or `$HOME` itself). Resolve the chosen path to `<chosen>`.

Then check whether `<chosen>/CLAUDE.md` or `<chosen>/.claude/CLAUDE.md` already exists. Three cases:

- **Both exist.** Do not pick one silently; the plugin should avoid creating dual-CLAUDE.md setups but must not disrupt a user who already has one. Notify the user via `AskUserQuestion` that two CLAUDE.md files were found at `<chosen>/CLAUDE.md` and `<chosen>/.claude/CLAUDE.md`, and ask which to operate on. The chosen file becomes `<existing>`; the other is left untouched. Then proceed with the existence-handling logic below against `<existing>`.
- **Exactly one exists.** That path is `<existing>`.
- **Neither exists.** Skip ahead to the verbatim-copy step at the end of this section.

If `<existing>` already contains the marker line `<!-- coauthor-canonical-rules v1 -->`, the canonical is already installed there: skip the install, set `install_choice=ancestor`, and proceed.

Otherwise notify the user via `AskUserQuestion` that a non-canonical `CLAUDE.md` was found at `<existing>` and offer four options:

- **Merge.** Prepend the canonical to `<existing>` so the marker line stays at the top. Concretely, write the contents of `<canonical>` followed by a blank line followed by the prior contents of `<existing>` back to `<existing>`. The user's existing rules end up appended below the canonical block. Set `install_choice=parent`.
- **Replace.** Overwrite `<existing>` with `<canonical>` verbatim. Destructive: confirm once before writing, and report the absolute path of the file being overwritten in the confirmation. Set `install_choice=parent`.
- **Choose a different directory.** Re-open the "default parent vs Elsewhere" sub-prompt, resolve a new `<chosen>`, and re-run this existence check against the new location. Loop until the user picks a directory with no existing `CLAUDE.md` / `.claude/CLAUDE.md`, or selects one of the other three options here.
- **Install in project instead.** Abort the parent-install branch and fall through to the `import` branch (write `@<canonical>` as the first line of `<cwd>/.claude/CLAUDE.md` per step (c)). Set `install_choice=import`.

If neither `<chosen>/CLAUDE.md` nor `<chosen>/.claude/CLAUDE.md` exists, copy `<canonical>` verbatim (preserving the `<!-- coauthor-canonical-rules v1 -->` marker) to `<chosen>/CLAUDE.md`. Set `install_choice=parent`.

For "Import in this project's CLAUDE.md", set `install_choice=import`.

For "Skip", set `install_choice=skip`.

### c. Scaffolding

1. Derive `project_id` from the cwd basename. Capture today's ISO date.
2. Create directories: `<cwd>/.claude/`, `<cwd>/coauthor/`, `<cwd>/coauthor/audit/`, `<cwd>/coauthor/validators/`. Empty placeholders are fine. The first write to `<cwd>/.claude/` may trigger a single permission prompt under default Claude Code settings; that is expected and one-time.
3. Copy `${CLAUDE_PLUGIN_ROOT}/templates/CONVENTIONS.md` to `<cwd>/coauthor/CONVENTIONS.md`. Fill `project_id` and `updated`.
4. Project `CLAUDE.md`. The destination is `<cwd>/.claude/CLAUDE.md`. If a project `CLAUDE.md` already exists at either `<cwd>/CLAUDE.md` (legacy location) or `<cwd>/.claude/CLAUDE.md`, leave it alone and print a notice describing what to add by hand: the `@<canonical>` line for `import`, nothing in the other branches. Otherwise copy `${CLAUDE_PLUGIN_ROOT}/templates/PROJECT-CLAUDE.md` to `<cwd>/.claude/CLAUDE.md` and branch on `install_choice`:
   - `import`: replace the first two template lines, namely the `<!-- COAUTHOR-IMPORT-LINE -->` marker and the placeholder `@<absolute path to plugin canonical CLAUDE.md>` line, with a single line: `@<canonical>`, where `<canonical>` is the absolute path computed in step (a). Print the resolved import line.
   - `parent`, `ancestor`, or `skip`: delete both the `<!-- COAUTHOR-IMPORT-LINE -->` marker line and the placeholder `@<...>` line, plus the blank line that follows them. The project file then starts with `# Project context`. For `parent` and `ancestor`, print the canonical location so the user knows where the rules are loaded from. For `skip`, print a warning that operating rules are not loaded.
   - Fill `Name` from cwd basename and `One-line description` from `$ARGUMENTS` in all branches.
5. **Input-spec move (file-input branch only).** If `$ARGUMENTS` resolved to an existing markdown file in step "Argument detection", move it to `<cwd>/.claude/specs/<basename>`:
   - Skip the move when the source already lives under `<cwd>/.claude/`.
   - If `<cwd>/.claude/specs/<basename>` already exists, abort with an error rather than overwrite; tell the user to rename or remove the destination and retry.
   - Otherwise create `<cwd>/.claude/specs/`, copy the source there, and delete the original so the operation is a move rather than a copy. Update the absolute path used downstream in step (d) to point at the new location.
6. Register the project in `~/.claude/coauthor/INDEX.md` (create from `${CLAUDE_PLUGIN_ROOT}/templates/INDEX.md` if missing). Append: `<project_id> | <absolute cwd> | scoping | <YYYY-MM-DD>`.

### d. Scope-clarification flow

1. Copy `${CLAUDE_PLUGIN_ROOT}/templates/SCOPE.md` to `<cwd>/coauthor/SCOPE.md` and fill `project_id` (cwd basename), `created` (today), `status: draft`.
2. **Description-input branch.** Open a structured scoping conversation with the user. Use `AskUserQuestion` for clarifications: one structured question per call. Cover the research question precision, what is in and out of scope, rough method, data, constraints, and what "done" looks like. Fill SCOPE.md as the conversation progresses.
3. **File-input branch.** Read the resolved markdown file. Treat its contents as the user's project specification (free-form: question, method, data, constraints, etc.).
   - Map content into SCOPE.md sections by heading match where possible. Examples: an input heading containing "question" feeds the `## Question` section, and "scope", "approach", "data", "constraints" map to their like-named template sections.
   - Put unmatched content verbatim under a final `## Notes from input file` section in SCOPE.md, prefixed with the absolute path of the source file.
   - Identify which required template sections the file did NOT cover: question, in/out scope, approach summary, data, constraints, definition of done. Ask the user via `AskUserQuestion` only about those gaps, one structured question per call. Skip any field the file already answered.
4. Do not restate the user's input. No "what you're describing is..." preamble. No affirmation paragraph that recasts their words. Ask only the questions you need answered, or write directly to SCOPE.md.

### e. Freeze

1. Once SCOPE.md is filled, show its path and ask the user to read it before freezing.
2. After sign-off, set `status: frozen` in SCOPE.md frontmatter.
3. Update `<cwd>/.claude/CLAUDE.md`: fill the `Question`, `Data`, and `Method summary` placeholders in the project-context section. Leave the import line (if present) and the rest untouched.
4. Update `~/.claude/coauthor/INDEX.md`: set status to `scoped`.

Do not proceed to planning in the same turn. `/plan` is a separate entry point.
