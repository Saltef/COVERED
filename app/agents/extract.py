"""Extract benefit-relevant fields from an uploaded document (e.g. a CRA Notice of Assessment)
via a multimodal model, so a busy person can upload what they already have instead of typing.

Privacy and honesty by design:
- Net income (line 23600) is the priority field; it drives most eligibility.
- The Social Insurance Number is never extracted or returned. The prompt forbids it and a guard
  strips any 9-digit number the model might return anyway.
- The result carries a plain "read" line (what we saw) and the tax year, so the person confirms
  the number before it is used. A stale year is flagged, not silently trusted.
- Degrades gracefully: with no provider key, returns available=False and the person types the
  fields manually.

Document data is the person's own and stays in our own storage. It is never sent to Agent Memory.
"""
from __future__ import annotations

import base64
import datetime as _dt
import json
import logging
import re

from app import llm

log = logging.getLogger(__name__)

# The latest tax year a person could have a Notice of Assessment for (filed the following year).
def _latest_tax_year() -> int:
    return _dt.date.today().year - 1


_PROMPT = (
    "You are reading a Canadian tax or benefit document, for example a CRA Notice of Assessment. "
    "Extract ONLY what is clearly printed. Return a single JSON object with any of these keys you find:\n"
    "  net_income (number, line 23600 'net income', digits only; this is the priority field)\n"
    "  total_income (number, line 15000, digits only)\n"
    "  tax_year (4-digit year this assessment is for)\n"
    "  province (2-letter code like ON/BC/QC)\n"
    "  age (integer, only if a birth year or age is clearly printed)\n"
    "Omit any key you cannot read with confidence. "
    "NEVER return a Social Insurance Number or any 9-digit personal identifier; ignore it completely. "
    "Return ONLY the JSON object, nothing else."
)


def _parse(text: str) -> dict:
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        return {}
    try:
        data = json.loads(match.group())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _num(v) -> float | None:
    if v in (None, ""):
        return None
    try:
        return float(str(v).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


def _looks_like_sin(v) -> bool:
    """A bare 9-digit number is almost certainly a SIN, not an income. Refuse it."""
    digits = re.sub(r"[^\d]", "", str(v))
    return len(digits) == 9


def _sanitize(raw: dict) -> tuple[dict, int | None]:
    """Return (profile_fields, tax_year). Drops anything out of a sane range or SIN-shaped."""
    fields: dict = {}

    # Net income is the priority; total income is a fallback for the engine's income input.
    net = _num(raw.get("net_income"))
    total = _num(raw.get("total_income"))
    income = net if net is not None else total
    if income is not None and not _looks_like_sin(raw.get("net_income") or raw.get("total_income")):
        if 0 <= income <= 10_000_000:   # reject nonsense; a SIN-as-number would be ~9 digits = too big
            fields["annual_net_income"] = income

    if raw.get("province"):
        prov = str(raw["province"]).strip()[:2].upper()
        if prov.isalpha():
            fields["province"] = prov

    age = raw.get("age")
    if age not in (None, ""):
        try:
            a = int(float(age))
            if 0 < a < 120:
                fields["age"] = a
        except (TypeError, ValueError):
            pass

    tax_year = None
    ty = _num(raw.get("tax_year"))
    if ty is not None and 2000 <= ty <= _dt.date.today().year:
        tax_year = int(ty)

    return fields, tax_year


def _read_line(fields: dict, tax_year: int | None) -> str:
    """A plain sentence the person confirms before we use the numbers."""
    parts = []
    if "annual_net_income" in fields:
        parts.append(f"net income ${fields['annual_net_income']:,.0f}")
    if "province" in fields:
        parts.append(f"province {fields['province']}")
    if "age" in fields:
        parts.append(f"age {fields['age']}")
    if not parts:
        return "We could not read the key fields. Please enter them yourself."
    src = f"your {tax_year} Notice of Assessment" if tax_year else "your document"
    return f"From {src} we read " + ", ".join(parts) + ". Please confirm this is right."


async def extract_profile_fields(image_bytes: bytes, content_type: str = "image/png") -> dict:
    if not llm.available():
        return {"available": False, "fields": {}, "detail": "LLM not configured"}
    if content_type and "pdf" in content_type.lower():
        # The vision model takes images, not PDFs. Ask for a photo or screenshot instead.
        return {"available": True, "fields": {},
                "detail": "Please upload a photo or screenshot of the page, not a PDF."}
    try:
        data_url = f"data:{content_type};base64," + base64.b64encode(image_bytes).decode()
        resp = llm.chat_vision(_PROMPT, data_url, max_tokens=400)
        text = resp.choices[0].message.content or ""
        fields, tax_year = _sanitize(_parse(text))
        stale = tax_year is not None and tax_year < _latest_tax_year() - 1
        return {
            "available": True,
            "fields": fields,
            "tax_year": tax_year,
            "stale": stale,       # income may be out of date; confirm before relying on it
            "read": _read_line(fields, tax_year),
        }
    except Exception as exc:  # noqa: BLE001
        log.info("Document extraction failed: %s", type(exc).__name__)
        return {"available": False, "fields": {}, "detail": type(exc).__name__}
