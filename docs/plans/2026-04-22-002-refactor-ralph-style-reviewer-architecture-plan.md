---
title: "refactor: Ralph-style reviewer architecture for CASM-tools"
type: refactor
status: active
date: 2026-04-22
origin: docs/brainstorms/2026-04-22-ralph-style-reviewer-architecture-requirements.md
---

# refactor: Ralph-style reviewer architecture for CASM-tools

## Overview

Replace the current subagent-dispatched reviewer cascade with a Ralph-style Python test harness. Each reviewer becomes a standalone `plugins/CASM-tools/tests/<reviewer>.py` that spawns `claude -p --output-format json --json-schema <schema>` as a subprocess and writes a structured JSON report. A `scripts/run-tests.py` runner dispatches tests in parallel, aggregates into `<logs_dir>/test-results/summary.json`, and a `scripts/render-results.py` produces a markdown table for the user. The iteration loop moves from the dedicated subagent orchestrator into the `/CASM-tools:review-document` skill body itself: the main Claude session is the writer, shelling out to `scripts/run-tests.py` and `scripts/author-plan.py` each iteration, reading the plan, and editing the document in place. All reviewer and creator agent `.md` files are retired; their prompts migrate into tests or skill bodies. The PreToolUse preference-injection hook is retired with them.

## Problem Frame

Reviewers in `/CASM-tools:review-document` are currently Claude Code subagents (`plugins/CASM-tools/agents/*-reviewer.md`) dispatched by the main session and orchestrated by `scripts/loop-engine.md` + `scripts/orchestrate-review.md`. Their outputs are markdown scorecards parsed with regex heuristics; severity and pass/fail are reconstructed post-hoc. Three practical costs follow.

First, parse validation is fragile and silently drops items when the scorecard drifts from the expected shape. Second, reviewers cannot run in isolation outside a live Claude Code session, so debugging a single reviewer requires standing up the full cascade and all its state. Third, per-reviewer cost and latency are invisible because subagent dispatch bundles into the parent session's metering.

The Ralph pattern in `chenandrewy/ralph-wiggum-asset-pricing` (branch `ralph/run-final`) solves all three cleanly: each reviewer is a standalone `.py` file that shells out to `claude -p` with `--output-format json --json-schema` and writes a structured report to a predictable path. The loop runs as a script (or, in our case, as the main session executing a small skill body). Porting CASM-tools to that shape yields machine-parseable scorecards, subprocess-isolated reviewers, and per-reviewer cost attribution.

(See origin: `docs/brainstorms/2026-04-22-ralph-style-reviewer-architecture-requirements.md`.)

## Requirements Trace

Summarized from the origin document, renumbered for plan continuity (full wording lives in the origin):

- **R1.** Reviewers as Python test scripts under `plugins/CASM-tools/tests/`, each invokable in isolation.
- **R2.** Structured JSON output per test with shared envelope `{verdict, score, reason, gating, payload}`; per-reviewer `payload` schema.
- **R3.** Aggregate `test-results/summary.json` with consistent shape and `gating_verdict`.
- **R4.** Main Claude session owns the iteration loop and is the writer. Shells out to `run-tests.py` and `author-plan.py`; reads the plan; edits the live document.
- **R5.** Parallel dispatch with per-reviewer subprocess isolation.
- **R6.** Advisory reviewers survive via per-test `gating: bool`; convergence gates on `gating_verdict == PASS`.
- **R7.** Human-readable renderer (`scripts/render-results.py`) writes a markdown table; not read by any agent.
- **R8.** Creator agents (`paper-summarizer`, `extension-proposer`, `presentation-builder`, `fixer`) deleted; prompts inlined into corresponding skill bodies.
- **R9.** Reviewer agents deleted; replaced by `tests/<reviewer>.py`.
- **R10.** Closed argument grammar of `/CASM-tools:review-document` preserved; skill translates it into CLI flags for `run-tests.py`.
- **R11.** `scripts/orchestrate-review.md` and `scripts/loop-engine.md` replaced by a single concise `scripts/review-loop.md`.
- **R12.** Iteration state layout flat and Ralph-style: `<logs_dir>/test-results/` live, rotated into `<logs_dir>/history/iter-NNN/` between iterations.
- **R13.** Paper-* skills' invocation of `/CASM-tools:review-document` unchanged at the call site.
- **R14.** Preference content still reaches each reviewer and creator — but via explicit in-script/in-skill reads rather than the hook, since the hook's `Agent`-tool matcher has nothing to fire on.

Derived from flow analysis (see §"Open Questions Resolved During Planning" and §"Risks"):

- **R15.** Per-test subprocess retry-with-backoff on retriable failures (rate limit, transient network); distinguish infrastructure failure (exit 2) from reviewer-declared FAIL (exit 1).
- **R16.** Directory rotation between iterations is atomic (`os.rename` of whole directory); never file-by-file.
- **R17.** Concurrent-invocation protection is explicitly dropped. The user workflow is single-person and interactive; a second invocation on the same artifact is user error, observable in `git diff` and in the resulting scrambled `<logs_dir>/`. Recovery is `git checkout <doc>` + delete `<logs_dir>` + rerun. (This is a deliberate simplification from the origin; the origin assumed `flock`-level protection but `flock` cannot span the main session's Bash-tool boundaries, and the marker-file alternative costs more than the risk it addresses.)
- **R18.** Baseline snapshot written once at cascade start (`<logs_dir>/baseline.md`); no monotonic versioning (git is the audit trail).
- **R19.** `REVIEW_SUSPENDED.md` resume semantics carry over with a new schema; old-schema suspend files are rejected with "delete and restart".

## Scope Boundaries

- Only the reviewer/fixer/creator plumbing changes; user-visible skill contracts (grammar, outputs, checkpoints, paths at the call site) are unchanged.
- Ralph's `ralph-garage/` history, `check-claude-budget.py`, `commit-iteration.py`, and continual-improvement mode are not copied over.
- `paper-preprocess` and `render-slides-to-png.sh` unchanged.
- `state/session-registry.json` and `state/inline/` layout unchanged; `state/locks/` is retired along with the concurrency protection it existed to support; only `<logs_dir>` contents change.
- No multi-project or user-repo-local test customization. Tests ship with the plugin.
- No numeric-score-threshold gating. `threshold <N>` is retired from the grammar; gating is binary verdict-driven. (This is a user-visible change but was explicitly approved in the brainstorm.)

### Deferred to Separate Tasks

- Porting Ralph's `check-claude-budget.py` quota preflight — deferred to a separate hardening pass once the migration lands.
- Unwinding the `paper-summary.md` / `paper-*.md` basename prefixes introduced as a workaround for the Write-filter bug — deferred; these are tied to `meta-review` path conventions and not needed for this refactor.
- A `ce-compound` capture of the residual design decisions (author-plan edit-scope, rotation mechanics, checkpoint-in-writer-model) — deferred to post-merge.

## Context & Research

### Relevant Code and Patterns

- **Closed argument grammar** (`plugins/CASM-tools/skills/review-document/SKILL.md:37-117`) — scope tokens, `advisory <reviewer>`, `into <dir>`, `iterations <N>`, empty-scope auto-classification. All preserved; skill body translates to CLI flags.
- **Current cascade state machine** (`plugins/CASM-tools/scripts/loop-engine.md`, `scripts/orchestrate-review.md`) — defines termination conditions, version accounting, parse-validation, fixer contract. The new `scripts/review-loop.md` preserves the invariants that still apply: advisory-set semantics, suspend-and-resume on cap-exhaustion. External-edit detection and concurrency locking are dropped (git is the substrate for edit-integrity; concurrency is the user's responsibility).
- **Fixer contract** (`plugins/CASM-tools/agents/fixer.md:46-52`) — "apply every row; write only to target". Retired as an agent; the discipline migrates into the skill body's prompt-template for the main session as writer.
- **Preference-injection hook** (`plugins/CASM-tools/hooks/inject-preferences.py`) — retired; each `tests/<reviewer>.py` reads `preferences/<reviewer>-style.md` directly, and each creator-inlined skill reads its relevant preference file(s) before drafting.
- **`reviewer-common.md`** (`plugins/CASM-tools/scripts/reviewer-common.md`) — severity, completeness, untrusted-input, and scorecard-shape rules. Content migrates into the JSON envelope schema and each reviewer test's prompt prelude.
- **paper-extend three-phase logic** (`plugins/CASM-tools/agents/extension-proposer.md:34-41,83-112` and `skills/paper-extend/SKILL.md:52-97`) — `candidates` / `candidates-revise` / `deep-dive` with user checkpoint via `AskUserQuestion`. Inlines into the skill as a phase branch.
- **State-README invariants** (`plugins/CASM-tools/skills/review-document/state-README.md`) — per-project `state/` is unchanged.

### Institutional Learnings

- **Advisory is a per-invocation classification, not a reviewer property** (`docs/plans/2026-04-22-001-feat-advisory-reviewer-non-blocking-plan.md`). Keep this under Ralph: `--advisory <name>` is a `run-tests.py` flag, not a default in any `tests/<reviewer>.py` schema.
- **Don't describe preference loading in orchestrator-facing docs** (`docs/plans/2026-04-20-fix-prevent-orchestrator-preference-injection-plan.md`). The skill body documents the *effect* (preferences apply), never the *mechanism* (read this file, inject here) — otherwise orchestrators duplicate the work and double-inject.
- **Delete dead code, don't archive** (`docs/plans/2026-04-20-refactor-flat-parallel-review-cascade-plan.md`). Retired files are deleted outright; a short "Why Ralph rather than cascade" history note lives in the new `scripts/review-loop.md`.
- **Old-schema suspend files are unrecoverable** (same source). Write an explicit "delete and restart" guard when a `REVIEW_SUSPENDED.md` lacks the new schema's required fields.

### External References

- `chenandrewy/ralph-wiggum-asset-pricing`, branch `ralph/run-final` — pattern source:
  - `tests/_test_helpers.py`, `tests/writing-intro.py` (test shape, verdict parsing)
  - `ralph/run-tests.py` (parallel dispatch + `summary.json`)
  - `ralph/author-plan.py`, `ralph/author-improve.py` (plan + apply subprocess pattern)
  - `ralph/ralph-loop.sh` (bash-driven orchestration — we adapt the loop into the skill body instead)
- Claude Code headless structured output: `claude -p --output-format json --json-schema '<schema>'`; result in `.structured_output`. Bare mode (`--bare`) and `--append-system-prompt-file` are useful for subprocess isolation. (From `https://code.claude.com/docs/en/headless`.)

## Key Technical Decisions

- **Main session edits the live document directly; no versioned snapshots.** A single immutable `<logs_dir>/baseline.md` is captured once at cascade start. The live file is edited in place each iteration; git is the audit trail and the recovery mechanism. Rationale: the brainstorm's "main session is writer" decision eliminates the fixer's isolated-target model; keeping versioned snapshots while allowing the main session to edit live is contradictory. Downside accepted: the "cp `<logs_dir>/<artifact>-v3.md` `<artifact>`" rollback pattern goes away.
- **Author-plan is an LLM subprocess, not a deterministic merge.** The user explicitly requested this pattern. Mitigation for hallucination / paraphrase risk: the plan must cite test names and severity labels verbatim; the main session has `summary.json` + per-test JSONs available when applying the plan and can cross-check against raw findings if the plan looks thin.
- **Writer discipline: "apply the plan as written; do not invent changes outside it; cite the plan row per edit".** The skill body includes this as a directive the main session follows when acting as writer. Enforcement is explicit and layered rather than guaranteed: (a) `author-plan.py`'s output is structured (each plan row carries `test_name` + `finding_index` + `proposed_edit` fields); (b) the main session's post-edit step writes a short `<logs_dir>/history/iter-NNN/applied-edits.md` noting which plan rows it applied and which it skipped with reasons; (c) `git diff baseline.md -- <doc>` gives the ground-truth diff for the whole cascade. This is weaker than the old fixer's subprocess-isolated write-only-to-target contract; the plan accepts the trade-off because R4 (main session is writer) is load-bearing for the Ralph architecture. Users who need the strict-containment guarantee should roll back to the pre-refactor cascade via git.
- **Envelope is shared; `payload` is per-reviewer.** One JSON schema fragment lives in `tests/_helpers.py`; each `tests/<reviewer>.py` extends it with its own `payload` schema as a Python dict literal. No sibling `schemas/` directory; self-contained tests.
- **Gating is binary, verdict-driven. Score is informational.** Convergence check: `summary.json.gating_verdict == "PASS"` iff every test with `gating: true` has `verdict == "PASS"`. Score is used by `author-plan.py` to prioritize findings and by `render-results.py` to show progress across iterations.
- **All-advisory edge case: vacuous PASS.** If every selected test is advisory (`gating_tests == 0`), `gating_verdict == "PASS"` immediately; the loop exits after one iteration with a warning in the terminal report. Matches current cascade behavior (`loop-engine.md:92`).
- **Retry policy at the subprocess boundary (minimal).** `claude -p` invocations retry at most once, only on JSON schema-validation failure (well-formed JSON that doesn't match the envelope or payload schema). HTTP-level retries, exponential backoff, and per-cascade call-count caps are deliberately deferred to the post-MVP hardening pass alongside `check-claude-budget.py`. Rationale: the failure cost is bounded — a test that exhausts its retry writes an infrastructure-failure envelope (exit 2) and the loop continues on the remaining tests. Surviving subprocess failures robustly is a future optimization, not a prerequisite for correctness.
- **Exit code semantics.** `0` = PASS verdict, `1` = FAIL verdict (normal reviewer finding), `2` = infrastructure failure (parse error, subprocess crash, schema validation). `run-tests.py` treats exit 2 as failed-to-parse but still aggregates the file into `summary.json` with `gating: false` forced so the loop can still terminate on a PASS-by-vacuity path if all real failures are advisory.
- **Rotation is atomic `os.rename` of the directory, performed BEFORE edits.** At end of iteration N's planning phase (after `author-plan.py` has written `current-plan.md` but before the main session applies edits), the skill body executes one `os.rename(test-results/, history/iter-NNN/)`, copies `current-plan.md` into that dir as `plan.md`, writes a `.iteration-complete` sentinel, then creates a fresh `test-results/`. The sentinel explicitly marks "this iteration's measurements + plan are archived" so resume after a crash can tell whether the crash happened before or after rotation. The rotation itself is atomic (single `rename` syscall on same filesystem); the sentinel guards a narrower case: distinguishing a completed iteration's record from one that was rotated but never acted on (useful for the between-rotation-and-edits crash path — see §"High-Level Technical Design" note).
- **No concurrency protection.** Single-user, interactive workflow; the user is expected not to invoke the skill twice concurrently on the same artifact. A second concurrent invocation produces observable damage (scrambled edits visible in `git diff`; interleaved `history/iter-*/plan.md` files in `<logs_dir>`). Recovery is `git checkout <doc>` + `rm -rf <logs_dir>` + rerun. No lockfile, no marker file, no heartbeat; the complexity cost exceeded the protection benefit for the actual usage pattern.
- **`REVIEW_SUSPENDED.md` schema.** YAML frontmatter: `schema_version: 2`, `suspended_at`, `last_iteration`, `failed_gating_tests: [...]`, `cascade_args` (original grammar string). On resume, if `schema_version != 2` → reject with "old schema; delete `<logs_dir>` and restart". If present and current, continue from `last_iteration + 1` with the same `cascade_args`.
- **Hook retirement is total, not partial.** Both the `PreToolUse`/`Agent` block in `plugin.json` and `hooks/inject-preferences.py` are deleted. The `PostToolUse`/`Write|Edit` hook (`hooks/verify-reminder.py`) is unchanged.
- **`threshold <N>` grammar token is retired.** The brainstorm explicitly retires score-threshold gating. The skill body parses it for back-compat, logs a one-line deprecation notice, and ignores it.
- **`thorough` token still runs tests in a post-convergence audit.** After `gating_verdict == PASS`, if `thorough` was passed, `run-tests.py` runs once more with `--thorough` writing to `<logs_dir>/thorough/`. Findings are informational; no further iteration.

## Open Questions

### Resolved During Planning

- **Per-reviewer payload schemas.** Co-located with each `tests/<reviewer>.py` as a Python dict literal; envelope schema in `tests/_helpers.py`. Structural rules fixed at planning time: `anyOf {findings: minItems 1} OR {commendations: minItems 1}` to prevent constrained-decoding from emitting valid-but-empty payloads. Field names within `findings` vary per reviewer (see the `writing` example in §"High-Level Technical Design").
- **`claude -p --allowedTools` default per test.** Default: `Read,Grep,Glob` (read-only document inspection). Exceptions: `code.py` uses `Read,Grep,Glob,Bash(pytest:*),Bash(ruff:*),Bash(mypy:*),Bash(python -c:*),Bash(python -m pytest:*),Bash(quarto render:*),Bash(quarto check:*)`; `simplicity.py` uses `Read,Grep,Glob,Bash(ruff:*),Bash(vulture:*),Bash(python -c:*)`. These are carried over from the retired agent frontmatter.
- **Migration sequencing.** Single PR, seven implementation units phased into three groups: new harness (U1–U2) → skill integration (U3–U6) → cleanup (U7). Running two review systems in parallel was rejected as doubling maintenance cost; the current system is retired in full within the PR.
- **Iteration cap configuration.** `iterations <N>` grammar token (`[1, 10]`, default 3). Skill translates to `--max-iter N` on `run-tests.py`. Cap is enforced in the skill body, not `run-tests.py` — the former drives the loop.
- **Test-results history rotation.** Atomic `os.rename` of the directory, at iteration-end, with `.iteration-complete` sentinel. Lives in the skill body (the skill drives the loop).
- **paper-extend checkpoint integration.** The three drafting phases (`candidates`, `candidates-revise`, `deep-dive`) move into a new lightweight subprocess `scripts/draft-candidates.py --phase <name>` — structurally analogous to `author-plan.py` — rather than inlining the drafting work into the main session. This preserves the clean-context-per-draft property the old subagent dispatch had, avoids unbounded context accumulation in the main session across an uncapped revise loop, and matches the Ralph pattern of one subprocess per drafting stage. The skill body still owns the checkpoint (`AskUserQuestion`), the user-interaction flow, and the phase-switching decision. After `deep-dive` writes `paper-extension/extensions.md`, the test harness runs against that file. Supplementary-paper request cycle is handled by a second `AskUserQuestion` inside the deep-dive branch that pauses the skill for user input between subprocess calls. Revise loop remains uncapped but each round is a fresh subprocess.
- **Preference file handling for the main session as writer.** Each creator-inlined skill (`paper-summarize`, `paper-extend`, `paper-present`) reads the relevant `preferences/*-style.md` files and includes their content in the main session's working context before drafting v0.
- **Suspended-cascade resume.** See `REVIEW_SUSPENDED.md` schema decision above. Skill reads the file on cascade start; acts accordingly.
- **CLI flag ambiguity between `logs_dir` and per-iteration results dir.** `<logs_dir>` is the user-facing destination (passed via `into <dir>`). `<logs_dir>/test-results/` is the current iteration's live directory, managed by the skill. `run-tests.py` takes `--logs-dir <path>` and operates on `<path>/test-results/` internally; no separate flag for the iteration dir.

### Deferred to Implementation

- **Exact JSON Schema strings for each reviewer's non-`writing` payload.** The `writing` example is concrete in §"High-Level Technical Design"; other reviewers' field names and enum values are determined at port time from the content of the corresponding agent `.md`. The structural rules (`anyOf` on `findings` / `commendations`, `minItems: 1`, envelope shape) are fixed planning-time.
- **`claude -p` invocation: `--bare` vs default.** Likely `--bare` for reproducibility, but the implementer verifies with one reviewer before committing to it across all nine.
- **Rich-text vs plain markdown in `summary-table.md`.** Plan specifies markdown; whether to include sparklines / score bars is a polish decision deferred.
- **Author-plan's prompt exact text.** Directional template in §"High-Level Technical Design"; the implementer tunes it during U1.
- **How the skill body renders the grammar parser.** Current parser is documented prose; implementer reuses or condenses it.

## Output Structure

New directories and files introduced by this plan (existing unchanged files not shown):

```
plugins/CASM-tools/
├── tests/                            # NEW
│   ├── _helpers.py                   # shared envelope, preference loader, claude -p wrapper
│   ├── writing.py                    # one file per reviewer
│   ├── structure.py
│   ├── math.py
│   ├── simplicity.py
│   ├── adversarial.py
│   ├── factual.py
│   ├── consistency.py
│   ├── code.py
│   └── presentation.py
├── scripts/
│   ├── run-tests.py                  # NEW — parallel dispatcher + summary.json
│   ├── render-results.py             # NEW — markdown table renderer
│   ├── author-plan.py                # NEW — reads summary.json, writes improvement plan
│   ├── review-loop.md                # NEW — concise state-machine description
│   ├── orchestrate-review.md         # DELETED
│   ├── loop-engine.md                # DELETED
│   ├── reviewer-common.md            # DELETED (content migrates to envelope schema + per-test prelude)
│   ├── session-log-template.md       # MODIFIED (layout references)
│   └── render-slides-to-png.sh       # unchanged
├── agents/                           # ENTIRE DIRECTORY REMOVED except what other skills import
│   └── (all 9 reviewers, 3 creators, fixer.md deleted)
├── hooks/
│   ├── inject-preferences.py         # DELETED
│   └── verify-reminder.py            # unchanged
├── preferences/                      # unchanged — read directly by tests and creator-inlined skills
├── skills/
│   ├── review-document/SKILL.md      # REWRITTEN — main-session loop
│   ├── review-document/state-README.md  # MODIFIED — <logs_dir> layout section
│   ├── paper-summarize/SKILL.md      # MODIFIED — creator prompt inlined
│   ├── paper-extend/SKILL.md         # MODIFIED — creator prompt + 3-phase checkpoint inlined
│   ├── paper-present/SKILL.md        # MODIFIED — creator prompt inlined
│   ├── paper-full-pipeline/SKILL.md  # MODIFIED — prose touch-up
│   ├── meta-review/SKILL.md          # MODIFIED — reads test-results/*.json instead of scorecards
│   └── paper-preprocess/SKILL.md     # unchanged
└── .claude-plugin/plugin.json        # MODIFIED — PreToolUse/Agent block removed

<logs_dir>/                           # per-cascade output; structure created by the skill
├── baseline.md                       # one-time snapshot of live doc at cascade start
├── current-plan.md                   # current iteration's author-plan output
├── test-results/                     # current iteration's live results
│   ├── writing.json
│   ├── structure.json
│   ├── ... (one per gated + advisory test)
│   ├── summary.json
│   └── summary-table.md
├── thorough/                         # populated only if `thorough` token passed
│   ├── writing.json
│   └── ... summary.json, summary-table.md
├── history/
│   ├── iter-001/
│   │   ├── plan.md                   # copy of that iteration's current-plan.md
│   │   ├── writing.json
│   │   ├── ... summary.json, summary-table.md
│   │   └── .iteration-complete       # sentinel; rotation succeeded
│   └── iter-002/
├── REVIEW_SUSPENDED.md               # written only on cap-exhaustion with gating FAIL
└── final-summary.md                  # written at clean convergence (last summary-table plus session stats)
```

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

### JSON envelope and payload schemas

Shared envelope (directional Python dict, refined into a JSON Schema string by the implementer):

```python
# tests/_helpers.py
ENVELOPE_SCHEMA = {
    "type": "object",
    "required": ["verdict", "score", "reason", "gating", "payload"],
    "properties": {
        "verdict": {"enum": ["PASS", "FAIL"]},
        "score":   {"type": "integer", "minimum": 0, "maximum": 100},
        "reason":  {"type": "string", "maxLength": 400},
        "gating":  {"type": "boolean"},
        "payload": {"type": "object"},   # per-reviewer
    },
}
```

Per-reviewer `payload` shape — representative example (`writing`):

```python
# tests/writing.py
PAYLOAD_SCHEMA = {
    "type": "object",
    "required": ["findings", "commendations"],
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["severity", "quote", "problem", "suggested_fix"],
                "properties": {
                    "severity": {"enum": ["CRITICAL", "MAJOR", "MINOR", "NIT"]},
                    "quote":    {"type": "string", "minLength": 1},
                    "problem":  {"type": "string", "minLength": 1},
                    "suggested_fix": {"type": "string", "minLength": 1},
                    "location": {"type": "string"},  # optional, free-form location hint
                },
            },
        },
        "commendations": {"type": "array", "items": {"type": "string"}},
    },
    # Content enforcement: at least one finding OR at least one commendation.
    # Prevents constrained-decoding from emitting empty-array valid-but-unhelpful payloads.
    "anyOf": [
        {"properties": {"findings":      {"minItems": 1}}, "required": ["findings"]},
        {"properties": {"commendations": {"minItems": 1}}, "required": ["commendations"]},
    ],
}
```

Each other reviewer owns its own payload schema, derived at port time from the content of the corresponding `agents/<reviewer>.md` (before deletion). Structural rules common to every schema: a `findings`-style array plus a `commendations`-style array, with the same `anyOf minItems: 1` content-enforcement rule. Field names within `findings` may vary by reviewer (`section` for structure, `slide_index` for presentation, etc.); see the reviewer's agent prompt for what makes sense.

`summary.json` aggregate:

```json
{
  "schema_version": 1,
  "generated_at":   "2026-04-22T19:34:37Z",
  "document":       "paper-extension/paper-summary.md",
  "iteration":      2,
  "tests": [
    {"name": "writing",      "verdict": "PASS", "score": 91, "reason": "...", "gating": true,  "runtime_s": 47.2, "exit_code": 0},
    {"name": "adversarial",  "verdict": "FAIL", "score": 54, "reason": "...", "gating": false, "runtime_s": 63.8, "exit_code": 1}
  ],
  "pass_rate":       0.89,
  "gating_verdict":  "PASS"
}
```

### Grammar → CLI flag mapping

| Skill grammar clause           | `run-tests.py` flag                         | Notes                                                   |
|--------------------------------|---------------------------------------------|---------------------------------------------------------|
| `<scope tokens...>`            | `--tests <resolved,comma,list>`             | Skill resolves before calling (see resolution order below) |
| `advisory <reviewer>` (repeatable) | `--advisory <name>` (repeatable)        | Validated against final resolved test list in the skill |
| `into <dir>`                   | `--logs-dir <dir>`                          | Default computed by the skill per artifact. Flag name is `--logs-dir` (deliberate rename from the origin's `--results-dir`; results dir at `<logs_dir>/test-results/` is identical from the user's perspective) |
| `iterations <N>`               | `--max-iter <N>` (default 3, range [1, 10]) | Enforced in skill body                                  |
| `thorough`                     | (skill-level; triggers post-convergence run with `--thorough`) | `--thorough` runs with the SAME resolved `--tests` scope as the main cascade used (matches current cascade's "all originally-dispatched reviewers" semantics when the user passed `all`; narrower scopes keep narrower thorough coverage) |
| `threshold <N>`                | *(retired; ignored with deprecation note)*  |                                                         |

**Resolution order (skill performs before calling `run-tests.py`):**
1. Strip filler words from the argument string.
2. If scope is empty → auto-classify from the artifact extension (per the current skill's extension table). `factual` is NEVER auto-selected.
3. `all` expands to all 9 reviewers including `factual`.
4. Apply `advisory <name>` validation against the resolved list; error if the name isn't in it.
5. Pass the explicit resolved list as `--tests a,b,c,...`. `run-tests.py` never does scope resolution itself.

### Per-iteration flow (skill body pseudocode)

`history/iter-NNN/` records the tests that motivated iter-NNN's plan — i.e., measurements taken at the START of iter-NNN against the state at the END of iter-(N-1). The cascade rotates the current `test-results/` into `history/iter-NNN/` BEFORE applying edits, so a reader opening `history/iter-NNN/` sees "what iter-NNN's reviewers flagged" without ambiguity about which document state they reviewed.

```text
# /CASM-tools:review-document <args>
1.  parse args; skill resolves scope → (paths, test_list, advisory_set, max_iter, logs_dir, thorough)
2.  if <logs_dir>/REVIEW_SUSPENDED.md exists:
        validate schema_version == 2; else error "delete <logs_dir> and restart"
        iter = last_iteration + 1
        remove REVIEW_SUSPENDED.md
    else:
        iter = 1
        write <logs_dir>/baseline.md  (one-time; skip if exists from a prior resume)

3.  loop:
       a. run:  python scripts/run-tests.py <doc> \
                   --tests <test_list> --advisory <set> --logs-dir <logs_dir>
          (writes <logs_dir>/test-results/*.json + summary.json)
       b. run:  python scripts/render-results.py <logs_dir>/test-results
          (writes <logs_dir>/test-results/summary-table.md; print to stdout)
       c. if summary.json.gating_verdict == "PASS":   break
       d. if iter == max_iter:
              write REVIEW_SUSPENDED.md (schema v2, failed gating test list)
              report suspension to user; exit with suspend
       e. run:  python scripts/author-plan.py <doc> <logs_dir>
          (writes <logs_dir>/current-plan.md)
       f. rotate FIRST, THEN edit:
             atomic os.rename(<logs_dir>/test-results, <logs_dir>/history/iter-{iter:03})
             copy current-plan.md into that dir as plan.md
             write sentinel history/iter-{iter:03}/.iteration-complete
             mkdir fresh <logs_dir>/test-results/
       g. main session reads <logs_dir>/current-plan.md
          reads <logs_dir>/history/iter-{iter:03}/summary.json + any <name>.json for failing gating tests
          edits <doc> in place, citing plan rows per edit
          (directive: do not invent changes outside the plan)
       h. iter += 1
4.  if thorough:
        run:  python scripts/run-tests.py <doc> --tests <test_list> \
                   --advisory <set> --logs-dir <logs_dir> --thorough
5.  write <logs_dir>/final-summary.md (copy of last summary-table.md + session stats)
6.  report final status
```

**Note on the rotate-then-edit order.** Rotating before edits means the iteration's history record is archived from a stable state. If the session is Ctrl-C'd between rotation (3f) and edits (3g), the next invocation sees `history/iter-NNN/.iteration-complete` present, no current `test-results/`, and a possibly-partially-edited live doc. Resume detects this by: most recent `history/iter-N/` has sentinel, no current `test-results/` populated. Recovery is "main session applies the `history/iter-N/plan.md` (re-reading and editing where not yet applied, no-op where already applied) and proceeds." This is a deliberately idempotent recovery; git is the ground truth for "what was already applied."

### `tests/<reviewer>.py` shape

```python
# tests/writing.py  (directional sketch)
from _helpers import (
    parse_cli,                  # -> (doc_path, logs_dir, gating, advisory_flag)
    load_preferences,           # reads preferences/writing-style.md
    run_claude_subprocess,      # claude -p with retry-with-backoff
    write_report,               # validates against ENVELOPE_SCHEMA; writes <logs_dir>/test-results/writing.json
    ENVELOPE_SCHEMA,
)

PAYLOAD_SCHEMA = {
    "type": "object",
    "required": ["findings"],
    "properties": {"findings": {"type": "array", "items": {
        "type": "object",
        "required": ["severity", "quote", "problem", "suggested_fix"],
        "properties": {
            "severity": {"enum": ["CRITICAL", "MAJOR", "MINOR", "NIT"]},
            # ... etc
        }}}},
}

PROMPT_TEMPLATE = """
You are a writing reviewer. You never edit the artifact; you only score it.

Preferences (calibration surface):
{preferences}

Artifact: {doc_path}

[reviewer-specific instructions, ported from agents/writing-reviewer.md]

Return JSON matching the schema. Include at least one finding or at least one commendation.
"""

def main():
    args = parse_cli()
    prefs = load_preferences("writing-style.md")
    prompt = PROMPT_TEMPLATE.format(preferences=prefs, doc_path=args.doc_path)
    schema = {**ENVELOPE_SCHEMA, "properties": {**ENVELOPE_SCHEMA["properties"], "payload": PAYLOAD_SCHEMA}}
    result = run_claude_subprocess(prompt, schema)  # retries, infra-error handling
    write_report(args.logs_dir, "writing", result, gating=not args.advisory_flag)

if __name__ == "__main__":
    raise SystemExit(main())
```

### `scripts/author-plan.py` shape

```text
Prompt (directional):
  Read <logs_dir>/test-results/summary.json and every <name>.json it references.
  For each failing gating test, list its findings verbatim (severity, quote, suggested_fix).
  For each failing advisory test, list top-3 findings by severity.
  Propose a concrete, severity-ordered set of edits to <doc> that would resolve
  the failing-gating findings. Cite each plan row by test_name + finding index.
  Do NOT paraphrase findings. Do NOT invent edits unrelated to a listed finding.
  Write plan to <logs_dir>/current-plan.md.
```

## Implementation Units

### Phase 1 — New harness

- [ ] **Unit 1: Python harness scaffolding**

**Goal:** Land the shared harness code — envelope schema, preference loader, `claude -p` subprocess wrapper with retry-with-backoff, test dispatcher, renderer, author-plan, and the replacement `scripts/review-loop.md`. No reviewers yet; the harness is unwired.

**Requirements:** R1, R2, R3, R5, R7, R11, R15 (groundwork for the retry-on-schema-validation-failure path).

**Dependencies:** None.

**Files:**
- Create: `plugins/CASM-tools/tests/_helpers.py`
- Create: `plugins/CASM-tools/scripts/run-tests.py`
- Create: `plugins/CASM-tools/scripts/render-results.py`
- Create: `plugins/CASM-tools/scripts/author-plan.py`
- Create: `plugins/CASM-tools/scripts/review-loop.md` (includes the two-paragraph "Why Ralph rather than cascade" history note as a brief one-sentence pointer to this plan, NOT a full section)
- Test: (none — harness code has no behavior until wired; U2's first reviewer validates it end-to-end)

**Approach:**
- `_helpers.py` exports `parse_cli`, `load_preferences`, `run_claude_subprocess` (with retry), `write_report` (validates against `ENVELOPE_SCHEMA`), and the envelope schema constant. Pure stdlib; PEP 723 header declares `requires-python = ">=3.11"` and no external deps. Uses `asyncio` for any parallelism inside the harness.
- `run-tests.py` discovers tests from `plugins/CASM-tools/tests/` (ignores files starting with `_`). Filters by `--tests` (comma-separated). Runs them in parallel via `concurrent.futures.ProcessPoolExecutor` or `asyncio.gather(create_subprocess_exec)`. Writes `<logs_dir>/test-results/<name>.json` as each finishes, then aggregates `summary.json` at the end.
- `render-results.py` reads `<logs_dir>/test-results/*.json` + `summary.json` and writes `summary-table.md` (columns: test, verdict, score, gating, reason, runtime). Prints table to stdout.
- `author-plan.py` reads `summary.json` + failing-test JSONs, spawns `claude -p` with the template in §"High-Level Technical Design", writes `<logs_dir>/current-plan.md`.
- `review-loop.md` documents the per-iteration flow (the pseudocode above) in prose, including resume semantics and rotation. Does NOT describe preference-loading mechanism (per institutional learning).

**Patterns to follow:**
- PEP 723 inline metadata (existing pattern in `hooks/*.py`).
- `uv run --script` invocation (existing pattern).
- Closed-grammar CLI flags with explicit enums where possible.

**Test scenarios:**
- Happy path: `python scripts/run-tests.py --help` lists all flags; `python scripts/render-results.py --help` prints usage.
- Edge case: `run-tests.py` on a directory with zero tests writes an empty `summary.json` with `gating_verdict: "PASS"` (vacuous) and logs a warning.
- Error path: `claude` binary not on PATH → `run_claude_subprocess` raises a specific error, test writes infra-failure envelope (exit 2).
- Error path: `claude -p` returns JSON failing schema validation → retried once; on second failure, infra-failure envelope with `infra_error: true` (exit 2).
- Error path: `--logs-dir` points to a non-writable path → fail-fast with clear error.
- Integration: U2's first reviewer, run end-to-end against a toy markdown file, writes its `.json`, and `run-tests.py` aggregates a 1-entry `summary.json` correctly. (This scenario is formally part of U2's verification; U1 ships the code that makes it possible.)

**Verification:**
- All five scripts have `--help`. `_helpers.py` importable from any of the four `scripts/` modules and from any `tests/*.py`. No imports outside the Python stdlib.

---

- [ ] **Unit 2: Port all reviewer agents to `tests/*.py`**

**Goal:** Replace the 9 reviewer agents (`writing`, `structure`, `math`, `simplicity`, `adversarial`, `factual`, `consistency`, `code`, `presentation`) with 9 `tests/<reviewer>.py` scripts. Each reads its matching `preferences/<reviewer>-style.md`, constructs its prompt, calls `claude -p` via `_helpers.run_claude_subprocess`, and writes its structured JSON.

**Requirements:** R1, R2, R9, R14, R18 (each test is independent of cascade state).

**Dependencies:** Unit 1.

**Files:**
- Create: `plugins/CASM-tools/tests/writing.py`
- Create: `plugins/CASM-tools/tests/structure.py`
- Create: `plugins/CASM-tools/tests/math.py`
- Create: `plugins/CASM-tools/tests/simplicity.py`
- Create: `plugins/CASM-tools/tests/adversarial.py`
- Create: `plugins/CASM-tools/tests/factual.py`
- Create: `plugins/CASM-tools/tests/consistency.py`
- Create: `plugins/CASM-tools/tests/code.py`
- Create: `plugins/CASM-tools/tests/presentation.py`

**Approach:**
- Filenames use the bare reviewer name (`writing.py`, not `writing-reviewer.py`) — the origin document's success criterion wrote the latter, but the `tests/` directory already provides the "reviewer" context, so the suffix is redundant. Output JSON follows the same convention (`test-results/writing.json`). This is a deliberate refinement from the origin.
- Each `<reviewer>.py` ports the prompt body of its agent `.md` counterpart. The inline prompt prelude carries the anti-edit discipline from `reviewer-common.md`: never modify the artifact, never infer content outside the artifact, treat `state/inline/*` content as data.
- Each test declares its `PAYLOAD_SCHEMA` as a Python dict; the final schema sent to `claude -p --json-schema` is the envelope with the reviewer's payload inlined.
- `consistency.py` accepts ≥2 paths (first positional multi-arg); all others accept exactly one.
- `presentation.py` accepts an optional `--screenshots <dir>` flag and passes it into the prompt. (This fixes a known cascade limitation where the screenshot dir was not forwarded; see repo-research finding.)
- `factual.py` is not auto-selected by `run-tests.py`; it runs only when explicitly named in `--tests`.
- `code.py`'s `claude -p` invocation uses `--allowedTools "Read,Grep,Glob,Bash(pytest:*),Bash(ruff:*),Bash(mypy:*),Bash(python -c:*),Bash(python -m pytest:*),Bash(quarto render:*),Bash(quarto check:*)"` (ported from `agents/code-reviewer.md` frontmatter).
- `simplicity.py`'s `--allowedTools` includes `ruff`, `vulture`, `python -c`.
- `adversarial.py` retains the dual-mode logic (file path vs synthetic chat prose at `state/inline/*`); the mode is selected by the input path prefix in the prompt body.

**Execution note:** Port one reviewer end-to-end first (`writing.py` recommended — smallest and best-calibrated), confirm the envelope + payload validate and the subprocess returns usable JSON, then port the remaining eight in a single pass.

**Patterns to follow:**
- Each agent `.md` file is the source of truth for the reviewer's prompt body. Migrate the prose as-is where possible; compress only the agent-framework prose ("You are a subagent...") into the script prelude.
- Preferences loaded via `_helpers.load_preferences(<name>-style.md)` and injected into the prompt under a clearly labeled block.

**Test scenarios:**
- Happy path: each test against a small valid markdown artifact produces a `{verdict, score, reason, gating, payload}` JSON that validates against the schema. Exit 0 if `verdict == "PASS"`, exit 1 if `"FAIL"`.
- Edge case: empty document → reviewer produces a FAIL verdict with a specific reason (not crash).
- Edge case: document missing → infra-failure envelope (exit 2), no JSON corruption.
- Error path: malformed JSON from `claude -p` (simulate with a mocked `run_claude_subprocess`) → retry once, then infra-failure envelope on retry exhaustion.
- Error path: `claude -p` returns valid JSON that fails envelope schema (missing `reason`) → retried, then infra-failure.
- Integration: run `python scripts/run-tests.py <doc> --logs-dir /tmp/t --tests writing,math`; `summary.json` has 2 entries; `gating_verdict` reflects both tests' verdicts.
- Integration: run with `--advisory writing`; `writing.json` has `gating: false`; `gating_verdict` is determined by `math` alone.
- Integration: `consistency.py` with 2 paths produces valid output; with 1 path exits with a clear error.

**Verification:**
- All 9 tests runnable standalone: `python plugins/CASM-tools/tests/<name>.py <doc> --logs-dir /tmp/x`. Exit codes follow the convention. `test-results/<name>.json` validates against the envelope + payload schema.

---

### Phase 2 — Skill integration

- [ ] **Unit 3: Rewrite `/CASM-tools:review-document` skill body**

**Goal:** Replace the current SKILL.md body with the main-session-as-writer loop. Parse the existing closed grammar (unchanged), translate to `run-tests.py` flags, drive the iteration loop, handle baseline + rotation + suspend + resume.

**Requirements:** R4, R6, R10, R11, R16, R18, R19; accepts CLI mapping from §"High-Level Technical Design".

**Dependencies:** Units 1 and 2.

**Files:**
- Modify: `plugins/CASM-tools/skills/review-document/SKILL.md` (near-total rewrite of the body; YAML frontmatter and grammar tables preserved)
- Modify: `plugins/CASM-tools/skills/review-document/state-README.md` (update `<logs_dir>` layout section to match new tree; the per-project `state/` section unchanged)
- Delete: `plugins/CASM-tools/scripts/orchestrate-review.md`
- Delete: `plugins/CASM-tools/scripts/loop-engine.md`
- Delete: `plugins/CASM-tools/scripts/reviewer-common.md` (content migrated into test preludes by U2; envelope schema replaces parse validation)

**Approach:**
- Preserve the argument-grammar section of SKILL.md verbatim (filler-word stripping, scope tokens, empty-scope auto-classify, `advisory <reviewer>`, `into <dir>`, `iterations <N>`; document the `threshold <N>` deprecation inline with a one-sentence deprecation note).
- Replace the "Cascade" section with a pointer to `scripts/review-loop.md` and an inline description of the user-facing contract (what outputs land where, when suspension fires, what `thorough` does).
- Skill body does baseline snapshot, drives the loop (pseudocode from §"High-Level Technical Design"), handles resume from `REVIEW_SUSPENDED.md` v2, writes `final-summary.md` on clean convergence.
- The skill body does NOT describe the preference-loading mechanism; it states that reviewer preferences apply and points at `preferences/` as the calibration surface.

**Patterns to follow:**
- Preserve the existing `AGENTS.md`-style section ordering where possible (Argument grammar → Preflight → Cascade → State management → Errors).
- Keep the artifact-basename Write-filter warning visible even though it no longer applies to subprocess Python writes — the warning still matters for any future subagent dispatch the skill might re-introduce.

**Test scenarios:**
- Happy path: `/CASM-tools:review-document writing paper.md` → runs `writing` test once; gating passes; no iteration; reports completion.
- Happy path: `/CASM-tools:review-document all paper.md` on a weak draft → iterates until `gating_verdict == PASS` or cap; each iteration's artifacts land in the correct dir; live doc is edited each iteration.
- Happy path: `/CASM-tools:review-document all advisory adversarial paper.md` → adversarial test runs each iteration but does not block convergence; advisory findings appear in plans.
- Happy path: `/CASM-tools:review-document all into custom/dir paper.md` → artifacts land in `custom/dir/`; default location not used.
- Edge case: `/CASM-tools:review-document threshold 75 writing paper.md` → threshold parsed, deprecation note logged, run proceeds with verdict-driven gating.
- Edge case: empty scope, `.py` artifact → auto-classifies to `code,simplicity`; only those tests run.
- Edge case: all selected tests advisory → `gating_verdict == PASS` vacuously after iteration 1; warning logged.
- Error path: `iterations 11` → errors with "iterations must be an integer between 1 and 10".
- Error path: `advisory nonexistent writing paper.md` → errors with "advisory target 'nonexistent' is not in the selected reviewer list".
- Error path: cap exhaustion with gating FAIL → writes `REVIEW_SUSPENDED.md` v2; exits with suspend; next invocation on same `<logs_dir>` resumes from iter `N+1`.
- Error path: `REVIEW_SUSPENDED.md` v1 (old schema) present → errors with "old schema; delete `<logs_dir>` and restart".
- Integration: rotation between iter 1 and iter 2 — `history/iter-001/` exists with `.iteration-complete` sentinel and `plan.md`; `test-results/` is fresh for iter 2.
- Integration: crash between rotation (4g) and edit-application (4h) → resume detects `history/iter-001/.iteration-complete` present, `test-results/` empty, live doc possibly-partially-edited. Recovery re-applies `history/iter-001/plan.md` (no-op where edits already made) and proceeds.
- Integration: crash during edit-application → same recovery path as above.
- Integration: `thorough` token → after convergence, one extra `--thorough` run writes to `<logs_dir>/thorough/`.

**Verification:**
- `/CASM-tools:review-document <args>` produces identical user-facing behavior (grammar, outputs at `<logs_dir>`, suspend/resume) as before migration except for (a) new dir layout and (b) `summary-table.md` in each iteration's dir. Grammar validators reject all the same bad inputs as before, with the same error messages.

---

- [ ] **Unit 4: Inline paper-summarizer into `/CASM-tools:paper-summarize`**

**Goal:** Remove `agents/paper-summarizer.md`; move its v0-drafting prompt into the skill body; main session does the drafting.

**Requirements:** R8, R13, R14.

**Dependencies:** Unit 3.

**Files:**
- Modify: `plugins/CASM-tools/skills/paper-summarize/SKILL.md`
- Delete: `plugins/CASM-tools/agents/paper-summarizer.md`

**Approach:**
- Step 3 of the current skill ("Initial draft from paper-summarizer") becomes an inline block: the skill reads `preferences/writing-style.md` + `preferences/structure-style.md` into its working context, then follows the prompt body (directly) to draft `paper-extension/paper-summary.md`.
- Step 4 (hand off to `/CASM-tools:review-document`) unchanged.
- Skill body carries the same "Dispatch exactly the task" discipline; do NOT document the preference-read mechanism (per institutional learning — orchestrator-facing docs that describe mechanism get duplicated).

**Patterns to follow:**
- Inline the prompt body compressed to skill-body style. The existing "Dispatch exactly the task" block disappears (no subagent dispatch).
- Preserve the existing session-log format.

**Test scenarios:**
- Happy path: `/CASM-tools:paper-summarize paper.pdf` → main session drafts v0 directly into `paper-extension/paper-summary.md`, then invokes `/CASM-tools:review-document all advisory adversarial paper-extension/paper-summary.md into <dir>` and iterates to convergence.
- Edge case: `paper-extension/paper.md` cache hit → summarizer uses the markdown cache, not the PDF.
- Integration: entire pipeline from PDF → finalized summary produces the same output file at the same path as before.

**Verification:**
- No references to `agents/paper-summarizer.md` remain anywhere in the plugin. `/CASM-tools:paper-summarize` end-to-end produces `paper-extension/paper-summary.md` with the same content quality as before.

---

- [ ] **Unit 5: Inline extension-proposer into `/CASM-tools:paper-extend` with 3-phase checkpoint**

**Goal:** Remove `agents/extension-proposer.md`; port the three-phase (`candidates` / `candidates-revise` / `deep-dive`) checkpoint logic into the skill body. Main session produces candidates, runs the checkpoint, revises if asked, produces the deep-dive, then hands the final file to `/CASM-tools:review-document`.

**Requirements:** R8, R13, R14; preserves candidate-checkpoint behavior from `docs/brainstorms/2026-04-22-paper-extend-candidate-checkpoint-requirements.md`.

**Dependencies:** Unit 3.

**Files:**
- Modify: `plugins/CASM-tools/skills/paper-extend/SKILL.md`
- Create: `plugins/CASM-tools/scripts/draft-candidates.py` (subprocess wrapper analogous to `author-plan.py`; takes `--phase candidates|candidates-revise|deep-dive` + doc inputs; spawns `claude -p` with the phase-appropriate prompt)
- Delete: `plugins/CASM-tools/agents/extension-proposer.md`

**Approach:**
- Skill body owns the checkpoint and user-interaction flow. Each drafting phase shells out to `python plugins/CASM-tools/scripts/draft-candidates.py --phase <name>` rather than drafting inline. This preserves the clean-context-per-draft property the old subagent dispatch had and prevents main-session context bloat across uncapped revise rounds.
- `candidates` and `candidates-revise` phases write `paper-extension/extensions-candidates.md` directly from the subprocess.
- Checkpoint fires via `AskUserQuestion` (accept top / pick N / revise). Revise loop uncapped; each revise round re-enters the subprocess with `--phase candidates-revise`.
- After user accepts a candidate, skill invokes `--phase deep-dive` which writes `paper-extension/extensions.md`. If the deep-dive subprocess signals a supplementary-paper request (e.g., by writing a sentinel file or exiting with a specific code), a second `AskUserQuestion` pauses for user input before re-invoking the subprocess.
- After `extensions.md` is written, skill invokes `/CASM-tools:review-document all advisory adversarial paper-extension/extensions.md into <dir>`.
- Session log gains one entry per checkpoint round and per phase.

**Patterns to follow:**
- Existing `AskUserQuestion` checkpoint usage in the skill already matches the pattern; extend it rather than re-inventing.
- The "Candidate identity preserved across revisions" rule from the checkpoint brainstorm: when the user asks to drop only #2, candidates #1 and #3 keep their prose unchanged where possible.

**Test scenarios:**
- Happy path: accept top on first checkpoint → deep-dive runs on candidate #1 → cascade runs on final `extensions.md`.
- Happy path: pick #3 at checkpoint → deep-dive runs on candidate #3.
- Happy path: revise once → `candidates-revise` produces updated `extensions-candidates.md` → checkpoint re-fires → user accepts.
- Edge case: user revises 4 times → loop works uncapped.
- Edge case: deep-dive pauses requesting supplementary papers → second `AskUserQuestion` pauses until user responds.
- Integration: pipeline from `/CASM-tools:paper-extend` through cascade to finalized `extensions.md` produces the same terminal output as the pre-migration flow.

**Verification:**
- No references to `agents/extension-proposer.md`. Checkpoint behavior matches the brainstorm's R1-R8 exactly.

---

- [ ] **Unit 6: Inline presentation-builder into `/CASM-tools:paper-present`**

**Goal:** Remove `agents/presentation-builder.md`; move its scope-and-format-switched drafting prompt into the skill body. Main session produces slides + writeup.

**Requirements:** R8, R13, R14.

**Dependencies:** Unit 3.

**Files:**
- Modify: `plugins/CASM-tools/skills/paper-present/SKILL.md`
- Delete: `plugins/CASM-tools/agents/presentation-builder.md`

**Approach:**
- Skill body inlines the prompt. Scope / format switches (revealjs / pptx / beamer; full / summary only / extension only) become skill-body branches.
- Reads `preferences/presentation-style.md` + `preferences/writing-style.md` + `preferences/structure-style.md` into its working context before drafting.
- `render-slides-to-png.sh` invocation unchanged.
- The previously-required "second post-cascade presentation-reviewer dispatch" (because the cascade didn't forward screenshots into the reviewer) is collapsed: `tests/presentation.py` now accepts `--screenshots <dir>`, and the skill passes it. The second dispatch is removed.

**Patterns to follow:**
- Preserve the existing compile → render PNG → review sequence.

**Test scenarios:**
- Happy path: `/CASM-tools:paper-present full revealjs` → main session produces slides + writeup, compiles, renders PNGs, runs cascade with `presentation.py` seeing the screenshots.
- Edge case: `summary only pptx` → correct format + scope branches selected.
- Integration: entire pipeline produces same output artifacts as pre-migration.

**Verification:**
- No references to `agents/presentation-builder.md`. Cascade sees the screenshots; no secondary post-cascade presentation-review dispatch exists.

---

### Phase 3 — Cleanup

- [ ] **Unit 7: Delete retired agents and update reference docs**

**Goal:** Delete every retired file; update any skill or doc that still references them. Strip the `PreToolUse`/`Agent` hook from `plugin.json`.

**Requirements:** R9, R11, R14 (mechanism change); also removes dead code identified by institutional learnings.

**Dependencies:** Units 1–6 (all replacements in place first).

**Files:**
- Delete: `plugins/CASM-tools/agents/fixer.md`
- Delete: `plugins/CASM-tools/agents/writing-reviewer.md`
- Delete: `plugins/CASM-tools/agents/structure-reviewer.md`
- Delete: `plugins/CASM-tools/agents/math-reviewer.md`
- Delete: `plugins/CASM-tools/agents/simplicity-reviewer.md`
- Delete: `plugins/CASM-tools/agents/adversarial-reviewer.md`
- Delete: `plugins/CASM-tools/agents/factual-reviewer.md`
- Delete: `plugins/CASM-tools/agents/consistency-reviewer.md`
- Delete: `plugins/CASM-tools/agents/code-reviewer.md`
- Delete: `plugins/CASM-tools/agents/presentation-reviewer.md`
- Delete: `plugins/CASM-tools/hooks/inject-preferences.py`
- Modify: `plugins/CASM-tools/.claude-plugin/plugin.json` (remove `PreToolUse` block with `Agent` matcher; `PostToolUse`/`Write|Edit` block unchanged)
- Modify: `plugins/CASM-tools/skills/paper-full-pipeline/SKILL.md` (prose touch-ups — the User Interaction Points list references cascade-specific behavior that's now different)
- Modify: `plugins/CASM-tools/skills/meta-review/SKILL.md` (replace "read combined scorecard" with "read `<logs_dir>/test-results/summary.json` and history summaries")
- Modify: `plugins/CASM-tools/scripts/session-log-template.md` (update Iteration Log section to reference `test-results/` / `summary.json` instead of `reviewer-logs/iter[N]-merged.md`)

**Approach:**
- Grep the plugin for every deleted filename and confirm zero remaining references before the delete step.
- `meta-review`'s clustering logic is file-format-agnostic; only the file-discovery section changes (now it reads JSON from `test-results/summary.json` and `history/iter-*/summary.json`).
- `paper-full-pipeline`'s "User Interaction Points" list was rewritten for the advisory-reviewer and candidate-checkpoint work; this pass just touches up any cascade-specific phrasing.

**Test scenarios:**
- Happy path: fresh clone → no references to deleted files (grep returns empty).
- Happy path: `/CASM-tools:paper-full-pipeline` still enumerates 4 user interaction points in the expected order.
- Integration: `/CASM-tools:meta-review` reads the new layout and produces a clustering report; pre-migration scorecards (if any still exist on disk) are ignored or reported missing.
- Error path: `plugin.json` is valid JSON and loads without error under Claude Code's hook discovery.

**Verification:**
- `grep -r "loop-engine\|orchestrate-review\|reviewer-common\|paper-summarizer\|extension-proposer\|presentation-builder\|-reviewer\.md\|fixer\.md" plugins/CASM-tools` returns zero results.
- The `PreToolUse`/`Agent` hook no longer fires on any tool call. `/CASM-tools:paper-full-pipeline` runs end-to-end. `/CASM-tools:meta-review` reads the new layout.
- The one-sentence pointer in `scripts/review-loop.md` references this plan file so a post-merge reader can reconstruct the design history without the plan itself being loaded into the model's runtime context.

---

## System-Wide Impact

- **Interaction graph.** The PreToolUse/`Agent` hook disappears; every skill that previously relied on silent preference injection must explicitly read preference files. Skills that dispatch subagents drop to zero (reviewer + creator agents retire). The PostToolUse/`Write|Edit` hook (`verify-reminder.py`) is unaffected and keeps firing on `.qmd` writes in `paper-extension/`.
- **Error propagation.** Per-test subprocess failures (`exit 2`) are captured in envelope form and flow into `summary.json` without crashing `run-tests.py`. Fatal cascade errors (lock failure, baseline write failure) propagate up the skill and fail-fast — the user sees the error immediately rather than a confused retry.
- **State lifecycle risks.** Rotation is the most fragile moment; an atomic `os.rename` eliminates partial-rotation risk. Main-session-as-writer means the live file is mutable throughout the cascade — git is the recovery mechanism if a mid-iteration edit goes wrong.
- **API surface parity.** Skill-level grammar (`all`, `advisory <name>`, `into <dir>`, etc.) unchanged. `threshold <N>` retired (documented deprecation, silent accept). Everything else that external callers depend on — call sites in paper-*, final output paths, `/CASM-tools:meta-review` input conventions — is preserved.
- **Integration coverage.** Unit 2's reviewer tests validate the envelope + payload contract end-to-end against `claude -p`. Unit 3's skill rewrite + rotation is exercised by full cascade runs in `/tmp/`. Unit 5's checkpoint needs a real user interaction to fully test; staged manual run against a small paper confirms all three checkpoint branches (accept / pick-N / revise).
- **Unchanged invariants:** `state/session-registry.json` schema; `state/inline/*` materialization with provenance marker; `render-slides-to-png.sh`; `paper-preprocess` skill; all nine `preferences/*-style.md` files; `hooks/verify-reminder.py`; the grammar tokens the skill accepts (except `threshold <N>` deprecation).
- **Retired:** `state/locks/` along with all lock semantics. Concurrency protection on the same artifact is the user's responsibility; the skill does not guard against it.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| `author-plan.py` paraphrases or drops findings, causing the main session to edit things the tests didn't flag. | Plan prompt requires verbatim citation of test name + finding index per plan row; main session has `summary.json` + per-test JSONs as ground-truth cross-references. Deliberate code review during U3 verifies the session's edits against the plan. |
| Losing v1/v2/v3 versioned snapshots removes the "cp `<v3>` live" rollback. | Git is the substitute audit trail. Before/after comparisons use `git diff`. `<logs_dir>/baseline.md` remains as a first-iteration reference. |
| `claude -p` subprocess quota exhaustion under 9+ parallel tests × 3 iterations. | Deferred to post-MVP hardening (see §"Scope Boundaries / Deferred to Separate Tasks"). In the MVP, a failing subprocess writes an infra-failure envelope and the loop continues on surviving tests. Quota preflight via `check-claude-budget.py` is out-of-scope. |
| JSON Schema validates shape but not content; `claude -p` can return valid-but-empty payloads under constrained decoding. | Every reviewer's payload schema enforces `anyOf {findings minItems 1} OR {commendations minItems 1}` — shown concretely in §"High-Level Technical Design". An empty-payload response fails schema validation, triggers one retry, then falls through to an infra-failure envelope. |
| Rotation crash (partial state between rotate and edits). | `os.rename` on a whole directory is atomic within a filesystem. Rotation happens BEFORE edits, so `history/iter-NNN/` always describes the state the plan was generated from. If the cascade crashes between rotation and edit-application, resume detects this via the `.iteration-complete` sentinel and re-applies the already-archived plan (idempotent per the main session's "no-op where already applied" discipline). |
| Main session edits drift beyond the plan (writer discipline weakness). | Multi-layer enforcement: (a) `author-plan.py` emits structured plan rows with `test_name` + `finding_index` + `proposed_edit`; (b) post-iteration the session writes `history/iter-NNN/applied-edits.md` noting applied vs skipped plan rows; (c) `git diff baseline.md -- <doc>` is the ground-truth audit trail for the whole cascade. No subprocess-isolated containment; drift is detectable but not prevented. |
| Suspend-and-resume across schema versions (old `REVIEW_SUSPENDED.md` incompatible). | Explicit schema version field; old schema rejects with "delete and restart" message. Tested in U3. |
| `tests/<reviewer>.py` prompt body drifts from the retired agent `.md` prose. | Unit 2's per-reviewer port is mechanical: migrate prose in full. Skim-review each port against the deleted agent `.md` before committing. |
| User invokes the skill concurrently on the same artifact. | Accepted as user error, not guarded. Damage is observable: interleaved edits in `git diff`, mixed `history/iter-*/` files in `<logs_dir>`. Recovery: `git checkout <doc>` + `rm -rf <logs_dir>` + rerun. |
| `scripts/review-loop.md` becomes a dumping ground as decisions accumulate. | Keep it to the state-machine + history note only. Never reintroduce mechanism-level preference documentation. |
| `paper-full-pipeline` or `meta-review` has an undiscovered dependency on a deleted file or path. | U7 grep verifies every retired filename returns zero hits before deletion. `meta-review` is exercised manually in U7 against the new layout. |

## Documentation / Operational Notes

- **User-facing changes:** None at the skill invocation surface, except (a) `threshold <N>` is a no-op with a deprecation notice, (b) the output directory layout under `<logs_dir>` has a new shape, (c) versioned snapshots (`<artifact>-v1.md` …) are gone — `<logs_dir>/baseline.md` replaces v1; there are no other versioned snapshots.
- **Migration guidance for existing open cascades:** A user with a currently-suspended cascade under the old schema must delete `<logs_dir>/` and restart. U3's resume guard enforces this with a clear message.
- **Release note stub:** "Reviewers now run as standalone Python test scripts that emit structured JSON. The `/CASM-tools:review-document` argument grammar is unchanged. Versioned per-iteration snapshots (`<artifact>-v1.md`, `<artifact>-v2.md`, ...) are replaced by a single `baseline.md` plus per-iteration directories under `history/iter-NNN/`. Rely on git for the full edit history."
- **Monitoring:** No new monitoring. If `/CASM-tools:meta-review` is run across many cascades, its new JSON-based input path should be verified against a real cascade output before broader adoption.

## Sources & References

- **Origin document:** `docs/brainstorms/2026-04-22-ralph-style-reviewer-architecture-requirements.md`
- **Related prior work:**
  - `docs/plans/2026-04-22-001-feat-advisory-reviewer-non-blocking-plan.md`
  - `docs/brainstorms/2026-04-22-paper-extend-candidate-checkpoint-requirements.md`
  - `docs/plans/2026-04-20-refactor-flat-parallel-review-cascade-plan.md`
  - `docs/plans/2026-04-20-fix-prevent-orchestrator-preference-injection-plan.md`
  - `docs/plans/2026-04-20-refactor-paper-prefix-skills-and-filenames-plan.md`
- **Pattern source:** `chenandrewy/ralph-wiggum-asset-pricing`, branch `ralph/run-final`:
  - `tests/_test_helpers.py`, `tests/writing-intro.py`
  - `ralph/run-tests.py`, `ralph/author-plan.py`, `ralph/author-improve.py`
  - `ralph/ralph-loop.sh`
- **Claude Code headless docs:** `https://code.claude.com/docs/en/headless` (structured output, `--output-format json --json-schema`, bare mode).
- **Primary code to migrate or delete:**
  - `plugins/CASM-tools/skills/review-document/SKILL.md`
  - `plugins/CASM-tools/skills/{paper-summarize,paper-extend,paper-present,paper-full-pipeline,meta-review}/SKILL.md`
  - `plugins/CASM-tools/scripts/{loop-engine,orchestrate-review,reviewer-common}.md`
  - `plugins/CASM-tools/agents/*.md`
  - `plugins/CASM-tools/hooks/inject-preferences.py`
  - `plugins/CASM-tools/.claude-plugin/plugin.json`
