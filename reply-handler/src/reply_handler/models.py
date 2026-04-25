from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ReplyClass = Literal[
    "interested",
    "question",
    "declined",
    "auto_reply",
    "none",
]


# Sheet status values (the existing outreach-agent uses "drafted" / "sent" /
# "skipped"). reply-handler extends this set:
#
#   drafted               (set by outreach-agent)
#   sent                  (set by reply-handler sync-sent)
#   replied_interested
#   replied_question
#   replied_declined
#   replied_auto_reply
#   followup_1_drafted
#   followup_2_drafted
#   cold


class TrackedLead(BaseModel):
    """A row from the Leads tab that reply-handler cares about. Includes the
    columns reply-handler reads/writes, plus a few from outreach-agent for
    context when drafting."""

    model_config = ConfigDict(frozen=True)

    row_number: int
    business_name: str
    niche: str
    city: str
    website: str
    email_guess: str
    owner_name_guess: str
    site_evidence: str
    lead_pitch: str
    subject_line: str         # set by outreach-agent
    status: str
    gmail_draft_id: str       # set by outreach-agent
    date_drafted: str         # ISO string, may be empty
    # populated as the lifecycle progresses
    date_sent: str
    gmail_thread_id: str
    gmail_message_id: str
    last_reply_date: str
    reply_class: str
    reply_draft_id: str
    followup_count: str       # "0" | "1" | "2"
    last_followup_date: str
    last_followup_draft_id: str

    def followup_count_int(self) -> int:
        try:
            return int(self.followup_count or "0")
        except ValueError:
            return 0


class LeadUpdate(BaseModel):
    """A pending update to one row in the Leads tab."""

    model_config = ConfigDict(frozen=True)

    row_number: int
    values: dict[str, str]

    @classmethod
    def sent(
        cls,
        *,
        row_number: int,
        date_sent: datetime,
        thread_id: str,
        message_id: str,
    ) -> "LeadUpdate":
        return cls(
            row_number=row_number,
            values={
                "status": "sent",
                "date_sent": date_sent.isoformat(),
                "gmail_thread_id": thread_id,
                "gmail_message_id": message_id,
            },
        )

    @classmethod
    def replied(
        cls,
        *,
        row_number: int,
        reply_class: ReplyClass,
        last_reply_date: datetime,
        reply_draft_id: str,
    ) -> "LeadUpdate":
        return cls(
            row_number=row_number,
            values={
                "status": f"replied_{reply_class}",
                "reply_class": reply_class,
                "last_reply_date": last_reply_date.isoformat(),
                "reply_draft_id": reply_draft_id,
            },
        )

    @classmethod
    def followup(
        cls,
        *,
        row_number: int,
        followup_number: int,
        date: datetime,
        draft_id: str,
    ) -> "LeadUpdate":
        return cls(
            row_number=row_number,
            values={
                "status": f"followup_{followup_number}_drafted",
                "followup_count": str(followup_number),
                "last_followup_date": date.isoformat(),
                "last_followup_draft_id": draft_id,
            },
        )

    @classmethod
    def cold(cls, *, row_number: int) -> "LeadUpdate":
        return cls(row_number=row_number, values={"status": "cold"})


class ReplyClassification(BaseModel):
    """LLM output: how the inbound reply should be categorized + what to draft
    back."""

    model_config = ConfigDict(frozen=True)

    reply_class: ReplyClass
    draft_subject: str   # usually "Re: <orig>" — keep what the LLM returns
    draft_body: str
    skip_reason: str = ""

    def should_draft(self) -> bool:
        return self.reply_class in ("interested", "question", "declined")


class FollowupContent(BaseModel):
    """LLM output: a follow-up nudge body."""

    model_config = ConfigDict(frozen=True)

    subject: str   # typically "Re: <orig>"
    body: str


class ReplyHandlerRun(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    date: datetime
    job: str   # "sync-sent" | "check-replies" | "follow-ups" | "all"
    sent_synced: int
    replies_drafted: int
    followups_drafted: int
    marked_cold: int
    errors: int
    duration_seconds: float
    dry_run: bool
    notes: str

    @classmethod
    def sheet_columns(cls) -> list[str]:
        return [
            "run_id", "date", "job",
            "sent_synced", "replies_drafted", "followups_drafted", "marked_cold",
            "errors", "duration_seconds", "dry_run", "notes",
        ]

    def to_sheet_row(self) -> list[str]:
        return [
            self.run_id,
            self.date.isoformat(),
            self.job,
            str(self.sent_synced),
            str(self.replies_drafted),
            str(self.followups_drafted),
            str(self.marked_cold),
            str(self.errors),
            f"{self.duration_seconds:.1f}",
            "TRUE" if self.dry_run else "FALSE",
            self.notes,
        ]
