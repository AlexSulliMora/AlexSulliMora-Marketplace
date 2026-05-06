---
id: derivation/dgp-simulation
domain: derivation
version: 0.1.0
applies_to: ["*.qmd", "*.tex", "IMPL-coder.md"]
---

# Derivation validator: DGP simulation

Simulate the data generating process and check the estimator converges to the true parameter. Per the user's `math.md` rules: a sanity check on claimed estimator properties.

## Checks

- The DGP generates data under the assumptions stated in the derivation.
- The estimator, applied to repeated draws of increasing N, has bias that shrinks to zero (consistency).
- The estimator's empirical sampling distribution at large N matches the claimed asymptotic distribution (asymptotic normality, where claimed).
- Any clustering or heteroskedasticity correction recovers nominal coverage.

## How to run

```python
import numpy as np
import polars as pl
import polars_reg as pr
from datetime import date

rng = np.random.default_rng(int(date.today().strftime("%Y%m%d")))

def simulate(n: int, beta_true: float = 0.5) -> pl.DataFrame:
    x = rng.standard_normal(n)
    e = rng.standard_normal(n)
    y = beta_true * x + e
    return pl.DataFrame({"x": x, "y": y})

estimates = []
for n in [100, 1_000, 10_000]:
    bs = []
    for _ in range(500):
        df = simulate(n)
        result = pr.ols(df, "y ~ x")
        bs.append(result.coef("x"))
    estimates.append({"n": n, "mean": np.mean(bs), "sd": np.std(bs)})

print(pl.DataFrame(estimates))
```

Set the random seed from the current date. 500 replications is a reasonable default for quick checks; bump to 5000 for tighter coverage assessments.

## Pass criteria

- Mean estimate at the largest N is within 2 simulation standard errors of the true parameter.
- Standard deviation of estimates shrinks at the rate the asymptotic theory predicts (typically 1/√N).
- For coverage checks: empirical 95% confidence interval coverage is between 0.93 and 0.97.

## Fail output

```
estimator: pr.ols
true beta: 0.5
- N=100: mean 0.502, sd 0.101, sim SE 0.0045 — ok
- N=10000: mean 0.487, sd 0.011, sim SE 0.0005 — bias 0.013, 26 sim SE from truth — FAIL
diagnosis: check moment condition or estimator implementation
```

## Applicable contexts

Attach to every `coder` slice that introduces a non-standard estimator, or to any slice whose IMPL claims a property (consistency, unbiasedness, asymptotic normality) that should be sanity-checked. Skip for off-the-shelf OLS on a textbook DGP, where `pr.compare` is the right validator.
