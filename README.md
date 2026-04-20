# AlexSulliMora-Marketplace

Personal Claude Code plugin marketplace. Ships one plugin:

- **CASM-tools** — tiered creator/reviewer review cascade (`/CASM-tools:review-document`) for multi-axis review of drafts, code, and documents, plus an academic-paper pipeline (`summarize`, `extend`, `present`) that uses the same cascade for its internal quality loops. Nine reviewer agents, three paper-pipeline creator agents, and shared `preferences/` files control scoring, severity calibration, and style rules.

## Prerequisites

- [Claude Code](https://docs.claude.com/en/docs/claude-code) (CLI, VS Code extension, or JetBrains extension)
- [uv](https://github.com/astral-sh/uv) — used by the hook scripts. Install once:
  - **Windows**: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
  - **Mac/Linux**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- For the paper pipeline (summarize / extend / present): [Quarto](https://quarto.org/docs/get-started/), `pdftoppm` (poppler-utils), and `marker-pdf`.

## Install

```
/plugin marketplace add AlexSulliMora/AlexSulliMora-Marketplace
/plugin install CASM-tools@AlexSulliMora-Marketplace
```

## Customizing style preferences

Every scoring rule, severity threshold, and style rule lives in `plugins/CASM-tools/preferences/`:

- `writing-style.md`, `structure-style.md`, `math-style.md`, `factual-style.md`, `consistency-style.md`, `presentation-style.md`, `simplicity-style.md`, `code-style.md`, `adversarial-style.md`

Edit these files directly. A `PreToolUse` hook injects the relevant file(s) into each reviewer agent's (and the paper-pipeline creator agents') prompt at dispatch time, so changes take effect on the next review without touching agent definitions.

## Layout

```
.claude-plugin/
  marketplace.json
plugins/
  CASM-tools/
    .claude-plugin/plugin.json
    agents/            — 9 reviewers + 3 paper-pipeline creators
    preferences/       — 9 style/scoring files (user-editable)
    scripts/           — shared reviewer infrastructure
    skills/            — review-document, summarize, extend, present, preprocess, run, meta-review
    hooks/             — inject-preferences.py, session-log-reminder.py, verify-reminder.py
```
