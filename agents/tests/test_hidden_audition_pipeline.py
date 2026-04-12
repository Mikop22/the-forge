from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import orchestrator
import pytest


def _make_finalist(candidate_id: str, item_name: str) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "item_name": item_name,
        "package_key": "storm_brand",
        "loop_family": "mark_cashout",
        "behavior_contract": {
            "seed_event": "seed_triggered",
            "escalate_event": "escalate_triggered",
            "cashout_event": "cashout_triggered",
            "max_hits_to_cashout": 3,
            "max_time_to_cashout_ms": 2500,
        },
        "manifest": {"item_name": item_name},
    }


def test_hidden_audition_pipeline_only_reveals_winner_after_runtime_gate_passes() -> (
    None
):
    async def run() -> None:
        finalists = [
            _make_finalist("candidate-001", "Storm Brand"),
            _make_finalist("candidate-002", "Star Verdict"),
        ]
        reviewed_audition = {
            "status": "success",
            "art_scored_finalists": [
                {
                    "finalist_id": "candidate-001",
                    "item_name": "Storm Brand",
                    "item_sprite_path": "/tmp/storm-brand.png",
                    "projectile_sprite_path": "/tmp/storm-brand-proj.png",
                    "winner_candidate_id": "candidate-001-art-001",
                    "winner_art_scores": {
                        "motif_strength": 8.0,
                        "family_coherence": 8.0,
                        "notes": "clear",
                    },
                    "winner_sprite_gate_report": {
                        "sprite_kind": "item",
                        "passed": True,
                        "foreground_bbox": [8, 6, 23, 25],
                        "checks": {},
                    },
                    "surviving_candidates": [],
                },
                {
                    "finalist_id": "candidate-002",
                    "item_name": "Star Verdict",
                    "item_sprite_path": "/tmp/star-verdict.png",
                    "projectile_sprite_path": "/tmp/star-verdict-proj.png",
                    "winner_candidate_id": "candidate-002-art-001",
                    "winner_art_scores": {
                        "motif_strength": 9.0,
                        "family_coherence": 9.0,
                        "notes": "best",
                    },
                    "winner_sprite_gate_report": {
                        "sprite_kind": "item",
                        "passed": True,
                        "foreground_bbox": [8, 6, 23, 25],
                        "checks": {},
                    },
                    "surviving_candidates": [],
                },
            ],
            "candidate_archive": {
                "prompt": "forge a hidden audition storm weapon",
                "theses": {
                    "candidate-001": {
                        "fantasy": "mark enemies then cash out with lightning",
                        "combat_package": "storm_brand",
                        "delivery_style": "direct",
                        "payoff_rate": "fast",
                        "loop_family": "mark_cashout",
                    },
                    "candidate-002": {
                        "fantasy": "mark enemies then call down astral verdict",
                        "combat_package": "storm_brand",
                        "delivery_style": "direct",
                        "payoff_rate": "fast",
                        "loop_family": "mark_cashout",
                    },
                },
                "finalists": ["candidate-001", "candidate-002"],
                "rejection_reasons": {},
            },
        }

        runtime_results = iter(
            [
                {
                    "candidate_id": "candidate-001",
                    "passed_runtime_gate": False,
                    "runtime_gate_reason": "missing cashout event",
                },
                {
                    "candidate_id": "candidate-002",
                    "passed_runtime_gate": True,
                    "runtime_gate_reason": None,
                },
            ]
        )
        ready_calls: list[str] = []

        async def fake_runtime_gate(
            *, finalist: dict[str, object], **_: object
        ) -> dict[str, object]:
            assert ready_calls == []
            result = next(runtime_results)
            assert result["candidate_id"] == finalist["candidate_id"]
            assert finalist["sprite_path"] in {
                "/tmp/storm-brand.png",
                "/tmp/star-verdict.png",
            }
            assert "item_sprite_path" not in finalist
            assert finalist["projectile_sprite_path"] in {
                "/tmp/storm-brand-proj.png",
                "/tmp/star-verdict-proj.png",
            }
            assert _["timeout_s"] == orchestrator.HIDDEN_LAB_RUNTIME_TIMEOUT_S
            return result

        with (
            mock.patch.object(
                orchestrator,
                "run_hidden_pixelsmith_audition",
                return_value=reviewed_audition,
            ),
            mock.patch.object(
                orchestrator,
                "run_hidden_lab_runtime_gate",
                side_effect=fake_runtime_gate,
            ),
            mock.patch.object(orchestrator, "_set_ready") as set_ready,
        ):
            result = await orchestrator.run_hidden_audition_pipeline(
                finalists=finalists,
                prompt="forge a hidden audition storm weapon",
            )
            set_ready.assert_not_called()

        assert result["winner"]["candidate_id"] == "candidate-002"
        assert result["winner"]["item_name"] == "Star Verdict"
        assert "candidate-001" not in result
        assert result["candidate_archive"].winning_finalist_id == "candidate-002"
        assert (
            result["candidate_archive"].runtime_gate_records["candidate-001"].passed
            is False
        )
        assert (
            result["candidate_archive"].rejection_reasons["candidate-001"]
            == "missing cashout event"
        )

    asyncio.run(run())


def test_hidden_audition_pipeline_picks_best_runtime_passing_finalist_not_first_seen() -> (
    None
):
    async def run() -> None:
        finalists = [
            _make_finalist("candidate-001", "Storm Brand"),
            _make_finalist("candidate-002", "Star Verdict"),
        ]
        reviewed_audition = {
            "status": "success",
            "art_scored_finalists": [
                {
                    "finalist_id": "candidate-001",
                    "item_name": "Storm Brand",
                    "item_sprite_path": "/tmp/storm-brand.png",
                    "winner_candidate_id": "candidate-001-art-001",
                    "winner_art_scores": {
                        "motif_strength": 7.0,
                        "family_coherence": 7.0,
                        "notes": "solid",
                    },
                    "winner_sprite_gate_report": {
                        "sprite_kind": "item",
                        "passed": True,
                        "foreground_bbox": [8, 6, 23, 25],
                        "checks": {},
                    },
                    "surviving_candidates": [],
                },
                {
                    "finalist_id": "candidate-002",
                    "item_name": "Star Verdict",
                    "item_sprite_path": "/tmp/star-verdict.png",
                    "winner_candidate_id": "candidate-002-art-001",
                    "winner_art_scores": {
                        "motif_strength": 9.0,
                        "family_coherence": 9.0,
                        "notes": "best",
                    },
                    "winner_sprite_gate_report": {
                        "sprite_kind": "item",
                        "passed": True,
                        "foreground_bbox": [8, 6, 23, 25],
                        "checks": {},
                    },
                    "surviving_candidates": [],
                },
            ],
            "candidate_archive": {
                "prompt": "forge a hidden audition storm weapon",
                "theses": {
                    "candidate-001": {
                        "fantasy": "mark enemies then cash out with lightning",
                        "combat_package": "storm_brand",
                        "delivery_style": "direct",
                        "payoff_rate": "fast",
                        "loop_family": "mark_cashout",
                    },
                    "candidate-002": {
                        "fantasy": "mark enemies then call down astral verdict",
                        "combat_package": "storm_brand",
                        "delivery_style": "direct",
                        "payoff_rate": "fast",
                        "loop_family": "mark_cashout",
                    },
                },
                "finalists": ["candidate-001", "candidate-002"],
                "rejection_reasons": {},
            },
        }

        async def fake_runtime_gate(
            *, finalist: dict[str, object], **_: object
        ) -> dict[str, object]:
            return {
                "candidate_id": finalist["candidate_id"],
                "passed_runtime_gate": True,
                "runtime_gate_reason": None,
            }

        with (
            mock.patch.object(
                orchestrator,
                "run_hidden_pixelsmith_audition",
                return_value=reviewed_audition,
            ),
            mock.patch.object(
                orchestrator,
                "run_hidden_lab_runtime_gate",
                side_effect=fake_runtime_gate,
            ),
        ):
            result = await orchestrator.run_hidden_audition_pipeline(
                finalists=finalists,
                prompt="forge a hidden audition storm weapon",
            )

        assert result["winner"]["candidate_id"] == "candidate-002"
        assert result["winner"]["item_name"] == "Star Verdict"
        assert result["candidate_archive"].winning_finalist_id == "candidate-002"

    asyncio.run(run())


def test_hidden_lab_runtime_gate_waits_for_terminal_evidence_before_evaluating() -> (
    None
):
    async def run() -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            request_file = tmp / "forge_lab_hidden_request.json"
            result_file = tmp / "forge_lab_hidden_result.json"

            async def write_results() -> None:
                while not request_file.exists():
                    await asyncio.sleep(0.001)

                request_payload = json.loads(request_file.read_text(encoding="utf-8"))
                result_file.write_text(
                    json.dumps(
                        {
                            "candidate_id": request_payload["candidate_id"],
                            "run_id": request_payload["run_id"],
                            "package_key": request_payload["package_key"],
                            "loop_family": request_payload["loop_family"],
                            "events": [
                                {
                                    "event_type": "seed_triggered",
                                    "timestamp_ms": 100,
                                    "run_id": request_payload["run_id"],
                                },
                                {
                                    "event_type": "escalate_triggered",
                                    "timestamp_ms": 450,
                                    "run_id": request_payload["run_id"],
                                    "stack_count": 1,
                                },
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
                await asyncio.sleep(0.01)
                result_file.write_text(
                    json.dumps(
                        {
                            "candidate_id": request_payload["candidate_id"],
                            "run_id": request_payload["run_id"],
                            "package_key": request_payload["package_key"],
                            "loop_family": request_payload["loop_family"],
                            "events": [
                                {
                                    "event_type": "seed_triggered",
                                    "timestamp_ms": 100,
                                    "run_id": request_payload["run_id"],
                                },
                                {
                                    "event_type": "escalate_triggered",
                                    "timestamp_ms": 450,
                                    "run_id": request_payload["run_id"],
                                    "stack_count": 1,
                                },
                                {
                                    "event_type": "cashout_triggered",
                                    "timestamp_ms": 900,
                                    "run_id": request_payload["run_id"],
                                    "stack_count": 2,
                                },
                            ],
                        }
                    ),
                    encoding="utf-8",
                )

            writer = asyncio.create_task(write_results())
            try:
                with (
                    mock.patch.object(
                        orchestrator, "HIDDEN_LAB_REQUEST_FILE", request_file
                    ),
                    mock.patch.object(
                        orchestrator, "HIDDEN_LAB_RESULT_FILE", result_file
                    ),
                ):
                    verdict = await orchestrator.run_hidden_lab_runtime_gate(
                        finalist=_make_finalist("candidate-001", "Storm Brand"),
                        timeout_s=0.1,
                        poll_interval_s=0.001,
                    )
            finally:
                await writer

            assert verdict["candidate_id"] == "candidate-001"
            assert verdict["passed_runtime_gate"] is True
            assert verdict["observed_hits_to_cashout"] == 2
            assert json.loads(request_file.read_text(encoding="utf-8"))["run_id"]

    asyncio.run(run())


def test_hidden_audition_pipeline_raises_explicit_error_for_unmapped_art_finalist() -> (
    None
):
    async def run() -> None:
        finalists = [_make_finalist("candidate-001", "Storm Brand")]
        reviewed_audition = {
            "status": "success",
            "art_scored_finalists": [
                {
                    "finalist_id": "candidate-999",
                    "item_name": "Unknown Verdict",
                    "item_sprite_path": "/tmp/unknown.png",
                    "winner_candidate_id": "candidate-999-art-001",
                    "winner_art_scores": {
                        "motif_strength": 8.0,
                        "family_coherence": 8.0,
                        "notes": "clear",
                    },
                    "winner_sprite_gate_report": {
                        "sprite_kind": "item",
                        "passed": True,
                        "foreground_bbox": [8, 6, 23, 25],
                        "checks": {},
                    },
                    "surviving_candidates": [],
                }
            ],
            "candidate_archive": {
                "prompt": "forge a hidden audition storm weapon",
                "theses": {
                    "candidate-001": {
                        "fantasy": "mark enemies then cash out with lightning",
                        "combat_package": "storm_brand",
                        "delivery_style": "direct",
                        "payoff_rate": "fast",
                        "loop_family": "mark_cashout",
                    }
                },
                "finalists": ["candidate-001"],
                "rejection_reasons": {},
            },
        }

        with mock.patch.object(
            orchestrator,
            "run_hidden_pixelsmith_audition",
            return_value=reviewed_audition,
        ):
            with pytest.raises(RuntimeError, match="Unable to map art finalist"):
                await orchestrator.run_hidden_audition_pipeline(
                    finalists=finalists,
                    prompt="forge a hidden audition storm weapon",
                )

    asyncio.run(run())


def test_hidden_audition_pipeline_skips_unsupported_runtime_gate_finalist() -> None:
    async def run() -> None:
        finalists = [
            {
                **_make_finalist("candidate-001", "Storm Brand"),
                "package_key": "orbit_furnace",
                "loop_family": "mark_cashout",
            },
            _make_finalist("candidate-002", "Star Verdict"),
        ]
        reviewed_audition = {
            "status": "success",
            "art_scored_finalists": [
                {
                    "finalist_id": "candidate-001",
                    "item_name": "Storm Brand",
                    "item_sprite_path": "/tmp/storm-brand.png",
                    "winner_candidate_id": "candidate-001-art-001",
                    "winner_art_scores": {
                        "motif_strength": 8.0,
                        "family_coherence": 8.0,
                        "notes": "clear",
                    },
                    "winner_sprite_gate_report": {
                        "sprite_kind": "item",
                        "passed": True,
                        "foreground_bbox": [8, 6, 23, 25],
                        "checks": {},
                    },
                    "surviving_candidates": [],
                },
                {
                    "finalist_id": "candidate-002",
                    "item_name": "Star Verdict",
                    "item_sprite_path": "/tmp/star-verdict.png",
                    "winner_candidate_id": "candidate-002-art-001",
                    "winner_art_scores": {
                        "motif_strength": 9.0,
                        "family_coherence": 9.0,
                        "notes": "best",
                    },
                    "winner_sprite_gate_report": {
                        "sprite_kind": "item",
                        "passed": True,
                        "foreground_bbox": [8, 6, 23, 25],
                        "checks": {},
                    },
                    "surviving_candidates": [],
                },
            ],
            "candidate_archive": {
                "prompt": "forge a hidden audition storm weapon",
                "theses": {
                    "candidate-001": {
                        "fantasy": "orbit embers before a thermal detonation",
                        "combat_package": "orbit_furnace",
                        "delivery_style": "direct",
                        "payoff_rate": "fast",
                        "loop_family": "mark_cashout",
                    },
                    "candidate-002": {
                        "fantasy": "mark enemies then call down astral verdict",
                        "combat_package": "storm_brand",
                        "delivery_style": "direct",
                        "payoff_rate": "fast",
                        "loop_family": "mark_cashout",
                    },
                },
                "finalists": ["candidate-001", "candidate-002"],
                "rejection_reasons": {},
            },
        }
        runtime_calls: list[str] = []

        async def fake_runtime_gate(
            *, finalist: dict[str, object], **_: object
        ) -> dict[str, object]:
            runtime_calls.append(str(finalist["candidate_id"]))
            return {
                "candidate_id": finalist["candidate_id"],
                "passed_runtime_gate": True,
                "runtime_gate_reason": None,
            }

        with (
            mock.patch.object(
                orchestrator,
                "run_hidden_pixelsmith_audition",
                return_value=reviewed_audition,
            ),
            mock.patch.object(
                orchestrator,
                "run_hidden_lab_runtime_gate",
                side_effect=fake_runtime_gate,
            ),
        ):
            result = await orchestrator.run_hidden_audition_pipeline(
                finalists=finalists,
                prompt="forge a hidden audition storm weapon",
            )

        assert result["winner"]["candidate_id"] == "candidate-002"
        assert runtime_calls == ["candidate-002"]
        assert result["candidate_archive"].rejection_reasons["candidate-001"] == (
            "hidden lab runtime telemetry only supports storm_brand/mark_cashout"
        )

    asyncio.run(run())


def test_hidden_audition_pipeline_skips_timed_out_finalist_and_uses_later_winner() -> (
    None
):
    async def run() -> None:
        finalists = [
            _make_finalist("candidate-001", "Storm Brand"),
            _make_finalist("candidate-002", "Star Verdict"),
        ]
        reviewed_audition = {
            "status": "success",
            "art_scored_finalists": [
                {
                    "finalist_id": "candidate-001",
                    "item_name": "Storm Brand",
                    "item_sprite_path": "/tmp/storm-brand.png",
                    "projectile_sprite_path": "/tmp/storm-brand-proj.png",
                    "winner_candidate_id": "candidate-001-art-001",
                    "winner_art_scores": {
                        "motif_strength": 8.0,
                        "family_coherence": 8.0,
                        "notes": "clear",
                    },
                    "winner_sprite_gate_report": {
                        "sprite_kind": "item",
                        "passed": True,
                        "foreground_bbox": [8, 6, 23, 25],
                        "checks": {},
                    },
                    "surviving_candidates": [],
                },
                {
                    "finalist_id": "candidate-002",
                    "item_name": "Star Verdict",
                    "item_sprite_path": "/tmp/star-verdict.png",
                    "projectile_sprite_path": "/tmp/star-verdict-proj.png",
                    "winner_candidate_id": "candidate-002-art-001",
                    "winner_art_scores": {
                        "motif_strength": 9.0,
                        "family_coherence": 9.0,
                        "notes": "best",
                    },
                    "winner_sprite_gate_report": {
                        "sprite_kind": "item",
                        "passed": True,
                        "foreground_bbox": [8, 6, 23, 25],
                        "checks": {},
                    },
                    "surviving_candidates": [],
                },
            ],
            "candidate_archive": {
                "prompt": "forge a hidden audition storm weapon",
                "theses": {
                    "candidate-001": {
                        "fantasy": "mark enemies then cash out with lightning",
                        "combat_package": "storm_brand",
                        "delivery_style": "direct",
                        "payoff_rate": "fast",
                        "loop_family": "mark_cashout",
                    },
                    "candidate-002": {
                        "fantasy": "mark enemies then call down astral verdict",
                        "combat_package": "storm_brand",
                        "delivery_style": "direct",
                        "payoff_rate": "fast",
                        "loop_family": "mark_cashout",
                    },
                },
                "finalists": ["candidate-001", "candidate-002"],
                "rejection_reasons": {},
            },
        }

        async def fake_runtime_gate(
            *, finalist: dict[str, object], **_: object
        ) -> dict[str, object]:
            if finalist["candidate_id"] == "candidate-001":
                raise TimeoutError(
                    "Timed out waiting for runtime evidence for candidate-001"
                )
            return {
                "candidate_id": "candidate-002",
                "passed_runtime_gate": True,
                "runtime_gate_reason": None,
            }

        with (
            mock.patch.object(
                orchestrator,
                "run_hidden_pixelsmith_audition",
                return_value=reviewed_audition,
            ),
            mock.patch.object(
                orchestrator,
                "run_hidden_lab_runtime_gate",
                side_effect=fake_runtime_gate,
            ),
        ):
            result = await orchestrator.run_hidden_audition_pipeline(
                finalists=finalists,
                prompt="forge a hidden audition storm weapon",
            )

        assert result["winner"]["candidate_id"] == "candidate-002"
        assert (
            result["candidate_archive"].rejection_reasons["candidate-001"]
            == "runtime gate timeout"
        )

    asyncio.run(run())


def test_hidden_audition_pipeline_surfaces_typed_hidden_pixelsmith_error() -> None:
    async def run() -> None:
        finalists = [_make_finalist("candidate-001", "Storm Brand")]
        reviewed_audition = {
            "status": "error",
            "art_scored_finalists": [],
            "candidate_archive": {
                "prompt": "forge a hidden audition storm weapon",
                "theses": {
                    "candidate-001": {
                        "fantasy": "mark enemies then cash out with lightning",
                        "combat_package": "storm_brand",
                        "delivery_style": "direct",
                        "payoff_rate": "fast",
                        "loop_family": "mark_cashout",
                    }
                },
                "finalists": ["candidate-001"],
                "rejection_reasons": {},
            },
            "error": {
                "code": "GENERATION",
                "message": "pixelsmith exploded",
            },
        }

        with mock.patch.object(
            orchestrator,
            "run_hidden_pixelsmith_audition",
            return_value=reviewed_audition,
        ):
            with pytest.raises(
                RuntimeError,
                match=r"GENERATION.*pixelsmith exploded",
            ):
                await orchestrator.run_hidden_audition_pipeline(
                    finalists=finalists,
                    prompt="forge a hidden audition storm weapon",
                )

    asyncio.run(run())
