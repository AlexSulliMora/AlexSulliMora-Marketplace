# coauthor

A Claude Code plugin that runs a task-oriented research workflow designed with economists in mind. The plugin is for working through well-defined tasks with a heavy emphasis on clear documentation and replicability; all features are intended to address issues I encountered while trying to incorporate claude code into my work:

-   **Documentation and replicability.** The workflow is `scope -> plan -> work -> review -> finalize`, each project or task will have a well-defined scope and initial plan, recorded in a markdown file which the human user signs off on before any work begins. Any discretionary choices claude makes in the working stage is documented alongside the planning files. After `work`, `review`, or `finalize`, a full transcript of human/claude and claude/subagent messages is rendered into a human-readable format, this way the user can fully audit the work and trace issues to their root.

-   **Structured and customizable review.** Claude often deviates from my stated preferences; I want my analysis in python using pixi for environment management and polars for dataframe manipulation, but claude will often default to pandas installed with uv or miniforge. The `review` stage provides a formal check to make sure the work is structured the way I want it to be. This is customizable, so you can have claude work whatever way you want.

-   **Claude only orchestrates.** Common read/write operations rapidly fill up the context window with the full contents of the files edited or read. This leads to "context rot", where performance degrades heavily as context (especially irrelevant context) increases. By having claude behave like a senior manager, delegating all work to junior staff, claude's context is only filled with (a) my prompts, (b) claude's questions to and answers from subagents, and (c) claude's responses to me. This ensures that all context is actually relevant.

-   **Long-lived subagents.** On the other hand, whoever is actually editing those python files needs to know what's in them. For this purpose, claude has multiple subagents persisting throughout the session with the accumulated context which main-claude avoids. This is the junior staff doing all the grunt work.

## Stages

Five slash commands move a project from idea to closure:

-   `/scope` initializes a project and opens a structured scoping conversation, eventually writing a frozen `SCOPE.md` file

-   `/plan` translates the scope into an actionable plan decomposed into tasks for each worker in a frozen `PLAN.md`

-   `/work` dispatches workers per the plan, collects `IMPL-<worker>.md` files which record any deviations from the plan or discretionary choices, and runs the five reviewer personas in parallel

-   `/review <persona|all>` is a manual override to re-run a reviewer after fixes, producing a fresh `REVIEW-<persona>.md` . Since this is already ran at the end of `/work`, this is only for subsequent fixes

-   `/finalize` audits project-specific reviewers to consider including them in the set of global review patterns, saves durable lessons to global memory, compiles `transcript.html`, and marks the project finalized in the global index

A separate `/rename <new-name>` slash command renames the project directory and rewrites `project_id` across all artifacts

## Project layout

Single-write project tooling lives under `<cwd>/.claude/`; the frequently-written coauthor scaffolding stays at `<cwd>/coauthor/`.

```         
<cwd>/
├── .claude/
│   ├── CLAUDE.md                    # project-context (name, question, data, method, team, validators)
│   └── specs/
│       └── <input>.md               # any spec passed to `/scope @<path>`, moved here once
└── coauthor/
    ├── SCOPE.md                     # frozen at /scope sign-off
    ├── PLAN.md                      # frozen at /plan sign-off
    ├── IMPL-<worker>.md             # append-only within a slice
    ├── REVIEW-<persona>.md          # one file per review pass; -2, -3 for repeats
    ├── CONVENTIONS.md               # living style guide; workers read before each task
    ├── notes.md                     # orchestrator scratch space, created lazily
    ├── audit/
    │   ├── coauthor.md              # turn-level log: prompts, dispatch refs, responses
    │   ├── <worker>.md              # per-worker dispatch log
    │   └── transcript.html          # compiled view, refreshed at /work, /review, /finalize
    └── validators/                  # project-local validators; promoted at /finalize
```

`project_id` is the cwd basename. The global index at `~/.claude/coauthor/INDEX.md` carries one line per project: `<project_id> | <absolute path> | <status> | <created date>`. Status values written by the commands are `scoping` (initial), `scoped`, `planned`, and `finalized`. The promotion log at `~/.claude/coauthor/promotion-log.md` records every `/finalize` recommendation and decision. Per-project durable learnings live at `~/.claude/coauthor/learnings/<project-name>.md` as an append-only tabular markdown file.

## Standing team

-   `analyst`: file reads, fact-checks, repo navigation, project digests, and scaffolding writes (SCOPE.md, PLAN.md, INDEX.md, project-CLAUDE.md, the per-project memory index).
-   `coder`: Python, polars, polars_reg, Quarto.
-   `writer`: paper drafting and text editing, with a built-in mechanical AI-tell catch-list.
-   `researcher`: literature search, web lookups, prior-art digging.
-   `reviewer`: adversarial review under a named persona.

Workers are long-lived and accumulate project context across a session. Inside a worker's task, ephemeral sub-workers handle retrieval and tangents.

## Document lifecycle

-   **Frozen:** `SCOPE.md`, `PLAN.md`. Amend only via explicit unfreeze (set `status: draft`, edit, refreeze).
-   **Append-only:** `IMPL-<worker>.md` while working through a step of the plan; audit logs (`coauthor.md`, `<worker>.md`).
-   **One-per-pass:** `REVIEW-<persona>.md`. A repeat methodology review writes `REVIEW-methodology-2.md`.
-   **Living:** `CONVENTIONS.md` (the project's style guide; workers read it before each task), `notes.md` (orchestrator scratch).

## Validator library

`validators/` holds mechanical checks attached to PLAN slices.

-   `writer/ai-tells.md` plus `writer/check.py`: banned words, AI-tells, em-dash misuse, undefined acronyms. The Python script is the canonical implementation; the markdown spec documents what it catches.
-   `data/basic-checks.md`: schema, null rates, key uniqueness, range bounds.
-   `regression/pr-compare.md`: `pr.compare()` cross-check pattern.
-   `derivation/dgp-simulation.md`: simulate the data generating process and check estimator convergence.
-   `reports/quarto-style.md` plus `reports/check.py`: deterministic conformance for `.qmd` files rendering to HTML, against `${CLAUDE_PLUGIN_ROOT}/skills/quarto-html-report/SKILL.md` (YAML keys, ISO dates, `gt-scroll` wrapper, missing-value convention, sticky-thead CSS, Python-output wrapping). Auto-attached to any slice whose deliverable is a `.qmd` rendering to HTML.

## Validator lifecycle

1.  New checks start as project-local validators under `<cwd>/coauthor/validators/`.
2.  During `/finalize`, the orchestrator generates a `promote` or `skip` recommendation per validator with a one-line rationale grounded in how it was used (slices it ran on, issues caught, how well it generalizes).
3.  The user supplies the final decision via `AskUserQuestion`; both recommendation and decision append to `~/.claude/coauthor/promotion-log.md`.
4.  On `promote`, the validator copies into `validators/<domain>/` with a bumped `version` and a provenance note. Edits to existing library validators happen in place with a version bump.

Project-local validators take precedence over library validators with the same id, so a project can override a library check without forking.

## Audit trail and transcript

A three-tier audit captures every turn while `<cwd>/coauthor/` exists. Hooks (silent if the directory is absent) write per-worker logs to `<cwd>/coauthor/audit/<worker>.md` (one entry per Agent or SendMessage call) and a turn-level log to `<cwd>/coauthor/audit/coauthor.md` (user prompt, dispatch references by exact timestamp, assistant final response, plus a `(scope|plan|work|review|finalize|none)` stage tag tracked in `.stage`). Tool calls made inside a subagent's own loop are not visible to the main session and therefore not recorded; only top-level Agent and SendMessage dispatches show up.

The transcript is compiled into a self-contained `transcript.html` at three trigger points:

-   End of `/work`, after the consolidated review digest is shown.
-   End of `/review`, after the persona's REVIEW file is written.
-   During `/finalize`.

The compiled file lives at `<cwd>/coauthor/audit/transcript.html`. Open it directly in a browser to inspect the stage-grouped sidebar TOC, collapsible dispatches, and the "Orphan dispatches" section for entries whose reference is missing.

## Customization

The plugin is meant to be adapted; customize the default behavior, standing team, and validators to change your workflow. Want your written content to use gen alpha slang and your code to be equally absurd? Just change the `agent/writer.md` file to prefer absurd slang and the `agent/coder.md` file to prefer stata, then adjust the validators so they view this as acceptable behavior. It's easiest to tell claude what you want to be different and have it make the changes itself.

### 1. Changing default behavior and preferences

Three layers stack:

-   **Plugin operating rules** live in `CLAUDE.md` at the plugin root, marked by `<!-- coauthor-canonical-rules v1 -->`. Edit this file to change banned writing patterns, response-style caps, the standing-team roster, workflow stages, or audit conventions. `/scope` ancestor-walks for the marker and offers three install paths: parent install, project `@import`, or skip.
-   **Project-level conventions** live in `templates/CONVENTIONS.md`, copied into each project's `coauthor/` directory at `/scope` time. Edit per project after the file is dropped.
-   **User-global rules** live in `~/.claude/CLAUDE.md` (loaded by Claude Code memory) and layer above plugin rules.

Common edit targets: the banned-patterns list and response-style caps in the plugin `CLAUDE.md`; the AI-tells regex set in `validators/writer/check.py`; the per-project acronym whitelist in `<cwd>/coauthor/.acronym-ignore`.

### 2. Customizing the standing team

Agent definitions are at `agents/{analyst,coder,writer,researcher,reviewer}.md`. Each has YAML frontmatter (`name`, `description` with triggering examples, `model: inherit`, `color`, `tools`) plus a markdown system-prompt body. Edit the files directly to change tool grants, descriptions, system-prompt content, or general behavior.

Current tool grants:

-   analyst: `Read, Grep, Glob, Bash, Agent`
-   coder: `Read, Edit, Write, Bash, Grep, Glob, Agent`
-   writer: `Read, Edit, Write, Grep, Agent`
-   researcher: `Read, Edit, Write, WebFetch, WebSearch, Agent`
-   reviewer: `Read, Grep, Glob, Bash, Agent`

All agents include `Agent` so workers can spawn ephemeral helpers. There is no hook-based preference-injection mechanism; hooks only handle audit logging.

### 3. Adding validators

Validators live at `validators/<domain>/`, with domains `writer`, `data`, `regression`, `derivation`, `reports`. Project-local validators at `<cwd>/coauthor/validators/` override library validators sharing an `id`, so a project can fork a check without touching the library.

Two flavors are supported:

-   **Markdown spec validators**: frontmatter (`id`, `domain`, `version`, `applies_to`) plus body sections Checks / How to run / Pass criteria / Fail output / Applicable contexts. The worker reads the spec and runs the checks manually.
-   **Python `check.py` validators**: stdlib-only scripts, exit 0 on pass and 1 on fail, supporting `--format=text|json`. Examples in `validators/writer/check.py` and `validators/reports/check.py`.

Attachment happens at `/plan`: the orchestrator attaches validators by deliverable type onto each slice. The `reports/quarto-style` validator auto-attaches to any slice whose deliverable is a `.qmd` rendering to HTML. Workers run validators inside their loop before declaring a slice complete.

Promotion runs at `/finalize`: the command enumerates `<cwd>/coauthor/validators/`, generates a promote-or-skip recommendation per validator, batches a single multi-select `AskUserQuestion`, appends the decisions to `~/.claude/coauthor/promotion-log.md`, and copies promoted validators to `validators/<domain>/` with a bumped version and a provenance note.

A per-project tunable: `<cwd>/coauthor/.acronym-ignore` whitelists acronyms for the writer validator.

## Files

-   `.claude-plugin/plugin.json`: manifest.
-   `commands/{scope,plan,work,review,finalize,rename}.md`: slash commands; thin entry points that load the workflow skill.
-   `CLAUDE.md` (plugin root): canonical operating-rules file. First line is the marker `<!-- coauthor-canonical-rules v1 -->`. The plugin-root copy stays in place; `/scope` may also copy it to a parent directory of cwd or wire it in via `@import` from the project file.
-   `skills/coauthor-workflow/SKILL.md`: procedural guide for the orchestrator.
-   `skills/coauthor-workflow/references/{validator-design,persona-briefs,scope-procedure}.md`: supporting reference content.
-   `skills/quarto-html-report/`: bundled skill defining the canonical `.qmd`-to-HTML report style enforced by the `reports/quarto-style` validator.
-   `agents/{analyst,coder,writer,researcher,reviewer}.md`: pre-defined worker agents.
-   `templates/{SCOPE,PLAN,IMPL,REVIEW,CONVENTIONS,INDEX,PROJECT-CLAUDE}.md`: document templates. `PROJECT-CLAUDE.md` is copied to `<cwd>/.claude/CLAUDE.md` at `/scope` time.
-   `validators/`: promotable validator library.
-   `hooks/{audit_user,audit_dispatch,audit_response,compile_audit,audit_common}.py`: audit-log hooks (with a shared `audit_common.py` helper) and the transcript compiler.