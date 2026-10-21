"""Run the ops co-pilot benchmark (agent vs ground truth) over the Era-simulated agency.

    python scripts/run_ops_benchmark.py
Ground truth is always computed from live Era data. The agent column runs only when
ANTHROPIC_API_KEY is set.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ops.benchmark import run  # noqa: E402


async def main() -> None:
    report = await run()
    if not report["agent_available"]:
        print("\nAgent not run (set ANTHROPIC_API_KEY to grade it). Showing computed ground truth:\n")
    else:
        acc = report["accuracy"]
        print(f"\nOps co-pilot benchmark: {report['passed']}/{report['n']} "
              f"({acc * 100:.0f}% accuracy vs ground truth)\n")
    for c in report["cases"]:
        mark = ("PASS" if c["correct"] else "FAIL") if c["agent_available"] else "GT"
        print(f"  [{mark:>4}] {c['id']:18} truth={c['ground_truth']!r}"
              + (f"  agent={c['agent_answer']!r} ({c['tool_calls']} tool calls)" if c["agent_available"] else ""))
    print()


if __name__ == "__main__":
    asyncio.run(main())
