from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class Thresholds:
    BATCH_SIZE_DEFAULT: int = 5
    BATCH_SIZE_HARD_CAP: int = 20
    FETCH_TIMEOUT_SECONDS: int = 15
    FETCH_RETRIES: int = 1
    CONCURRENCY: int = 3
    CLAUDE_TIMEOUT_SECONDS: int = 120


@dataclass(frozen=True)
class Config:
    google_sheet_id: str
    service_account_path: Path
    gmail_credentials_path: Path
    gmail_token_path: Path
    sender_name: str
    sender_agency_name: str
    sender_calendar_url: str

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        required = [
            "GOOGLE_SHEET_ID",
            "GOOGLE_SERVICE_ACCOUNT_PATH",
            "GMAIL_OAUTH_CREDENTIALS_PATH",
            "GMAIL_TOKEN_PATH",
            "SENDER_NAME",
            "SENDER_AGENCY_NAME",
            "SENDER_CALENDAR_URL",
        ]
        missing = [k for k in required if not os.getenv(k)]
        if missing:
            raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

        return cls(
            google_sheet_id=os.environ["GOOGLE_SHEET_ID"],
            service_account_path=Path(os.environ["GOOGLE_SERVICE_ACCOUNT_PATH"]),
            gmail_credentials_path=Path(os.environ["GMAIL_OAUTH_CREDENTIALS_PATH"]),
            gmail_token_path=Path(os.environ["GMAIL_TOKEN_PATH"]),
            sender_name=os.environ["SENDER_NAME"],
            sender_agency_name=os.environ["SENDER_AGENCY_NAME"],
            sender_calendar_url=os.environ["SENDER_CALENDAR_URL"],
        )
