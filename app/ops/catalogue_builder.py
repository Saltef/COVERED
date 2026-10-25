"""AI discovery: enumerate Ontario Health and home-and-community-care programs from official
sources, classify each as rule-based or assessment-based, and verify each is grounded in the page.

Generator-verifier, same discipline as the drift checker:
  - generator enumerates the programs named on an official page.
  - a grounded check drops any name that does not actually appear on the page (no invented programs).
  - a classifier labels each rule-based (fixed criteria a computer could screen) or assessment-based
    (a professional assesses need).

The output is a DRAFT catalogue for human curation. Nothing here is shown to users or added to the
engine automatically. Rule-based programs can later join the deterministic engine, the registry and
the drift checker; assessment-based ones become routed leads, like Ontario Health atHome.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass

from app.ops.policy_checker import CHAT_MODEL, _client, available  # reuse the Cohere client

log = logging.getLogger(__name__)

SEED_SOURCES = [
    "https://www.ontario.ca/page/home-community-care",
    "https://www.ontario.ca/page/get-coverage-high-prescription-drug-costs",
]


@dataclass
class Program:
    name: str
    for_whom: str
    kind: str            # "rule-based" | "assessment-based" | "unknown"
    how_to_apply: str
    source_url: str
    grounded: bool       # the name actually appears on the source page
    note: str = ""


def _fetch_text(url: str, cap: int = 9000) -> str:
    import httpx
    with httpx.Client(timeout=30, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0 (compatible; CoveredCatalogue/1.0)"}) as c:
        html = c.get(url).text
    html = re.sub(r"(?is)<(script|style|noscript|head).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text).replace("&amp;", "&")
    return re.sub(r"[ \t]+", " ", text).strip()[:cap]


def _json_array(text: str) -> list[dict]:
    m = re.search(r"\[.*\]", text or "", re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group())
        return [d for d in data if isinstance(d, dict)]
    except Exception:
        return []


def _enumerate(client, text: str) -> list[dict]:
    """Generator: list the programs/services actually named in the official text."""
    prompt = (
        "From the official Ontario health and home-care text below, list the distinct government "
        "programs or services it names. For each, return {\"name\": ..., \"for_whom\": <one line>, "
        "\"how_to_apply\": <one line>}. Return ONLY a JSON array. Include only programs actually named "
        "in the text; do not add any you merely know of.\n\n" + text
    )
    try:
        resp = client.chat(model=CHAT_MODEL, messages=[{"role": "user", "content": prompt}])
        return _json_array(resp.message.content[0].text)
    except Exception as exc:  # noqa: BLE001
        log.info("enumerate failed: %s", type(exc).__name__)
        return []


def _classify(client, name: str, text: str) -> str:
    """Rule-based (thresholds a computer can check) vs assessment-based (a professional assesses need)."""
    prompt = (
        f"For the Ontario program '{name}', decide if its eligibility is 'rule-based' (fixed criteria "
        "such as income, age or residency that a computer could screen) or 'assessment-based' (a care "
        "coordinator or clinician assesses the person's need). Use the text if it helps. Return ONLY "
        "JSON {\"kind\": \"rule-based\"|\"assessment-based\"|\"unknown\"}.\n\n" + text[:4000]
    )
    try:
        resp = client.chat(model=CHAT_MODEL, messages=[{"role": "user", "content": prompt}])
        m = re.search(r"\{.*\}", resp.message.content[0].text, re.S)
        return (json.loads(m.group()).get("kind") if m else "unknown") or "unknown"
    except Exception:
        return "unknown"


def _grounded(name: str, text: str) -> bool:
    key = re.sub(r"\(.*?\)", "", name).strip().lower()[:20]
    return bool(key) and key in text.lower()


def build(sources: list[str] | None = None) -> list[Program]:
    client = _client()
    seen: dict[str, Program] = {}
    for url in (sources or SEED_SOURCES):
        try:
            text = _fetch_text(url)
        except Exception as exc:  # noqa: BLE001
            log.info("catalogue fetch failed for %s: %s", url, type(exc).__name__)
            continue
        for item in _enumerate(client, text):
            name = (item.get("name") or "").strip()
            if not name or name.lower() in seen:
                continue
            grounded = _grounded(name, text)
            kind = _classify(client, name, text) if grounded else "unknown"
            seen[name.lower()] = Program(
                name=name, for_whom=(item.get("for_whom") or "").strip(),
                kind=kind, how_to_apply=(item.get("how_to_apply") or "").strip(),
                source_url=url, grounded=grounded,
                note="" if grounded else "name not found verbatim on the page; drop or re-source")
    return list(seen.values())


def build_dicts(sources: list[str] | None = None) -> list[dict]:
    return [asdict(p) for p in build(sources)]
