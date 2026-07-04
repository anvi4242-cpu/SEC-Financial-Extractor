import numpy as np
import pandas as pd
import requests

# Shared Configuration
HEADERS = {"User-Agent": "Bhavika Gupta bhavika.gupta@r9wealth.com"}

# ==============================================================================
# 1. CORE TICKER DIRECTORY LOADER
# ==============================================================================

def load_sec_ticker_directory():
    """Fetches the official SEC ticker-to-CIK directory and pads CIKs to 10 digits."""
    url = "https://www.sec.gov/files/company_tickers.json"
    response = requests.get(url, headers=HEADERS)

    if response.status_code == 200:
        ticker_data = response.json()
        df_tickers = pd.DataFrame.from_dict(ticker_data, orient="index")
        df_tickers["cik_str"] = df_tickers["cik_str"].astype(str).str.zfill(10)
        print("✅ SEC Ticker Directory successfully loaded!")
        return df_tickers
    else:
        print(f"❌ Failed to fetch ticker data. Status Code: {response.status_code}.")
        return None

# ==============================================================================
# 2. PORTFOLIO PERFORMANCE MATRIX (REVENUE & NET INCOME WITH QUARTER DETAILS)
# ==============================================================================

TAG_MAPPINGS = {
    "Revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "Revenues"],
    # Added common fallback tags used when companies report net losses or have non-controlling interests
    "Net_Profit": ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"]
}

def fetch_clean_sec_df(company_facts, metric_name):
    """Fetches all entries for a metric and adds columns to compute exact day durations."""
    us_gaap_data = company_facts.get("facts", {}).get("us-gaap", {})
    combined_dfs = []

    for tag in TAG_MAPPINGS[metric_name]:
        if tag in us_gaap_data:
            units = us_gaap_data[tag].get("units", {})
            for unit_key in units.keys():
                df = pd.DataFrame(units[unit_key])
                if not df.empty and 'form' in df.columns:
                    combined_dfs.append(df)

    if not combined_dfs:
        return pd.DataFrame()

    total_df = pd.concat(combined_dfs, ignore_index=True)
    total_df = total_df[total_df['form'].isin(['10-K', '10-Q'])].copy()

    if 'start' in total_df.columns and 'end' in total_df.columns:
        total_df['start'] = pd.to_datetime(total_df['start'])
        total_df['end'] = pd.to_datetime(total_df['end'])
        total_df['days'] = (total_df['end'] - total_df['start']).dt.days
    else:
        total_df['end'] = pd.to_datetime(total_df['end'])
        total_df['days'] = 0

    return total_df

def get_income_statement_series(facts, metric_name, target_years):
    """Extracts precise values for annual years, individual components, and calculates LTM."""
    df = fetch_clean_sec_df(facts, metric_name)
    results = {f"FY{yr}": 0.0 for yr in target_years}

    # Initialize component placeholders for the user to view the breakdown calculation
    results["Base_Annual_Val"] = 0.0
    results["Current_YTD_Val"] = 0.0
    results["Prior_YTD_Val"] = 0.0
    results["LTM"] = 0.0

    if df.empty:
        return results

    # --- Annual Processing ---
    df_annual = df[(df["form"] == "10-K") & (df["days"] > 330) & (df["days"] < 380)]
    for yr in target_years:
        match = df_annual[df_annual["fy"] == yr]
        if not match.empty:
            results[f"FY{yr}"] = match.sort_values(by="end").iloc[-1]["val"] / 1e6

    # --- LTM Processing with Explicit Components Exposed ---
    max_fy_in_10k = df_annual["fy"].max() if not df_annual.empty else 0
    df_quarterly = df[df["form"] == "10-Q"].sort_values(by="end")

    if df_quarterly.empty:
        val = results[f"FY{max_fy_in_10k}"] if max_fy_in_10k in target_years else 0.0
        results["LTM"] = val
        results["Base_Annual_Val"] = val
        return results

    latest_10q = df_quarterly.iloc[-1]
    latest_10q_fy = latest_10q["fy"]
    latest_10q_fp = latest_10q["fp"]

    if latest_10q_fy <= max_fy_in_10k:
        val = results[f"FY{max_fy_in_10k}"] if max_fy_in_10k in target_years else 0.0
        results["LTM"] = val
        results["Base_Annual_Val"] = val
        return results

    base_annual_val = df_annual[df_annual["fy"] == max_fy_in_10k].sort_values(by="end").iloc[-1]["val"] / 1e6 if not df_annual[df_annual["fy"] == max_fy_in_10k].empty else 0.0
    curr_ytd_match = df_quarterly[(df_quarterly["fy"] == latest_10q_fy) & (df_quarterly["fp"] == latest_10q_fp)]
    curr_ytd_val = curr_ytd_match.iloc[-1]["val"] / 1e6 if not curr_ytd_match.empty else 0.0
    prior_ytd_match = df_quarterly[(df_quarterly["fy"] == max_fy_in_10k) & (df_quarterly["fp"] == latest_10q_fp)]
    prior_ytd_val = prior_ytd_match.iloc[-1]["val"] / 1e6 if not prior_ytd_match.empty else 0.0

    results["Base_Annual_Val"] = base_annual_val
    results["Current_YTD_Val"] = curr_ytd_val
    results["Prior_YTD_Val"] = prior_ytd_val
    results["LTM"] = base_annual_val + curr_ytd_val - prior_ytd_val
    return results

def extract_audited_sec_matrix(tickers_list, df_tickers_source, target_years=[2024, 2025]):
    """Generates the clean data table exposing the formula steps for calculating LTM figures."""
    matrix_rows = []

    for ticker in tickers_list:
        ticker = ticker.upper().strip()
        print(f"💼 Auditing income statement for: {ticker}...")

        row = df_tickers_source[df_tickers_source["ticker"] == ticker]
        if row.empty:
            continue
        cik = row.iloc[0]["cik_str"]

        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        res = requests.get(url, headers=HEADERS)
        if res.status_code != 200:
            continue
        facts = res.json()

        company_row = {"Company/Ticker": ticker}
        rev_data = get_income_statement_series(facts, "Revenue", target_years)
        net_data = get_income_statement_series(facts, "Net_Profit", target_years)

        for yr in target_years:
            company_row[f"Revenue (FY{yr})"] = round(rev_data[f"FY{yr}"], 2)
        company_row["Revenue (Base FY)"] = round(rev_data["Base_Annual_Val"], 2)
        company_row["Revenue (Current YTD)"] = round(rev_data["Current_YTD_Val"], 2)
        company_row["Revenue (Prior YTD)"] = round(rev_data["Prior_YTD_Val"], 2)
        company_row["Revenue (LTM)"] = round(rev_data["LTM"], 2)

        for yr in target_years:
            company_row[f"Net Profit (FY{yr})"] = round(net_data[f"FY{yr}"], 2)
        company_row["Net Profit (Base FY)"] = round(net_data["Base_Annual_Val"], 2)
        company_row["Net Profit (Current YTD)"] = round(net_data["Current_YTD_Val"], 2)
        company_row["Net Profit (Prior YTD)"] = round(net_data["Prior_YTD_Val"], 2)
        company_row["Net Profit (LTM)"] = round(net_data["LTM"], 2)

        matrix_rows.append(company_row)

    return pd.DataFrame(matrix_rows).set_index("Company/Ticker")

# ==============================================================================
# 3. LEAN BALANCE SHEET EXTRACTOR (CORE DEBT, LIQUIDITY & PREFERRED EQUITY)
# ==============================================================================

def get_lean_filtered_balance_sheet(ticker):
    """Fetches liquid assets, core debt, and preferred equity parameters from the balance sheet."""
    ticker = ticker.upper().strip()
    print(f"📡 Locating SEC data and applying lean filters for {ticker}...")

    tickers_url = "https://www.sec.gov/files/company_tickers.json"
    try:
        ticker_data = requests.get(tickers_url, headers=HEADERS).json()
        cik = next((str(v['cik_str']).zfill(10) for v in ticker_data.values() if v['ticker'] == ticker), None)
    except Exception:
        print("❌ Failed to reach SEC ticker directory.")
        return None

    if not cik:
        print(f"❌ Ticker {ticker} not found.")
        return None

    facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    facts_res = requests.get(facts_url, headers=HEADERS)
    if facts_res.status_code != 200:
        print(f"❌ Failed to fetch financial facts for {ticker}.")
        return None

    us_gaap = facts_res.json().get("facts", {}).get("us-gaap", {})

    # Explicit Whitelist including Preferred Equity structural tags
    allowed_liquid_assets = [
        "CashAndCashEquivalentsAtCarryingValue", "Cash", "ShortTermInvestments",
        "AvailableForSaleSecuritiesCurrent", "MarketableSecuritiesCurrent",
        "PreferredStockValue", "PreferredStockCarryingValue", "TemporaryEquityCarryingAmountAttributableToParent"
    ]

    # Adjusted blocklist to bypass keyword matches if the tag contains structural preferred labels
    keyword_blocklist = [
        "asset", "receivable", "inventory", "property", "plant", "equipment",
        "goodwill", "intangible", "prepaid", "advance", "rightofuse", "capitalized",
        "investments", "accountspayable", "sharebasedcompensation", "comprehensive",
        "retainedearnings", "total", "tax", "employee", "pension", "postretirement",
        "benefit", "dividend", "stock", "equity", "paidincapital"
    ]

    exact_total_tags = [
        "liabilities", "liabilitiescurrent", "liabilitiesnoncurrent",
        "stockholdersequity", "partnersequity", "liabilitiesandstockholdersequity",
        "liabilitiesandpartnersequity"
    ]

    standard_keys = {'end', 'val', 'accn', 'fy', 'fp', 'form', 'filed', 'frame'}
    rows = []

    for tag, details in us_gaap.items():
        tag_lower = tag.lower()
        is_whitelisted = tag in allowed_liquid_assets

        # Ensure preferred stock variations aren't accidentally trapped by 'stock' or 'equity' filters
        is_preferred_exception = "preferredstock" in tag_lower

        is_keyword_blocked = any(keyword in tag_lower for keyword in keyword_blocklist) and not is_preferred_exception
        is_exact_blocked = tag_lower in exact_total_tags

        if is_whitelisted or (not is_keyword_blocked and not is_exact_blocked):
            for unit_name, unit_data in details.get("units", {}).items():
                for entry in unit_data:
                    if 'start' not in entry and entry.get('form') in ['10-Q', '10-K']:
                        if set(entry.keys()).issubset(standard_keys):
                            rows.append({
                                "Original SEC Tag": tag,
                                "Value": entry["val"],
                                "Date": entry["end"],
                                "Form": entry["form"]
                            })

    if not rows:
        print(f"❌ No valid filtered data found for {ticker}.")
        return None

    df = pd.DataFrame(rows)
    df['Date'] = pd.to_datetime(df['Date'])
    latest_date = df['Date'].max()
    df_latest = df[df['Date'] == latest_date].copy()
    df_latest = df_latest.drop_duplicates(subset=['Original SEC Tag'], keep='last')

    df_latest['Value ($ Millions)'] = (df_latest['Value'] / 1e6).round(2)
    df_final = df_latest[['Original SEC Tag', 'Value ($ Millions)']].sort_values('Original SEC Tag').reset_index(drop=True)

    print(f"\n========================================================")
    print(f"🏛️ LEAN BALANCE SHEET (CORE DEBT, LIQUIDITY & PREFERRED): {ticker}")
    print(f"📅 As of Date: {latest_date.date()} | Form: {df_latest.iloc[0]['Form']}")
    print(f"========================================================")

    return df_final

# ==============================================================================
# 4. DEPRECIATION, AMORTIZATION & IMPAIRMENT (LTM-READY)
# ==============================================================================

def get_dna_and_impairment_ltm_ready(ticker):
    """Fetches D&A and Impairment metrics for last 2 FYs and current/prior YTD quarters."""
    ticker = ticker.upper().strip()
    print(f"📡 Locating LTM-ready D&A and Impairment data for {ticker}...")

    tickers_url = "https://www.sec.gov/files/company_tickers.json"
    try:
        ticker_data = requests.get(tickers_url, headers=HEADERS).json()
        cik = next((str(v['cik_str']).zfill(10) for v in ticker_data.values() if v['ticker'] == ticker), None)
    except Exception:
        print("❌ Failed to reach SEC ticker directory.")
        return None

    if not cik:
        print(f"❌ Ticker {ticker} not found.")
        return None

    facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    facts_res = requests.get(facts_url, headers=HEADERS)
    if facts_res.status_code != 200:
        print(f"❌ Failed to fetch financial facts for {ticker}.")
        return None

    us_gaap = facts_res.json().get("facts", {}).get("us-gaap", {})

    target_tags = [
        "DepreciationDepletionAndAmortization", "DepreciationAndAmortization", "Depreciation",
        "AmortizationOfIntangibleAssets", "AssetImpairmentCharges", "GoodwillImpairmentLoss",
        "ImpairmentOfIntangibleAssetsExcludingGoodwill", "RestructuringAndImpairmentCharges",
        "PropertyPlantAndEquipmentImpairment"
    ]

    standard_keys = {'start', 'end', 'val', 'accn', 'fy', 'fp', 'form', 'filed', 'frame'}
    rows = []

    for tag in target_tags:
        if tag in us_gaap:
            for unit_name, unit_data in us_gaap[tag].get("units", {}).items():
                for entry in unit_data:
                    if 'start' in entry and 'end' in entry and 'form' in entry:
                        if set(entry.keys()).issubset(standard_keys):
                            rows.append({
                                "tag": tag,
                                "value": entry["val"],
                                "start": entry["start"],
                                "end": entry["end"],
                                "form": entry["form"]
                            })

    if not rows:
        print(f"❌ No valid D&A or Impairment data found for {ticker}.")
        return None

    df = pd.DataFrame(rows)
    df['start'] = pd.to_datetime(df['start'])
    df['end'] = pd.to_datetime(df['end'])
    df['duration_days'] = (df['end'] - df['start']).dt.days

    target_records = []
    column_metadata = {}

    df_annual = df[(df['form'] == '10-K') & (df['duration_days'].between(360, 375))].copy()
    if not df_annual.empty:
        annual_dates = sorted(df_annual['end'].unique(), reverse=True)[:2]
        for d in annual_dates:
            temp = df_annual[df_annual['end'] == d].drop_duplicates('tag', keep='last')
            target_records.append(temp)
            column_metadata[d] = f"FY Ended {d.date()}"
        latest_fy_date = annual_dates[0]
    else:
        print("⚠️ No annual 10-K data found.")
        latest_fy_date = pd.Timestamp.min

    df_ytd = df[(df['form'] == '10-Q') & (df['end'] > latest_fy_date)].copy()

    if not df_ytd.empty:
        latest_ytd_date = df_ytd['end'].max()
        temp_ytd = df_ytd[df_ytd['end'] == latest_ytd_date]
        max_ytd_duration = temp_ytd['duration_days'].max()
        temp_ytd = temp_ytd[temp_ytd['duration_days'] == max_ytd_duration].drop_duplicates('tag', keep='last')
        target_records.append(temp_ytd)

        months = max(1, round(max_ytd_duration / 30))
        column_metadata[latest_ytd_date] = f"Latest YTD ({months} Mos) Ended {latest_ytd_date.date()}"

        prior_ytd_target = latest_ytd_date - pd.Timedelta(days=365)
        df_prior_ytd = df[
            (df['form'] == '10-Q') &
            (df['end'].between(prior_ytd_target - pd.Timedelta(days=15), prior_ytd_target + pd.Timedelta(days=15))) &
            (df['duration_days'].between(max_ytd_duration - 5, max_ytd_duration + 5))
        ].copy()

        if not df_prior_ytd.empty:
            prior_ytd_date = df_prior_ytd['end'].max()
            temp_prior_ytd = df_prior_ytd[df_prior_ytd['end'] == prior_ytd_date].drop_duplicates('tag', keep='last')
            target_records.append(temp_prior_ytd)
            column_metadata[prior_ytd_date] = f"Prior YTD ({months} Mos) Ended {prior_ytd_date.date()}"
        else:
            print("⚠️ Match for prior year's YTD quarter not found in database.")

    if not target_records:
        print(f"❌ Could not isolate requested periods for {ticker}.")
        return None

    final_df = pd.concat(target_records)
    final_df['value_millions'] = (final_df['value'] / 1e6).round(2)

    matrix = final_df.pivot_table(index='tag', columns='end', values='value_millions', aggfunc='last')
    matrix.columns = [column_metadata[col] for col in matrix.columns]
    matrix = matrix.fillna(0.00).sort_index()

    print(f"\n========================================================")
    print(f"📉 LTM-READY RECONCILIATION MATRIX: {ticker}")
    print(f"========================================================")

    return matrix

# ==============================================================================
# 5. EBIT, EBT & NET INTEREST EXPENSE RECONCILIATION (LTM-READY)
# ==============================================================================

def get_earnings_and_interest_ltm_ready(ticker):
    """Fetches EBIT, EBT, Interest Expense, and Income tags to compute Net metrics."""
    ticker = ticker.upper().strip()
    print(f"📡 Locating LTM-ready Earnings & Interest data for {ticker}...")

    tickers_url = "https://www.sec.gov/files/company_tickers.json"
    try:
        ticker_data = requests.get(tickers_url, headers=HEADERS).json()
        cik = next((str(v['cik_str']).zfill(10) for v in ticker_data.values() if v['ticker'] == ticker), None)
    except Exception:
        print("❌ Failed to reach SEC ticker directory.")
        return None

    if not cik:
        print(f"❌ Ticker {ticker} not found.")
        return None

    facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    facts_res = requests.get(facts_url, headers=HEADERS)
    if facts_res.status_code != 200:
        print(f"❌ Failed to fetch financial facts for {ticker}.")
        return None

    us_gaap = facts_res.json().get("facts", {}).get("us-gaap", {})

    # Added "InterestExpenseNet" to catch combined net interest lines
    # Added non-operating variants to catch items filed under "Other Income/Expense"
    target_tags = [
        "OperatingIncomeLoss",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "InterestExpense", "InterestAndDebtExpense", "InterestExpenseNet",
        "InterestExpenseNonoperating", "InterestIncomeExpenseNonoperatingNet",
        "InterestIncome", "InvestmentIncomeInterest", "InterestAndDividendIncome"
    ]

    standard_keys = {'start', 'end', 'val', 'accn', 'fy', 'fp', 'form', 'filed', 'frame'}
    rows = []

    for tag in target_tags:
        if tag in us_gaap:
            for unit_name, unit_data in us_gaap[tag].get("units", {}).items():
                for entry in unit_data:
                    if 'start' in entry and 'end' in entry and 'form' in entry:
                        if set(entry.keys()).issubset(standard_keys):
                            rows.append({
                                "tag": tag,
                                "value": entry["val"],
                                "start": entry["start"],
                                "end": entry["end"],
                                "form": entry["form"]
                            })

    if not rows:
        print(f"❌ No valid earnings or interest data found for {ticker}.")
        return None

    df = pd.DataFrame(rows)
    df['start'] = pd.to_datetime(df['start'])
    df['end'] = pd.to_datetime(df['end'])
    df['duration_days'] = (df['end'] - df['start']).dt.days

    target_records = []
    column_metadata = {}

    df_annual = df[(df['form'] == '10-K') & (df['duration_days'].between(360, 375))].copy()
    if not df_annual.empty:
        annual_dates = sorted(df_annual['end'].unique(), reverse=True)[:2]
        for d in annual_dates:
            temp = df_annual[df_annual['end'] == d].drop_duplicates('tag', keep='last')
            target_records.append(temp)
            column_metadata[d] = f"FY Ended {d.date()}"
        latest_fy_date = annual_dates[0]
    else:
        print("⚠️ No annual 10-K data found.")
        latest_fy_date = pd.Timestamp.min

    df_ytd = df[(df['form'] == '10-Q') & (df['end'] > latest_fy_date)].copy()

    if not df_ytd.empty:
        latest_ytd_date = df_ytd['end'].max()
        temp_ytd = df_ytd[df_ytd['end'] == latest_ytd_date]
        max_ytd_duration = temp_ytd['duration_days'].max()
        temp_ytd = temp_ytd[temp_ytd['duration_days'] == max_ytd_duration].drop_duplicates('tag', keep='last')
        target_records.append(temp_ytd)

        months = max(1, round(max_ytd_duration / 30))
        column_metadata[latest_ytd_date] = f"Latest YTD ({months} Mos) Ended {latest_ytd_date.date()}"

        prior_ytd_target = latest_ytd_date - pd.Timedelta(days=365)
        df_prior_ytd = df[
            (df['form'] == '10-Q') &
            (df['end'].between(prior_ytd_target - pd.Timedelta(days=15), prior_ytd_target + pd.Timedelta(days=15))) &
            (df['duration_days'].between(max_ytd_duration - 5, max_ytd_duration + 5))
        ].copy()

        if not df_prior_ytd.empty:
            prior_ytd_date = df_prior_ytd['end'].max()
            temp_prior_ytd = df_prior_ytd[df_prior_ytd['end'] == prior_ytd_date].drop_duplicates('tag', keep='last')
            target_records.append(temp_prior_ytd)
            column_metadata[prior_ytd_date] = f"Prior YTD ({months} Mos) Ended {prior_ytd_date.date()}"
        else:
            print("⚠️ Match for prior year's YTD quarter not found.")

    if not target_records:
        print(f"❌ Could not isolate requested periods for {ticker}.")
        return None

    final_df = pd.concat(target_records)
    final_df['value_millions'] = (final_df['value'] / 1e6).round(2)

    matrix = final_df.pivot_table(index='tag', columns='end', values='value_millions', aggfunc='last')
    matrix.columns = [column_metadata[col] for col in matrix.columns]
    matrix = matrix.fillna(0.00).sort_index()

    print(f"\n========================================================")
    print(f"📊 INCOME STATEMENT METRICS & INTEREST MATRIX: {ticker}")
    print(f"========================================================")

    return matrix

# ==============================================================================
# EXECUTION WORKFLOW
# ==============================================================================
if __name__ == "__main__":
    # 1. Run CIK Loader
    df_tickers = load_sec_ticker_directory()

    if df_tickers is not None:
        # Display directory top snippet
        display(df_tickers.head())

        # 2. Run Portfolio Auditing Matrix (Exposing calculation quarters)
        portfolio = ["CLF"]
        df_income_statement = extract_audited_sec_matrix(portfolio, df_tickers, target_years=[2024, 2025])
        print("\n🎉 Performance Breakdown Table Complete!")
        display(df_income_statement)

        # 3. Run Lean Balance Sheet with Preferred Equity parameters Included
        df_nucor_balance_sheet = get_lean_filtered_balance_sheet("CLF")
        display(df_nucor_balance_sheet)

        # 4. Run D&A Matrix
        df_nucor_dna = get_dna_and_impairment_ltm_ready("CLF")
        display(df_nucor_dna)

        # 5. Run EBIT/EBT/Interest Matrix with Net Interest parameters loaded
        df_nucor_earnings = get_earnings_and_interest_ltm_ready("CLF")
        display(df_nucor_earnings)

