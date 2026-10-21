"""Extract benefit-relevant fields from an uploaded document (e.g. a CRA Notice of Assessment)
via a multimodal model. Degrades gracefully: with no provider key, returns available=False and
the person just enters the fields manually.
"""
from __future__ import annotations

import base64
import json
import logging
import re

from app import llm

log = logging.getLogger(__name__)

_PROMPT = (
    "You are reading a Canadian tax or benefit document (for example a CRA Notice of Assessment). "
    "Extract ONLY what is clearly printed. Return a single JSON object with any of these keys you find: "
    "first_name (string), province (2-letter code like ON/BC/QC), age (integer), "
    "annual_net_income (number, the person's net income, digits only). "
    "Omit any key you cannot read with confidence. Return ONLY the JSON object, nothing else."
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


def _sanitize(raw: dict) -> dict:
    out: dict = {}
    if raw.get("first_name"):
        out["first_name"] = str(raw["first_name"]).strip()[:40]
    if raw.get("province"):
        out["province"] = str(raw["province"]).strip()[:2].upper()
    if raw.get("age") not in (None, ""):
        try:
            out["age"] = int(float(raw["age"]))
        except (TypeError, ValueError):
            pass
    if raw.get("annual_net_income") not in (None, ""):
        try:
            out["annual_net_income"] = float(str(raw["annual_net_income"]).replace(",", "").replace("$", ""))
        except (TypeError, ValueError):
            pass
    return out


async def extract_profile_fields(image_bytes: bytes, content_type: str = "image/png") -> dict:
    if not llm.available():
        return {"available": False, "fields": {}, "detail": "LLM not configured"}
    try:
        data_url = f"data:{content_type};base64," + base64.b64encode(image_bytes).decode()
        resp = llm.chat_vision(_PROMPT, data_url, max_tokens=400)
        text = resp.choices[0].message.content or ""
        return {"available": True, "fields": _sanitize(_parse(text))}
    except Exception as exc:  # noqa: BLE001
        log.info("Document extraction failed: %s", type(exc).__name__)
        return {"available": False, "fields": {}, "detail": type(exc).__name__}
