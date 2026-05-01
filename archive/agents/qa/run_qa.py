"""QA runner for prompt → output validation against modded Terraria standards.

Tiers:
  A — sub_type classification only (free, fast, full corpus)
  B — architect manifest generation (~$0.05/prompt OpenAI)
  C — full pipeline incl. sprite + C# + gatekeeper compile (~$0.30/prompt FAL+OpenAI)

Usage:
  python3 -m qa.run_qa --tier A
  python3 -m qa.run_qa --tier B
  python3 -m qa.run_qa --tier C

Results are written to agents/qa/results/<timestamp>/.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

# Make `agents/` importable as the package root when run from repo root.
_AGENTS_DIR = Path(__file__).resolve().parent.parent
if str(_AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENTS_DIR))

from dotenv import load_dotenv

load_dotenv(_AGENTS_DIR / ".env")

from qa.corpus import CORPUS, TIER_B_SUBSET_IDS, TIER_C_SUBSET_IDS, by_id, QAPrompt  # noqa: E402

import orchestrator  # noqa: E402
from architect.architect import ArchitectAgent  # noqa: E402
from architect.models import TIER_TABLE  # noqa: E402


# --------------------------------------------------------------------- helpers

def _results_dir() -> Path:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = _AGENTS_DIR / "qa" / "results" / stamp
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write(out: Path, name: str, data: Any) -> None:
    target = out / name
    if isinstance(data, (dict, list)):
        target.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    else:
        target.write_text(str(data), encoding="utf-8")


# --------------------------------------------------------------------- tier A

def run_tier_a(out: Path) -> dict[str, Any]:
    """Sub_type classification — pure function over prompt text."""
    rows: list[dict[str, Any]] = []
    for p in CORPUS:
        request = {
            "prompt": p.prompt,
            "tier": p.tier,
            "content_type": "Weapon",
            "sub_type": "",  # let orchestrator infer
        }
        actual = orchestrator._request_sub_type(request)
        rows.append({
            "id": p.id,
            "prompt": p.prompt,
            "category": p.category,
            "expected_sub_type": p.expected_sub_type,
            "actual_sub_type": actual,
            "match": actual == p.expected_sub_type,
        })

    summary = {
        "tier": "A",
        "total": len(rows),
        "passed": sum(1 for r in rows if r["match"]),
        "failed": [r for r in rows if not r["match"]],
        "results": rows,
    }
    _write(out, "tier_a.json", summary)
    return summary


# --------------------------------------------------------------------- tier B

def _validate_manifest_against_tier(manifest: dict[str, Any], tier: str) -> list[str]:
    """Return a list of issue strings (empty list = clean).

    Stats live under ``manifest['stats']`` per ``architect/models.py``; do not
    read from top-level.
    """
    issues: list[str] = []
    table = TIER_TABLE.get(tier)
    if table is None:
        issues.append(f"unknown tier {tier!r}")
        return issues

    stats = manifest.get("stats") or {}

    dmg = stats.get("damage")
    if isinstance(dmg, (int, float)):
        lo, hi = table["damage"]
        if not (lo <= dmg <= hi):
            issues.append(f"damage={dmg} outside tier range [{lo}, {hi}]")
    else:
        issues.append(f"damage missing or non-numeric: {dmg!r}")

    use_time = stats.get("use_time")
    if isinstance(use_time, (int, float)):
        lo, hi = table["use_time"]
        if not (lo <= use_time <= hi):
            issues.append(f"use_time={use_time} outside tier range [{lo}, {hi}]")
    else:
        issues.append(f"use_time missing or non-numeric: {use_time!r}")

    rarity = stats.get("rarity")
    if rarity != table["rarity"]:
        issues.append(f"rarity={rarity!r} != tier expected {table['rarity']!r}")

    return issues


def run_tier_b(out: Path) -> dict[str, Any]:
    architect = ArchitectAgent()
    rows: list[dict[str, Any]] = []
    for pid in TIER_B_SUBSET_IDS:
        p = by_id(pid)
        # Mirror production: orchestrator infers sub_type from prompt keywords
        # via _request_sub_type BEFORE handing off to architect.
        inferred_sub_type = orchestrator._request_sub_type({
            "prompt": p.prompt,
            "content_type": "Weapon",
            "sub_type": "",
        })
        try:
            manifest = architect.generate_manifest(
                prompt=p.prompt,
                tier=p.tier,
                content_type="Weapon",
                sub_type=inferred_sub_type,
            )
            issues = _validate_manifest_against_tier(manifest, p.tier)
            actual_sub_type = manifest.get("sub_type")
            sub_type_ok = actual_sub_type == p.expected_sub_type
            stats = manifest.get("stats") or {}
            row = {
                "id": p.id,
                "prompt": p.prompt,
                "expected_sub_type": p.expected_sub_type,
                "inferred_sub_type": inferred_sub_type,
                "actual_sub_type": actual_sub_type,
                "tier": p.tier,
                "manifest_subset": {
                    "item_name": manifest.get("item_name"),
                    "sub_type": manifest.get("sub_type"),
                    "damage": stats.get("damage"),
                    "use_time": stats.get("use_time"),
                    "rarity": stats.get("rarity"),
                    "tooltip": manifest.get("tooltip"),
                    "visuals_description": (manifest.get("visuals") or {}).get("description"),
                },
                "stat_issues": issues,
                "verdict": "pass" if sub_type_ok and not issues else "fail",
            }
            _write(out, f"tier_b_{pid:02d}_manifest.json", manifest)
        except Exception as exc:  # noqa: BLE001
            row = {
                "id": p.id,
                "prompt": p.prompt,
                "expected_sub_type": p.expected_sub_type,
                "tier": p.tier,
                "error": f"{type(exc).__name__}: {exc}",
                "trace": traceback.format_exc(),
                "verdict": "error",
            }
        rows.append(row)
        print(f"[Tier B] #{p.id} {p.prompt!r:50s} → {row.get('verdict')}", flush=True)

    summary = {
        "tier": "B",
        "total": len(rows),
        "passed": sum(1 for r in rows if r.get("verdict") == "pass"),
        "results": rows,
    }
    _write(out, "tier_b.json", summary)
    return summary


# --------------------------------------------------------------------- tier C

async def _run_pipeline_for_prompt(p: QAPrompt) -> dict[str, Any]:
    request = {
        "prompt": p.prompt,
        "tier": p.tier,
        "content_type": "Weapon",
        "sub_type": "",
        "mode": "compile",
    }
    await orchestrator.run_pipeline(request)
    # After run_pipeline, orchestrator writes outputs under ModSources.
    # Inspect generation_status.json for the final manifest + sprite paths.
    from core.paths import mod_sources_root  # late import to honor env var
    mods = mod_sources_root()
    status_path = Path(mods) / "generation_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
    return status


def run_tier_c(out: Path) -> dict[str, Any]:
    # Isolate ModSources to the QA results dir so we don't disturb real game state.
    qa_mods = out / "modsources"
    qa_mods.mkdir(parents=True, exist_ok=True)
    os.environ["FORGE_MOD_SOURCES_DIR"] = str(qa_mods)

    rows: list[dict[str, Any]] = []
    loop = asyncio.new_event_loop()
    try:
        for pid in TIER_C_SUBSET_IDS:
            p = by_id(pid)
            try:
                status = loop.run_until_complete(_run_pipeline_for_prompt(p))
                manifest = status.get("manifest") or {}
                actual_sub_type = manifest.get("sub_type")
                stat_issues = _validate_manifest_against_tier(manifest, p.tier) if manifest else ["no manifest"]
                pipeline_status = status.get("status")
                error_code = status.get("error_code")
                error_msg = status.get("message") if pipeline_status == "error" else None
                sprite_path = status.get("sprite_path")
                sub_type_ok = actual_sub_type == p.expected_sub_type
                verdict = (
                    "pass"
                    if pipeline_status == "ready" and sub_type_ok and not stat_issues
                    else "fail"
                )
                stats = manifest.get("stats") or {}
                row = {
                    "id": p.id,
                    "prompt": p.prompt,
                    "tier": p.tier,
                    "expected_sub_type": p.expected_sub_type,
                    "actual_sub_type": actual_sub_type,
                    "pipeline_status": pipeline_status,
                    "error_code": error_code,
                    "error_message": error_msg,
                    "sprite_path": sprite_path,
                    "stat_issues": stat_issues,
                    "manifest_subset": {
                        "item_name": manifest.get("item_name"),
                        "sub_type": manifest.get("sub_type"),
                        "damage": stats.get("damage"),
                        "use_time": stats.get("use_time"),
                        "rarity": stats.get("rarity"),
                        "tooltip": manifest.get("tooltip"),
                        "shoot_projectile": (manifest.get("mechanics") or {}).get("shoot_projectile"),
                    },
                    "verdict": verdict,
                }
                _write(out, f"tier_c_{pid:02d}_status.json", status)
            except Exception as exc:  # noqa: BLE001
                row = {
                    "id": p.id,
                    "prompt": p.prompt,
                    "tier": p.tier,
                    "expected_sub_type": p.expected_sub_type,
                    "error": f"{type(exc).__name__}: {exc}",
                    "trace": traceback.format_exc(),
                    "verdict": "error",
                }
            rows.append(row)
            print(f"[Tier C] #{p.id} {p.prompt!r:50s} → {row.get('verdict')}", flush=True)
    finally:
        loop.close()

    summary = {
        "tier": "C",
        "total": len(rows),
        "passed": sum(1 for r in rows if r.get("verdict") == "pass"),
        "results": rows,
    }
    _write(out, "tier_c.json", summary)
    return summary


# --------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", choices=["A", "B", "C", "all"], required=True)
    args = ap.parse_args()

    out = _results_dir()
    print(f"QA results → {out}", flush=True)

    if args.tier in ("A", "all"):
        a = run_tier_a(out)
        print(f"Tier A: {a['passed']}/{a['total']} passed", flush=True)
        if a["failed"]:
            print(f"  failures: {[f['id'] for f in a['failed']]}", flush=True)

    if args.tier in ("B", "all"):
        b = run_tier_b(out)
        print(f"Tier B: {b['passed']}/{b['total']} passed", flush=True)

    if args.tier in ("C", "all"):
        c = run_tier_c(out)
        print(f"Tier C: {c['passed']}/{c['total']} passed", flush=True)

    print(f"\nResults dir: {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
