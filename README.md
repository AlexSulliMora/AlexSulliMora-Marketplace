# AlexSulliMora-Marketplace

Personal Claude Code plugin marketplace. Ships two plugins:

- **deep-review** — tiered creator/reviewer cascade for multi-axis review of drafts, code, and documents. Provides `/deep-review:review-document`, nine reviewer agents, and a shared `preferences/` directory controlling scoring weights, severity calibration, and style rules.
- **paper-extension** — academic-paper pipeline for economics. Provides `/paper-extension:summarize`, `/paper-extension:extend`, and `/paper-extension:present`. Depends on `deep-review` for the review cascade.

## Prerequisites

- [Claude Code](https://docs.claude.com/en/docs/claude-code) (CLI, VS Code extension, or JetBrains extension)
- [uv](https://github.com/astral-sh/uv) — used by the hook scripts. Install once:
  - **Windows**: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
  - **Mac/Linux**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- For `paper-extension` workflows: [Quarto](https://quarto.org/docs/get-started/), `pdftoppm` (poppler-utils), and `marker-pdf` (for PDF preprocessing).

## Install

```
/plugin marketplace add AlexSulliMora/AlexSulliMora-Marketplace
/plugin install deep-review@AlexSulliMora-Marketplace
/plugin install paper-extension@AlexSulliMora-Marketplace
```

Install `deep-review` first — `paper-extension` uses its hook to inject style preferences.

## Customizing style preferences

Every scoring rule, severity threshold, and style rule lives in `plugins/deep-review/preferences/`:

- `writing-style.md`, `structure-style.md`, `math-style.md`, `factual-style.md`, `consistency-style.md`, `presentation-style.md`, `simplicity-style.md`, `code-style.md`, `adversarial-style.md`

Edit these files directly. A `PreToolUse` hook injects the relevant file(s) into each reviewer agent's prompt at dispatch time, so changes take effect on the next review without touching agent definitions.

## Layout

```
.claude-plugin/
  marketplace.json
plugins/
  deep-review/
    .claude-plugin/plugin.json
    agents/            — 9 reviewer agents
    preferences/       — 9 style/scoring files (user-editable)
    scripts/           — shared reviewer infrastructure
    skills/review-document/
    hooks/inject-preferences.py
  paper-extension/
    .claude-plugin/plugin.json
    agents/            — paper-summarizer, extension-proposer, presentation-builder
    skills/            — summarize, extend, present, preprocess, run, meta-review
    hooks/             — session-log-reminder.py, verify-reminder.py
```
