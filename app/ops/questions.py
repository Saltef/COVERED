"""Benchmark questions for the ops co-pilot, each with ground truth computed from Era's data."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.ops import era_client as era


@dataclass
class Question:
    id: str
    text: str
    ground_truth: Callable[[], Awaitable[Any]]
    kind: str  # "count" | "number" | "text"


def _prop(record: dict, name: str):
    return (record.get("properties") or {}).get(name)


async def _gt_contacts_in_country(country: str) -> int:
    rows = await era.list_all("contacts", ["country"])
    return sum(1 for r in rows if _prop(r, "country") == country)


async def _gt_plan_count(plan: str) -> int:
    rows = await era.list_all("contacts", ["plan_name"])
    return sum(1 for r in rows if _prop(r, "plan_name") == plan)


async def _gt_total_deal_value() -> float:
    rows = await era.list_all("deals", ["amount"])
    return round(sum(float(_prop(r, "amount") or 0) for r in rows), 2)


async def _gt_company_count() -> int:
    return len(await era.list_all("companies", []))


async def _gt_top_plan() -> str:
    rows = await era.list_all("contacts", ["plan_name"])
    counts = Counter(_prop(r, "plan_name") for r in rows if _prop(r, "plan_name"))
    return counts.most_common(1)[0][0] if counts else ""


QUESTIONS: list[Question] = [
    Question("canada_contacts", "How many contacts are based in Canada?",
             lambda: _gt_contacts_in_country("Canada"), "count"),
    Question("enterprise_plan", "How many contacts are on the 'enterprise' plan?",
             lambda: _gt_plan_count("enterprise"), "count"),
    Question("total_deal_value", "What is the total value (sum of 'amount') of all deals?",
             _gt_total_deal_value, "number"),
    Question("company_count", "How many companies are in the CRM?",
             _gt_company_count, "count"),
    Question("top_plan", "Which plan_name has the most contacts?",
             _gt_top_plan, "text"),
]
