"""Universal ticker-driven SEC companyfacts extraction pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shutil
from typing import Any, Iterable, Mapping

import pandas as pd
import requests

from config import CONFIG, PipelineConfig
from metric_aliases import BALANCE_SHEET_METRICS, LTM_METRICS, METRIC_ALIASES


SEC_TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
MILLIONS = 1_000_000

BASE_ANNUAL = "Base Annual Value"
CURRENT_YTD = "Current YTD Value"
PRIOR_YTD = "Prior Year YTD Value"
FINAL_LTM = "Final LTM Value"
LTM_COMPONENT_COLUMNS = (BASE_ANNUAL, CURRENT_YTD, PRIOR_YTD, FINAL_LTM)


@dataclass
class PipelineResult:
    """All reusable outputs produced by one pipeline run."""

    ltm_metrics: pd.DataFrame
    balance_sheet: pd.DataFrame
    output_path: Path | None = None
    errors: dict[str, str] = field(default_factory=dict)


def _request_headers(config: PipelineConfig) -> dict[str, str]:
    return {"User-Agent": config.sec_user_agent, "Accept-Encoding": "gzip, deflate"}


def load_sec_ticker_directory(
    config: PipelineConfig = CONFIG,
    session: Any = requests,
) -> pd.DataFrame:
    """Fetch the official SEC ticker-to-CIK directory and normalize its keys."""
    response = session.get(
        SEC_TICKER_URL,
        headers=_request_headers(config),
        timeout=config.request_timeout_seconds,
    )
    response.raise_for_status()
    directory = pd.DataFrame.from_dict(response.json(), orient="index")
    directory["ticker"] = directory["ticker"].str.upper().str.strip()
    directory["cik_str"] = directory["cik_str"].astype(str).str.zfill(10)
    return directory


def resolve_cik(ticker: str, ticker_directory: pd.DataFrame) -> str:
    """Resolve one ticker without performing another SEC request."""
    normalized_ticker = ticker.upper().strip()
    match = ticker_directory[ticker_directory["ticker"] == normalized_ticker]
    if match.empty:
        raise ValueError(f"Ticker {normalized_ticker!r} was not found in the SEC directory.")
    return str(match.iloc[0]["cik_str"]).zfill(10)


def fetch_company_facts(
    ticker: str | None = None,
    cik: str | None = None,
    config: PipelineConfig = CONFIG,
    ticker_directory: pd.DataFrame | None = None,
    session: Any = requests,
) -> Mapping[str, Any]:
    """Fetch SEC companyfacts by CIK, resolving a supplied ticker when necessary."""
    if cik is None:
        if ticker is None:
            raise ValueError("Either ticker or cik is required.")
        directory = ticker_directory
        if directory is None:
            directory = load_sec_ticker_directory(config=config, session=session)
        cik = resolve_cik(ticker, directory)

    normalized_cik = str(cik).zfill(10)
    response = session.get(
        SEC_COMPANYFACTS_URL.format(cik=normalized_cik),
        headers=_request_headers(config),
        timeout=config.request_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def _available_unit_items(units: Mapping[str, Any]) -> Iterable[tuple[str, Any]]:
    """Yield monetary USD facts and ignore share/count units."""
    if "USD" in units:
        yield "USD", units["USD"]


def _collect_metric_entries(
    company_facts: Mapping[str, Any],
    metric_name: str,
    *,
    require_duration: bool,
    aliases: Mapping[str, tuple[str, ...]] = METRIC_ALIASES,
) -> pd.DataFrame:
    if metric_name not in aliases:
        raise KeyError(f"Unknown metric {metric_name!r}.")

    us_gaap = company_facts.get("facts", {}).get("us-gaap", {})
    rows: list[dict[str, Any]] = []

    for priority, tag in enumerate(aliases[metric_name]):
        details = us_gaap.get(tag)
        if not details:
            continue
        for unit_name, unit_data in _available_unit_items(details.get("units", {})):
            for entry in unit_data:
                has_duration = "start" in entry and "end" in entry
                if require_duration != has_duration:
                    continue
                if entry.get("form") not in {"10-K", "10-Q"}:
                    continue
                rows.append(
                    {
                        **entry,
                        "tag": tag,
                        "metric": metric_name,
                        "unit": unit_name,
                        "tag_priority": priority,
                    }
                )

    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows)
    frame["end"] = pd.to_datetime(frame["end"], errors="coerce")
    frame["filed"] = pd.to_datetime(frame.get("filed"), errors="coerce")
    if require_duration:
        frame["start"] = pd.to_datetime(frame["start"], errors="coerce")
        frame["days"] = (frame["end"] - frame["start"]).dt.days
    return frame.dropna(subset=["end", "val"])


def fetch_clean_sec_df(
    company_facts: Mapping[str, Any],
    metric_name: str,
    aliases: Mapping[str, tuple[str, ...]] = METRIC_ALIASES,
) -> pd.DataFrame:
    """Return normalized 10-K/10-Q duration facts for a named metric."""
    return _collect_metric_entries(
        company_facts,
        metric_name,
        require_duration=True,
        aliases=aliases,
    )


def _best_fact(frame: pd.DataFrame) -> pd.Series | None:
    if frame.empty:
        return None
    sort_columns = [column for column in ("tag_priority", "filed", "end") if column in frame]
    ascending = [True if column == "tag_priority" else False for column in sort_columns]
    return frame.sort_values(sort_columns, ascending=ascending, na_position="last").iloc[0]


def _latest_period_fact(frame: pd.DataFrame) -> pd.Series | None:
    if frame.empty:
        return None
    latest_end = frame["end"].max()
    return _best_fact(frame[frame["end"] == latest_end])


def _annual_facts(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[
        (frame["form"] == "10-K") & frame["days"].between(330, 380, inclusive="both")
    ].copy()


def _annual_fact_for_year(frame: pd.DataFrame, year: int) -> pd.Series | None:
    if frame.empty:
        return None
    if "fy" in frame:
        fiscal_year = pd.to_numeric(frame["fy"], errors="coerce")
        match = frame[fiscal_year == year]
    else:
        match = frame.iloc[0:0]
    if match.empty:
        match = frame[frame["end"].dt.year == year]
    return _latest_period_fact(match)


def _to_millions(fact: pd.Series | None) -> float:
    return 0.0 if fact is None else float(fact["val"]) / MILLIONS


def get_income_statement_series(
    facts: Mapping[str, Any],
    metric_name: str,
    target_years: Iterable[int],
    aliases: Mapping[str, tuple[str, ...]] = METRIC_ALIASES,
) -> dict[str, float]:
    """Extract fiscal years and an auditable LTM bridge for any duration metric.

    LTM = latest annual FY + current YTD - prior-year YTD.
    """
    years = tuple(int(year) for year in target_years)
    results: dict[str, float] = {f"FY{year}": 0.0 for year in years}
    results.update({column: 0.0 for column in LTM_COMPONENT_COLUMNS})

    frame = fetch_clean_sec_df(facts, metric_name, aliases=aliases)
    if frame.empty:
        return _with_legacy_component_keys(results)

    annual = _annual_facts(frame)
    for year in years:
        results[f"FY{year}"] = _to_millions(_annual_fact_for_year(annual, year))

    base_fact = _latest_period_fact(annual)
    base_value = _to_millions(base_fact)
    results[BASE_ANNUAL] = base_value

    quarterly = frame[
        (frame["form"] == "10-Q") & frame["days"].between(70, 300, inclusive="both")
    ].copy()
    if base_fact is None or quarterly.empty:
        results[FINAL_LTM] = base_value
        return _with_legacy_component_keys(results)

    latest_quarter_end = quarterly["end"].max()
    if latest_quarter_end <= base_fact["end"]:
        results[FINAL_LTM] = base_value
        return _with_legacy_component_keys(results)

    current_candidates = quarterly[quarterly["end"] == latest_quarter_end]
    longest_current_duration = current_candidates["days"].max()
    current_candidates = current_candidates[
        current_candidates["days"].between(
            longest_current_duration - 5,
            longest_current_duration + 5,
            inclusive="both",
        )
    ]
    current_fact = _best_fact(current_candidates)

    prior_target_end = latest_quarter_end - pd.DateOffset(years=1)
    prior_candidates = quarterly[
        quarterly["end"].between(
            prior_target_end - pd.Timedelta(days=20),
            prior_target_end + pd.Timedelta(days=20),
            inclusive="both",
        )
        & quarterly["days"].between(
            longest_current_duration - 7,
            longest_current_duration + 7,
            inclusive="both",
        )
    ]
    if current_fact is not None and "fp" in prior_candidates:
        same_period = prior_candidates[prior_candidates["fp"] == current_fact.get("fp")]
        if not same_period.empty:
            prior_candidates = same_period
    prior_fact = _best_fact(prior_candidates)

    current_value = _to_millions(current_fact)
    prior_value = _to_millions(prior_fact)
    results[CURRENT_YTD] = current_value
    results[PRIOR_YTD] = prior_value
    results[FINAL_LTM] = base_value + current_value - prior_value
    return _with_legacy_component_keys(results)


def _with_legacy_component_keys(results: dict[str, float]) -> dict[str, float]:
    """Keep existing callers working while exposing clearer output labels."""
    results["Base_Annual_Val"] = results[BASE_ANNUAL]
    results["Current_YTD_Val"] = results[CURRENT_YTD]
    results["Prior_YTD_Val"] = results[PRIOR_YTD]
    results["LTM"] = results[FINAL_LTM]
    return results


def extract_ltm_metrics(
    facts: Mapping[str, Any],
    ticker: str,
    cik: str,
    target_years: Iterable[int],
    metrics: Iterable[str] = LTM_METRICS,
) -> pd.DataFrame:
    """Build one row per LTM metric with every formula component exposed."""
    years = tuple(int(year) for year in target_years)
    rows: list[dict[str, Any]] = []
    for metric in metrics:
        values = get_income_statement_series(facts, metric, years)
        row: dict[str, Any] = {"Ticker": ticker, "CIK": cik, "Metric": metric}
        row.update({f"FY{year}": round(values[f"FY{year}"], 2) for year in years})
        row.update({column: round(values[column], 2) for column in LTM_COMPONENT_COLUMNS})
        row["LTM Formula"] = "Latest Annual FY + Current YTD - Prior Year YTD"
        rows.append(row)
    return pd.DataFrame(rows)


def extract_audited_sec_matrix(
    tickers_list: Iterable[str],
    df_tickers_source: pd.DataFrame,
    target_years: Iterable[int],
    config: PipelineConfig = CONFIG,
    session: Any = requests,
) -> pd.DataFrame:
    """Backward-compatible wide Revenue/Net Income matrix for multiple tickers."""
    rows: list[dict[str, Any]] = []
    years = tuple(int(year) for year in target_years)
    for ticker_value in tickers_list:
        ticker = ticker_value.upper().strip()
        cik = resolve_cik(ticker, df_tickers_source)
        facts = fetch_company_facts(
            ticker=ticker,
            cik=cik,
            config=config,
            ticker_directory=df_tickers_source,
            session=session,
        )
        row: dict[str, Any] = {"Company/Ticker": ticker}
        for metric, label in (("Revenue", "Revenue"), ("Net Income", "Net Profit")):
            values = get_income_statement_series(facts, metric, years)
            for year in years:
                row[f"{label} (FY{year})"] = round(values[f"FY{year}"], 2)
            row[f"{label} (Base FY)"] = round(values[BASE_ANNUAL], 2)
            row[f"{label} (Current YTD)"] = round(values[CURRENT_YTD], 2)
            row[f"{label} (Prior YTD)"] = round(values[PRIOR_YTD], 2)
            row[f"{label} (LTM)"] = round(values[FINAL_LTM], 2)
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("Company/Ticker")


def extract_balance_sheet_metrics(
    facts: Mapping[str, Any],
    ticker: str,
    cik: str,
    metrics: Iterable[str] = BALANCE_SHEET_METRICS,
) -> pd.DataFrame:
    """Return latest reported point-in-time facts for reusable balance metrics."""
    rows: list[dict[str, Any]] = []
    for metric in metrics:
        frame = _collect_metric_entries(facts, metric, require_duration=False)
        if frame.empty:
            rows.append(
                {
                    "Ticker": ticker,
                    "CIK": cik,
                    "Metric": metric,
                    "Original SEC Tag": None,
                    "As Of Date": None,
                    "Form": None,
                    "Value ($ Millions)": 0.0,
                }
            )
            continue

        latest_end = frame["end"].max()
        latest = frame[frame["end"] == latest_end]
        for _, fact in (
            latest.sort_values(["tag_priority", "filed"], ascending=[True, False])
            .drop_duplicates("tag", keep="first")
            .iterrows()
        ):
            rows.append(
                {
                    "Ticker": ticker,
                    "CIK": cik,
                    "Metric": metric,
                    "Original SEC Tag": fact["tag"],
                    "As Of Date": latest_end.date().isoformat(),
                    "Form": fact["form"],
                    "Value ($ Millions)": round(float(fact["val"]) / MILLIONS, 2),
                }
            )
    return pd.DataFrame(rows)


def _resolve_facts(
    ticker: str,
    cik: str | None,
    facts: Mapping[str, Any] | None,
    config: PipelineConfig,
    ticker_directory: pd.DataFrame | None,
    session: Any,
) -> tuple[str, Mapping[str, Any]]:
    if cik is None:
        directory = ticker_directory
        if directory is None:
            directory = load_sec_ticker_directory(config=config, session=session)
        cik = resolve_cik(ticker, directory)
    normalized_cik = str(cik).zfill(10)
    if facts is None:
        facts = fetch_company_facts(
            ticker=ticker,
            cik=normalized_cik,
            config=config,
            ticker_directory=ticker_directory,
            session=session,
        )
    return normalized_cik, facts


def get_lean_filtered_balance_sheet(
    ticker: str,
    cik: str | None = None,
    target_years: Iterable[int] | None = None,
    config: PipelineConfig = CONFIG,
    facts: Mapping[str, Any] | None = None,
    ticker_directory: pd.DataFrame | None = None,
    session: Any = requests,
) -> pd.DataFrame:
    """Compatibility wrapper for the latest cash, investments, debt, and preferred equity."""
    del target_years  # Point-in-time facts do not have an LTM or duration.
    normalized_ticker = ticker.upper().strip()
    resolved_cik, resolved_facts = _resolve_facts(
        normalized_ticker, cik, facts, config, ticker_directory, session
    )
    return extract_balance_sheet_metrics(resolved_facts, normalized_ticker, resolved_cik)


def _ltm_subset_wrapper(
    ticker: str,
    metrics: Iterable[str],
    cik: str | None,
    target_years: Iterable[int] | None,
    config: PipelineConfig,
    facts: Mapping[str, Any] | None,
    ticker_directory: pd.DataFrame | None,
    session: Any,
) -> pd.DataFrame:
    normalized_ticker = ticker.upper().strip()
    resolved_cik, resolved_facts = _resolve_facts(
        normalized_ticker, cik, facts, config, ticker_directory, session
    )
    years = config.target_years if target_years is None else tuple(target_years)
    return extract_ltm_metrics(
        resolved_facts,
        normalized_ticker,
        resolved_cik,
        years,
        metrics=metrics,
    )


def get_dna_and_impairment_ltm_ready(
    ticker: str,
    cik: str | None = None,
    target_years: Iterable[int] | None = None,
    config: PipelineConfig = CONFIG,
    facts: Mapping[str, Any] | None = None,
    ticker_directory: pd.DataFrame | None = None,
    session: Any = requests,
) -> pd.DataFrame:
    """Return auditable D&A and impairment FY/LTM rows."""
    return _ltm_subset_wrapper(
        ticker,
        ("D&A", "Impairment"),
        cik,
        target_years,
        config,
        facts,
        ticker_directory,
        session,
    )


def get_earnings_and_interest_ltm_ready(
    ticker: str,
    cik: str | None = None,
    target_years: Iterable[int] | None = None,
    config: PipelineConfig = CONFIG,
    facts: Mapping[str, Any] | None = None,
    ticker_directory: pd.DataFrame | None = None,
    session: Any = requests,
) -> pd.DataFrame:
    """Return auditable EBIT, EBT, and interest FY/LTM rows."""
    return _ltm_subset_wrapper(
        ticker,
        ("EBIT", "EBT", "Interest Expense", "Interest Income"),
        cik,
        target_years,
        config,
        facts,
        ticker_directory,
        session,
    )


def _derived_output_path(template_path: Path) -> Path:
    suffix = template_path.suffix if template_path.suffix.lower() == ".xlsx" else ".xlsx"
    return template_path.with_name(f"{template_path.stem}_SEC_output{suffix}")


def write_results_to_excel(
    ltm_metrics: pd.DataFrame,
    balance_sheet: pd.DataFrame,
    config: PipelineConfig,
) -> Path:
    """Preserve the template and write results to a derived output workbook."""
    template_path = config.excel_template_path.expanduser().resolve()
    output_path = _derived_output_path(template_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if template_path.exists():
        shutil.copy2(template_path, output_path)
        writer_options: dict[str, Any] = {
            "engine": "openpyxl",
            "mode": "a",
            "if_sheet_exists": "replace",
        }
    else:
        writer_options = {"engine": "openpyxl", "mode": "w"}

    with pd.ExcelWriter(output_path, **writer_options) as writer:
        ltm_metrics.to_excel(writer, sheet_name="SEC LTM Metrics", index=False)
        balance_sheet.to_excel(writer, sheet_name="SEC Balance Sheet", index=False)
    return output_path


def run_pipeline(
    config: PipelineConfig = CONFIG,
    *,
    session: Any = requests,
    write_excel: bool = True,
) -> PipelineResult:
    """Run the complete ticker-driven pipeline with one companyfacts fetch per ticker."""
    ticker_directory = load_sec_ticker_directory(config=config, session=session)
    ltm_frames: list[pd.DataFrame] = []
    balance_frames: list[pd.DataFrame] = []
    errors: dict[str, str] = {}

    for ticker in config.tickers:
        try:
            cik = resolve_cik(ticker, ticker_directory)
            facts = fetch_company_facts(
                ticker=ticker,
                cik=cik,
                config=config,
                ticker_directory=ticker_directory,
                session=session,
            )
            ltm_frames.append(extract_ltm_metrics(facts, ticker, cik, config.target_years))
            balance_frames.append(extract_balance_sheet_metrics(facts, ticker, cik))
        except (requests.RequestException, ValueError, KeyError) as exc:
            errors[ticker] = str(exc)

    ltm_metrics = pd.concat(ltm_frames, ignore_index=True) if ltm_frames else pd.DataFrame()
    balance_sheet = (
        pd.concat(balance_frames, ignore_index=True) if balance_frames else pd.DataFrame()
    )
    output_path = None
    if write_excel and (not ltm_metrics.empty or not balance_sheet.empty):
        output_path = write_results_to_excel(ltm_metrics, balance_sheet, config)

    return PipelineResult(
        ltm_metrics=ltm_metrics,
        balance_sheet=balance_sheet,
        output_path=output_path,
        errors=errors,
    )


def main(config: PipelineConfig = CONFIG) -> PipelineResult:
    """Single public runner for scripts, notebooks, and scheduled jobs."""
    result = run_pipeline(config)
    print(f"Processed {len(config.tickers) - len(result.errors)} of {len(config.tickers)} tickers.")
    if result.output_path:
        print(f"Workbook written to: {result.output_path}")
    for ticker, error in result.errors.items():
        print(f"{ticker}: {error}")
    return result


if __name__ == "__main__":
    main()

