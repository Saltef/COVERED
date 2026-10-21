"""The DTC 'unlock chain' — the product's spine.

A single DTC approval opens the door to several other programs. This graph annotates
downstream results so the UI can show the chain lighting up.
"""
from __future__ import annotations

from app.models import Eligibility, ProgramResult

# node -> programs it unlocks
UNLOCK_EDGES: dict[str, list[str]] = {
    "dtc": ["cdb", "rdsp", "cdcp"],
}

_ACTIVE = (Eligibility.eligible, Eligibility.likely, Eligibility.maybe)


def apply_unlocks(by_id: dict[str, ProgramResult]) -> dict[str, ProgramResult]:
    for source, targets in UNLOCK_EDGES.items():
        src = by_id.get(source)
        if not src or src.eligibility not in _ACTIVE:
            continue
        for target_id in targets:
            child = by_id.get(target_id)
            if not child:
                continue
            child.unlocked_by = source
            if src.eligibility is not Eligibility.eligible:
                child.reasons.append(f"Becomes available once your {source.upper()} is approved.")
    return by_id
