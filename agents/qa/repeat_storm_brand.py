"""Repeat-run Storm Brand and Verdant Bow N times each to measure sprite
gate failure rate before the LinkedIn recording.

Codex's adversarial review said N=1 is too small to demote demo prompts;
this script gathers N=5 per prompt to make the call.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import json
import os
import sys
import traceback
from pathlib import Path

_AGENTS_DIR = Path(__file__).resolve().parent.parent
if str(_AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENTS_DIR))

from dotenv import load_dotenv

load_dotenv(_AGENTS_DIR / ".env")

from qa.corpus import by_id  # noqa: E402

import orchestrator  # noqa: E402


N = 5
PROMPT_IDS = (3, 9)  # Storm Brand, Verdant Elven Longbow


def main() -> int:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = _AGENTS_DIR / "qa" / "results" / f"repeat-{stamp}"
    out.mkdir(parents=True, exist_ok=True)

    # Isolate ModSources so we don't disturb real game state.
    qa_mods = out / "modsources"
    qa_mods.mkdir(parents=True, exist_ok=True)
    os.environ["FORGE_MOD_SOURCES_DIR"] = str(qa_mods)

    aggregate: dict[str, list[dict]] = {}
    loop = asyncio.new_event_loop()
    try:
        for pid in PROMPT_IDS:
            p = by_id(pid)
            runs: list[dict] = []
            for i in range(1, N + 1):
                request = {
                    "prompt": p.prompt,
                    "tier": p.tier,
                    "content_type": "Weapon",
                    "sub_type": "",
                    "mode": "compile",
                }
                run_record: dict = {"iter": i}
                try:
                    loop.run_until_complete(orchestrator.run_pipeline(request))
                    run_record["status"] = "completed"
                    run_record["error"] = None
                except Exception as exc:  # noqa: BLE001
                    msg = str(exc)
                    run_record["status"] = "error"
                    run_record["error"] = f"{type(exc).__name__}: {msg}"
                    # Tag the gate name if present in the error message.
                    for gate in (
                        "silhouette_readability", "occupancy",
                        "center_background_cleanup", "min_contrast_check",
                        "aspect_ratio_check", "min_pixel_count",
                        "max_pixel_count",
                    ):
                        if gate in msg:
                            run_record["gate"] = gate
                            break
                runs.append(run_record)
                gate_label = run_record.get("gate") or "—"
                print(
                    f"[#{p.id} iter {i}/{N}] {p.prompt[:50]!r:55s} "
                    f"status={run_record['status']:9s} gate={gate_label}",
                    flush=True,
                )

            passes = sum(1 for r in runs if r["status"] == "completed")
            fails = sum(1 for r in runs if r["status"] == "error")
            gate_breakdown: dict[str, int] = {}
            for r in runs:
                if r.get("gate"):
                    gate_breakdown[r["gate"]] = gate_breakdown.get(r["gate"], 0) + 1
            aggregate[f"id_{pid}"] = {
                "id": pid,
                "prompt": p.prompt,
                "passes": passes,
                "fails": fails,
                "fail_rate": fails / N,
                "gate_breakdown": gate_breakdown,
                "runs": runs,
            }
    finally:
        loop.close()

    out_file = out / "summary.json"
    out_file.write_text(json.dumps(aggregate, indent=2), encoding="utf-8")

    print("\n=== SUMMARY ===")
    for key, info in aggregate.items():
        print(
            f"#{info['id']:>2} {info['prompt']!r:55s} "
            f"pass={info['passes']}/{N} fail_rate={info['fail_rate']*100:.0f}% "
            f"gates={info['gate_breakdown']}"
        )
    print(f"\nDetails: {out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
