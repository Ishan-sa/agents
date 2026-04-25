from __future__ import annotations

from pathlib import Path

import gspread

from .models import LeadUpdate, ReplyHandlerRun, TrackedLead

LEADS = "Leads"
RUNS = "Reply_Handler_Runs"

# Columns reply-handler adds to the Leads tab if they're not already present.
NEW_LEAD_COLUMNS = [
    "date_sent",
    "gmail_thread_id",
    "gmail_message_id",
    "last_reply_date",
    "reply_class",
    "reply_draft_id",
    "followup_count",
    "last_followup_date",
    "last_followup_draft_id",
]


def _col_letter(col_index_1based: int) -> str:
    letters = ""
    n = col_index_1based
    while n > 0:
        n, r = divmod(n - 1, 26)
        letters = chr(65 + r) + letters
    return letters


class ReplyHandlerSheets:
    def __init__(self, spread):
        self._spread = spread

    @classmethod
    def from_credentials(
        cls, service_account_path: Path, sheet_id: str
    ) -> "ReplyHandlerSheets":
        gc = gspread.service_account(filename=str(service_account_path))
        return cls(spread=gc.open_by_key(sheet_id))

    def ensure_schema(self) -> None:
        """Add reply-handler columns to Leads, create Reply_Handler_Runs tab."""
        leads_ws = self._spread.worksheet(LEADS)
        existing_headers = leads_ws.row_values(1)
        missing = [c for c in NEW_LEAD_COLUMNS if c not in existing_headers]
        if missing:
            new_headers = existing_headers + missing
            leads_ws.update(range_name="A1", values=[new_headers])

        try:
            self._spread.worksheet(RUNS)
        except gspread.WorksheetNotFound:
            ws = self._spread.add_worksheet(
                title=RUNS, rows=1000, cols=len(ReplyHandlerRun.sheet_columns())
            )
            ws.update(range_name="A1", values=[ReplyHandlerRun.sheet_columns()])

    def _read_all(self) -> tuple[list[str], list[list[str]]]:
        leads_ws = self._spread.worksheet(LEADS)
        rows = leads_ws.get_all_values()
        if not rows:
            return [], []
        return rows[0], rows[1:]

    def _row_to_tracked(
        self, row_number: int, headers: list[str], raw: list[str]
    ) -> TrackedLead:
        idx = {h: i for i, h in enumerate(headers)}

        def col(name: str) -> str:
            i = idx.get(name)
            return raw[i] if i is not None and i < len(raw) else ""

        return TrackedLead(
            row_number=row_number,
            business_name=col("business_name"),
            niche=col("niche"),
            city=col("city"),
            website=col("website"),
            email_guess=col("email_guess"),
            owner_name_guess=col("owner_name_guess"),
            site_evidence=col("site_evidence"),
            lead_pitch=col("lead_pitch"),
            subject_line=col("subject_line"),
            status=col("status").strip(),
            gmail_draft_id=col("gmail_draft_id"),
            date_drafted=col("date_drafted"),
            date_sent=col("date_sent"),
            gmail_thread_id=col("gmail_thread_id"),
            gmail_message_id=col("gmail_message_id"),
            last_reply_date=col("last_reply_date"),
            reply_class=col("reply_class"),
            reply_draft_id=col("reply_draft_id"),
            followup_count=col("followup_count"),
            last_followup_date=col("last_followup_date"),
            last_followup_draft_id=col("last_followup_draft_id"),
        )

    def read_leads_with_status(self, statuses: set[str]) -> list[TrackedLead]:
        headers, data = self._read_all()
        if not headers:
            return []
        out: list[TrackedLead] = []
        for offset, raw in enumerate(data, start=2):
            tl = self._row_to_tracked(offset, headers, raw)
            if tl.status in statuses:
                out.append(tl)
        return out

    def apply_lead_updates(self, updates: list[LeadUpdate]) -> None:
        if not updates:
            return
        leads_ws = self._spread.worksheet(LEADS)
        headers = leads_ws.row_values(1)
        col_index = {h: i + 1 for i, h in enumerate(headers)}

        payload = []
        for upd in updates:
            for col_name, value in upd.values.items():
                if col_name not in col_index:
                    continue
                cell = f"{_col_letter(col_index[col_name])}{upd.row_number}"
                payload.append({"range": cell, "values": [[value]]})

        if payload:
            leads_ws.batch_update(payload, value_input_option="RAW")

    def append_run(self, run: ReplyHandlerRun) -> None:
        ws = self._spread.worksheet(RUNS)
        ws.append_row(run.to_sheet_row(), value_input_option="RAW")
