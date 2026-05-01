from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class ReferenceSlotIntent(BaseModel):
    subject: str = ""
    protected_terms: list[str] = Field(default_factory=list)


class ReferenceSlotsIntent(BaseModel):
    item: ReferenceSlotIntent = Field(default_factory=ReferenceSlotIntent)
    projectile: ReferenceSlotIntent = Field(default_factory=ReferenceSlotIntent)

    def __getitem__(self, key: str) -> ReferenceSlotIntent:
        if key not in {"item", "projectile"}:
            raise KeyError(key)
        return getattr(self, key)


class PromptDirectorResult(BaseModel):
    raw_prompt: str
    enhanced_prompt: str
    protected_reference_terms: list[str] = Field(default_factory=list)
    reference_slots: ReferenceSlotsIntent = Field(default_factory=ReferenceSlotsIntent)
    reference_subject: str = ""
    mechanics_intent: str = ""
    spectacle_intent: str = ""

    @model_validator(mode="after")
    def enhanced_prompt_must_not_be_empty(self) -> "PromptDirectorResult":
        if not self.enhanced_prompt.strip():
            self.enhanced_prompt = self.raw_prompt
        return self


REFERENCE_TERM_PATTERNS = (
    ("gojo", ("gojo",)),
    ("hollow purple", ("hollow purple", "hollow-purple", "hollowpurple")),
    ("jjk", ("jjk", "jujutsu kaisen")),
)


def _normalized_prompt(prompt: str) -> str:
    return " ".join(prompt.lower().replace("-", " ").split())


def _protected_terms(prompt: str) -> list[str]:
    lowered = prompt.lower()
    normalized = _normalized_prompt(prompt)
    terms: list[str] = []
    for canonical, variants in REFERENCE_TERM_PATTERNS:
        if any(variant in lowered or variant in normalized for variant in variants):
            terms.append(canonical)
    return terms


def _has_hollow_purple_intent(prompt: str) -> bool:
    normalized = _normalized_prompt(prompt)
    lowered = prompt.lower()
    if "hollow purple" in normalized or "hollowpurple" in lowered:
        return True
    return "gojo" in normalized and "purple" in normalized


def enhance_prompt(raw_prompt: str, tier: str = "") -> PromptDirectorResult:
    terms = _protected_terms(raw_prompt)

    if _has_hollow_purple_intent(raw_prompt):
        if tier == "Tier3_Hardmode":
            enhanced = (
                "a forbidden staff that charges a slow black-violet singularity, "
                "pulls enemies inward, tears space behind it, then collapses into "
                "a huge hollow-purple shockwave"
            )
        else:
            enhanced = (
                "a black-violet weapon that releases a compact hollow-purple "
                "singularity projectile with a clear charging pulse"
            )
        return PromptDirectorResult(
            raw_prompt=raw_prompt,
            enhanced_prompt=enhanced,
            protected_reference_terms=terms,
            reference_slots=ReferenceSlotsIntent(
                projectile=ReferenceSlotIntent(
                    subject="Gojo Hollow Purple from JJK",
                    protected_terms=terms,
                )
            ),
            reference_subject="Gojo Hollow Purple from JJK" if terms else "",
            mechanics_intent=(
                "charged singularity projectile with gravity pull and collapse payoff"
            ),
            spectacle_intent=(
                "black-violet spatial distortion, inward particle flow, massive "
                "purple shockwave"
            ),
        )

    return PromptDirectorResult(
        raw_prompt=raw_prompt,
        enhanced_prompt=raw_prompt,
        protected_reference_terms=terms,
    )
