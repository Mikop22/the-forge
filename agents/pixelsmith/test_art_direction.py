from __future__ import annotations

import pytest
from pydantic import ValidationError

from pixelsmith.art_direction import map_art_direction_profile
from pixelsmith.models import PixelsmithInput


def test_art_direction_profile_maps_to_wide_strategy() -> None:
    strategy = map_art_direction_profile("exploratory")

    assert strategy.profile == "exploratory"
    assert strategy.strategy_bucket == "wide"
    assert strategy.variant_count >= 2


def test_pixelsmith_input_rejects_unknown_art_direction_profile() -> None:
    with pytest.raises(ValidationError):
        PixelsmithInput.model_validate(
            {
                "item_name": "Star Forge",
                "visuals": {
                    "description": "A blade with a bright core.",
                    "art_direction_profile": "unbounded-chaos",
                },
            }
        )
