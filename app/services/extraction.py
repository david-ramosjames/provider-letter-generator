"""Extract provider payment data from a signed settlement disbursement PDF.

Only providers listed under "Medical Providers Paid by Firm" are returned.
Providers under "Paid/Adjusted by MAP Insurance", "Given Directly to Client",
$0.00 payments, and "Reduced from"/parenthetical amounts are ignored.

These disbursements use a two-column layout: provider names sit in a left
column and the paid amount sits in a right column on the SAME row as the
provider name (the "Reduced from" figure is a row below, in parentheses).
Linear text extraction scrambles that association, so:

* the preferred path sends the PDF directly to Claude, which reads the visual
  layout (requires ANTHROPIC_API_KEY); and
* the fallback parser uses word coordinates (pdfplumber) to match each
  provider name to the dollar amount on its own row.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Optional

import pdfplumber

logger = logging.getLogger(__name__)

EXTRACTION_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")

# x-coordinate boundary between the left (name/address) and right (amount) columns.
COLUMN_SPLIT_X = 400
# Vertical tolerance (points) for treating words as being on the same row.
ROW_TOL = 6


@dataclass
class Provider:
    provider_name: str = ""
    address_line1: str = ""
    address_line2: str = ""
    account_number: str = ""
    payment_amount: str = ""  # dollar amount without the leading "$", e.g. "2,807.00"
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


# --------------------------------------------------------------------------- #
# Claude-based extraction (preferred) — PDF document input
# --------------------------------------------------------------------------- #

_SYSTEM_PROMPT = """You extract medical-provider payment data from signed legal \
settlement disbursement documents for a law firm's billing staff.

You will be given the disbursement PDF. Extract ONLY the providers the firm is \
paying directly, listed under the heading "Medical Providers Paid by Firm" (the \
wording may vary slightly).

LAYOUT: Amounts appear in a right-hand column. The amount the firm PAID is on the \
SAME line as the provider's name (the top figure for that provider). Directly \
below it, in parentheses, is a "Reduced from $X" figure — the amount BEFORE \
reduction. ALWAYS use the top figure (the amount paid), NEVER the "Reduced from" \
or any parenthesized amount.

STRICT RULES:
- Include a provider ONLY if it is under "Medical Providers Paid by Firm".
- IGNORE providers under "Medical Providers Paid/Adjusted by MAP Insurance".
- IGNORE providers under "Given Directly to Client" (or similar).
- IGNORE any provider whose paid amount is $0.00.
- IGNORE "Reduced from $X" amounts and ANY amount shown in parentheses.
- Do NOT confuse gross-settlement, attorney-fee, or case-expense amounts with
  provider payments.
- payment_amount = the paid dollar figure WITHOUT a leading "$" or parentheses,
  e.g. "2,807.00".
- Split the mailing address into address_line1 (street / PO box, incl. any suite)
  and address_line2 (city, state ZIP). One-line address -> address_line1 only.
- account_number = the value after "Account #", or "" if none is listed.
- Also extract the client's name (the "Client:" field).

Return data strictly via the provided output schema. If the section is absent,
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


def _extract_with_claude(pdf_bytes: bytes) -> Optional[ExtractionResult]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")
        response = client.messages.create(
            model=EXTRACTION_MODEL,
            max_tokens=4000,
            system=_SYSTEM_PROMPT,
            output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "Extract the providers paid by the firm from this "
                                "disbursement, using the amount on the same line as "
                                "each provider's name (not the reduced-from amount)."
                            ),
                        },
                    ],
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
# Helpers
# --------------------------------------------------------------------------- #

_AMOUNT_RE = re.compile(r"\$?\s*([\d,]+\.\d{2})")
_ACCOUNT_RE = re.compile(r"account\s*#?\s*:?\s*([A-Za-z0-9\-]+)", re.I)
_LABEL_WORDS = {"matter", "date", "cause", "client", "release", "gross"}

# Section headers that end the "paid by firm" section.
_END_HEADERS = [
    "medical providers paid/adjusted by map",
    "medical providers paid / adjusted by map",
    "given directly to client",
    "net settlement",
    "release",
]


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


# --------------------------------------------------------------------------- #
# Positional fallback parser (pdfplumber word coordinates)
# --------------------------------------------------------------------------- #

@dataclass
class _Line:
    page: int
    top: float
    words: list  # list of (x0, text)

    def text(self) -> str:
        return " ".join(t for _, t in sorted(self.words))

    def left_text(self) -> str:
        return " ".join(t for x, t in sorted(self.words) if x < COLUMN_SPLIT_X)

    def right_amount(self) -> str:
        """Paid amount in the right column on this row (not parenthesized)."""
        for x, t in sorted(self.words):
            if x < COLUMN_SPLIT_X:
                continue
            if "(" in t or ")" in t:
                continue
            m = _AMOUNT_RE.search(t)
            if m:
                return m.group(1)
        return ""


def _build_lines(pdf_bytes: bytes) -> tuple[list[_Line], str]:
    import io

    lines: list[_Line] = []
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for pi, page in enumerate(pdf.pages):
            text_parts.append(page.extract_text() or "")
            words = page.extract_words(use_text_flow=False)
            words.sort(key=lambda w: (round(w["top"]), w["x0"]))
            current: Optional[_Line] = None
            for w in words:
                top = w["top"]
                if current is None or abs(top - current.top) > ROW_TOL:
                    current = _Line(page=pi, top=top, words=[])
                    lines.append(current)
                current.words.append((w["x0"], w["text"]))
    return lines, "\n".join(text_parts)


def _global_index(lines: list[_Line], needle: str, start: int = 0) -> int:
    needle = needle.lower()
    for i in range(start, len(lines)):
        if needle in lines[i].text().lower():
            return i
    return -1


def _heuristic_client_name(full: str) -> str:
    # Litigation disbursements name the client in the cause/style line:
    # "Cause No. ...; Nodel Saunders vs. David Garza" or
    # "Cause # ... Paula Perez v. Farmers ...".
    m = re.search(
        r"cause\s*(?:no\.?|#)?\s*[\w\-.]+\s*;?\s*"
        r"([A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+){0,3}?)\s+(?:v\.|vs\.?)\b",
        full,
        re.I,
    )
    if m:
        return re.sub(r"\s+", " ", m.group(1).strip())
    # Otherwise the first proper-name line after the "Client" label, skipping the
    # other label words that share the column.
    m = re.search(r"client\s*:?(.*)", full, re.I | re.S)
    if m:
        for line in m.group(1).splitlines():
            line = line.strip()
            if not line or line.lower().rstrip(":") in _LABEL_WORDS:
                continue
            if re.fullmatch(r"[A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+){1,3}", line):
                return re.sub(r"\s+", " ", line)
            break
    return ""


def _extract_heuristic(pdf_bytes: bytes) -> ExtractionResult:
    lines, full_text = _build_lines(pdf_bytes)
    result = ExtractionResult(used_llm=False)
    result.client_name = _heuristic_client_name(full_text)

    start = _global_index(lines, "medical providers paid by firm")
    if start == -1:
        return result

    end = len(lines)
    for header in _END_HEADERS:
        idx = _global_index(lines, header, start + 1)
        if idx != -1:
            end = min(end, idx)

    section = lines[start + 1 : end]

    # A provider line starts with a "-" bullet in the left column and has a name.
    bullet_idxs = [
        i
        for i, ln in enumerate(section)
        if any(t == "-" and x < COLUMN_SPLIT_X for x, t in ln.words)
        and re.search(r"[A-Za-z]", ln.left_text().replace("-", "").strip())
    ]

    for n, bi in enumerate(bullet_idxs):
        ln = section[bi]
        name = ln.left_text()
        name = re.sub(r"^\s*-\s*", "", name).strip()
        name = _AMOUNT_RE.sub("", name).strip(" -:")

        amount = ln.right_amount()
        if not amount or _is_zero(amount):
            continue

        # Left-column detail lines until the next provider bullet.
        block_end = bullet_idxs[n + 1] if n + 1 < len(bullet_idxs) else len(section)
        account = ""
        addr_lines: list[str] = []
        for det in section[bi + 1 : block_end]:
            left = det.left_text().strip()
            if not left:
                continue
            am = _ACCOUNT_RE.search(left)
            if left.lower().startswith("account") and am:
                account = am.group(1).strip()
                continue
            addr_lines.append(left)

        result.providers.append(
            Provider(
                provider_name=name,
                address_line1=addr_lines[0] if addr_lines else "",
                address_line2=" ".join(addr_lines[1:]) if len(addr_lines) > 1 else "",
                account_number=account,
                payment_amount=amount,
            )
        )
    return result


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #

def extract_providers(pdf_bytes: bytes) -> ExtractionResult:
    result = _extract_with_claude(pdf_bytes)
    if result is not None:
        return result
    return _extract_heuristic(pdf_bytes)
