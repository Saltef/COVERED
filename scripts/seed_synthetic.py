"""Seed a synthetic agency book into SurrealDB and print the rollup (needs SurrealDB up).

    python scripts/seed_synthetic.py [N]     # default 120 clients

Generates a deterministic synthetic Canadian population, screens each person with the real engine,
and saves the results as screenings owned by three demo caseworkers — so the agency console and the
book co-pilot light up with a realistic caseload. Re-running replaces the synthetic set only; it
never touches the hand-seeded demo clients (owned by 'dev-user').

Every client here is generated, not real. See app/seed/synthetic.py.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

os.environ.setdefault("SURREAL_URL", "ws://localhost:8001/rpc")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.schemas import ProfileIn, ProgramResultOut  # noqa: E402
from app.db import repository as repo  # noqa: E402
from app.domain.rules_engine import screen, summarize  # noqa: E402
from app.ops import book_agent  # noqa: E402
from app.seed.synthetic import generate_population  # noqa: E402

CASEWORKERS = ["caseworker-amara", "caseworker-ben", "caseworker-chen"]


async def _clear_synthetic() -> None:
    await repo.init_schema()
    async with repo._db() as db:
        for owner in CASEWORKERS:
            await db.query("DELETE screening WHERE owner=$o;", {"o": owner})


async def _seed(n: int) -> None:
    await _clear_synthetic()
    pop = generate_population(n)
    for i, p in enumerate(pop):
        results = screen(ProfileIn(**p).to_domain())
        s = summarize(results)
        headline = (f"You could be owed about ${s['total_estimated_annual']:,.0f} a year across "
                    f"{s['n_eligible_or_maybe']} programs you may not be getting.")
        result_dicts = [ProgramResultOut.from_domain(r).model_dump() for r in results]
        await repo.save_screening(CASEWORKERS[i % len(CASEWORKERS)], headline, p, result_dicts, s)
    print(f"Seeded {n} synthetic clients across {len(CASEWORKERS)} caseworkers.")


async def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    await _seed(n)
    stats = await book_agent.book_stats()
    print("\n=== Agency book rollup ===")
    print(f"  Clients screened:        {stats['n_clients']}")
    print(f"  Total unclaimed / year:  ${stats['total_unclaimed_annual']:,}")
    print(f"  Average per client:      ${stats['avg_per_client']:,}")
    print(f"  Have >=1 benefit:        {stats['pct_with_benefit']}%")
    print("  Clients eligible by program:")
    for name, count in stats["program_counts"].items():
        print(f"    - {name}: {count}")
    print("  Clients by province:", stats["province_counts"])


if __name__ == "__main__":
    asyncio.run(main())
