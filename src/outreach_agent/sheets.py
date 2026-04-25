from __future__ import annotations

from pathlib import Path

import gspread

from .models import EligibleLead, LeadUpdate, OutreachRun, Tier

LEADS = "Leads"
OUTREACH_RUNS = "Outreach_Runs"

NEW_LEAD_COLUMNS = ["date_drafted", "subject_line", "gmail_draft_id", "skip_reason"]


def _col_letter(col_index_1based: int) -> str:
    """Convert 1-indexed column number to A1-style letter (1 → 'A', 27 → 'AA')."""
    letters = ""
    n = col_index_1based
    while n > 0:
        n, r = divmod(n - 1, 26)
        letters = chr(65 + r) + letters
    return letters


class OutreachSheets:
    def __init__(self, spread):
        self._spread = spread

    @classmethod
    def from_credentials(cls, service_account_path: Path, sheet_id: str) -> "OutreachSheets":
        gc = gspread.service_account(filename=str(service_account_path))
        return cls(spread=gc.open_by_key(sheet_id))

    def ensure_schema(self) -> None:
        """Add missing columns to Leads, create Outreach_Runs tab if absent."""
        leads_ws = self._spread.worksheet(LEADS)
        existing_headers = leads_ws.row_values(1)
        missing = [c for c in NEW_LEAD_COLUMNS if c not in existing_headers]
        if missing:
            new_headers = existing_headers + missing
            leads_ws.update(range_name="A1", values=[new_headers])

        try:
            self._spread.worksheet(OUTREACH_RUNS)
        except gspread.WorksheetNotFound:
            ws = self._spread.add_worksheet(
                title=OUTREACH_RUNS, rows=1000, cols=len(OutreachRun.sheet_columns())
            )
            ws.update(range_name="A1", values=[OutreachRun.sheet_columns()])

    def read_eligible_leads(
        self,
        niche: str | None = None,
        city: str | None = None,
        tier: str | None = None,
    ) -> list[EligibleLead]:
        leads_ws = self._spread.worksheet(LEADS)
        rows = leads_ws.get_all_values()
        if len(rows) < 2:
            return []
        headers = rows[0]
        idx = {h: i for i, h in enumerate(headers)}

        eligible: list[EligibleLead] = []
        for row_offset, raw in enumerate(rows[1:], start=2):  # row 2 is first data row
            def col(name: str) -> str:
                i = idx.get(name)
                return raw[i] if i is not None and i < len(raw) else ""

            status = col("status").strip()
            if status:
                continue  # already drafted/sent/skipped

            email = col("email_guess").strip()
            form_url = col("contact_form_url").strip()
            has_email = bool(email)
            has_abs_form = form_url.lower().startswith(("http://", "https://"))
            if not (has_email or has_abs_form):
                continue

            tier_raw = col("tier").strip().lower()
            if tier_raw not in ("hot", "warm"):
                continue

            if niche and col("niche").strip().lower() != niche.lower():
                continue
            if city and col("city").strip().lower() != city.lower():
                continue
            if tier and tier_raw != tier.lower():
                continue

            try:
                site_score = int(col("site_score") or "0")
            except ValueError:
                site_score = 0

            eligible.append(EligibleLead(
                row_number=row_offset,
                business_name=col("business_name"),
                niche=col("niche"),
                city=col("city"),
                website=col("website"),
                email_guess=email,
                contact_form_url=form_url,
                owner_name_guess=col("owner_name_guess"),
                site_score=site_score,
                site_evidence=col("site_evidence"),
                lead_pitch=col("lead_pitch"),
                tier=tier_raw,  # type: ignore[arg-type]
            ))

        # tier=hot first, then site_score desc
        eligible.sort(key=lambda l: (0 if l.tier == "hot" else 1, -l.site_score))
        return eligible

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

    def append_run(self, run: OutreachRun) -> None:
        ws = self._spread.worksheet(OUTREACH_RUNS)
        ws.append_row(run.to_sheet_row(), value_input_option="RAW")
