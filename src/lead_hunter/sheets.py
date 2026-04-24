from __future__ import annotations

from pathlib import Path

import gspread

from .models import Lead, RejectedLead, Run

LEADS = "Leads"
REJECTED = "Rejected"
RUNS = "Runs"


class SheetsClient:
    def __init__(self, spread):
        self._spread = spread

    @classmethod
    def from_credentials(cls, service_account_path: Path, sheet_id: str) -> "SheetsClient":
        gc = gspread.service_account(filename=str(service_account_path))
        spread = gc.open_by_key(sheet_id)
        return cls(spread=spread)

    def ensure_schema(self) -> None:
        existing = {ws.title for ws in self._spread.worksheets()}
        specs = [
            (LEADS, Lead.sheet_columns()),
            (REJECTED, RejectedLead.sheet_columns()),
            (RUNS, Run.sheet_columns()),
        ]
        for name, headers in specs:
            if name not in existing:
                ws = self._spread.add_worksheet(title=name, rows=1000, cols=len(headers))
                ws.update(range_name="A1", values=[headers])
            else:
                ws = self._spread.worksheet(name)
                first_row = ws.row_values(1)
                if first_row != headers:
                    ws.update(range_name="A1", values=[headers])

    def existing_dedup_keys(self) -> set[str]:
        keys: set[str] = set()
        for name in (LEADS, REJECTED):
            try:
                ws = self._spread.worksheet(name)
            except gspread.WorksheetNotFound:
                continue
            for row in ws.get_all_records():
                website = (row.get("website") or "").strip()
                phone = (row.get("phone") or "").strip()
                if website:
                    keys.add(f"website:{website}")
                if phone:
                    keys.add(f"phone:{phone}")
        return keys

    def append(
        self,
        leads: list[Lead],
        rejected: list[RejectedLead],
        run: Run,
    ) -> None:
        if leads:
            self._spread.worksheet(LEADS).append_rows(
                [lead.to_sheet_row() for lead in leads],
                value_input_option="RAW",
            )
        if rejected:
            self._spread.worksheet(REJECTED).append_rows(
                [r.to_sheet_row() for r in rejected],
                value_input_option="RAW",
            )
        self._spread.worksheet(RUNS).append_row(
            run.to_sheet_row(),
            value_input_option="RAW",
        )
