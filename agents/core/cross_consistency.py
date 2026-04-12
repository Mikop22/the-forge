"""Minimal cross-consistency gate for hidden audition outputs."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field

_WORD_RE = re.compile(r"[a-z0-9_]+")
_NEGATED_WORD_RE = re.compile(r"\b(?:no|without)\s+([a-z0-9_]+)")
_GENERIC_ART_WORDS = {"generic", "plain", "basic", "simple"}
_PACKAGE_SIGNAL_GROUPS = {
    "storm_brand": (
        ("storm", "lightning", "thunder"),
        ("brand", "mark", "starfall", "celestial"),
    ),
    "orbit_furnace": (
        ("orbit", "ring", "halo"),
        ("furnace", "ember", "heat", "molten", "fire"),
    ),
    "frost_shatter": (
        ("frost", "ice", "glacier", "cryo"),
        ("shatter", "crack", "crystal", "spike"),
    ),
}


class CrossConsistencyVerdict(BaseModel):
    """Compact result for the prompt/thesis/manifest/art consistency gate."""

    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    minimum_score: float = Field(default=0.6, ge=0.0, le=1.0)
    fail_reason: str | None = None


_MINIMUM_SCORE = CrossConsistencyVerdict.model_fields["minimum_score"].default


def evaluate_cross_consistency(
    *,
    prompt: str,
    thesis: Mapping[str, Any] | None,
    manifest: Mapping[str, Any] | None,
    item_visual_summary: str = "",
    projectile_visual_summary: str = "",
    item_motif_strength: float | None = None,
    item_family_coherence: float | None = None,
    item_sprite_gate_passed: bool | None = None,
    item_secondary_summary: str = "",
    projectile_secondary_summary: str = "",
    item_art_output: str = "",
    projectile_art_output: str = "",
) -> CrossConsistencyVerdict:
    """Score whether the art read still matches the combat fantasy.

    This is intentionally heuristic and text-based. It checks for a small set of
    package and fantasy signals in the art summaries and output metadata rather
    than pretending to be an image evaluator.
    """

    thesis_data = dict(thesis or {})
    manifest_data = dict(manifest or {})
    mechanics = _mapping(manifest_data.get("mechanics"))
    resolved_combat = _mapping(manifest_data.get("resolved_combat"))
    visuals = _mapping(manifest_data.get("visuals"))
    projectile_visuals = _mapping(manifest_data.get("projectile_visuals"))

    package_key = str(
        resolved_combat.get("package_key") or mechanics.get("combat_package") or ""
    ).strip()
    if not package_key:
        return CrossConsistencyVerdict(passed=True, score=1.0, fail_reason=None)

    context_text = " ".join(
        part
        for part in (
            prompt,
            str(thesis_data.get("fantasy") or ""),
            str(visuals.get("description") or ""),
            str(projectile_visuals.get("description") or ""),
            package_key,
            str(manifest_data.get("sub_type") or ""),
        )
        if part
    )
    primary_art_text = " ".join(
        part
        for part in (
            item_visual_summary,
            projectile_visual_summary,
        )
        if part
    )
    secondary_art_text = " ".join(
        part
        for part in (
            item_secondary_summary,
            projectile_secondary_summary,
        )
        if part
    )

    context_tokens = _tokenize(context_text)
    primary_art_tokens = _positive_tokens(primary_art_text)
    secondary_art_tokens = _positive_tokens(secondary_art_text).difference(
        primary_art_tokens
    )
    expected_groups = _expected_signal_groups(
        package_key=package_key, context_tokens=context_tokens
    )
    if not expected_groups:
        return CrossConsistencyVerdict(passed=True, score=1.0, fail_reason=None)

    matched: list[str] = []
    missing: list[str] = []
    signal_score = 0.0
    for group in expected_groups:
        label = "/".join(group)
        if primary_art_tokens.intersection(group):
            matched.append(label)
            signal_score += 1.0
            continue
        if secondary_art_tokens.intersection(group):
            signal_score += 0.25
            missing.append(label)
            continue
        missing.append(label)

    text_score = signal_score / len(expected_groups)
    structured_score = _structured_art_score(
        item_motif_strength=item_motif_strength,
        item_family_coherence=item_family_coherence,
        item_sprite_gate_passed=item_sprite_gate_passed,
    )
    if structured_score is None:
        score = 0.2 + (0.8 * text_score)
    elif not primary_art_tokens and not any(
        secondary_art_tokens.intersection(group) for group in expected_groups
    ):
        score = structured_score
    else:
        score = 0.15 + (0.15 * text_score) + (0.7 * structured_score)
    if missing and primary_art_tokens.intersection(_GENERIC_ART_WORDS):
        score = max(0.0, score - 0.2)

    passed = score >= _MINIMUM_SCORE
    fail_reason = None
    if not passed:
        reason_bits = []
        if package_key:
            reason_bits.append(f"{package_key} art mismatch")
        if missing:
            reason_bits.append(f"missing visual signals: {', '.join(missing)}")
        fail_reason = "; ".join(reason_bits) or "cross-consistency gate failed"

    return CrossConsistencyVerdict(
        passed=passed,
        score=round(score, 3),
        fail_reason=fail_reason,
    )


def apply_hidden_audition_consistency_gate(
    *,
    prompt: str,
    finalists: list[dict[str, Any]],
    art_audition: dict[str, Any],
):
    """Filter hidden-audition finalists through the cross-consistency gate."""
    from pixelsmith.models import (
        PixelsmithHiddenAuditionOutput,
        PixelsmithReviewedHiddenAuditionOutput,
    )

    audition = PixelsmithHiddenAuditionOutput.model_validate(art_audition)
    manifest_by_id = {
        str(manifest.get("candidate_id") or manifest.get("item_name") or ""): manifest
        for manifest in finalists
    }
    manifest_by_name = {
        str(manifest.get("item_name") or ""): manifest for manifest in finalists
    }

    rejection_reasons = dict(audition.candidate_archive.rejection_reasons)
    reports: dict[str, CrossConsistencyVerdict] = {}
    surviving_finalists = []

    for finalist in audition.art_scored_finalists:
        finalist_id = finalist.finalist_id
        manifest = manifest_by_id.get(finalist_id) or manifest_by_name.get(
            finalist.item_name
        )
        thesis = audition.candidate_archive.theses.get(finalist_id) or (
            (manifest or {}).get("weapon_thesis") or {}
        )
        verdict = evaluate_cross_consistency(
            prompt=prompt,
            thesis=thesis,
            manifest=manifest or {},
            item_visual_summary=finalist.item_visual_summary,
            projectile_visual_summary=finalist.projectile_visual_summary,
            item_motif_strength=finalist.observed_art_signals.item_motif_strength,
            item_family_coherence=finalist.observed_art_signals.item_family_coherence,
            item_sprite_gate_passed=finalist.observed_art_signals.item_sprite_gate_passed,
            item_secondary_summary=finalist.winner_art_scores.notes,
            projectile_secondary_summary=_winner_candidate_notes(finalist),
            item_art_output=finalist.item_sprite_path,
        )
        reports[finalist_id] = verdict
        if verdict.passed:
            surviving_finalists.append(finalist)
            continue
        rejection_reasons[finalist_id] = (
            verdict.fail_reason or "failed cross-consistency gate"
        )

    archive = audition.candidate_archive.model_copy(
        update={"rejection_reasons": rejection_reasons}
    )
    return PixelsmithReviewedHiddenAuditionOutput(
        status=audition.status,
        art_scored_finalists=surviving_finalists,
        candidate_archive=archive,
        cross_consistency_reports=reports,
        error=audition.error,
    )


def _expected_signal_groups(
    *, package_key: str, context_tokens: set[str]
) -> list[tuple[str, ...]]:
    groups = list(_PACKAGE_SIGNAL_GROUPS.get(package_key, ()))
    for group in (
        ("celestial", "astral", "star", "starfall", "cosmic"),
        ("storm", "lightning", "thunder"),
        ("frost", "ice", "glacier", "crystal"),
        ("furnace", "ember", "molten", "fire"),
    ):
        if context_tokens.intersection(group) and group not in groups:
            groups.append(group)
    return groups


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _winner_candidate_notes(finalist: Any) -> str:
    winner_candidate_id = str(getattr(finalist, "winner_candidate_id", "") or "")
    for candidate in getattr(finalist, "surviving_candidates", ()):
        if str(getattr(candidate, "candidate_id", "") or "") != winner_candidate_id:
            continue
        return str(getattr(candidate, "judge_notes", "") or "").strip()
    return ""


def _structured_art_score(
    *,
    item_motif_strength: float | None,
    item_family_coherence: float | None,
    item_sprite_gate_passed: bool | None,
) -> float | None:
    if (
        item_motif_strength is None
        and item_family_coherence is None
        and item_sprite_gate_passed is None
    ):
        return None

    motif = max(0.0, min(float(item_motif_strength or 0.0), 10.0)) / 10.0
    family = max(0.0, min(float(item_family_coherence or 0.0), 10.0)) / 10.0
    gate = 1.0 if item_sprite_gate_passed else 0.0
    return (0.45 * motif) + (0.45 * family) + (0.10 * gate)


def _tokenize(text: str) -> set[str]:
    return {match.group(0) for match in _WORD_RE.finditer(text.lower())}


def _positive_tokens(text: str) -> set[str]:
    tokens = _tokenize(text)
    negated = {match.group(1) for match in _NEGATED_WORD_RE.finditer(text.lower())}
    return tokens.difference(negated)
