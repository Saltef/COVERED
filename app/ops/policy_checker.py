"""AI policy-drift checker: re-reads each official source and flags when the live page disagrees
with the engine's encoded value.

Pipeline, all Cohere:
  1. fetch the source page and reduce it to text passages (keep only passages with a number).
  2. rerank the passages against the parameter's query to find the one that states it.
  3. extract the value from the top passages, grounded, with a VERBATIM quote.
  4. compare to the registry value: match / mismatch / unverified.

It never changes a rule. It produces a report for human review. No quote means unverified, not a
mismatch, which is the guard against the model inventing a number.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from app.config import get_settings
from app.domain.policy_registry import REGISTRY, Rule

log = logging.getLogger(__name__)

RERANK_MODEL = "rerank-v3.5"
CHAT_MODEL = "command-a-03-2025"
UA = {"User-Agent": "Mozilla/5.0 (compatible; CoveredPolicyChecker/1.0)"}


@dataclass
class CheckResult:
    id: str
    label: str
    engine_value: float
    extracted_value: float | None
    quote: str
    status: str          # "match" | "mismatch" | "unverified"
    detail: str = ""
    confidence: str = ""     # "high" | "low" (from the verifier agent)
    verifier_note: str = ""


def available() -> bool:
    return bool(get_settings().cohere_api_key)


def _client():
    import cohere
    return cohere.ClientV2(api_key=get_settings().cohere_api_key)


def _fetch_passages(url: str) -> list[str]:
    """Fetch the page, strip to text, split into passages, keep only those containing a number."""
    import httpx
    with httpx.Client(timeout=30, follow_redirects=True, headers=UA) as c:
        html = c.get(url).text
    html = re.sub(r"(?is)<(script|style|noscript|head).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"[ \t]+", " ", text)
    # split into passages on blank lines / sentence-ish boundaries
    raw = re.split(r"(?:\n\s*){2,}|(?<=\.)\s{2,}", text)
    passages, buf = [], ""
    for seg in raw:
        seg = seg.strip()
        if not seg:
            continue
        buf = (buf + " " + seg).strip() if len(buf) < 300 else buf
        if len(buf) >= 300 or seg is raw[-1]:
            passages.append(buf)
            buf = ""
    if buf:
        passages.append(buf)
    # keep passages that actually contain a figure
    return [p for p in passages if re.search(r"\d", p)][:400]


def _parse_amount(s: str) -> float | None:
    if s is None:
        return None
    s = str(s)
    pct = "%" in s
    m = re.search(r"-?\d[\d,]*\.?\d*", s.replace(",", ""))
    if not m:
        return None
    try:
        v = float(m.group())
    except ValueError:
        return None
    if pct and v > 1:
        v = v / 100.0
    return v


def _rerank_top(client, query: str, passages: list[str], top_n: int = 5) -> list[str]:
    """Cohere rerank: the passages most relevant to the parameter query, highest first."""
    if not passages:
        return []
    try:
        rr = client.rerank(model=RERANK_MODEL, query=query, documents=passages, top_n=top_n)
        return [passages[r.index] for r in rr.results]
    except Exception as exc:  # noqa: BLE001
        log.info("rerank failed (%s); using unranked passages", type(exc).__name__)
        return passages[:top_n]


def _extract(client, rule: Rule, top: list[str]) -> tuple[float | None, str]:
    """Generator agent: extract the value + a verbatim quote from the top passages."""
    if not top:
        return None, ""
    context = "\n---\n".join(top)
    prompt = (
        f"From the official text below, find: {rule.label}.\n"
        f"Specifically: {rule.query}.\n\n"
        "Return ONLY a JSON object: {\"found\": true|false, \"value\": <number or null>, "
        "\"quote\": \"<verbatim sentence from the text>\"}. "
        "The quote MUST be copied verbatim from the text and MUST contain the number you report in "
        "\"value\". If no single sentence states the number, found=false.\n\n"
        f"TEXT:\n{context[:6000]}"
    )
    try:
        resp = client.chat(model=CHAT_MODEL, messages=[{"role": "user", "content": prompt}])
        out = resp.message.content[0].text
    except Exception as exc:  # noqa: BLE001
        log.info("chat extract failed: %s", type(exc).__name__)
        return None, ""
    m = re.search(r"\{.*\}", out, re.S)
    if not m:
        return None, ""
    try:
        data = json.loads(m.group())
    except Exception:
        return None, ""
    if not data.get("found"):
        return None, ""
    quote = (data.get("quote") or "").strip()
    value = _parse_amount(data.get("value"))
    # guard 1: the quote must actually appear in the fetched text (no fabricated quotes)
    norm = re.sub(r"\s+", " ", context).lower()
    if quote and re.sub(r"\s+", " ", quote).lower()[:60] not in norm:
        return None, ""
    # guard 2: the quote must contain the reported number, so the evidence backs the value
    if value is not None and quote:
        quote_digits = re.sub(r"[^\d]", "", quote)
        val_digits = re.sub(r"[^\d]", "", f"{value:g}")
        if val_digits and val_digits not in quote_digits:
            return None, ""  # value not evidenced by the quote -> unverified
    return value, quote


def _verify(client, rule: Rule, value: float, quote: str, top: list[str]) -> dict:
    """Verifier agent: independently check the generator's value and quote against the text,
    and look for a conflicting figure. Returns {agrees, current_period, conflicting_value, reason}."""
    context = "\n---\n".join(top)
    prompt = (
        f"A claim says the value for '{rule.label}' is {value}, supported by this quote:\n"
        f'"{quote}"\n\n'
        "Independently check the official text below. Return ONLY JSON: "
        "{\"agrees\": true|false, \"current_period\": true|false, \"conflicting_value\": <number or null>, "
        "\"reason\": \"<short>\"}. Set agrees=true only if the text clearly states that value for this "
        "parameter. conflicting_value is any DIFFERENT figure the text gives for the SAME parameter, else null.\n\n"
        f"TEXT:\n{context[:6000]}"
    )
    try:
        resp = client.chat(model=CHAT_MODEL, messages=[{"role": "user", "content": prompt}])
        m = re.search(r"\{.*\}", resp.message.content[0].text, re.S)
        return json.loads(m.group()) if m else {"agrees": False, "reason": "no verifier output"}
    except Exception as exc:  # noqa: BLE001
        log.info("verify failed: %s", type(exc).__name__)
        return {"agrees": False, "reason": "verifier error"}


def check_rule(rule: Rule, client=None) -> CheckResult:
    """Generator extracts, verifier confirms. Only a verifier-confident result gets a definitive
    match/mismatch; anything the verifier cannot stand behind is downgraded to unverified for a human."""
    client = client or _client()
    try:
        passages = _fetch_passages(rule.source_url)
    except Exception as exc:  # noqa: BLE001
        return CheckResult(rule.id, rule.label, rule.value, None, "", "unverified",
                           f"fetch failed ({type(exc).__name__})")
    top = _rerank_top(client, rule.query, passages)
    value, quote = _extract(client, rule, top)
    if value is None or not quote:
        return CheckResult(rule.id, rule.label, rule.value, None, "", "unverified",
                           "no grounded value found on the page")
    tol = 0.5 if rule.value >= 100 else 0.001
    raw = "match" if abs(value - rule.value) <= tol else "mismatch"

    v = _verify(client, rule, value, quote, top)
    conflict = _parse_amount(v.get("conflicting_value")) if v.get("conflicting_value") is not None else None
    note = (v.get("reason") or "").strip()
    confident = (bool(v.get("agrees")) and v.get("current_period", True) is not False
                 and (conflict is None or abs(conflict - value) <= tol))
    if confident:
        return CheckResult(rule.id, rule.label, rule.value, value, quote, raw,
                           confidence="high", verifier_note=note)
    # verifier not confident: do not assert a verdict, send it to a human
    detail = f"page also shows {conflict:g}" if (conflict is not None and abs(conflict - value) > tol) \
        else "verifier not confident"
    return CheckResult(rule.id, rule.label, rule.value, value, quote, "unverified", detail,
                       confidence="low", verifier_note=note)


def run(only: list[str] | None = None) -> list[CheckResult]:
    """Check every web-checkable registry entry (optionally a subset by id)."""
    client = _client()
    out = []
    for rule in REGISTRY:
        if not rule.checkable:
            continue
        if only and rule.id not in only:
            continue
        out.append(check_rule(rule, client))
    return out
