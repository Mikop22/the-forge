"""Tests for agents/core/runtime_capabilities.py."""

from __future__ import annotations

from core.runtime_capabilities import RuntimeCapabilityMatrix


def test_default_runtime_capability_matrix_supports_staff_mark_cashout() -> None:
    matrix = RuntimeCapabilityMatrix.default()

    assert matrix.supported_loop_families == {
        "Weapon": {
            "Staff": ("mark_cashout",),
        }
    }

    assert (
        matrix.supports(
            content_type="Weapon",
            sub_type="Staff",
            loop_family="mark_cashout",
        )
        is True
    )
