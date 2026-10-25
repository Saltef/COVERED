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


def _extract(client, rule: Rule, passages: list[str]) -> tuple[float | None, str]:
    """Rerank to the best passages, then extract the value + a verbatim quote."""
    if not passages:
        return None, ""
    top = passages
    try:
        rr = client.rerank(model=RERANK_MODEL, query=rule.query, documents=passages, top_n=5)
        top = [passages[r.index] for r in rr.results]
    except Exception as exc:  # noqa: BLE001
        log.info("rerank failed (%s); using unranked passages", type(exc).__name__)
        top = passages[:5]
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


def check_rule(rule: Rule, client=None) -> CheckResult:
    client = client or _client()
    try:
        passages = _fetch_passages(rule.source_url)
    except Exception as exc:  # noqa: BLE001
        return CheckResult(rule.id, rule.label, rule.value, None, "", "unverified",
                           f"fetch failed ({type(exc).__name__})")
    value, quote = _extract(client, rule, passages)
    if value is None or not quote:
        return CheckResult(rule.id, rule.label, rule.value, None, "", "unverified",
                           "no grounded value found on the page")
    # tolerance: exact for dollars, small relative for rates
    tol = 0.5 if rule.value >= 100 else 0.001
    status = "match" if abs(value - rule.value) <= tol else "mismatch"
    return CheckResult(rule.id, rule.label, rule.value, value, quote, status)


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
