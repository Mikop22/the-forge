"""Recovery/search policy helpers for hidden audition rerolls."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from core.weapon_lab_models import SearchBudget, WeaponThesis

RecoverySearchProfile = Literal["steady", "wide", "wild"]

_WORD_RE = re.compile(r"[a-z0-9]+")


class RecoveryMode(BaseModel):
    """Explicit knobs for rerolling hidden batches after failures."""

    model_config = ConfigDict(frozen=True)

    failed_batches: int = Field(..., ge=0)
    search_profile: RecoverySearchProfile
    search_budget: SearchBudget
    novelty_bias: int = Field(..., ge=0)
    quality_threshold: float = Field(..., ge=0.0)
    discard_weak_batches: bool = True
    dedupe_fingerprints: bool = True
    allow_quality_drop: bool = False


def next_recovery_mode(
    *,
    failed_batches: int,
    base_budget: SearchBudget | None = None,
    quality_threshold: float,
) -> RecoveryMode:
    """Escalate search breadth and novelty without relaxing the quality bar."""

    budget = base_budget or SearchBudget(
        max_candidates=6, finalist_count=2, reroll_limit=1
    )
    if failed_batches >= 3:
        return RecoveryMode(
            failed_batches=failed_batches,
            search_profile="wild",
            search_budget=SearchBudget(
                max_candidates=budget.max_candidates + 4,
                finalist_count=budget.finalist_count,
                reroll_limit=budget.reroll_limit + 2,
            ),
            novelty_bias=3,
            quality_threshold=quality_threshold,
        )
    if failed_batches >= 1:
        return RecoveryMode(
            failed_batches=failed_batches,
            search_profile="wide",
            search_budget=SearchBudget(
                max_candidates=budget.max_candidates + 2,
                finalist_count=budget.finalist_count,
                reroll_limit=budget.reroll_limit + 1,
            ),
            novelty_bias=1,
            quality_threshold=quality_threshold,
        )
    return RecoveryMode(
        failed_batches=failed_batches,
        search_profile="steady",
        search_budget=budget,
        novelty_bias=0,
        quality_threshold=quality_threshold,
    )


def fingerprint_thesis(thesis: WeaponThesis | Mapping[str, object]) -> str:
    """Collapse near-identical thesis wording into a stable search fingerprint."""

    parsed = (
        thesis
        if isinstance(thesis, WeaponThesis)
        else WeaponThesis.model_validate(thesis)
    )
    words = sorted(
        {
            _stem_word(match.group(0))
            for match in _WORD_RE.finditer(parsed.fantasy.lower())
            if len(match.group(0)) >= 4
        }
    )
    idea = " ".join(words[:8])
    return "|".join(
        [
            parsed.combat_package,
            parsed.loop_family,
            parsed.delivery_style,
            parsed.payoff_rate,
            idea,
        ]
    )


def dedupe_near_identical_candidates(
    candidates: Sequence[WeaponThesis | Mapping[str, object]],
) -> list[WeaponThesis]:
    """Preserve order while dropping candidates with matching recovery fingerprints."""

    deduped: list[WeaponThesis] = []
    seen_fingerprints: set[str] = set()
    for candidate in candidates:
        parsed = (
            candidate
            if isinstance(candidate, WeaponThesis)
            else WeaponThesis.model_validate(candidate)
        )
        fingerprint = fingerprint_thesis(parsed)
        if fingerprint in seen_fingerprints:
            continue
        seen_fingerprints.add(fingerprint)
        deduped.append(parsed)
    return deduped


def _stem_word(word: str) -> str:
    if len(word) > 4 and word.endswith("s"):
        return word[:-1]
    return word
