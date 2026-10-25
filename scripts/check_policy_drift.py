"""Check the engine's encoded figures against the live official sources (needs COHERE_API_KEY).

    python scripts/check_policy_drift.py                 # check all web-checkable figures
    python scripts/check_policy_drift.py cdcp_income_cap # check one

Reads each registry source, extracts the current value with a verbatim quote (Cohere rerank +
chat), and reports match / mismatch / unverified. It never changes a rule. A mismatch is a flag
for a human to review the quote and decide whether to update the engine (and the benchmark).
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ops import policy_checker as pc  # noqa: E402

MARK = {"match": "[MATCH]", "mismatch": "[DRIFT]", "unverified": "[  ?  ]"}


def main() -> None:
    if not pc.available():
        print("COHERE_API_KEY not set."); sys.exit(2)
    only = sys.argv[1:] or None
    print("\nPolicy drift check (engine vs live official sources)")
    print("-" * 72)
    results = pc.run(only=only)
    drift = 0
    for r in results:
        got = f"{r.extracted_value:g}" if r.extracted_value is not None else "-"
        print(f"  {MARK[r.status]}  {r.id:<22} engine={r.engine_value:<10g} source={got}")
        if r.quote:
            print(f'            quote: "{r.quote[:170]}"')
        if r.detail:
            print(f"            {r.detail}")
        if r.status == "mismatch":
            drift += 1
    print("-" * 72)
    print(f"  {len(results)} checked, {drift} drift flag(s) for review.\n")
    sys.exit(1 if drift else 0)


if __name__ == "__main__":
    main()
