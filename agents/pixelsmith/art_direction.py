"""Bounded art-direction profiles for Pixelsmith strategy selection."""

from __future__ import annotations

try:
    from pixelsmith.models import ArtDirectionProfileLiteral, ArtDirectionStrategy
except ImportError:
    from models import ArtDirectionProfileLiteral, ArtDirectionStrategy


_PROFILE_TO_STRATEGY: dict[ArtDirectionProfileLiteral, ArtDirectionStrategy] = {
    "conservative": ArtDirectionStrategy(
        profile="conservative",
        strategy_bucket="tight",
        variant_count=1,
        prompt_intensity="literal",
    ),
    "balanced": ArtDirectionStrategy(
        profile="balanced",
        strategy_bucket="balanced",
        variant_count=2,
        prompt_intensity="balanced",
    ),
    "exploratory": ArtDirectionStrategy(
        profile="exploratory",
        strategy_bucket="wide",
        variant_count=4,
        prompt_intensity="expressive",
    ),
}


def map_art_direction_profile(
    profile: ArtDirectionProfileLiteral,
) -> ArtDirectionStrategy:
    """Map a bounded art profile to a small internal generation strategy."""
    return _PROFILE_TO_STRATEGY[profile].model_copy(deep=True)
