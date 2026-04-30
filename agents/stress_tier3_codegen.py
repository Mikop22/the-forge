#!/usr/bin/env python3
"""Run Tier 3 codegen stress without art generation or tModLoader build."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

_AGENTS_DIR = Path(__file__).resolve().parent
if str(_AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENTS_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_AGENTS_DIR / ".env")

from architect.architect import ArchitectAgent  # noqa: E402
from architect.prompt_director import enhance_prompt  # noqa: E402
from forge_master.forge_master import CoderAgent  # noqa: E402
from stress_tier3_basis import DEFAULT_PROMPTS, _infer_sub_type  # noqa: E402


@dataclass
class CodegenStressResult:
    prompt: str
    enhanced_prompt: str
    sub_type: str
    item_name: str
    atom_kinds: list[str]
    status: str
    passed: bool
    failures: list[str]
    manifest_path: str = ""
    cs_path: str = ""


def run_codegen_stress(
    prompts: Iterable[str] = DEFAULT_PROMPTS,
    *,
    tier: str = "Tier3_Hardmode",
    output_dir: Path | str = _AGENTS_DIR / "output" / "tier3_codegen_stress",
    architect=None,
    coder=None,
    skip_reference_search: bool = True,
    progress: bool = False,
) -> list[CodegenStressResult]:
    architect = architect or ArchitectAgent()
    if skip_reference_search and hasattr(architect, "_reference_policy"):
        architect._reference_policy = _NoopReferencePolicy()
    coder = coder or CoderAgent()
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[CodegenStressResult] = []
    for index, prompt in enumerate(prompts, start=1):
        if progress:
            print(f"[{index}] start: {prompt}", file=sys.stderr, flush=True)
        result = _stress_prompt(
            index=index,
            prompt=prompt,
            tier=tier,
            output_dir=out_dir,
            architect=architect,
            coder=coder,
        )
        results.append(result)
        if progress:
            status = "PASS" if result.passed else "FAIL"
            print(
                f"[{index}] {status}: {result.item_name or result.sub_type}",
                file=sys.stderr,
                flush=True,
            )
    return results


def _stress_prompt(
    *,
    index: int,
    prompt: str,
    tier: str,
    output_dir: Path,
    architect,
    coder,
) -> CodegenStressResult:
    director = enhance_prompt(prompt, tier=tier)
    sub_type = _infer_sub_type(prompt)
    failures: list[str] = []
    manifest: dict = {}
    code_result: dict = {}
    manifest_path = ""
    cs_path = ""

    try:
        manifest = architect.generate_manifest(
            prompt=director.enhanced_prompt,
            tier=tier,
            content_type="Weapon",
            sub_type=sub_type,
            raw_prompt=director.raw_prompt,
            protected_reference_terms=director.protected_reference_terms,
            reference_subject=director.reference_subject,
            reference_slots=director.reference_slots,
        )
    except Exception as exc:  # pragma: no cover - exercised in live stress.
        failures.append(f"Architect error: {exc}")
        return _result(
            prompt=prompt,
            enhanced_prompt=director.enhanced_prompt,
            sub_type=sub_type,
            manifest=manifest,
            code_result=code_result,
            failures=failures,
        )

    item_name = str(manifest.get("item_name") or f"Stress{index}")
    stem = f"{index:02d}_{_safe_name(item_name)}"
    manifest_file = output_dir / f"{stem}.manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    manifest_path = str(manifest_file)

    try:
        code_result = coder.write_code(manifest)
    except Exception as exc:  # pragma: no cover - exercised in live stress.
        failures.append(f"Coder error: {exc}")
        return _result(
            prompt=prompt,
            enhanced_prompt=director.enhanced_prompt,
            sub_type=sub_type,
            manifest=manifest,
            code_result=code_result,
            failures=failures,
            manifest_path=manifest_path,
        )

    status = str(code_result.get("status") or "")
    cs_code = str(code_result.get("cs_code") or "")
    if cs_code:
        cs_file = output_dir / f"{stem}.cs"
        cs_file.write_text(cs_code, encoding="utf-8")
        cs_path = str(cs_file)

    if status != "success":
        error = code_result.get("error") if isinstance(code_result.get("error"), dict) else {}
        message = str(error.get("message") or code_result.get("error_message") or status)
        failures.append(message)
    if not cs_code and status == "success":
        failures.append("codegen returned success without cs_code")

    return _result(
        prompt=prompt,
        enhanced_prompt=director.enhanced_prompt,
        sub_type=sub_type,
        manifest=manifest,
        code_result=code_result,
        failures=failures,
        manifest_path=manifest_path,
        cs_path=cs_path,
    )


def _result(
    *,
    prompt: str,
    enhanced_prompt: str,
    sub_type: str,
    manifest: dict,
    code_result: dict,
    failures: list[str],
    manifest_path: str = "",
    cs_path: str = "",
) -> CodegenStressResult:
    return CodegenStressResult(
        prompt=prompt,
        enhanced_prompt=enhanced_prompt,
        sub_type=sub_type,
        item_name=str(manifest.get("item_name") or ""),
        atom_kinds=_atom_kinds(manifest),
        status=str(code_result.get("status") or ("error" if failures else "")),
        passed=not failures,
        failures=failures,
        manifest_path=manifest_path,
        cs_path=cs_path,
    )


def _atom_kinds(manifest: dict) -> list[str]:
    ir = manifest.get("mechanics_ir") if isinstance(manifest, dict) else {}
    atoms = ir.get("atoms") if isinstance(ir, dict) else []
    if not isinstance(atoms, list):
        return []
    return [
        str(atom.get("kind"))
        for atom in atoms
        if isinstance(atom, dict) and str(atom.get("kind") or "").strip()
    ]


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    return safe or "stress_case"


class _NoopReferencePolicy:
    def resolve(self, **kwargs) -> dict:
        return {
            "reference_needed": bool(kwargs.get("reference_needed")),
            "reference_subject": kwargs.get("reference_subject"),
            "reference_image_url": None,
            "generation_mode": "text_to_image",
            "reference_attempts": 0,
            "reference_notes": "codegen_stress_reference_search_skipped",
        }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", default="Tier3_Hardmode")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_AGENTS_DIR / "output" / "tier3_codegen_stress",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Run only the first N prompts (default: all)",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=1,
        help="1-based prompt index to start from (default: 1)",
    )
    parser.add_argument(
        "--reference-search",
        action="store_true",
        help="Allow live BrowserReferenceFinder/approval during Architect finalization",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high"),
        default="low",
        help="Reasoning effort for Forge Master codegen during stress runs",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=90,
        help="Per-request timeout for codegen models during stress runs",
    )
    return parser.parse_args()


def main() -> None:
    ns = _parse_args()
    os.environ["FORGE_BESPOKE_REASONING_EFFORT"] = ns.reasoning_effort
    os.environ["FORGE_CODEGEN_REASONING_EFFORT"] = ns.reasoning_effort
    os.environ["FORGE_BESPOKE_TIMEOUT_SECONDS"] = str(ns.timeout_seconds)
    os.environ["FORGE_CODEGEN_TIMEOUT_SECONDS"] = str(ns.timeout_seconds)
    start_index = max(ns.start, 1) - 1
    prompts = DEFAULT_PROMPTS[start_index:]
    if ns.limit:
        prompts = prompts[: ns.limit]
    results = run_codegen_stress(
        prompts,
        tier=ns.tier,
        output_dir=ns.output_dir,
        skip_reference_search=not ns.reference_search,
        progress=not ns.json,
    )
    if ns.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        for result in results:
            status = "PASS" if result.passed else "FAIL"
            atoms = ", ".join(result.atom_kinds)
            print(f"{status} | {result.sub_type:<7} | {result.item_name:<28} | {atoms}")
            print(f"     {result.prompt}")
            for failure in result.failures:
                print(f"     - {failure}")
    raise SystemExit(0 if all(result.passed for result in results) else 1)


if __name__ == "__main__":
    main()
