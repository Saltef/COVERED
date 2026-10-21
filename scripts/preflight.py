"""Pre-demo health check: one command that says whether the demo will run clean.

    python scripts/preflight.py          # check everything
    python scripts/preflight.py --no-llm # skip the live LLM call (save a token / go offline)

Pings each dependency, reports OK / WARN / FAIL with a one-line reason, and names exactly which
demo features degrade when one is down. Exit code is non-zero only when a REQUIRED dependency is
down, so it is safe to wire into a start script. Everything here degrades gracefully in the app;
this just tells you in advance instead of mid-demo.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import os
import sys
from pathlib import Path

os.environ.setdefault("SURREAL_URL", "ws://localhost:8001/rpc")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OK, WARN, FAIL = "ok", "warn", "fail"
MARK = {OK: "[ OK ]", WARN: "[WARN]", FAIL: "[FAIL]"}

# Severity decides the exit code: a required dependency down means NOT READY.
# The degraded note is what the audience would actually notice.
CHECKS_META = {
    "SurrealDB": ("required", "no persistence: agency caseload, book rollup, care team and audit "
                              "go 503. Screening still computes, nothing is saved."),
    "OpenRouter (LLM)": ("important", "co-pilots and plain-language explanations fall back to "
                                      "deterministic text. Screening and dollar values are unaffected."),
    "Cohere (voice)": ("optional", "voice input is off; typing works. Voice is already optional."),
    "Era (Eon)": ("optional", "Era CRM co-pilot and live-ingestion demo are off. The book co-pilot "
                              "is unaffected."),
}


async def _check_surreal() -> tuple[str, str]:
    from app.db import repository as repo
    try:
        status = await asyncio.wait_for(repo.ping(), timeout=8)
        return (OK, "connected") if status == "connected" else (FAIL, status)
    except Exception as exc:  # noqa: BLE001
        return FAIL, type(exc).__name__


def _check_llm(live: bool) -> tuple[str, str]:
    from app import llm
    if not llm.available():
        return WARN, "OPENROUTER_API_KEY not set"
    if not live:
        return OK, f"key set ({llm.model()}); live call skipped"
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(lambda: llm.chat([{"role": "user", "content": "ping"}], max_tokens=1))
            fut.result(timeout=25)
        return OK, f"live call OK ({llm.model()})"
    except concurrent.futures.TimeoutError:
        return FAIL, "live call timed out (25s)"
    except Exception as exc:  # noqa: BLE001
        return FAIL, f"live call failed ({type(exc).__name__})"


def _check_cohere() -> tuple[str, str]:
    from app.config import get_settings
    if not get_settings().cohere_api_key:
        return WARN, "COHERE_API_KEY not set"
    try:
        import cohere
        cohere.ClientV2(api_key=get_settings().cohere_api_key)
        return OK, "key set, client builds (not live-tested)"
    except Exception as exc:  # noqa: BLE001
        return FAIL, f"client build failed ({type(exc).__name__})"


async def _check_era() -> tuple[str, str]:
    from app.ops import era_client as era
    if not era.configured():
        return WARN, "HUBSPOT_BASE_URL / ERA_* not configured"
    try:
        await asyncio.wait_for(era.list_all("contacts", [], cap=1), timeout=15)
        return OK, "live API reachable"
    except Exception as exc:  # noqa: BLE001
        return FAIL, f"live API unreachable ({type(exc).__name__})"


def _auth_line() -> str:
    from app.config import get_settings
    s = get_settings()
    if s.dev_allow_no_auth and s.is_development:
        return "Auth: DEV MODE, not enforced (any header can claim admin). Fine for a local demo; do not use real data."
    return "Auth: enforced."


async def main() -> None:
    live = "--no-llm" not in sys.argv
    results: dict[str, tuple[str, str]] = {}
    results["SurrealDB"] = await _check_surreal()
    results["OpenRouter (LLM)"] = _check_llm(live)
    results["Cohere (voice)"] = _check_cohere()
    results["Era (Eon)"] = await _check_era()

    print("\nCovered pre-demo check")
    print("-" * 64)
    degraded = []
    required_down = False
    for name, (status, detail) in results.items():
        severity, note = CHECKS_META[name]
        print(f"  {MARK[status]}  {name:<18} {detail}")
        if status != OK:
            degraded.append(name)
            print(f"           -> {note}")
            if severity == "required":
                required_down = True
    print("-" * 64)
    print(" ", _auth_line())
    print("-" * 64)
    if required_down:
        print("  NOT READY: a required dependency is down (see FAIL above).")
    elif degraded:
        print(f"  READY, degraded: {', '.join(degraded)} unavailable (features above will fall back).")
    else:
        print("  READY: all dependencies green.")
    print()
    sys.exit(1 if required_down else 0)


if __name__ == "__main__":
    asyncio.run(main())
