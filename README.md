# SEC Financial Extractor

A ticker-driven Python pipeline that uses SEC `companyfacts` as its primary
source, calculates auditable FY/LTM metrics, and writes the result into a copy
of an Excel template.

## Configure

Edit only these three values at the top of `config.py`:

```python
tickers = ["CLF", "NUE"]
target_years = [2024, 2025]
excel_template_path = "my_template.xlsx"
```

Ticker normalization, CIK lookup, SEC URLs, headers, timeouts, metric tags,
output naming, and the extraction sequence are handled internally.

## Run

```bash
python -m pip install -r requirement.txt
python main.py
```

`main()` is the single runner. It performs one ticker-directory request and one
companyfacts request per ticker, then reuses the returned facts across all
metrics. The template is preserved; results are written to
`<template-name>_SEC_output.xlsx` in two sheets:

- `SEC LTM Metrics`
- `SEC Balance Sheet`

## Metrics

The reusable `METRIC_ALIASES` dictionary in `metric_aliases.py` covers:

- Revenue
- Net Income
- EBIT
- EBT
- Interest Expense
- Interest Income
- Cash
- Investments
- Debt
- Preferred Equity
- D&A
- Impairment

Aliases are ordered from the preferred US-GAAP tag to fallbacks. The extractor
records balance-sheet tags individually to avoid silently double-counting debt
or investment totals and components.

## LTM calculation

Every duration metric uses:

```text
LTM = Latest Annual FY + Current YTD - Prior Year YTD
```

Every LTM output row exposes:

- Base Annual Value
- Current YTD Value
- Prior Year YTD Value
- Final LTM Value

Values are reported in USD millions. When there is no newer 10-Q after the
latest 10-K, Final LTM Value falls back to the latest annual value.

## Reusable functions

Existing entry points remain available and no longer contain hardcoded tickers:

- `extract_audited_sec_matrix(...)`
- `get_lean_filtered_balance_sheet(...)`
- `get_dna_and_impairment_ltm_ready(...)`
- `get_earnings_and_interest_ltm_ready(...)`

They accept ticker, CIK, target years, configuration, pre-fetched facts, or a
session as appropriate. Passing pre-fetched facts prevents duplicate SEC calls.

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests use synthetic SEC responses and verify ticker/CIK routing, alias
coverage, latest balance facts, annual fallback, and the LTM bridge formula.

