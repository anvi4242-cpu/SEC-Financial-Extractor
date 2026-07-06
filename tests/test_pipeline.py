import unittest
from pathlib import Path

from config import PipelineConfig
from main import (
    BASE_ANNUAL,
    CURRENT_YTD,
    FINAL_LTM,
    PRIOR_YTD,
    extract_balance_sheet_metrics,
    get_income_statement_series,
    run_pipeline,
)
from metric_aliases import METRIC_ALIASES


def duration_fact(start, end, value, form, fy, fp, filed="2026-01-01"):
    return {
        "start": start,
        "end": end,
        "val": value,
        "form": form,
        "fy": fy,
        "fp": fp,
        "filed": filed,
    }


def instant_fact(end, value, form="10-Q", filed="2025-08-01"):
    return {"end": end, "val": value, "form": form, "filed": filed}


def companyfacts(revenue_units=None, extra_tags=None):
    tags = {}
    if revenue_units is not None:
        tags["RevenueFromContractWithCustomerExcludingAssessedTax"] = {
            "units": {"USD": revenue_units}
        }
    tags.update(extra_tags or {})
    return {"facts": {"us-gaap": tags}}


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, directory, facts):
        self.directory = directory
        self.facts = facts
        self.urls = []

    def get(self, url, **_kwargs):
        self.urls.append(url)
        if url.endswith("company_tickers.json"):
            return FakeResponse(self.directory)
        return FakeResponse(self.facts)


class PipelineTests(unittest.TestCase):
    def test_alias_dictionary_covers_every_requested_metric(self):
        expected = {
            "Revenue",
            "Net Income",
            "EBIT",
            "EBT",
            "Interest Expense",
            "Interest Income",
            "Cash",
            "Investments",
            "Debt",
            "Preferred Equity",
            "D&A",
            "Impairment",
        }
        self.assertEqual(expected, set(METRIC_ALIASES))
        self.assertTrue(all(METRIC_ALIASES[metric] for metric in expected))
        self.assertFalse(
            set(METRIC_ALIASES["Interest Expense"])
            & set(METRIC_ALIASES["Interest Income"])
        )

    def test_ltm_uses_annual_plus_current_ytd_minus_prior_ytd(self):
        facts = companyfacts(
            [
                duration_fact(
                    "2024-01-01", "2024-12-31", 1_000_000_000, "10-K", 2024, "FY"
                ),
                duration_fact(
                    "2025-01-01", "2025-06-30", 600_000_000, "10-Q", 2025, "Q2"
                ),
                duration_fact(
                    "2025-04-01", "2025-06-30", 350_000_000, "10-Q", 2025, "Q2"
                ),
                duration_fact(
                    "2024-01-01", "2024-06-30", 500_000_000, "10-Q", 2024, "Q2"
                ),
            ]
        )

        result = get_income_statement_series(facts, "Revenue", [2024])

        self.assertEqual(1_000.0, result[BASE_ANNUAL])
        self.assertEqual(600.0, result[CURRENT_YTD])
        self.assertEqual(500.0, result[PRIOR_YTD])
        self.assertEqual(1_100.0, result[FINAL_LTM])

    def test_ltm_falls_back_to_latest_annual_without_new_quarter(self):
        facts = companyfacts(
            [
                duration_fact(
                    "2024-01-01", "2024-12-31", 900_000_000, "10-K", 2024, "FY"
                )
            ]
        )

        result = get_income_statement_series(facts, "Revenue", [2024])

        self.assertEqual(900.0, result[BASE_ANNUAL])
        self.assertEqual(900.0, result[FINAL_LTM])
        self.assertEqual(0.0, result[CURRENT_YTD])
        self.assertEqual(0.0, result[PRIOR_YTD])

    def test_balance_sheet_uses_latest_instant_facts(self):
        facts = companyfacts(
            extra_tags={
                "CashAndCashEquivalentsAtCarryingValue": {
                    "units": {
                        "USD": [
                            instant_fact("2025-03-31", 100_000_000),
                            instant_fact("2025-06-30", 125_000_000),
                        ]
                    }
                }
            }
        )

        result = extract_balance_sheet_metrics(facts, "TEST", "0000000001", ["Cash"])

        self.assertEqual("2025-06-30", result.iloc[0]["As Of Date"])
        self.assertEqual(125.0, result.iloc[0]["Value ($ Millions)"])

    def test_main_pipeline_is_ticker_driven_and_fetches_companyfacts_once(self):
        directory = {
            "0": {"cik_str": 1, "ticker": "TEST", "title": "Test Company"}
        }
        facts = companyfacts(
            [
                duration_fact(
                    "2024-01-01", "2024-12-31", 1_000_000, "10-K", 2024, "FY"
                )
            ]
        )
        session = FakeSession(directory, facts)
        config = PipelineConfig.from_values(["test"], [2024], Path("template.xlsx"))

        result = run_pipeline(config, session=session, write_excel=False)

        self.assertFalse(result.ltm_metrics.empty)
        self.assertEqual({"TEST"}, set(result.ltm_metrics["Ticker"]))
        self.assertEqual(2, len(session.urls))
        self.assertIn("CIK0000000001.json", session.urls[-1])


if __name__ == "__main__":
    unittest.main()

