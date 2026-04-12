"""Archive records for weapon lab audition runs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from core.weapon_lab_models import ArtDirection, JudgeScore, WeaponThesis


class RuntimeGateRecord(BaseModel):
    """Archived runtime gate outcome for one hidden-audition finalist."""

    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(..., min_length=1)
    passed: bool
    reason: str | None = None
    observed_hits_to_cashout: int | None = None
    observed_time_to_cashout_ms: int | None = None


class WeaponLabArchive(BaseModel):
    """Serializable archive for prompt, candidates, and final rationale."""

    model_config = ConfigDict(frozen=True)

    prompt: str = Field(..., min_length=1)
    theses: dict[str, WeaponThesis] = Field(default_factory=dict)
    finalists: list[str] = Field(default_factory=list)
    art_strategies: dict[str, ArtDirection] = Field(default_factory=dict)
    judge_scores: dict[str, list[JudgeScore]] = Field(default_factory=dict)
    rejection_reasons: dict[str, str] = Field(default_factory=dict)
    reroll_ancestry: dict[str, list[str]] = Field(default_factory=dict)
    runtime_gate_records: dict[str, RuntimeGateRecord] = Field(default_factory=dict)
    winning_finalist_id: str | None = None
    final_winner_rationale: str | None = None
