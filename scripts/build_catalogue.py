"""Build a DRAFT catalogue of Ontario Health / home-care programs from official sources (needs
COHERE_API_KEY). Enumerates, grounds, and classifies each program. For human curation, not auto-use.

    python scripts/build_catalogue.py
    python scripts/build_catalogue.py --json > data/ontario_health_catalogue.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ops import catalogue_builder as cb  # noqa: E402


def main() -> None:
    if not cb.available():
        print("COHERE_API_KEY not set."); sys.exit(2)
    programs = cb.build()
    if "--json" in sys.argv:
        import datetime
        print(json.dumps({
            "generated": datetime.date.today().isoformat(),
            "note": ("AI-discovered draft from official Ontario sources. For human curation; not "
                     "authoritative and not shown to users as-is. Rule-based programs can become "
                     "deterministic screens; assessment-based ones become routed leads."),
            "sources": cb.SEED_SOURCES,
            "programs": [p.__dict__ for p in programs],
        }, indent=2))
        return
    print(f"\nOntario Health catalogue (draft, {len(programs)} programs)")
    print("-" * 72)
    for p in programs:
        flag = "" if p.grounded else "  [ungrounded]"
        print(f"  [{p.kind:<16}] {p.name}{flag}")
        if p.for_whom:
            print(f"       for: {p.for_whom}")
        if p.how_to_apply:
            print(f"       apply: {p.how_to_apply}")
    rule = sum(1 for p in programs if p.kind == "rule-based")
    assess = sum(1 for p in programs if p.kind == "assessment-based")
    print("-" * 72)
    print(f"  {rule} rule-based (engine candidates), {assess} assessment-based (routed leads). "
          "Human review before any enter the product.\n")


if __name__ == "__main__":
    main()
