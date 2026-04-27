"""Production-realistic reproduction of the generation_status.json
final-state race that QA Tier C exposed.

Differs from `qa.run_qa --tier C`:
- Does NOT override `FORGE_MOD_SOURCES_DIR`. Uses whatever the environment
  resolves to at module load (matches TUI auto-launch path resolution).
- Reads the resolved STATUS_FILE path FROM the orchestrator module, so the
  harness reads from the same path orchestrator wrote to.
- Captures `generation_status.json` snapshot immediately after each run.
- Reports pass/fail per run + the final stage label of any stuck run.

Run before the LinkedIn recording to confirm the bug is QA-only or
reproduces in production.

Usage:
  cd /Users/user/Desktop/the-forge/agents
  python3 -m qa.repro_status_race
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import json
import sys
import time
from pathlib import Path

_AGENTS_DIR = Path(__file__).resolve().parent.parent
if str(_AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENTS_DIR))

from dotenv import load_dotenv

load_dotenv(_AGENTS_DIR / ".env")

# Import orchestrator AFTER load_dotenv so its module-level path constants
# resolve from the production environment, exactly as the TUI auto-launch does.
import orchestrator  # noqa: E402


N = 3
PROMPT = "Storm Brand — a long sword wreathed in crackling cobalt lightning"
TIER = "Tier3_Hardmode"


def main() -> int:
    status_file: Path = orchestrator.STATUS_FILE
    print(f"orchestrator.STATUS_FILE → {status_file}")
    print(f"resolved exists: {status_file.parent.exists()}")
    print(f"prompt: {PROMPT!r}")
    print(f"runs: {N}")
    print()

    runs: list[dict] = []
    loop = asyncio.new_event_loop()
    try:
        for i in range(1, N + 1):
            request = {
                "prompt": PROMPT,
                "tier": TIER,
                "content_type": "Weapon",
                "sub_type": "",
                "mode": "compile",
            }
            t0 = time.monotonic()
            error: str | None = None
            try:
                loop.run_until_complete(orchestrator.run_pipeline(request))
            except Exception as exc:  # noqa: BLE001
                error = f"{type(exc).__name__}: {exc}"
            elapsed = time.monotonic() - t0

            snapshot: dict = {}
            try:
                snapshot = json.loads(status_file.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                snapshot = {"_read_error": str(exc)}

            run = {
                "iter": i,
                "elapsed_sec": round(elapsed, 1),
                "pipeline_error": error,
                "status_after_run": snapshot.get("status"),
                "stage_pct": snapshot.get("stage_pct"),
                "stage_label": snapshot.get("stage_label"),
                "message": snapshot.get("message"),
            }
            runs.append(run)
            stuck = snapshot.get("status") != "ready" and error is None
            print(
                f"[run {i}/{N}] elapsed={run['elapsed_sec']}s "
                f"status={run['status_after_run']!r} "
                f"stage_pct={run['stage_pct']} "
                f"{'⚠ STUCK' if stuck else '✓ ok' if not error else f'✗ {error[:60]}'}"
            )
    finally:
        loop.close()

    # Summary
    completed = sum(1 for r in runs if r["pipeline_error"] is None)
    ready_final = sum(1 for r in runs if r["status_after_run"] == "ready")
    stuck = completed - ready_final
    pipeline_errors = sum(1 for r in runs if r["pipeline_error"])
    # Errors-only runs are inconclusive: nothing reached the final-write
    # path, so absence of "stuck" doesn't mean the race is absent.
    inconclusive = completed == 0

    out_dir = _AGENTS_DIR / "qa" / "results" / f"repro-status-{_dt.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(
            {
                "status_file": str(status_file),
                "completed": completed,
                "ready_final": ready_final,
                "stuck_at_non_ready": stuck,
                "pipeline_errors": pipeline_errors,
                "runs": runs,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=== SUMMARY ===")
    print(f"Pipeline completions:   {completed}/{N}")
    print(f"Final status=ready:     {ready_final}/{N}")
    print(f"Stuck at non-ready:     {stuck}/{N}")
    print(f"Pipeline errors:        {pipeline_errors}/{N}")
    if inconclusive:
        print()
        print("⚠  INCONCLUSIVE — all runs errored before completion. The race")
        print("   never had a chance to surface. Investigate the pipeline errors")
        print("   first, then re-run this harness.")
        print()
        print("   Errors:")
        for r in runs:
            if r["pipeline_error"]:
                print(f"   run {r['iter']}: {r['pipeline_error'][:120]}")
    elif stuck:
        print()
        print("⚠  Stuck runs (codex's race hypothesis confirmed in production):")
        for r in runs:
            if r["pipeline_error"] is None and r["status_after_run"] != "ready":
                print(f"   run {r['iter']}: status={r['status_after_run']!r} pct={r['stage_pct']} label={r['stage_label']!r}")
    else:
        print()
        print(f"✓  All {completed} completed runs ended at status=ready. The QA")
        print("   Tier C 'building 95%' artifact is QA-harness-only; close Fix 1")
        print("   as 'no production race; document limitation in run_qa.py'.")
    print(f"\nDetails: {out_dir / 'summary.json'}")
    # Exit codes:
    #   0 — production is clean (all completed runs ended at ready, at least one completed)
    #   1 — production race confirmed (≥1 stuck)
    #   2 — inconclusive (all errors; race never had a chance to surface)
    if inconclusive:
        return 2
    return 1 if stuck else 0


if __name__ == "__main__":
    raise SystemExit(main())
