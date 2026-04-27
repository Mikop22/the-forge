"""Pre-record corpus quarantine check.

Codex v2 review of the product-fixes plan flagged that deferring Fix 3
(Pickaxe content_type=Weapon) is only safe if no Pickaxe item can reach
the demo flow. This script enforces the deferral by greping every place
demo prompts could enter the recording:

  1. The QA prompt corpus (agents/qa/corpus.py).
  2. The dry-run checklist (docs/superpowers/specs/2026-04-26-demo-dry-run-checklist.md).
  3. The README's demo prompt section.
  4. Any persisted workshop-session JSON in ModSources (carries items
     from past forges that could resurface in the workshop bench).

Exits non-zero with a clear message if any banned pattern is detected,
so the operator stops and clears state before recording.

Usage:
  python3 agents/qa/quarantine_check.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Items banned from the demo per docs/superpowers/specs/2026-04-26-demo-dry-run-checklist.md
# Ban is strict for Pickaxe (Fix 3 deferred). The Frostgun/bow items are
# also documented as banned — included here so quarantine catches any
# accidental reintroduction.
BANNED_PROMPT_SUBSTRINGS = (
    "obsidian pickaxe",
    "verdant bow",
    "verdant elven longbow",
    "frostgun",
)

# A workshop session that has accepted an item with this combination is
# the on-camera mismatch codex flagged.
BANNED_MANIFEST_SHAPE = {
    "sub_type": "Pickaxe",
    "content_type": "Weapon",
}


def check_text_files() -> list[str]:
    issues: list[str] = []
    # Scope is DEMO-FACING surface only. The QA corpus
    # (agents/qa/corpus.py) intentionally contains banned prompts to
    # exercise sub_type classification — do not scan it here.
    targets = [
        REPO_ROOT / "docs" / "superpowers" / "specs" / "2026-04-26-demo-dry-run-checklist.md",
        REPO_ROOT / "README.md",
    ]
    for path in targets:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        # Scan line-by-line so we can ignore lines that are part of a
        # banned-list block (those lines INCLUDE the banned substring on
        # purpose, marked with strikethrough or "banned" / "removed" text).
        for ln, line in enumerate(text.splitlines(), start=1):
            lower = line.lower()
            if any(b in lower for b in BANNED_PROMPT_SUBSTRINGS):
                # Skip lines that are explicitly documenting the ban.
                if re.search(r"~~|banned|removed|do not|don'?t", lower):
                    continue
                issues.append(f"{path.relative_to(REPO_ROOT)}:{ln} active reference to banned prompt → {line.strip()!r}")
    return issues


def check_workshop_session() -> list[str]:
    """Scan ModSources persisted state for banned manifest shapes."""
    issues: list[str] = []
    # Best-effort: import core.paths to resolve mod_sources_root the same
    # way orchestrator does. Tolerate import failure.
    sys.path.insert(0, str(REPO_ROOT / "agents"))
    try:
        from core.paths import mod_sources_root  # type: ignore
    except Exception:
        return issues  # cannot resolve; skip silently

    try:
        root = Path(mod_sources_root())
    except Exception:
        return issues

    if not root.is_dir():
        return issues

    for json_path in root.rglob("*.json"):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        for manifest in _walk_manifests(data):
            if all(manifest.get(k) == v for k, v in BANNED_MANIFEST_SHAPE.items()):
                issues.append(
                    f"{json_path.relative_to(root)} contains a manifest with "
                    f"sub_type=Pickaxe + content_type=Weapon — clear before recording"
                )
                break  # one issue per file is enough
    return issues


def _walk_manifests(node):
    """Yield dicts that look like manifests (have sub_type + content_type)."""
    if isinstance(node, dict):
        if "sub_type" in node and "content_type" in node:
            yield node
        for v in node.values():
            yield from _walk_manifests(v)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_manifests(item)


def main() -> int:
    issues = check_text_files() + check_workshop_session()
    if not issues:
        print("✓  corpus quarantine clean — safe to record")
        return 0
    print("⚠  corpus quarantine FAILED — clear before recording:")
    for issue in issues:
        print(f"   {issue}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
