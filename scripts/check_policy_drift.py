"""Check the engine's encoded figures against the live official sources (needs COHERE_API_KEY).

    python scripts/check_policy_drift.py                 # check all web-checkable figures
    python scripts/check_policy_drift.py cdcp_income_cap # check one
    python scripts/check_policy_drift.py --sync          # also write confident readings to memory

Reads each registry source, extracts the current value with a verbatim quote (Cohere rerank +
chat), and reports match / mismatch / unverified. It never changes a rule. A mismatch is a flag
for a human to review the quote and decide whether to update the engine (and the benchmark).

With --sync (and SPECTRON_* configured), each verifier-confident reading is written to the shared
policy history in Agent Memory, with its source, date, and verbatim quote. A changed value
supersedes the prior fact, so the memory becomes a queryable record of what each figure was.
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.domain.policy_registry import REGISTRY, coverage  # noqa: E402
from app.ops import policy_checker as pc  # noqa: E402
from app.ops import policy_history as hist  # noqa: E402

MARK = {"match": "[MATCH]", "mismatch": "[DRIFT]", "unverified": "[  ?  ]"}


def main() -> None:
    if not pc.available():
        print("COHERE_API_KEY not set."); sys.exit(2)
    args = sys.argv[1:]
    sync = "--sync" in args
    only = [a for a in args if not a.startswith("--")] or None
    sources = {r.id: r for r in REGISTRY}
    if sync and not hist.available():
        print("--sync given but SPECTRON_* not configured; running without memory writes.")
        sync = False
    cov = coverage()
    print("\nPolicy drift check (engine vs live official sources)")
    print(f"Coverage: {cov['web_checkable']}/{cov['total']} figures web-checkable; "
          f"{cov['manual_review']} manual-review (PDF/formula): {', '.join(cov['manual_ids'])}")
    print("-" * 72)
    results = pc.run(only=only)
    drift = written = 0
    for r in results:
        got = f"{r.extracted_value:g}" if r.extracted_value is not None else "-"
        conf = f" conf={r.confidence}" if r.confidence else ""
        print(f"  {MARK[r.status]}  {r.id:<22} engine={r.engine_value:<10g} source={got}{conf}")
        if r.quote:
            print(f'            quote: "{r.quote[:170]}"')
        if r.detail:
            print(f"            {r.detail}")
        if r.verifier_note:
            print(f"            verifier: {r.verifier_note[:100]}")
        if r.status == "mismatch":
            drift += 1
        if sync:
            rule = sources.get(r.id)
            if hist.record_check(r, source_url=rule.source_url if rule else "") is not None:
                written += 1
                print("            -> written to policy history (Agent Memory)")
    print("-" * 72)
    tail = f", {written} fact(s) written to memory" if sync else ""
    print(f"  {len(results)} checked, {drift} drift flag(s) for review{tail}.\n")
    sys.exit(1 if drift else 0)


if __name__ == "__main__":
    main()
