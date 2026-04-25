from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

Tier = Literal["hot", "warm"]
Action = Literal["draft", "skip"]


class EligibleLead(BaseModel):
    """A lead read from the Sheet that is eligible for drafting."""

    model_config = ConfigDict(frozen=True)

    row_number: int            # 1-indexed; row 1 is header, first data row is 2
    business_name: str
    niche: str
    city: str
    website: str
    email_guess: str
    contact_form_url: str
    owner_name_guess: str
    site_score: int
    site_evidence: str
    lead_pitch: str
    tier: Tier

    def has_email(self) -> bool:
        return bool(self.email_guess.strip())

    def has_absolute_form_url(self) -> bool:
        return self.contact_form_url.strip().lower().startswith(("http://", "https://"))


class DraftResult(BaseModel):
    """What the Claude draft-writer returns."""

    model_config = ConfigDict(frozen=True)

    action: Action
    subject: str
    body: str
    skip_reason: str

    def is_draft(self) -> bool:
        return self.action == "draft"

    def is_skip(self) -> bool:
        return self.action == "skip"


class LeadUpdate(BaseModel):
    """A pending update to one row in the Leads tab. Built via factory methods
    so all fields are populated correctly for each transition."""

    model_config = ConfigDict(frozen=True)

    row_number: int
    values: dict[str, str]  # column_name -> string value

    @classmethod
    def drafted(
        cls,
        *,
        row_number: int,
        date_drafted: datetime,
        subject_line: str,
        gmail_draft_id: str,
    ) -> "LeadUpdate":
        return cls(
            row_number=row_number,
            values={
                "status": "drafted",
                "date_drafted": date_drafted.isoformat(),
                "subject_line": subject_line,
                "gmail_draft_id": gmail_draft_id,
                "skip_reason": "",
            },
        )

    @classmethod
    def skipped(
        cls,
        *,
        row_number: int,
        date_drafted: datetime,
        skip_reason: str,
    ) -> "LeadUpdate":
        return cls(
            row_number=row_number,
            values={
                "status": "skipped",
                "date_drafted": date_drafted.isoformat(),
                "subject_line": "",
                "gmail_draft_id": "",
                "skip_reason": skip_reason,
            },
        )


class OutreachRun(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    date: datetime
    batch_size: int
    filter_niche: str
    filter_city: str
    filter_tier: str
    eligible_count: int
    drafted: int
    skipped: int
    errors: int
    duration_seconds: float
    dry_run: bool
    notes: str

    @classmethod
    def sheet_columns(cls) -> list[str]:
        return [
            "run_id", "date", "batch_size",
            "filter_niche", "filter_city", "filter_tier",
            "eligible_count", "drafted", "skipped", "errors",
            "duration_seconds", "dry_run", "notes",
        ]

    def to_sheet_row(self) -> list[str]:
        return [
            self.run_id,
            self.date.isoformat(),
            str(self.batch_size),
            self.filter_niche,
            self.filter_city,
            self.filter_tier,
            str(self.eligible_count),
            str(self.drafted),
            str(self.skipped),
            str(self.errors),
            f"{self.duration_seconds:.1f}",
            "TRUE" if self.dry_run else "FALSE",
            self.notes,
        ]
