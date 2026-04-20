# Code Style Preferences

Scoring weights, severity calibration, and style rules for the code-reviewer. Edit this file to tune the reviewer — scoring weights, what libraries count as idiomatic, and which idioms count as anti-patterns all live here.

## Scoring weights

| Category | What it measures | Weight |
|---|---|---|
| Correctness | Does the code compute the right thing? Tests pass? | 40% |
| Edge cases | Empty inputs, NaN, duplicates, timezones, overflow handled? | 20% |
| Project style | Adherence to the preferred library stack and idioms (see below) | 25% |
| Test coverage | Claimed behavior has tests; critical paths covered | 15% |

Composite = Correctness × 0.40 + Edge cases × 0.20 + Project style × 0.25 + Test coverage × 0.15

A score of 90+ means the code is correct, idiomatic, and tested. It does not mean the code uses every advanced feature of the preferred stack.

## Preferred stack (Python data analysis, academic research)

Edit this section to match your team's stack. Grad students or collaborators with a different stack should replace the lists below.

- **DataFrames:** Polars, lazy-first. Hold expressions in `LazyFrame`s; `.collect()` only at materialization boundaries. Avoid pandas conversion unless an external library requires it.
- **Econometrics:** `polars_reg` (`pr.ols`, `pr.iv`, `pr.fe`, `pr.compare`, `pr.regtable`, etc.). Prefer this over statsmodels, linearmodels, and pyfixest.
- **Plotting:** Altair. Prefer this over matplotlib, seaborn, and pandas plotting.
- **Tables:** GreatTables. Prefer this over pandas styling or matplotlib-rendered tables.
- **Documents:** Quarto (`.qmd`). Raw notebooks acceptable only for exploration.
- **Random seed:** derive from the current date/time; do not hard-code 42.

## Severity calibration

### CRITICAL
- Bugs that produce wrong numerical results.
- Bugs that crash on typical input.
- Security issues (e.g., `shell=True` with user input, SQL injection, unsafe deserialization).
- Test-suite failures.
- A docstring or comment that misdescribes what the code does (correctness-documentation mismatch).
- Error handling that silently hides a bug producing wrong numerical results (e.g., bare `except:` swallowing a NaN-producing exception).
- Wrong econometric idioms (standard errors that ignore panel structure, identification strategy that does not identify the claimed parameter, fixed-effect scheme that differs from the one described) when the resulting number is misleading.

### MAJOR
- Untested claimed behavior.
- Missing edge-case handling (empty inputs, NaN, duplicate keys, timezone-naive dates, integer overflow).
- Non-lazy Polars where lazy would be correct.
- Use of statsmodels, linearmodels, or pyfixest where `polars_reg` fits.
- Matplotlib where Altair fits, or pandas plotting where GreatTables would format the table.
- Raw notebooks where the project convention is `.qmd` Quarto with code folding enabled.
- Bare `except:`, `except Exception` as a shortcut, or silent fallbacks that do not rise to CRITICAL.
- Wrong econometric idioms that degrade quality but do not produce a misleading number.
- A test dependency missing from the environment (flag rather than install).

### MINOR
- Idiomatic improvements.
- Stylistic nits.
- Linter warnings that do not affect correctness.

## What NOT to flag

- Writing quality in docstrings or comments — writing-reviewer's domain.
- Unnecessary complexity, dead code, over-abstraction — simplicity-reviewer's domain. Correct-but-complex code defers to that reviewer.
- Mathematical correctness of derivations implemented in code — math-reviewer's domain.
- Missing comments. The project convention defaults to no comments unless the code is non-obvious.

## Domain-specific rules

- Bugs must be demonstrable. Quote the line of code and explain, or show via `python -c`, how the bug triggers.
- When a library API is uncertain, say so instead of guessing. Flag the relevant docs (Polars, polars_reg, Quarto) in the scorecard rather than fabricating API details.
- Run the linter, type checker, and scoped tests via the allowlist commands (`ruff`, `mypy`, `pytest`, `quarto check`, `python -c`). Do NOT install packages, make network calls, or modify files.
