"""Plain-language explanation of a screening result.

The model phrases the 'why'; it does NOT decide eligibility (the rules engine already did).
Runs through the swappable provider (app/llm.py). With no provider key, a deterministic fallback
builds the summary from the rules' own reasons.
"""
from __future__ import annotations

import logging
from typing import Iterable

from app import llm

log = logging.getLogger(__name__)

_ACTIVE = ("eligible", "likely", "maybe")

_SYSTEM = ("You help a low-income Canadian senior understand benefits they may qualify for. "
           "Warm, plain language, grade-6 reading level. Do NOT change any eligibility decision "
           "or invent programs — only explain the findings given. End by reminding them a human "
           "confirms and submits; nothing is filed automatically.")


def _fallback(headline: str, results: Iterable) -> str:
    wins = [r for r in results if getattr(r, "eligibility", None) in _ACTIVE]
    lines = [headline, "", "Here's what I found and why:"]
    for r in wins:
        why = r.reasons[0] if getattr(r, "reasons", None) else ""
        lines.append(f"• {r.program_name}: {why}")
    lines += ["", "I've prepared these — you (or your caregiver) confirm and submit. "
                  "Nothing is ever filed automatically."]
    return "\n".join(lines)


async def explain(headline: str, results: list) -> str:
    if not llm.available():
        return _fallback(headline, results)
    try:
        facts = "\n".join(f"- {r.program_name} [{r.eligibility}]: {'; '.join(r.reasons)}" for r in results)
        resp = llm.chat(
            messages=[{"role": "system", "content": _SYSTEM},
                      {"role": "user", "content": f"{headline}\n\nFindings:\n{facts}"}],
            max_tokens=600,
        )
        return resp.choices[0].message.content or _fallback(headline, results)
    except Exception as exc:  # noqa: BLE001
        log.info("Explain unavailable (%s); using fallback.", type(exc).__name__)
        return _fallback(headline, results)
