"""Look up case data in Supabase by case_number.

Reads cases.client_name, cases.date_of_incident, cases.date_of_birth.
Missing values are returned as empty strings so staff can fill them in manually.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import httpx
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)

DEFAULT_SUPABASE_URL = "https://mcczpwrmzemlqfsupquw.supabase.co"
SUPABASE_URL = os.environ.get("SUPABASE_URL", DEFAULT_SUPABASE_URL).rstrip("/")
# Accept either name; service role or anon key both work for a read.
SUPABASE_KEY = (
    os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_ANON_KEY")
    or ""
)


@dataclass
class CaseRecord:
    found: bool = False
    case_number: str = ""
    client_name: str = ""
    date_of_incident: str = ""  # formatted MM/DD/YYYY (Date of Loss)
    date_of_birth: str = ""  # formatted MM/DD/YYYY
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "found": self.found,
            "case_number": self.case_number,
            "client_name": self.client_name,
            "date_of_incident": self.date_of_incident,
            "date_of_birth": self.date_of_birth,
            "error": self.error,
        }


def _fmt_date(value: str | None) -> str:
    if not value:
        return ""
    try:
        return date_parser.parse(str(value)).strftime("%m/%d/%Y")
    except (ValueError, OverflowError, TypeError):
        return str(value)


def lookup_case(case_number: str) -> CaseRecord:
    case_number = (case_number or "").strip()
    record = CaseRecord(case_number=case_number)
    if not case_number:
        return record
    if not SUPABASE_KEY:
        record.error = (
            "Supabase key not configured (set SUPABASE_KEY). "
            "Enter case fields manually."
        )
        return record

    url = f"{SUPABASE_URL}/rest/v1/cases"
    params = {
        "case_number": f"eq.{case_number}",
        "select": "case_number,client_name,date_of_incident,date_of_birth",
        "limit": "1",
    }
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": "application/json",
    }
    try:
        resp = httpx.get(url, params=params, headers=headers, timeout=15.0)
        resp.raise_for_status()
        rows = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("Supabase lookup HTTP %s", exc.response.status_code)
        record.error = f"Supabase lookup failed (HTTP {exc.response.status_code})."
        return record
    except Exception as exc:  # pragma: no cover - network errors
        logger.exception("Supabase lookup failed")
        record.error = f"Supabase lookup failed: {exc}"
        return record

    if not rows:
        record.error = "No case found for that case number. Enter fields manually."
        return record

    row = rows[0]
    record.found = True
    record.client_name = (row.get("client_name") or "").strip()
    record.date_of_incident = _fmt_date(row.get("date_of_incident"))
    record.date_of_birth = _fmt_date(row.get("date_of_birth"))
    return record
