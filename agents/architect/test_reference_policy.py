from __future__ import annotations

import asyncio

from architect.reference_finder import ReferenceCandidate
from architect.reference_policy import ReferencePolicy


class _LoopSensitiveFinder:
    def find_candidates(self, subject, prompt, *, attempt=0, item_type="", sub_type=""):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError("sync_playwright inside asyncio loop")

        return [
            ReferenceCandidate(
                url="https://example.com/reference.png",
                title="Reference",
                source="https://example.com",
                score=50.0,
                rationale="test",
            )
        ]


class _Approver:
    def approve(self, *, prompt, subject, candidates, item_type="", sub_type=""):
        return candidates[0], "approved"


def test_reference_policy_runs_finder_off_event_loop_thread():
    async def run_policy():
        policy = ReferencePolicy(
            finder=_LoopSensitiveFinder(),
            approver=_Approver(),
            max_retries=0,
        )
        return policy.resolve(
            prompt="a staff that shoots gojo's hollow purple from jjk",
            reference_needed=True,
            reference_subject="Hollow Purple",
            item_type="Weapon",
            sub_type="Staff",
        )

    result = asyncio.run(run_policy())

    assert result["reference_image_url"] == "https://example.com/reference.png"
    assert result["generation_mode"] == "image_to_image"
