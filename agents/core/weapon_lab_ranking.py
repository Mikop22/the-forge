"""Stable import path for weapon lab ranking policy.

``RankingPolicy`` is defined in ``core.weapon_lab_models``; this module re-exports it so lab
code can depend on a single ``weapon_lab_ranking`` surface without touching models directly.
"""

from __future__ import annotations

from core.weapon_lab_models import RankingPolicy

__all__ = ["RankingPolicy"]
