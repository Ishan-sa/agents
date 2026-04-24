from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

Tier = Literal["hot", "warm"]
EmailConfidence = Literal["high", "medium", "low", "none"]


class Business(BaseModel):
    """Raw Google Maps record, pre-qualification."""

    model_config = ConfigDict(frozen=True)

    name: str
    address: str
    phone: str | None
    website: str | None
    maps_rating: float
    maps_reviews: int
    permanently_closed: bool

    def dedup_keys(self) -> set[str]:
        keys: set[str] = set()
        if self.website:
            keys.add(f"website:{self.website}")
        if self.phone:
            keys.add(f"phone:{self.phone}")
        return keys


class Lead(BaseModel):
    model_config = ConfigDict(frozen=True)

    date_added: datetime
    source_run: str
    business_name: str
    niche: str
    city: str
    address: str
    phone: str | None
    website: str | None
    maps_rating: float
    maps_reviews: int
    site_score: int
    site_evidence: str
    owner_name_guess: str
    email_guess: str
    email_confidence: EmailConfidence
    contact_form_url: str
    linkedin_url: str
    lead_pitch: str
    tier: Tier
    site_unreachable: bool

    @classmethod
    def sheet_columns(cls) -> list[str]:
        return [
            "date_added", "source_run", "business_name", "niche", "city",
            "address", "phone", "website", "maps_rating", "maps_reviews",
            "site_score", "site_evidence", "owner_name_guess", "email_guess",
            "email_confidence", "contact_form_url", "linkedin_url", "lead_pitch",
            "site_unreachable", "tier", "status",
        ]

    def to_sheet_row(self) -> list[str]:
        return [
            self.date_added.isoformat(),
            self.source_run,
            self.business_name,
            self.niche,
            self.city,
            self.address,
            self.phone or "",
            self.website or "",
            f"{self.maps_rating:.1f}",
            str(self.maps_reviews),
            str(self.site_score),
            self.site_evidence,
            self.owner_name_guess,
            self.email_guess,
            self.email_confidence,
            self.contact_form_url,
            self.linkedin_url,
            self.lead_pitch,
            "TRUE" if self.site_unreachable else "FALSE",
            self.tier,
            "",  # status column reserved
        ]


class RejectedLead(BaseModel):
    model_config = ConfigDict(frozen=True)

    date_added: datetime
    source_run: str
    business_name: str
    niche: str
    city: str
    address: str
    phone: str | None
    website: str | None
    maps_rating: float
    maps_reviews: int
    site_score: int | None  # None if rejected pre-scoring (e.g., closed)
    reject_reason: str

    @classmethod
    def sheet_columns(cls) -> list[str]:
        return [
            "date_added", "source_run", "business_name", "niche", "city",
            "address", "phone", "website", "maps_rating", "maps_reviews",
            "site_score", "reject_reason",
        ]

    def to_sheet_row(self) -> list[str]:
        return [
            self.date_added.isoformat(),
            self.source_run,
            self.business_name,
            self.niche,
            self.city,
            self.address,
            self.phone or "",
            self.website or "",
            f"{self.maps_rating:.1f}",
            str(self.maps_reviews),
            "" if self.site_score is None else str(self.site_score),
            self.reject_reason,
        ]


class Run(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    date: datetime
    niche: str
    city: str
    max_results: int
    apify_results: int
    new_after_dedup: int
    qualified: int
    rejected: int
    apify_cost_usd: float
    duration_seconds: float
    notes: str

    @classmethod
    def sheet_columns(cls) -> list[str]:
        return [
            "run_id", "date", "niche", "city", "max_results",
            "apify_results", "new_after_dedup", "qualified", "rejected",
            "apify_cost_usd", "duration_seconds", "notes",
        ]

    def to_sheet_row(self) -> list[str]:
        return [
            self.run_id,
            self.date.isoformat(),
            self.niche,
            self.city,
            str(self.max_results),
            str(self.apify_results),
            str(self.new_after_dedup),
            str(self.qualified),
            str(self.rejected),
            f"{self.apify_cost_usd:.4f}",
            f"{self.duration_seconds:.1f}",
            self.notes,
        ]
