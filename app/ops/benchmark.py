"""Grade the ops co-pilot's answers against ground truth computed from the same Era data."""
from __future__ import annotations

from app.ops import agent as ops_agent
from app.ops.questions import QUESTIONS


def _num(x):
    try:
        return float(str(x).replace(",", "").replace("$", "").strip())
    except Exception:
        return None


def _correct(gt, ans, kind: str) -> bool:
    if ans is None:
        return False
    if kind in ("count", "number"):
        a, g = _num(ans), _num(gt)
        if a is None or g is None:
            return False
        return abs(a - g) < (0.5 if kind == "count" else 1.0)
    return str(ans).strip().lower() == str(gt).strip().lower()


async def run() -> dict:
    cases = []
    for q in QUESTIONS:
        gt = await q.ground_truth()
        result = await ops_agent.answer(q.text)
        ans = result.get("answer") if result else None
        cases.append({
            "id": q.id, "question": q.text, "ground_truth": gt, "agent_answer": ans,
            "correct": _correct(gt, ans, q.kind),
            "tool_calls": result.get("tool_calls") if result else 0,
            "agent_available": result is not None,
        })
    graded = [c for c in cases if c["agent_available"]]
    passed = sum(1 for c in graded if c["correct"])
    return {
        "n": len(cases),
        "agent_available": bool(graded),
        "passed": passed,
        "accuracy": round(passed / len(graded), 4) if graded else None,
        "cases": cases,
    }
