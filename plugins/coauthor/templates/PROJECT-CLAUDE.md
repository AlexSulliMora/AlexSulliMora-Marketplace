<!-- COAUTHOR-IMPORT-LINE -->
@<absolute path to plugin canonical CLAUDE.md>

# Project context

This file is written by `/scope` to `<cwd>/.claude/CLAUDE.md`. Claude Code auto-loads `<cwd>/.claude/CLAUDE.md` (and `<cwd>/CLAUDE.md`) for every session inside the project directory; the `.claude/` location keeps tooling out of the project root. It carries project-specific context only. Operating rules (principles, response style, banned writing patterns, workflow stages, standing team, audit-log conventions) come from the coauthor plugin's canonical `CLAUDE.md`. `/scope` offers two ways to load them: install the canonical at the project's parent directory so Claude Code's directory walk picks it up automatically, or keep the `@import` line above so the absolute path resolves into this session. The first line marker and the `@import` line are written or omitted by `/scope` based on the user's choice; the marker is removed when the import is omitted. If the plugin moves on disk and you used the `@import` route, update the path here by hand.

## Context

- **Name:** <auto-filled from cwd basename at /scope>
- **One-line description:** <filled by /scope argument>
- **Question:** <filled at scope-freeze>
- **Data:** <filled at scope-freeze>
- **Method summary:** <filled at scope-freeze>

## Standing team

<!-- Populated at /plan. List the named workers active here and one line on each role's beat. -->

- analyst: <beat>
- coder: <beat>
- writer: <beat>
- reviewer: <beat>
- researcher: <beat>

## Active validators

<!-- Populated at /plan. List validator ids attached to slices. -->
