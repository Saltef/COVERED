"""Offline screening demo — proves the domain core with zero dependencies and no API keys.

    python scripts/run_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Windows consoles default to cp1252 and choke on the checkmark glyphs; force UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.domain.rules_engine import screen, summarize  # noqa: E402
from app.models import Eligibility  # noqa: E402
from app.seed.personas import sample_senior  # noqa: E402

MARK = {
    Eligibility.eligible: "✓",
    Eligibility.likely: "✓",
    Eligibility.maybe: "?",
    Eligibility.not_eligible: "✗",
}


def main() -> None:
    p = sample_senior()
    results = screen(p)
    s = summarize(results)

    print(f"\nPersona: {p.first_name}, {p.age}, {p.province}, net income ${p.annual_net_income:,.0f}\n")
    print(f'Headline: "You could be owed about ${s["total_estimated_annual"]:,.0f} a year across '
          f'{s["n_eligible_or_maybe"]} programs you may not be getting."\n')

    order = sorted(results, key=lambda r: (r.eligibility is Eligibility.not_eligible, -r.confidence))
    for r in order:
        val = f"${r.estimated_annual_value:,.0f}" if r.estimated_annual_value else "   —   "
        unlock = f"  (unlocked by {r.unlocked_by.upper()})" if r.unlocked_by else ""
        print(f"  {MARK[r.eligibility]} {r.program_name:<34} conf {r.confidence:.2f}  {val}{unlock}")
        if r.reasons:
            print(f"       → {r.reasons[0]}")
    print("\n(Figures use 2025 CRA / Ontario rates; individual amounts vary.)\n")


if __name__ == "__main__":
    main()
