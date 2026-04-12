"""Select the best variant from multiple generated images by comparing to reference."""

from __future__ import annotations

import base64
import logging
import urllib.request
from io import BytesIO

from PIL import Image
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class _VariantSelection(BaseModel):
    index: int = Field(
        description="1-based index of the best candidate (e.g. 1, 2, or 3)"
    )


class _SpriteCandidateScore(BaseModel):
    motif_strength: float = Field(ge=0.0, le=10.0)
    family_coherence: float = Field(ge=0.0, le=10.0)
    notes: str = ""


class _SurvivorJudgement(BaseModel):
    winner_index: int = Field(
        description="0-based winner index among surviving candidates"
    )
    scores: list[_SpriteCandidateScore] = Field(default_factory=list)


_SELECTOR_SYSTEM = """\
You are selecting the best pixel art sprite from {n} candidates.

You will see:
1. A reference image showing the original weapon/item
2. {n} generated pixel art sprite candidates (labeled 1 through {n})

Pick the candidate whose SHAPE and PROPORTIONS best match the reference weapon. \
Consider:
- Blade shape (curved vs straight, thin vs thick, correct proportions)
- Guard/crossguard shape and size
- Handle length and style
- Overall silhouette similarity to the reference

All candidates should have similar colors. Focus on SHAPE quality.

Return the number of the best candidate (1 through {n}) in the `index` field."""


_AUDITION_SYSTEM = """\
You are judging hidden Pixelsmith audition survivors.

Score each surviving sprite candidate on:
- motif_strength: how strongly the sprite expresses the requested fantasy and signature motifs
- family_coherence: how well the sprite fits the same visual family and art direction

Then choose the best surviving candidate using those scores.

Return:
- `winner_index`: the 0-based index of the winner
- `scores`: one score object per candidate, in order"""


def _image_to_b64(img: Image.Image) -> str:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _url_to_b64(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return base64.b64encode(resp.read()).decode("ascii")


def select_best_variant(
    candidates: list[Image.Image],
    reference_url: str,
    *,
    model: str = "gpt-4o",
) -> int:
    """Pick the best candidate index (0-based) by comparing to reference.

    Returns the index of the best candidate in the list.
    """
    n = len(candidates)
    if n <= 1:
        return 0

    logger.info("Selecting best variant from %d candidates", n)

    ref_b64 = _url_to_b64(reference_url)

    content: list[dict] = [
        {"type": "text", "text": "Reference image:"},
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{ref_b64}", "detail": "high"},
        },
    ]

    for i, img in enumerate(candidates, 1):
        b64 = _image_to_b64(img)
        content.append({"type": "text", "text": f"Candidate {i}:"})
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
            }
        )

    llm = ChatOpenAI(model=model, timeout=60).with_structured_output(_VariantSelection)
    messages = [
        SystemMessage(content=_SELECTOR_SYSTEM.format(n=n)),
        HumanMessage(content=content),
    ]

    result: _VariantSelection = llm.invoke(messages)
    if 1 <= result.index <= n:
        logger.info("LLM selected candidate %d of %d", result.index, n)
        return result.index - 1

    logger.warning(
        "LLM returned out-of-range index %d (n=%d), defaulting to candidate 1",
        result.index,
        n,
    )
    return 0


def judge_surviving_candidates(
    candidates: list[Image.Image],
    *,
    prompt: str,
    family_hint: str = "",
    model: str = "gpt-4o",
) -> dict[str, object]:
    """Judge surviving candidates on motif strength and family coherence."""
    n = len(candidates)
    if n <= 0:
        raise ValueError("At least one surviving candidate is required")
    if n == 1:
        return {
            "winner_index": 0,
            "scores": [
                {
                    "motif_strength": 6.0,
                    "family_coherence": 6.0,
                    "notes": "single surviving candidate; limited comparative evidence",
                }
            ],
        }

    content: list[dict] = [
        {
            "type": "text",
            "text": (
                f"Prompt: {prompt}\n"
                f"Family hint: {family_hint or 'none provided'}\n"
                f"Judge motif strength and family coherence across {n} surviving candidates."
            ),
        }
    ]

    for i, img in enumerate(candidates):
        b64 = _image_to_b64(img)
        content.append({"type": "text", "text": f"Candidate {i}:"})
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
            }
        )

    llm = ChatOpenAI(model=model, timeout=60).with_structured_output(_SurvivorJudgement)
    result: _SurvivorJudgement = llm.invoke(
        [
            SystemMessage(content=_AUDITION_SYSTEM),
            HumanMessage(content=content),
        ]
    )

    winner_index = result.winner_index if 0 <= result.winner_index < n else 0
    scores = [score.model_dump() for score in result.scores[:n]]
    while len(scores) < n:
        scores.append(
            {
                "motif_strength": 0.0,
                "family_coherence": 0.0,
                "notes": "missing score from judge",
            }
        )
    return {"winner_index": winner_index, "scores": scores}
