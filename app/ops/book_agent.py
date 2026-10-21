"""Book co-pilot: question answering over the agency's screened population.

The Era ops co-pilot (app/ops/agent.py) reads the partner CRM. This one reads the benefits
*book* — the screenings seeded into SurrealDB — so it can answer the question that actually
matters to an agency: how much coverage is my caseload missing, and who qualifies for what.

Same design as the Era co-pilot: the tools compute EXACT aggregates server-side, so even a cheap
model only has to pick the right tool. Deterministic stats are also exposed directly (book_stats)
for the dashboard, with no model in the loop.
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from typing import Optional

from app import llm
from app.db import repository as repo

log = logging.getLogger(__name__)

CLAIMABLE = {"eligible", "likely", "maybe"}
PROGRAM_NAMES = {
    "dtc": "Disability Tax Credit", "cdb": "Canada Disability Benefit",
    "cdcp": "Canadian Dental Care Plan", "metc": "Medical Expense Tax Credit",
    "ccc": "Canada Caregiver Credit", "rdsp": "Registered Disability Savings Plan",
    "otdp": "Ontario Trillium Drug Program",
}


def _claimable(results: list) -> list:
    return [r for r in (results or []) if isinstance(r, dict) and r.get("eligibility") in CLAIMABLE]


async def book_stats() -> dict:
    """Deterministic rollup over the whole book (no LLM)."""
    rows = await repo.all_screenings_detailed()
    n = len(rows)
    total = sum((r.get("summary") or {}).get("total_estimated_annual") or 0 for r in rows)
    with_benefit = sum(1 for r in rows if _claimable(r.get("results")))
    prog = Counter()
    prov = Counter()
    for r in rows:
        prov[r.get("province") or "?"] += 1
        for pr in _claimable(r.get("results")):
            prog[pr.get("program_id")] += 1
    return {
        "n_clients": n,
        "total_unclaimed_annual": round(total),
        "avg_per_client": round(total / n) if n else 0,
        "pct_with_benefit": round(100 * with_benefit / n) if n else 0,
        "program_counts": {PROGRAM_NAMES.get(k, k): v for k, v in prog.most_common()},
        "province_counts": dict(prov.most_common()),
    }


# ---- co-pilot tools (exact aggregates over the book) ----
TOOLS = [
    {"type": "function", "function": {
        "name": "total_clients",
        "description": "Exact number of screened clients in the book.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "total_benefit_value",
        "description": "Exact total estimated annual benefit value (CAD) the whole book is owed but may not be claiming.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "avg_benefit_value",
        "description": "Exact average estimated annual benefit value (CAD) per client.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "count_eligible_for",
        "description": "Exact number of clients who are eligible, likely, or maybe for a program. "
                       "program is one of: dtc, cdb, cdcp, metc, ccc, rdsp, otdp.",
        "parameters": {"type": "object",
                       "properties": {"program": {"type": "string", "enum": list(PROGRAM_NAMES)}},
                       "required": ["program"]}}},
    {"type": "function", "function": {
        "name": "clients_by_province",
        "description": "Count of clients per province, highest first.",
        "parameters": {"type": "object", "properties": {}}}},
]


async def _run_tool(name: str, inp: dict) -> str:
    rows = await repo.all_screenings_detailed()
    if name == "total_clients":
        return str(len(rows))
    if name == "total_benefit_value":
        return str(round(sum((r.get("summary") or {}).get("total_estimated_annual") or 0 for r in rows)))
    if name == "avg_benefit_value":
        n = len(rows)
        total = sum((r.get("summary") or {}).get("total_estimated_annual") or 0 for r in rows)
        return str(round(total / n) if n else 0)
    if name == "count_eligible_for":
        prog = (inp.get("program") or "").lower()
        return str(sum(1 for r in rows if any(pr.get("program_id") == prog for pr in _claimable(r.get("results")))))
    if name == "clients_by_province":
        c = Counter(r.get("province") or "?" for r in rows)
        return json.dumps(c.most_common())
    return "unknown tool"


def available() -> bool:
    return llm.available()


def _parse_answer(text: str):
    match = re.search(r"\{.*\}", text or "", re.S)
    if match:
        try:
            return json.loads(match.group()).get("answer")
        except Exception:
            pass
    num = re.search(r"-?\d[\d,]*\.?\d*", text or "")
    return num.group().replace(",", "") if num else (text or "").strip()


async def answer(question: str) -> Optional[dict]:
    if not llm.available():
        return None
    messages = [{"role": "user", "content": (
        "You are an operations assistant for a benefits agency, working over its book of screened "
        "clients. Each tool returns an EXACT aggregate over all clients. Pick the single tool that "
        "answers the question and return its result verbatim. Never add, sum, average, or adjust tool "
        "results yourself, and never estimate: if one tool already gives the number asked for, that IS "
        "the answer. Benefit values are in Canadian dollars per year. "
        f"Question: {question}\n\n"
        "When you have the answer, reply with ONLY a JSON object: {\"answer\": <value>} "
        "(a number for counts/sums, a string otherwise).")}]
    tool_calls = 0
    try:
        for _ in range(6):
            resp = llm.chat(messages, tools=TOOLS, max_tokens=800)
            msg = resp.choices[0].message
            if msg.tool_calls:
                messages.append({"role": "assistant", "content": msg.content or "",
                                 "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
                for tc in msg.tool_calls:
                    tool_calls += 1
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except Exception:
                        args = {}
                    messages.append({"role": "tool", "tool_call_id": tc.id,
                                     "content": await _run_tool(tc.function.name, args)})
                continue
            text = msg.content or ""
            return {"raw": text, "answer": _parse_answer(text), "tool_calls": tool_calls}
        # Out of tool budget: answer from the tool results already gathered, never a fresh guess.
        final = llm.chat(messages + [{"role": "user", "content": (
            "Answer now using ONLY the tool results above, as {\"answer\": <value>}. "
            "Do not compute anything new.")}], max_tokens=200)
        text = final.choices[0].message.content or ""
        return {"raw": text, "answer": _parse_answer(text), "tool_calls": tool_calls}
    except Exception as exc:  # noqa: BLE001
        log.info("Book agent failed: %s", type(exc).__name__)
        return None
