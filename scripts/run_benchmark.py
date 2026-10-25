"""Run the agent benchmark against ground-truth cases.

    python scripts/run_benchmark.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.eval.benchmark import run  # noqa: E402
from app.eval.era import fetch_era_cases  # noqa: E402


def main() -> None:
    report = run(fetch_era_cases())  # None unless Era access is configured -> built-in ground truth
    print(f"\nRegression suite source: {report['source']}")
    print("Measures: regression / self-consistency vs hand-labeled expectations")
    print("External accuracy check: scripts/check_policy_drift.py (figures vs official sources)")
    print(f"Cases passed:     {report['cases_passed']}/{report['n_cases']}")
    print(f"Decision match:   {report['decision_accuracy'] * 100:.1f}%  "
          f"({report['correct_decisions']}/{report['total_decisions']} program decisions)\n")
    for c in report["cases"]:
        mark = "PASS" if c["passed"] else "FAIL"
        print(f"  [{mark}] {c['id']:<22} {c['correct']}/{c['total']}")
        for m in c["mismatches"]:
            print(f"        - {m['program']}: got_actionable={m['got_actionable']} "
                  f"expected={m['expected_actionable']}")
    if report["per_program_errors"]:
        print("\nPer-program errors:", report["per_program_errors"])
    print()


if __name__ == "__main__":
    main()
