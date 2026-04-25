from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class Thresholds:
    FETCH_TIMEOUT_SECONDS: int = 15
    LLM_TIMEOUT_SECONDS: int = 120
    GMAIL_PAGE_SIZE: int = 50
    CONCURRENCY: int = 3
    # Hard caps so a runaway run can't draft hundreds of replies/follow-ups
    MAX_REPLIES_PER_RUN: int = 25
    MAX_FOLLOWUPS_PER_RUN: int = 25


def llm_settings() -> dict:
    """Return OpenRouter API key + model. Raises if key missing."""
    load_dotenv()
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set in .env")
    model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash").strip()
    return {"api_key": key, "model": model}


@dataclass(frozen=True)
class Cadence:
    followup_1_days: int
    followup_2_days: int
    cold_days: int

    @classmethod
    def from_env(cls) -> "Cadence":
        load_dotenv()
        return cls(
            followup_1_days=int(os.getenv("FOLLOWUP_1_DAYS", "5")),
            followup_2_days=int(os.getenv("FOLLOWUP_2_DAYS", "12")),
            cold_days=int(os.getenv("COLD_DAYS", "25")),
        )


@dataclass(frozen=True)
class Config:
    google_sheet_id: str
    service_account_path: Path
    gmail_credentials_path: Path
    gmail_token_path: Path
    sender_name: str
    sender_agency_name: str
    sender_calendar_url: str
    cadence: Cadence

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
            cadence=Cadence.from_env(),
        )
