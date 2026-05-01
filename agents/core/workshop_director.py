"""Bounded variant generation for the Forge Director workshop.

Always emits **three** workshop variants from the bench manifest. ``directive`` text picks a
template triple (labels + narrative strings); ``_materialize_manifest`` applies small **stat
deltas** per theme so variants differ without rerolling codegen:

- ``stronger-impact``: +1 damage, +0.5 knockback (heavier hit feel).
- ``cleaner-read``: −1 use_time (snappier cadence), capped at 1.
- ``bigger-spectacle``: +2 damage, +1 use_time (more wind-up / payoff framing).

Those numbers are deliberately modest tuning knobs for UX comparison, not balance doctrine.
"""

from __future__ import annotations

import copy
from typing import Any


def _variant_templates(directive: str) -> list[tuple[str, str, str, str]]:
    text = directive.lower().strip()
    if "heavier" in text or "weight" in text or "impact" in text:
        return [
            ("stronger-impact", "Heavier Shot", "Pushes more weight into the projectile read.", "Leans into heavier travel and impact."),
            ("cleaner-read", "Punchier Cast", "Keeps the shot readable but sharpens the release.", "More front-loaded cast emphasis."),
            ("bigger-spectacle", "Clean Pressure", "Adds force without making the projectile busier.", "Heavier feel with restrained presentation."),
        ]
    if "clean" in text or "read" in text or "clarity" in text:
        return [
            ("cleaner-read", "Cleaner Read", "Strips noise around the main shot silhouette.", "Focuses on readability."),
            ("stronger-impact", "Tighter Core", "Keeps the identity but narrows the effect footprint.", "Less spread, more focus."),
            ("bigger-spectacle", "Signal First", "Prioritizes what the player should notice first.", "More clarity per frame."),
        ]
    if "cast" in text or "dramatic" in text:
        return [
            ("bigger-spectacle", "Charged Cast", "Pushes the release moment harder than the travel.", "More dramatic muzzle read."),
            ("cleaner-read", "Arc Ritual", "Emphasizes pre-fire energy over sustained motion.", "Bigger cast without changing the core shot."),
            ("stronger-impact", "Flash Release", "Short, bright cast emphasis with a cleaner follow-through.", "Improves the moment of release."),
        ]
    return [
        ("stronger-impact", "Take One", "A direct response to the current direction.", "Balances the requested change against the current bench."),
        ("bigger-spectacle", "Take Two", "Pushes the direction further.", "A stronger interpretation of the same note."),
        ("cleaner-read", "Take Three", "Looks for a cleaner answer to the same problem.", "Trades some spectacle for readability."),
    ]


def _materialize_manifest(bench_manifest: dict[str, Any], theme: str, label: str) -> dict[str, Any]:
    manifest = copy.deepcopy(bench_manifest)
    stats = manifest.get("stats")
    if isinstance(stats, dict):
        damage = stats.get("damage")
        knockback = stats.get("knockback")
        use_time = stats.get("use_time")

        if theme == "stronger-impact":
            if isinstance(damage, (int, float)):
                stats["damage"] = damage + 1
            if isinstance(knockback, (int, float)):
                stats["knockback"] = round(float(knockback) + 0.5, 1)
        elif theme == "cleaner-read":
            if isinstance(use_time, (int, float)):
                stats["use_time"] = max(1, int(use_time) - 1)
        elif theme == "bigger-spectacle":
            if isinstance(damage, (int, float)):
                stats["damage"] = damage + 2
            if isinstance(use_time, (int, float)):
                stats["use_time"] = int(use_time) + 1

        manifest["stats"] = stats

    manifest["workshop_variant_label"] = label
    manifest["workshop_variant_theme"] = theme
    return manifest


def build_variants(
    *,
    bench_manifest: dict[str, Any],
    directive: str,
    session_id: str = "sess",
    sprite_path: str | None = None,
    projectile_sprite_path: str | None = None,
) -> list[dict[str, Any]]:
    """Produce three labeled variants from ``bench_manifest`` using ``directive`` template selection."""
    variants: list[dict[str, Any]] = []
    for idx, (theme, label, rationale, change_summary) in enumerate(_variant_templates(directive), start=1):
        variants.append(
            {
                "variant_id": f"{session_id}-v{idx}",
                "label": label,
                "rationale": rationale,
                "change_summary": change_summary,
                "manifest": _materialize_manifest(bench_manifest, theme, label),
                "sprite_path": sprite_path,
                "projectile_sprite_path": projectile_sprite_path,
            }
        )
    return variants
