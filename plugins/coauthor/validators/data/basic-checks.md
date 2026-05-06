---
id: data/basic-checks
domain: data
version: 0.1.0
applies_to: ["*.parquet", "*.csv", "*.feather"]
---

# Data validator: basic checks

Schema validity, null rates, key uniqueness, range bounds. Polars-flavored; lift the snippet directly.

## Checks

- **Schema.** Column names and dtypes match the project's stated schema (in `CONVENTIONS.md` or PLAN's context pointers).
- **Null rates.** Per column, report null fraction. Flag any column with null fraction above the project-stated threshold (default 0.05) unless explicitly exempt.
- **Key uniqueness.** The stated primary-key columns yield no duplicates.
- **Range bounds.** Numeric columns fall within stated bounds (min, max). Date columns fall within stated date range.
- **Row count.** Within the expected order of magnitude given the source (off by 10× is a fail).

## How to run

```python
import polars as pl

lf = pl.scan_parquet("data/clean.parquet")

# Schema
schema = lf.collect_schema()
print(schema)

# Null rates
null_rates = (
    lf.select(pl.all().null_count() / pl.len())
    .collect()
)
print(null_rates)

# Key uniqueness
keys = ["id", "year"]  # from CONVENTIONS
n_total = lf.select(pl.len()).collect().item()
n_unique = lf.select(pl.struct(keys).n_unique()).collect().item()
assert n_total == n_unique, f"Duplicate keys: {n_total - n_unique}"

# Range bounds
bounds = lf.select(
    pl.col("wage").min().alias("wage_min"),
    pl.col("wage").max().alias("wage_max"),
).collect()
print(bounds)
```

Adjust column names, key set, and threshold per project. Stay lazy until materialization is needed.

## Pass criteria

Schema matches. All null rates within threshold or explicitly exempt. Zero duplicates on the stated key. All numeric and date columns within stated bounds. Row count within an order of magnitude of the expected.

## Fail output

```
file: data/clean.parquet
- schema: column "treatment" missing (expected dtype Int8)
- null rate: column "wage" 0.12 above threshold 0.05
- key uniqueness: 47 duplicate (id, year) pairs
- range: column "age" min -3 below stated bound 0
```

## Applicable contexts

Attach to every `coder` slice that ingests, cleans, or merges data. Skip for slices that consume already-validated data and only transform it.
