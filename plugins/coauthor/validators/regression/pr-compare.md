---
id: regression/pr-compare
domain: regression
version: 0.1.0
applies_to: ["IMPL-coder.md", "*.qmd"]
---

# Regression validator: pr.compare cross-check

The `pr.compare()` cross-check from the user's `python-econometrics` rules. Confirms a `polars_reg` regression matches a reference implementation (Stata, R, or statsmodels) when correctness matters.

## Checks

- For each main-table specification, run the same regression in `polars_reg` and a reference engine.
- Compare coefficients, standard errors, R² (or pseudo-R²), and N.
- Deltas above tolerance are a fail.

## How to run

```python
import polars_reg as pr

result = pr.ols(df, "y ~ x1 + x2", cluster="firm_id")
ref = pr.compare(result, against="statsmodels")  # or "stata", "R"
print(ref)
```

`pr.compare()` returns a side-by-side table of estimates and the maximum absolute delta.

Default tolerance:

- Coefficients: relative delta below 1e-4.
- Standard errors: relative delta below 1e-3 (allows for clustering implementation differences).
- N: exact match.

## Interpreting deltas

- Coefficient delta above tolerance with SE delta below indicates a specification or sample mismatch; diagnose by checking the reference implementation's sample, fixed effects, and weights.
- SE delta above tolerance with coefficient delta below indicates a clustering, robust-SE, or degrees-of-freedom convention difference; confirm the cluster level and the small-sample correction.
- Both delta above tolerance: investigate the reference engine first; assume your code is wrong until proven otherwise.

## Pass criteria

All deltas within tolerance for every reported specification.

## Fail output

```
spec: ols y ~ x1 + x2, cluster=firm_id
- coef on x1: pr 0.142, statsmodels 0.139, delta 0.021 (above 1e-4)
- SE on x1: pr 0.011, statsmodels 0.010, delta 0.10 (above 1e-3)
- diagnosis: check cluster level
```

## Applicable contexts

Attach to every `coder` slice that produces regression output destined for a paper, report, or presentation. Skip for exploratory regressions whose output the user will not cite.
