"""The ops co-pilot: an LLM tool-use agent that answers questions over the agency's Era systems.

The model is given read-only tools over the CRM and must reach the answer itself — it never sees
the ground truth. The tools do the aggregation server-side (exact counts/sums), so even a cheap
model only has to choose the right tool + arguments. Runs through the swappable provider
(app/llm.py). Degrades gracefully: with no provider key, answer() returns None.
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from typing import Optional

from app import llm
from app.ops import era_client as era

log = logging.getLogger(__name__)

_OBJECTS = ["contacts", "companies", "deals", "tickets"]

# OpenAI-style function tools (OpenRouter is OpenAI-compatible). Each returns an EXACT aggregate
# computed over ALL records, so the model should use the result directly without recomputing.
TOOLS = [
    {"type": "function", "function": {
        "name": "total_count",
        "description": "Exact total number of records of a CRM object.",
        "parameters": {"type": "object",
                       "properties": {"object_type": {"type": "string", "enum": _OBJECTS}},
                       "required": ["object_type"]}}},
    {"type": "function", "function": {
        "name": "count_where",
        "description": "Exact number of records whose property equals a given value "
                       "(e.g. contacts where country == 'Canada', or plan_name == 'enterprise').",
        "parameters": {"type": "object", "properties": {
            "object_type": {"type": "string", "enum": _OBJECTS},
            "property": {"type": "string"},
            "equals": {"type": "string"}},
            "required": ["object_type", "property", "equals"]}}},
    {"type": "function", "function": {
        "name": "sum_property",
        "description": "Exact sum of a numeric property across all records (e.g. sum of deal 'amount').",
        "parameters": {"type": "object", "properties": {
            "object_type": {"type": "string", "enum": _OBJECTS},
            "property": {"type": "string"}},
            "required": ["object_type", "property"]}}},
    {"type": "function", "function": {
        "name": "value_counts",
        "description": "The most common values of a property with their exact counts, highest first "
                       "(e.g. which plan_name has the most contacts).",
        "parameters": {"type": "object", "properties": {
            "object_type": {"type": "string", "enum": _OBJECTS},
            "property": {"type": "string"}},
            "required": ["object_type", "property"]}}},
]


def _props(record: dict) -> dict:
    return record.get("properties") or {}


async def _run_tool(name: str, inp: dict) -> str:
    object_type = inp.get("object_type")
    if name == "total_count":
        return str(len(await era.list_all(object_type, [])))
    if name == "count_where":
        prop, target = inp["property"], inp.get("equals")
        rows = await era.list_all(object_type, [prop])
        return str(sum(1 for r in rows if _props(r).get(prop) == target))
    if name == "sum_property":
        prop = inp["property"]
        rows = await era.list_all(object_type, [prop])
        total = 0.0
        for r in rows:
            try:
                total += float(_props(r).get(prop))
            except (TypeError, ValueError):
                pass
        return str(round(total, 2))
    if name == "value_counts":
        prop = inp["property"]
        rows = await era.list_all(object_type, [prop])
        counts = Counter(_props(r).get(prop) for r in rows if _props(r).get(prop) is not None)
        return json.dumps(counts.most_common(20))
    return "unknown tool"


def available() -> bool:
    return llm.available() and era.configured()


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
        "You are an operations assistant for a benefits agency, working over its CRM "
        "(HubSpot: contacts, companies, deals, tickets). The tools return EXACT aggregates over all "
        "records — use their results directly, do not recompute or estimate. "
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

        # Out of tool budget — force a final answer with no tools.
        final = llm.chat(messages + [{"role": "user",
                                      "content": "Give your final answer now as {\"answer\": <value>}."}],
                         max_tokens=200)
        text = final.choices[0].message.content or ""
        return {"raw": text, "answer": _parse_answer(text), "tool_calls": tool_calls}
    except Exception as exc:  # noqa: BLE001
        log.info("Ops agent failed: %s", type(exc).__name__)
        return None
