"""Discover an Era system's record schema so FIELD_MAP in app/eval/era.py can be finalized.

Steps:
  1. Generate a company and write its .env with the `era` CLI.
  2. In .env set ERA_SYSTEM + ERA_RECORDS_PATH (and ensure <SYSTEM>_BASE_URL / <SYSTEM>_MCP_HEADER exist).
  3. python scripts/era_probe.py
Then paste the printed field names (NOT the secret header) back so the mapping can be finalized.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.eval.era import era_configured, fetch_era_records  # noqa: E402


async def main() -> None:
    if not era_configured():
        print("Era not configured. In .env set ERA_SYSTEM, ERA_RECORDS_PATH and "
              "<SYSTEM>_BASE_URL / <SYSTEM>_MCP_HEADER (from the `era` CLI).")
        return
    records = await fetch_era_records(limit=3)
    print(f"Fetched {len(records)} record(s).")
    if records:
        print("\nTop-level fields:", list(records[0].keys()))
        print("\nFirst record (inspect these fields for FIELD_MAP):")
        print(json.dumps(records[0], indent=2, default=str)[:4000])


if __name__ == "__main__":
    asyncio.run(main())
