"""Select the best variant from multiple generated images by comparing to reference."""

from __future__ import annotations

import base64
import logging
import urllib.request
from io import BytesIO

import anthropic
from PIL import Image

logger = logging.getLogger(__name__)

_CLAUDE_VISION_MODEL = "claude-sonnet-4-6"


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

All candidates should have similar colors. Focus on SHAPE quality."""


_AUDITION_SYSTEM = """\
You are judging hidden Pixelsmith audition survivors.

Score each surviving sprite candidate on:
- motif_strength: how strongly the sprite expresses the requested fantasy and signature motifs (0.0 to 10.0)
- family_coherence: how well the sprite fits the same visual family and art direction (0.0 to 10.0)

Then choose the best surviving candidate using those scores."""


_SELECTOR_TOOL = {
    "name": "report_best_variant",
    "description": "Report which candidate index is the best match.",
    "input_schema": {
        "type": "object",
        "properties": {
            "index": {
                "type": "integer",
                "description": "1-based index of the best candidate",
            },
        },
        "required": ["index"],
    },
}


_AUDITION_TOOL = {
    "name": "report_audition_result",
    "description": "Report the winner and per-candidate scores.",
    "input_schema": {
        "type": "object",
        "properties": {
            "winner_index": {
                "type": "integer",
                "description": "0-based winner index among surviving candidates",
            },
            "scores": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "motif_strength": {"type": "number"},
                        "family_coherence": {"type": "number"},
                        "notes": {"type": "string"},
                    },
                    "required": ["motif_strength", "family_coherence"],
                },
            },
        },
        "required": ["winner_index", "scores"],
    },
}


def _image_to_b64(img: Image.Image) -> str:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _url_to_b64(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return base64.b64encode(resp.read()).decode("ascii")


def _image_block(b64: str) -> dict:
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": b64},
    }


def _extract_tool_input(message: anthropic.types.Message, tool_name: str) -> dict:
    for block in message.content:
        if block.type == "tool_use" and block.name == tool_name:
            return dict(block.input)
    raise RuntimeError(f"Claude did not return a {tool_name} tool_use block")


def select_best_variant(
    candidates: list[Image.Image],
    reference_url: str,
    *,
    model: str = _CLAUDE_VISION_MODEL,
) -> int:
    """Pick the best candidate index (0-based) by comparing to reference."""
    n = len(candidates)
    if n <= 1:
        return 0

    logger.info("Selecting best variant from %d candidates", n)

    ref_b64 = _url_to_b64(reference_url)

    content: list[dict] = [
        {"type": "text", "text": "Reference image:"},
        _image_block(ref_b64),
    ]
    for i, img in enumerate(candidates, 1):
        content.append({"type": "text", "text": f"Candidate {i}:"})
        content.append(_image_block(_image_to_b64(img)))

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=model,
        max_tokens=512,
        system=_SELECTOR_SYSTEM.format(n=n),
        tools=[_SELECTOR_TOOL],
        tool_choice={"type": "tool", "name": "report_best_variant"},
        messages=[{"role": "user", "content": content}],
    )

    payload = _extract_tool_input(message, "report_best_variant")
    raw_index = int(payload.get("index", 1))
    if 1 <= raw_index <= n:
        logger.info("Claude selected candidate %d of %d", raw_index, n)
        return raw_index - 1

    logger.warning(
        "Claude returned out-of-range index %d (n=%d), defaulting to candidate 1",
        raw_index,
        n,
    )
    return 0


def judge_surviving_candidates(
    candidates: list[Image.Image],
    *,
    prompt: str,
    family_hint: str = "",
    model: str = _CLAUDE_VISION_MODEL,
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
        content.append({"type": "text", "text": f"Candidate {i}:"})
        content.append(_image_block(_image_to_b64(img)))

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=model,
        max_tokens=1024,
        system=_AUDITION_SYSTEM,
        tools=[_AUDITION_TOOL],
        tool_choice={"type": "tool", "name": "report_audition_result"},
        messages=[{"role": "user", "content": content}],
    )

    payload = _extract_tool_input(message, "report_audition_result")
    raw_winner = int(payload.get("winner_index", 0))
    winner_index = raw_winner if 0 <= raw_winner < n else 0

    raw_scores = payload.get("scores") or []
    scores: list[dict] = []
    for entry in raw_scores[:n]:
        scores.append(
            {
                "motif_strength": float(entry.get("motif_strength", 0.0)),
                "family_coherence": float(entry.get("family_coherence", 0.0)),
                "notes": str(entry.get("notes", "")),
            }
        )
    while len(scores) < n:
        scores.append(
            {
                "motif_strength": 0.0,
                "family_coherence": 0.0,
                "notes": "missing score from judge",
            }
        )

    return {"winner_index": winner_index, "scores": scores}
