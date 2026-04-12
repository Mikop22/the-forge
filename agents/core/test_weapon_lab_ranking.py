"""Tests for agents/core/weapon_lab_ranking.py."""

from __future__ import annotations

from core.weapon_lab_ranking import RankingPolicy


def test_ranking_policy_default_includes_good_and_bad_anchors() -> None:
    policy = RankingPolicy.default()

    assert policy.anchor_sets.good
    assert policy.anchor_sets.bad
