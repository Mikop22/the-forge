"""Reference decision/approval policy for Architect manifests."""

from __future__ import annotations

import base64
import json
import logging
import re
import urllib.request
from dataclasses import dataclass
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

try:
    from architect.reference_finder import ReferenceCandidate
except ImportError:
    from reference_finder import ReferenceCandidate

logger = logging.getLogger(__name__)

_REFERENCE_SYSTEM = """\
You are a visual reference evaluator for a Terraria pixel art sprite generator.

You will be shown candidate images alongside their metadata. Your job is to pick
the SINGLE best image that can serve as a visual reference for generating a
Terraria-style 2D pixel art item sprite.

BEST references (in order of preference):
1. The item/weapon/object shown in isolation on a clean background
2. A clear illustration, render, or concept art of the item — even if a character
   is holding it, as long as the item is clearly visible and recognizable
3. Fan art or anime screenshots where the item's shape, color, and key details
   are easy to identify

ACCEPTABLE references:
- Character renders where the weapon/item is prominently displayed and clearly visible
- Images with simple or slightly busy backgrounds, as long as the item stands out
- Anime/manga art showing the item with good detail, even if not perfectly isolated

For SWORDS and bladed weapons specifically:
- Prefer images showing the blade unsheathed and drawn
- A character holding the drawn sword is fine if the blade is clearly visible

REJECT candidates that are:
- Game UI cards, gacha cards, or mobile game screenshots with overlaid text/stats
- Photographs of real-world replicas, cosplay props, or merchandise
- Cursor packs, icon sets, or tiled sprite sheets
- Too small, blurry, or heavily watermarked to be useful
- Completely unrelated to the subject

Return the 0-based index of the best candidate, or null to reject ALL.
Only reject all if NONE of the candidates show the requested item in any usable form."""

_REFERENCE_HUMAN_TEXT = """\
Prompt: {prompt}
Reference Subject: {subject}
Item Type: {item_type}
Sub Type: {sub_type}

I am showing you {num_candidates} candidate images below.
Each image is labeled with its index number, title, and source.

After viewing all images, select the best one or reject all.

Candidate metadata:
{candidates_json}"""


class ReferenceApprovalOutput(BaseModel):
    approved_index: Optional[int] = Field(
        default=None,
        description="0-based index of approved candidate; null to reject all",
    )
    reason: str = ""


def _download_thumbnail(url: str, timeout: int = 8) -> Optional[str]:
    """Download an image URL and return base64-encoded data, or None on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            if len(data) < 500:  # too small to be a real image
                return None
            return base64.b64encode(data).decode("ascii")
    except Exception:
        return None


def _guess_media_type(url: str) -> str:
    lower = url.lower()
    if ".png" in lower:
        return "image/png"
    if ".gif" in lower:
        return "image/gif"
    if ".webp" in lower:
        return "image/webp"
    return "image/jpeg"


@dataclass
class HybridReferenceApprover:
    """Vision-based LLM approval: downloads thumbnails, sends as images to GPT."""

    model_name: str = "gpt-5.4"

    def __post_init__(self) -> None:
        self._llm = ChatOpenAI(model=self.model_name, timeout=60).with_structured_output(
            ReferenceApprovalOutput
        )

    def approve(
        self,
        *,
        prompt: str,
        subject: str,
        candidates: list[ReferenceCandidate],
        item_type: str = "",
        sub_type: str = "",
    ) -> tuple[Optional[ReferenceCandidate], str]:
        if not candidates:
            return None, "no_candidates"

        # Download thumbnails in parallel-ish (sequential but fast, they're small)
        thumbnails: list[tuple[int, str, str]] = []  # (index, base64, media_type)
        for i, c in enumerate(candidates):
            b64 = _download_thumbnail(c.url)
            if b64:
                thumbnails.append((i, b64, _guess_media_type(c.url)))

        if not thumbnails:
            logger.warning("Could not download any candidate thumbnails")
            return self._fallback_text_only(prompt, subject, candidates, item_type, sub_type)

        # Build multimodal message with images
        payload = [
            {
                "index": i,
                "title": c.title,
                "source": c.source,
                "score": c.score,
            }
            for i, c in enumerate(candidates)
        ]

        human_text = _REFERENCE_HUMAN_TEXT.format(
            prompt=prompt,
            subject=subject,
            item_type=item_type or "Unknown",
            sub_type=sub_type or "Unknown",
            num_candidates=len(candidates),
            candidates_json=json.dumps(payload, indent=2),
        )

        # Build content blocks: text first, then labeled images
        content: list[dict] = [{"type": "text", "text": human_text}]

        for idx, b64, media_type in thumbnails:
            c = candidates[idx]
            content.append({
                "type": "text",
                "text": f"\n--- Candidate {idx}: \"{c.title}\" (source: {c.source}) ---",
            })
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{media_type};base64,{b64}",
                    "detail": "low",  # save tokens, thumbnails are small
                },
            })

        messages = [
            SystemMessage(content=_REFERENCE_SYSTEM),
            HumanMessage(content=content),
        ]

        try:
            result: ReferenceApprovalOutput = self._llm.invoke(messages)
            if result.approved_index is None:
                return None, result.reason or "llm_rejected"
            idx = int(result.approved_index)
            if idx < 0 or idx >= len(candidates):
                return None, "llm_invalid_index"
            return candidates[idx], result.reason or "llm_approved"
        except Exception as exc:
            logger.warning("Vision approval failed: %s — falling back to score-based", exc)
            top = candidates[0]
            if top.score >= 25.0:
                return top, "llm_unavailable_fallback_top_candidate"
            return None, "llm_unavailable_and_low_score"

    def _fallback_text_only(
        self,
        prompt: str,
        subject: str,
        candidates: list[ReferenceCandidate],
        item_type: str,
        sub_type: str,
    ) -> tuple[Optional[ReferenceCandidate], str]:
        """Fallback when thumbnails can't be downloaded — use score-based selection."""
        top = candidates[0]
        if top.score >= 25.0:
            return top, "thumbnails_unavailable_fallback_top_score"
        return None, "thumbnails_unavailable_and_low_score"


class ReferencePolicy:
    """Decides if and how reference retrieval/approval should run."""

    def __init__(self, finder, approver, *, max_retries: int = 1) -> None:
        self._finder = finder
        self._approver = approver
        self._max_retries = max(0, max_retries)

    def resolve(
        self,
        *,
        prompt: str,
        reference_needed: bool,
        reference_subject: Optional[str],
        item_type: str = "",
        sub_type: str = "",
    ) -> dict:
        initial_needed = reference_needed or _prompt_implies_reference(prompt)
        if not initial_needed:
            return _reference_result(False, None, None, "text_to_image", 0, "reference_not_requested")

        subject = (reference_subject or _infer_subject(prompt) or "").strip()
        if not subject:
            return _reference_result(True, None, None, "text_to_image", 0, "reference_subject_not_detected")

        notes = []
        attempts = 0

        for attempt in range(self._max_retries + 1):
            attempts += 1
            candidates = self._finder.find_candidates(
                subject, prompt, attempt=attempt,
                item_type=item_type, sub_type=sub_type,
            )
            if not candidates:
                notes.append("search_failed_or_empty")
                continue

            selected, reason = self._approver.approve(
                prompt=prompt, subject=subject, candidates=candidates,
                item_type=item_type, sub_type=sub_type,
            )
            if reason:
                notes.append(reason)

            if selected is not None:
                return _reference_result(
                    True,
                    subject,
                    selected.url,
                    "image_to_image",
                    attempts,
                    "; ".join(notes) or "approved",
                )

            subject = _refine_subject(subject, prompt)

        return _reference_result(
            True,
            subject,
            None,
            "text_to_image",
            attempts,
            "; ".join(notes) or "approval_failed",
        )


def _reference_result(
    needed: bool,
    subject: Optional[str],
    url: Optional[str],
    mode: str,
    attempts: int,
    notes: str,
) -> dict:
    return {
        "reference_needed": needed,
        "reference_subject": subject,
        "reference_image_url": url,
        "generation_mode": mode,
        "reference_attempts": attempts,
        "reference_notes": notes,
    }


def _prompt_implies_reference(prompt: str) -> bool:
    lower = prompt.lower()
    explicit = (
        "in the style of",
        "based on",
        "looks like",
        "reference",
        "character",
    )
    if any(token in lower for token in explicit):
        return True

    known_names = (
        "batman",
        "naruto",
        "messi",
        "mario",
        "zelda",
        "pikachu",
    )
    return any(name in lower for name in known_names)


def _infer_subject(prompt: str) -> Optional[str]:
    prompt = prompt.strip()
    if not prompt:
        return None

    named_match = re.search(r"(?:as|like|of)\s+([A-Z][a-zA-Z0-9_-]+(?:\s+[A-Z][a-zA-Z0-9_-]+)?)", prompt)
    if named_match:
        return named_match.group(1)

    for token in ["batman", "naruto", "messi", "mario", "zelda", "pikachu"]:
        if token in prompt.lower():
            return token.title()

    return None


def _refine_subject(subject: str, prompt: str) -> str:
    prompt_lower = prompt.lower()
    suffix = []
    if "armor" in prompt_lower:
        suffix.append("armor")
    if "classic" in prompt_lower:
        suffix.append("classic")
    if suffix:
        refined = " ".join(suffix)
        if refined not in subject:
            return f"{subject} {refined}"
        return subject
    if "weapon art isolated" not in subject:
        return f"{subject} weapon art isolated"
    return subject
