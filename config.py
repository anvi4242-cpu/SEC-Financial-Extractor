"""User-editable configuration for the SEC Financial Extractor.

Only edit the three values under USER SETTINGS. Everything else is an
internal pipeline default.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


# ---------------------------------------------------------------------------
# USER SETTINGS — these are the only values a normal run needs to change.
# ---------------------------------------------------------------------------
tickers = ["CLF"]
target_years = [2024, 2025]
excel_template_path = "my_template.xlsx"


@dataclass(frozen=True)
class PipelineConfig:
    """Validated runtime configuration shared by every pipeline stage."""

    tickers: tuple[str, ...]
    target_years: tuple[int, ...]
    excel_template_path: Path
    sec_user_agent: str = "SEC Financial Extractor bhavika.gupta@r9wealth.com"
    request_timeout_seconds: int = 30

    @classmethod
    def from_values(
        cls,
        ticker_values: Sequence[str],
        year_values: Sequence[int],
        template_path: str | Path,
    ) -> "PipelineConfig":
        normalized_tickers = tuple(
            dict.fromkeys(value.upper().strip() for value in ticker_values if value.strip())
        )
        normalized_years = tuple(sorted({int(value) for value in year_values}))

        if not normalized_tickers:
            raise ValueError("At least one ticker is required.")
        if not normalized_years:
            raise ValueError("At least one target year is required.")

        return cls(
            tickers=normalized_tickers,
            target_years=normalized_years,
            excel_template_path=Path(template_path),
        )


CONFIG = PipelineConfig.from_values(tickers, target_years, excel_template_path)

