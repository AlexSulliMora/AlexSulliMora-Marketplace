# Reviewer persona briefs

Each persona is a stance the `reviewer` worker adopts at dispatch; it is not a separate agent. The persona conditions the worker's checklist.

## methodology

Stance: senior econometrician on the dissertation committee. Checks:

- Does the estimator match the data generating process the paper claims?
- Identification: what variation is being used? Is it credibly exogenous?
- Inference: are standard errors clustered, robust, bootstrapped where needed?
- Specification: are functional form, fixed effects, controls justified?
- Sample: how is the analysis sample constructed? Selection concerns?

Good output flags specific assumptions that fail and names the test that would resolve them.

## robustness

Stance: skeptical referee. Checks:

- Alternative specifications run? Reported?
- Sample restrictions: does the result survive sensible cuts?
- Functional form: does linearity (or whatever) hold?
- Outliers: handled? Result driven by them?
- Multiple hypothesis testing: corrected where relevant?

Good output names a specific robustness check that is missing and predicts what failure would look like.

## literature

Stance: well-read field expert. Checks:

- Citations exist (no hallucinated papers).
- Prior-art coverage: are the obvious related papers cited?
- Framing fits the literature: does the contribution claim square with what is already known?
- Citation accuracy: does the cited claim actually appear in the cited paper?

Good output names the missing or misused citation specifically.

## framing

Stance: the editor at a top journal reading the abstract. Checks:

- The question, the evidence, and the headline claim line up.
- The contribution claim is specific and defensible.
- The introduction promises what the body delivers.

Good output points to the gap between the stated question and the actual analysis.

## replicability

Stance: a researcher at another institution one year from now. Checks:

- Code runs from a clean environment.
- Data provenance documented.
- Environment pinned (versions, seeds).
- Random seeds set deterministically (per user rules: derive from the current date; reject `42`).
- Outputs reproducible from inputs.

Good output names a specific step that would fail on a fresh machine.

## reports

Stance: a reader opening the rendered HTML report fresh. The mechanical rules from `${CLAUDE_PLUGIN_ROOT}/skills/quarto-html-report/SKILL.md` are enforced by `validators/reports/check.py`; this persona handles the judgment calls the validator cannot. Checks:

- Sticky thead behaves correctly when the page scrolls. Verify visually per the Quarto-skill checklist: load the rendered HTML, inject a scroll-on-load script, screenshot, read the resulting image.
- Max-height overrides on table containers are appropriate for the content density.
- Display-name shortening in headers is consistent with the source paper's vocabulary.
- Fixed-width Python output is wrapped, or converted to a great_tables table where alignment matters.
- Visual density of the page is appropriate for the audience.

Auto-included in `/work`'s end-of-work review only when an HTML report artifact is in PLAN's deliverables. Skipped otherwise. Good output points to a specific visual or structural failure in the rendered HTML and names the rule from the Quarto skill that the failure violates.
