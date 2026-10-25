"""Publish the engine's policy figures to SurrealDB Agent Memory, with provenance, and show
supersession and traceable recall. Policy facts only; no user or health data ever goes here.

    python scripts/sync_policy_memory.py           # publish current figures from the registry
    python scripts/sync_policy_memory.py --check    # run the live drift check first, publish confident results
    python scripts/sync_policy_memory.py --demo      # demonstrate supersession on one figure

This is the shared memory for the drift loop: the generator-verifier writes a figure as a fact; a
changed value supersedes the prior one; recall returns the current value with where it came from.
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.domain.policy_registry import REGISTRY  # noqa: E402
from app.ops import agent_memory as mem  # noqa: E402
from app.ops import policy_history as hist  # noqa: E402


def _top_text(resp: dict) -> str:
    # Facts are superseded, not overwritten, so the newest fact is the current value.
    chunks = [h for h in resp.get("hits", []) if h.get("source") == "memory_chunk"]
    if chunks:
        chunks.sort(key=lambda h: h.get("occurredAt", ""), reverse=True)
        return chunks[0].get("text", "")
    hits = resp.get("hits", [])
    return hits[0].get("text", "") if hits else "(no hits)"


def publish_from_registry() -> None:
    print("Publishing policy figures to Agent Memory (with source + date):")
    for r in REGISTRY:
        mem.publish_policy_fact(r.label, r.display, r.source_url, r.verified_date)
        print(f"  wrote {r.id}: {r.display}")


def publish_from_check() -> None:
    from app.ops import policy_checker as pc
    sources = {r.id: r for r in REGISTRY}
    print("Running the live drift check, publishing confident results as facts (with source)...")
    for res in pc.run():
        rule = sources.get(res.id)
        if hist.record_check(res, source_url=rule.source_url if rule else "") is not None:
            print(f"  wrote {res.id}: {res.extracted_value:g} ({res.status})")


def demo_supersession() -> None:
    print("\nSupersession demo (Canada Disability Benefit single threshold):")
    mem.remember("As of 2025-01-01, the Canada Disability Benefit single income threshold is $23,000.")
    print("  wrote old fact: $23,000")
    mem.remember("As of 2026-10-25, the Canada Disability Benefit single income threshold is $23,483 "
                 "(2026-27 indexed). Source: canada.ca.")
    print("  wrote new fact: $23,483 (supersedes)")
    r = mem.recall("What is the current Canada Disability Benefit single income threshold?")
    print(f"  recall tier={r.get('tier')} -> {_top_text(r)[:120]}")


def main() -> None:
    if not mem.available():
        print("SPECTRON_* not configured in .env."); sys.exit(2)
    if "--check" in sys.argv:
        publish_from_check()
    else:
        publish_from_registry()
    if "--demo" in sys.argv:
        demo_supersession()
    r = mem.recall("What is the Canadian Dental Care Plan adjusted family net income cap, and its source?")
    print(f"\nTraceable recall (tier={r.get('tier')}):\n  {_top_text(r)[:160]}\n")


if __name__ == "__main__":
    main()
