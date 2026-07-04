# SEC Financial Extractor

## Project Overview

SEC Financial Extractor is a Python-based automation tool that extracts financial data from SEC EDGAR/XBRL filings for selected US-listed companies.

The tool uses company tickers, maps them to SEC CIK numbers, pulls financial data from 10-K and 10-Q filings, calculates FY and LTM metrics, and prepares data for valuation, comparable company analysis, and financial modelling.

## Current Objective

The current code already extracts SEC data, but it needs to be improved to make it more universal and scalable.

The main goal is to reduce hardcoding so that the user only needs to change:
- Ticker input
- Target years
- Excel template path

The code should not require manual ticker changes in multiple functions.

## Data Source

The project uses SEC EDGAR/XBRL data through:
- SEC ticker-to-CIK directory
- SEC companyfacts API

The current code pulls:
- Ticker directory
- Company facts
- 10-K data
- 10-Q data
- Income statement metrics
- Balance sheet metrics
- D&A and impairment metrics
- EBIT, EBT, and interest-related metrics

## Key Metrics Extracted

### Income Statement
- Revenue
- Net Profit
- EBIT / Operating Income
- EBT / Profit Before Tax
- Interest Expense
- Interest Income
- Net Interest Expense

### Balance Sheet
- Cash and Cash Equivalents
- Short-term Investments
- Marketable Securities
- Debt-related items
- Preferred Equity

### Other Metrics
- Depreciation
- Amortization
- Depreciation & Amortization
- Impairment
- Goodwill impairment
- Intangible asset impairment

## LTM Calculation

The tool should calculate LTM using:

LTM = Latest Annual FY + Current YTD - Prior Year YTD

The output should clearly show:
- Base Annual Value
- Current YTD Value
- Prior YTD Value
- Final LTM Value

This makes the LTM calculation auditable.

## Current Problem in Code

The current code has hardcoding in multiple places, such as:

```python
portfolio = ["CLF"]
get_lean_filtered_balance_sheet("CLF")
get_dna_and_impairment_ltm_ready("CLF")
get_earnings_and_interest_ltm_ready("CLF")
target_years=[2024, 2025]
