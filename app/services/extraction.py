"""Extract provider payment data from a signed settlement disbursement PDF.

Only providers listed under "Medical Providers Paid by Firm" are returned.
Providers under "Paid/Adjusted by MAP Insurance", "Given Directly to Client",
$0.00 payments, and "Reduced from"/parenthetical amounts are ignored.

Extraction is performed by Claude (preferred, when ANTHROPIC_API_KEY is set)
with a deterministic heuristic parser as a fallback so the app remains usable
without an API key.
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Optional

from pdfminer.high_level import extract_text

logger = logging.getLogger(__name__)

EXTRACTION_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")


@dataclass
class Provider:
    provider_name: str = ""
    address_line1: str = ""
    address_line2: str = ""
    account_number: str = ""
    payment_amount: str = ""  # dollar amount without the leading "$", e.g. "1,048.60"
    check_number: str = ""


@dataclass
class ExtractionResult:
    client_name: str = ""
    providers: list[Provider] = field(default_factory=list)
    used_llm: bool = False

    def to_dict(self) -> dict:
        return {
            "client_name": self.client_name,
            "providers": [asdict(p) for p in self.providers],
            "used_llm": self.used_llm,
        }


def pdf_to_text(data: bytes) -> str:
    return extract_text(io.BytesIO(data))


# --------------------------------------------------------------------------- #
# Claude-based extraction (preferred)
# --------------------------------------------------------------------------- #

_SYSTEM_PROMPT = """You extract medical-provider payment data from signed legal \
settlement disbursement documents for a law firm's billing staff.

You will be given the raw text of a settlement disbursement. Extract ONLY the \
providers that the firm is paying directly, listed under the heading \
"Medical Providers Paid by Firm" (the heading wording may vary slightly).

STRICT RULES:
- Include a provider ONLY if it appears under "Medical Providers Paid by Firm".
- IGNORE every provider under "Medical Providers Paid/Adjusted by MAP Insurance".
- IGNORE every provider under "Given Directly to Client" (or similar).
- IGNORE any provider whose payment amount is $0.00.
- For each included provider use the actual payment amount the firm is sending.
  IGNORE "Reduced from $X" amounts and ANY amount shown in parentheses.
- payment_amount must be the dollar figure WITHOUT the leading "$" or any
  parentheses, e.g. "1,048.60".
- Split the mailing address into address_line1 (street / PO box, including any
  suite) and address_line2 (city, state ZIP). If the address has only one line,
  put it in address_line1 and leave address_line2 empty.
- account_number is the value after "Account #" (digits/letters), or "" if none.
- Also extract the client's name from the disbursement (the "Client:" field).

Return data strictly via the provided output schema. If a section is absent,
return an empty providers list rather than guessing."""

_SCHEMA = {
    "type": "object",
    "properties": {
        "client_name": {"type": "string"},
        "providers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "provider_name": {"type": "string"},
                    "address_line1": {"type": "string"},
                    "address_line2": {"type": "string"},
                    "account_number": {"type": "string"},
                    "payment_amount": {"type": "string"},
                },
                "required": [
                    "provider_name",
                    "address_line1",
                    "address_line2",
                    "account_number",
                    "payment_amount",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["client_name", "providers"],
    "additionalProperties": False,
}


def _extract_with_claude(text: str) -> Optional[ExtractionResult]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=EXTRACTION_MODEL,
            max_tokens=4000,
            system=_SYSTEM_PROMPT,
            output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Here is the disbursement text. Extract the providers "
                        "paid by the firm.\n\n<disbursement>\n"
                        + text
                        + "\n</disbursement>"
                    ),
                }
            ],
        )
        if response.stop_reason == "refusal":
            logger.warning("Claude refused extraction; falling back to heuristic.")
            return None
        raw = next((b.text for b in response.content if b.type == "text"), "")
        data = json.loads(raw)
        providers = [
            Provider(
                provider_name=p.get("provider_name", "").strip(),
                address_line1=p.get("address_line1", "").strip(),
                address_line2=p.get("address_line2", "").strip(),
                account_number=p.get("account_number", "").strip(),
                payment_amount=_clean_amount(p.get("payment_amount", "")),
            )
            for p in data.get("providers", [])
        ]
        # Drop any $0.00 the model may have let through.
        providers = [p for p in providers if not _is_zero(p.payment_amount)]
        return ExtractionResult(
            client_name=data.get("client_name", "").strip(),
            providers=providers,
            used_llm=True,
        )
    except Exception:  # pragma: no cover - network/SDK errors
        logger.exception("Claude extraction failed; falling back to heuristic.")
        return None


# --------------------------------------------------------------------------- #
# Heuristic fallback parser
# --------------------------------------------------------------------------- #

_SECTION_HEADERS = [
    "medical providers paid by firm",
    "medical providers paid/adjusted by map",
    "medical providers paid / adjusted by map",
    "given directly to client",
    "net settlement",
    "release",
]
_AMOUNT_RE = re.compile(r"\$\s*([\d,]+\.\d{2})")
_ACCOUNT_RE = re.compile(r"account\s*#?\s*:?\s*([A-Za-z0-9\-]+)", re.I)


def _clean_amount(value: str) -> str:
    value = (value or "").strip().lstrip("$").strip()
    m = re.search(r"([\d,]+\.\d{2})", value)
    return m.group(1) if m else value


def _is_zero(amount: str) -> bool:
    digits = re.sub(r"[^\d.]", "", amount or "")
    try:
        return float(digits) == 0.0
    except ValueError:
        return False


_LABEL_WORDS = {"matter", "date", "cause", "client", "release", "gross"}


def _heuristic_client_name(text: str) -> str:
    # Litigation disbursements name the plaintiff in the cause line:
    # "Cause # D-1-GN-23-007739 Paula Perez v. Farmers ...".
    m = re.search(
        r"cause\s*#?\s*[\w\-]+\s+([A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+){0,3}?)\s+v\.",
        text,
        re.I,
    )
    if m:
        return re.sub(r"\s+", " ", m.group(1).strip())

    # Otherwise take the first proper-name line that follows a "Client" label,
    # skipping the other label words that share the column.
    m = re.search(r"client\s*:?(.*)", text, re.I | re.S)
    if m:
        for line in m.group(1).splitlines():
            line = line.strip()
            if not line or line.lower().rstrip(":") in _LABEL_WORDS:
                continue
            if re.fullmatch(r"[A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+){1,3}", line):
                return line
            break
    return ""


def _find_paid_by_firm_section(text: str) -> str:
    lower = text.lower()
    start = lower.find("medical providers paid by firm")
    if start == -1:
        return ""
    start = lower.find("\n", start)
    if start == -1:
        return ""
    end = len(text)
    for header in _SECTION_HEADERS:
        if header == "medical providers paid by firm":
            continue
        idx = lower.find(header, start)
        if idx != -1:
            end = min(end, idx)
    return text[start:end]


def _extract_heuristic(text: str) -> ExtractionResult:
    result = ExtractionResult(used_llm=False)
    result.client_name = _heuristic_client_name(text)

    section = _find_paid_by_firm_section(text)
    if not section:
        return result

    # Each provider block starts with a leading dash bullet ("- Name").
    blocks = re.split(r"\n\s*-\s+", section)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue

        # Payment amount = first $ amount that is not inside parentheses and
        # not a "reduced from" figure.
        amount = ""
        for ln in lines:
            if "(" in ln or "reduced from" in ln.lower():
                continue
            am = _AMOUNT_RE.search(ln)
            if am:
                amount = am.group(1)
                break
        if not amount or _is_zero(amount):
            continue

        name = lines[0]
        name = re.sub(r"\s*account\s*#.*$", "", name, flags=re.I).strip()
        name = _AMOUNT_RE.sub("", name).strip(" -:")

        account = ""
        am = _ACCOUNT_RE.search(block)
        if am:
            account = am.group(1).strip()

        # Address: non-name, non-account, non-amount lines.
        addr_lines: list[str] = []
        for ln in lines[1:]:
            low = ln.lower()
            if low.startswith("account"):
                continue
            if "(" in ln or "reduced from" in low:
                continue
            if _AMOUNT_RE.fullmatch(ln.replace("$", "$").strip()):
                continue
            if _AMOUNT_RE.search(ln) and not re.search(r"[A-Za-z]", ln):
                continue
            addr_lines.append(ln)

        line1 = addr_lines[0] if addr_lines else ""
        line2 = " ".join(addr_lines[1:]) if len(addr_lines) > 1 else ""

        result.providers.append(
            Provider(
                provider_name=name,
                address_line1=line1,
                address_line2=line2,
                account_number=account,
                payment_amount=amount,
            )
        )
    return result


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #

def extract_providers(pdf_bytes: bytes) -> ExtractionResult:
    text = pdf_to_text(pdf_bytes)
    result = _extract_with_claude(text)
    if result is not None:
        return result
    return _extract_heuristic(text)
