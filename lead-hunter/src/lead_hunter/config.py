from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class Thresholds:
    """Tunable scoring and filtering constants. Edit here, not inline."""

    REVIEWS_MIN: int = 10
    REVIEWS_DEAD_BELOW: int = 5
    RATING_MIN: float = 3.5
    RATING_REJECT_BELOW: float = 3.0

    SITE_SCORE_HOT_MIN: int = 6
    SITE_SCORE_WARM_MIN: int = 3
    SITE_SCORE_REJECT_MAX: int = 2

    MAX_RESULTS_HARD_CAP: int = 250

    FETCH_CONCURRENCY: int = 10
    FETCH_TIMEOUT_SECONDS: int = 15
    FETCH_RETRIES: int = 1


@dataclass(frozen=True)
class Config:
    apify_api_token: str
    google_sheet_id: str
    service_account_path: Path
    apify_max_cost_usd: float
    default_max_results: int

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        required = ["APIFY_API_TOKEN", "GOOGLE_SHEET_ID", "GOOGLE_SERVICE_ACCOUNT_PATH"]
        missing = [k for k in required if not os.getenv(k)]
        if missing:
            raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

        return cls(
            apify_api_token=os.environ["APIFY_API_TOKEN"],
            google_sheet_id=os.environ["GOOGLE_SHEET_ID"],
            service_account_path=Path(os.environ["GOOGLE_SERVICE_ACCOUNT_PATH"]),
            apify_max_cost_usd=float(os.getenv("APIFY_MAX_COST_USD", "5")),
            default_max_results=int(os.getenv("DEFAULT_MAX_RESULTS", "100")),
        )
