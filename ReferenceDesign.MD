# Reference Image Design for Terraria Sprite Pipeline

Archived design summary for reference-aware sprite generation.

## Goal

Use reference images only when identity matters, while keeping the normal text-only path as fallback.

## Intended Flow

1. `Architect` decides whether the prompt needs a reference.
2. A reference finder pulls a small candidate set from image search.
3. `Architect` approves one candidate or retries once.
4. `Pixelsmith` uses `text_to_image` or `image_to_image`.

## Manifest Fields

- `reference_needed`
- `reference_subject`
- `reference_image_url`
- `generation_mode`
- optional `reference_attempts`
- optional `reference_notes`

## Decision Rules

- Use reference mode for named people, characters, recognizable items, or direct style-copy requests.
- Stay text-only for generic fantasy/custom prompts.
- If approval fails, fall back cleanly to text-only generation.

## Retrieval Rules

- Query the subject directly, with illustration/concept-art/pixel-art variants.
- Rank for single-subject focus, clean composition, and pixel-art or illustration preference.
- Show only a small top set to the approver.

## Failure Rules

- Search failure, no acceptable candidate, or image download failure must not break the run.
- Fallback is always `generation_mode="text_to_image"`.

## Kept As Archive Because

- The high-level idea remains useful.
- The original prose was much larger than the actionable content.
- Approved URL -> `image_to_image`
- Missing URL -> `text_to_image`

5. End-to-end integration tests
- Prompt with existing character routes through reference path
- Prompt without known identity skips reference path

---

## 14. Open Design Questions

1. Should Architect approval be deterministic heuristic-only, LLM-judged, or hybrid?
2. How much prompt context should be sent to the Reference Finder query rewriter?
3. Should fallback reason be surfaced in manifest for debugging?
4. Should image-to-image strength parameters be configurable per request?

---

## 15. Recommended Initial Defaults

- Candidate fetch count: 8
- Candidates for Architect review: 3
- Retry rounds: 1
- Fallback on any reference-step failure: yes
- Style ranking priority: pixel art > illustration > photo

---

## 16. Summary

This feature introduces a conditional reference pipeline that improves identity fidelity for existing subjects while preserving the current fast path for generic concepts. It keeps Architect as the decision authority and adds one lightweight reference-search loop with safe fallback to the current generation behavior.
