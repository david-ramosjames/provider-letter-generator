"""Render one Word payment letter per provider from the firm's template."""

from __future__ import annotations

import os
import re

from docxtpl import DocxTemplate

TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "templates", "payment_letter_template.docx"
)


def _sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]+', " ", name or "").strip()
    name = re.sub(r"\s+", " ", name)
    return name or "Unknown"


def _amount_no_dollar(value: str) -> str:
    """Template already prints '$', so strip a leading '$' if present."""
    return (value or "").strip().lstrip("$").strip()


def output_filename(client_name: str, provider_name: str) -> str:
    client = _sanitize_filename(client_name) or "Client"
    provider = _sanitize_filename(provider_name) or "Provider"
    return f"{client} - {provider} - Payment Letter.docx"


def generate_letter(
    *,
    output_path: str,
    letter_date: str,
    provider_name: str,
    address_line1: str,
    address_line2: str,
    client_name: str,
    account_number: str,
    date_of_birth: str,
    date_of_loss: str,
    check_number: str,
    payment_amount: str,
) -> str:
    tpl = DocxTemplate(TEMPLATE_PATH)
    tpl.render(
        {
            "letter_date": letter_date or "",
            "provider_name": provider_name or "",
            "provider_address_line1": address_line1 or "",
            "provider_address_line2": address_line2 or "",
            "client_name": client_name or "",
            "account_number": account_number or "",
            "date_of_birth": date_of_birth or "",
            "date_of_loss": date_of_loss or "",
            "check_number": check_number or "",
            "payment_amount": _amount_no_dollar(payment_amount),
        }
    )
    tpl.save(output_path)
    return output_path
