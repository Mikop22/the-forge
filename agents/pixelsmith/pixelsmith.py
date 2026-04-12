"""Pixelsmith Agent – generates game-ready pixel art assets for Terraria.

Receives the ``visuals`` slice of an Architect manifest and produces .png
sprite files via fal-ai FLUX.2 Klein + strict post-processing.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image
from pydantic import ValidationError

try:  # Prefer package imports to avoid cross-agent module name collisions.
    from core.weapon_lab_archive import WeaponLabArchive
    from core.weapon_lab_models import WeaponThesis
    from pixelsmith.art_direction import map_art_direction_profile
    from pixelsmith.armor_compositor import (
        FRAME_HEIGHT,
        FRAME_WIDTH,
        composite_armor,
    )
    from pixelsmith.color_extraction import (
        extract_colors,
        get_accent_colors,
        get_color_palette_string,
    )
    from pixelsmith.image_processing import downscale, remove_background
    from pixelsmith.models import (
        PixelsmithError,
        PixelsmithHiddenAuditionFinalist,
        PixelsmithHiddenAuditionOutput,
        PixelsmithInput,
        PixelsmithOutput,
    )
    from pixelsmith.sprite_gates import evaluate_sprite_gates
    from pixelsmith.variant_selector import (
        judge_surviving_candidates,
        select_best_variant,
    )
except ImportError:  # Fallback for direct script execution from the folder.
    from core.weapon_lab_archive import WeaponLabArchive
    from core.weapon_lab_models import WeaponThesis
    from art_direction import map_art_direction_profile
    from armor_compositor import (
        FRAME_HEIGHT,
        FRAME_WIDTH,
        composite_armor,
    )
    from color_extraction import (
        extract_colors,
        get_accent_colors,
        get_color_palette_string,
    )
    from image_processing import downscale, remove_background
    from models import (
        PixelsmithError,
        PixelsmithHiddenAuditionFinalist,
        PixelsmithHiddenAuditionOutput,
        PixelsmithInput,
        PixelsmithOutput,
    )
    from sprite_gates import evaluate_sprite_gates
    from variant_selector import judge_surviving_candidates, select_best_variant

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAL_MODEL_ENDPOINT = "fal-ai/flux-2/klein/9b/base/lora"
FAL_IMG2IMG_ENDPOINT = "fal-ai/flux-2/klein/9b/base/edit/lora"
NODE_RUNNER = Path(__file__).resolve().parent / "fal_flux2_runner.mjs"
DEFAULT_LORA_PATH = str(
    Path(__file__).resolve().parent / "terraria_weights.safetensors"
)
GENERATION_SIZE = {"width": 512, "height": 512}

POSITIVE_TEMPLATE = (
    "pixel art sprite, {description}, plain white background, centered, "
    "{orientation}, "
    "hard edges, terraria game style, 2D, no anti-aliasing, "
    "clean silhouette, high contrast{lora_trigger}"
)
LORA_TRIGGER_WORD = "terraria style"
LORA_SCALE = 0.85
IMG2IMG_VARIANTS = 4
HIDDEN_AUDITION_MIN_VARIANTS = 2

# System prompt baked into the positive prompt preamble.
SYSTEM_CONTEXT = (
    "You are a pixel art generator for a video game. You strictly generate "
    "items on a plain white background. You focus on clear silhouettes and "
    "high contrast. You do not generate text, UI elements, or complex scenes. "
    "You only generate the single object described."
)

# Template for img2img prompts — LLM fills in shape, we inject accent colors
IMG2IMG_TEMPLATE = (
    "pixel art sprite, {description}{accent_clause}"
    ", terraria style, {orientation}"
    ", white background, centered"
)

# ---------------------------------------------------------------------------
# Orientation maps — keyed on sub_type / projectile description keywords
# ---------------------------------------------------------------------------

DEFAULT_ORIENTATION = "diagonal orientation tilted 45 degrees pointing upper-right"

WEAPON_ORIENTATION_MAP: dict[str, str] = {
    # 45° diagonal (Terraria default for melee swing weapons)
    "Sword": DEFAULT_ORIENTATION,
    "Broadsword": DEFAULT_ORIENTATION,
    "Shortsword": DEFAULT_ORIENTATION,
    "Spear": DEFAULT_ORIENTATION,
    "Lance": DEFAULT_ORIENTATION,
    "Axe": DEFAULT_ORIENTATION,
    "Pickaxe": DEFAULT_ORIENTATION,
    "Hamaxe": DEFAULT_ORIENTATION,
    "Hammer": DEFAULT_ORIENTATION,
    "Yoyo": DEFAULT_ORIENTATION,
    "Flail": DEFAULT_ORIENTATION,
    # Vertical orientation (bows, staves, wands)
    "Bow": "vertical orientation pointing straight up",
    "Repeater": "vertical orientation pointing straight up",
    "Staff": "vertical orientation pointing straight up, slight tilt",
    "Wand": "vertical orientation pointing straight up, slight tilt",
    "Tome": "upright orientation, no tilt, facing forward",
    "Spellbook": "upright orientation, no tilt, facing forward",
    # Horizontal orientation (guns, launchers)
    "Gun": "horizontal orientation pointing right",
    "Launcher": "horizontal orientation pointing right",
    "Rifle": "horizontal orientation pointing right",
    "Pistol": "horizontal orientation pointing right",
    "Shotgun": "horizontal orientation pointing right",
    "Cannon": "horizontal orientation pointing right",
}

# Keywords scanned from projectile descriptions to pick orientation.
# Checked in order — first match wins. Fallback is no orientation constraint.
PROJECTILE_ORIENTATION_KEYWORDS: list[tuple[list[str], str]] = [
    (
        ["arrow", "bolt", "javelin", "spear", "lance", "stake"],
        "vertical orientation pointing straight up",
    ),
    (
        ["bullet", "beam", "laser", "ray", "missile", "rocket"],
        "horizontal orientation pointing right",
    ),
]
PROJECTILE_DEFAULT_ORIENTATION = "centered, no specific orientation"


def _resolve_weapon_orientation(sub_type: str) -> str:
    """Return the orientation phrase for a weapon sub_type."""
    return WEAPON_ORIENTATION_MAP.get(sub_type, DEFAULT_ORIENTATION)


def _resolve_projectile_orientation(description: str) -> str:
    """Infer projectile orientation from keywords in its description."""
    desc_lower = description.lower()
    for keywords, orientation in PROJECTILE_ORIENTATION_KEYWORDS:
        if any(kw in desc_lower for kw in keywords):
            return orientation
    return PROJECTILE_DEFAULT_ORIENTATION


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_fal_key(explicit_key: str | None = None) -> str:
    key = explicit_key or os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY")
    if not key:
        raise RuntimeError("FAL_KEY (or FAL_API_KEY) is required for Pixelsmith.")
    return key


def _extract_projectile_name(manifest: dict) -> str:
    """Best-effort extraction of a projectile class name from the manifest.

    Falls back to ``{item_name}Projectile`` if no shoot_projectile is present.
    """
    shoot = (manifest.get("mechanics") or {}).get("shoot_projectile", "")
    match = re.search(r"<(\w+)>", shoot)
    if match:
        return match.group(1)
    return manifest.get("item_name", "CustomProjectile") + "Projectile"


def _hidden_audition_item_output_name(item_name: str, finalist_id: str) -> str:
    safe_finalist_id = re.sub(r"[^A-Za-z0-9_-]+", "_", finalist_id).strip("_")
    if not safe_finalist_id:
        return f"{item_name}.png"
    return f"{item_name}_{safe_finalist_id}.png"


def build_prompt(
    description: str,
    *,
    lora_loaded: bool = False,
    orientation: str = DEFAULT_ORIENTATION,
) -> str:
    """Construct a FLUX positive prompt from the manifest description."""
    lora_trigger = f", {LORA_TRIGGER_WORD}" if lora_loaded else ""
    return POSITIVE_TEMPLATE.format(
        description=description,
        lora_trigger=lora_trigger,
        orientation=orientation,
    )


def _download_reference(url: str) -> Image.Image:
    """Download a reference image URL and return as PIL Image."""
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read()
    from io import BytesIO

    return Image.open(BytesIO(data)).convert("RGBA")


def _describe_shape_with_colors(ref_url: str, color_palette: str) -> str:
    """LLM describes weapon shape and maps extracted colors to parts."""
    import base64
    import urllib.request
    from io import BytesIO
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    req = urllib.request.Request(ref_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read()
    b64 = base64.b64encode(data).decode("ascii")

    llm = ChatOpenAI(model="gpt-4o", timeout=60)
    messages = [
        SystemMessage(
            content=(
                "This reference image shows a weapon we want to turn into a single pixel art sprite. "
                "Describe ONLY the main unsheathed weapon — ignore scabbards, sheaths, duplicates, "
                "characters, backgrounds, or any other objects in the image. "
                "We are making ONE sprite of ONE weapon.\n\n"
                "We extracted these colors from the image using computer vision:\n"
                f"  {color_palette}\n\n"
                "Your job: describe the weapon in under 25 words, assigning the extracted colors "
                "to the correct weapon parts (blade, edge, guard, handle, pommel, glow, etc). "
                "Example: 'slightly curved black blade with bright green glowing edge, gold crossguard, "
                "dark brown wrapped handle with gold pommel'"
            )
        ),
        HumanMessage(
            content=[
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{b64}",
                        "detail": "high",
                    },
                },
                {
                    "type": "text",
                    "text": "Describe this weapon with the extracted colors placed on the correct parts.",
                },
            ]
        ),
    ]
    result = llm.invoke(messages)
    return result.content.strip()


def build_img2img_prompt(
    base_description: str,
    reference_url: str,
    orientation: str = DEFAULT_ORIENTATION,
) -> str:
    """Build an img2img prompt by combining LLM shape description with extracted accent colors.

    1. Downloads reference image
    2. Extracts dominant colors via k-means
    3. LLM describes weapon shape and assigns colors to parts
    4. Injects any accent colors the LLM missed
    """
    # Extract colors from reference
    ref_img = _download_reference(reference_url)
    colors = extract_colors(ref_img)
    palette_str = get_color_palette_string(colors)
    accent_colors = get_accent_colors(colors)

    logger.info("Extracted color palette: %s", palette_str)
    logger.info("Accent colors: %s", accent_colors)

    # LLM describes shape with color placement
    description = _describe_shape_with_colors(reference_url, palette_str)
    logger.info("LLM img2img description: %s", description)

    # Check if any accent colors are missing from description — inject them
    desc_lower = description.lower()
    missing = [c for c in accent_colors if c.lower() not in desc_lower and c != "gold"]
    accent_clause = ""
    if missing:
        accent_clause = f" with {' and '.join(missing)} glowing edge"
        logger.info("Injecting missing accent colors: %s", missing)

    return IMG2IMG_TEMPLATE.format(
        description=description,
        accent_clause=accent_clause,
        orientation=orientation,
    )


class ArtistAgent:
    """The Pixelsmith — generates pixel art sprites from Architect manifests."""

    def __init__(
        self,
        *,
        output_dir: str | Path = "output",
        lora_path: str | None = DEFAULT_LORA_PATH,
        fal_key: str | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._lora_path = (
            lora_path if (lora_path and Path(lora_path).exists()) else None
        )
        self._lora_loaded = self._lora_path is not None
        self._fal_key = _resolve_fal_key(fal_key)
        self._image_to_image_enabled = _env_flag(
            "FAL_IMAGE_TO_IMAGE_ENABLED", default=False
        )

        logger.info(
            "ArtistAgent ready — endpoint=%s, output=%s",
            FAL_MODEL_ENDPOINT,
            self.output_dir,
        )

    def generate_asset(self, manifest: dict) -> dict:
        """Generate pixel art assets from *manifest*."""
        try:
            parsed = PixelsmithInput.model_validate(manifest)
        except Exception as exc:
            return PixelsmithOutput(
                status="error",
                error=PixelsmithError(code="VALIDATION", message=str(exc)),
            ).model_dump()

        try:
            if parsed.type == "Armor":
                item_path = self._generate_armor(parsed)
            else:
                item_path = self._generate_standard_item(parsed)

            proj_path: str | None = None
            if parsed.projectile_visuals is not None:
                proj_path = self._generate_projectile(parsed, manifest)

            return PixelsmithOutput(
                item_sprite_path=str(item_path),
                projectile_sprite_path=proj_path,
                status="success",
            ).model_dump()
        except Exception as exc:
            logger.exception("Generation failed for %s", parsed.item_name)
            return PixelsmithOutput(
                status="error",
                error=PixelsmithError(code="GENERATION", message=str(exc)),
            ).model_dump()

    def generate_hidden_audition_finalists(
        self,
        *,
        finalists: list[dict],
        prompt: str,
    ) -> dict:
        """Generate art-scored finalists without selecting a final weapon winner."""
        archive_theses: dict[str, WeaponThesis] = {}
        archive_finalists: list[str] = [
            str(manifest.get("candidate_id") or "").strip()
            for manifest in finalists
            if str(manifest.get("candidate_id") or "").strip()
        ]
        archive_rejection_reasons: dict[str, str] = {}
        art_scored_finalists: list[PixelsmithHiddenAuditionFinalist] = []
        if not prompt.strip():
            return self._hidden_audition_error_output(
                prompt=prompt,
                theses=archive_theses,
                finalists=archive_finalists,
                rejection_reasons=archive_rejection_reasons,
                code="VALIDATION",
                message="prompt must not be empty",
            )

        for manifest in finalists:
            finalist_id = str(manifest.get("candidate_id") or "").strip()

            try:
                parsed = PixelsmithInput.model_validate(manifest)
            except ValidationError as exc:
                return self._hidden_audition_error_output(
                    prompt=prompt,
                    theses=archive_theses,
                    finalists=archive_finalists,
                    rejection_reasons=archive_rejection_reasons,
                    code="VALIDATION",
                    message=str(exc),
                )

            if not finalist_id:
                finalist_id = parsed.item_name
                archive_finalists.append(finalist_id)

            try:
                thesis = manifest.get("weapon_thesis")
                if thesis is not None:
                    archive_theses[finalist_id] = WeaponThesis.model_validate(thesis)
                winner = self._audition_item_finalist(
                    finalist_id=finalist_id,
                    parsed=parsed,
                    prompt=prompt,
                    rejection_reasons=archive_rejection_reasons,
                )
                if winner is None:
                    continue
                art_scored_finalists.append(winner)
            except ValidationError as exc:
                return self._hidden_audition_error_output(
                    prompt=prompt,
                    theses=archive_theses,
                    finalists=archive_finalists,
                    rejection_reasons=archive_rejection_reasons,
                    code="VALIDATION",
                    message=str(exc),
                )
            except Exception as exc:
                logger.exception("Hidden audition failed")
                return self._hidden_audition_error_output(
                    prompt=prompt,
                    theses=archive_theses,
                    finalists=archive_finalists,
                    rejection_reasons=archive_rejection_reasons,
                    code="GENERATION",
                    message=str(exc),
                )

        try:
            return PixelsmithHiddenAuditionOutput(
                status="success",
                art_scored_finalists=art_scored_finalists,
                candidate_archive=WeaponLabArchive(
                    prompt=prompt,
                    theses=archive_theses,
                    finalists=archive_finalists,
                    rejection_reasons=archive_rejection_reasons,
                ),
            ).model_dump()
        except Exception as exc:
            logger.exception("Hidden audition failed")
            return self._hidden_audition_error_output(
                prompt=prompt,
                theses=archive_theses,
                finalists=archive_finalists,
                rejection_reasons=archive_rejection_reasons,
                code="GENERATION",
                message=str(exc),
            )

    def _hidden_audition_error_output(
        self,
        *,
        prompt: str,
        theses: dict[str, WeaponThesis],
        finalists: list[str],
        rejection_reasons: dict[str, str],
        code: str,
        message: str,
    ) -> dict:
        archive_prompt = prompt.strip() or "<hidden audition prompt unavailable>"
        return PixelsmithHiddenAuditionOutput(
            status="error",
            art_scored_finalists=[],
            candidate_archive=WeaponLabArchive(
                prompt=archive_prompt,
                theses=theses,
                finalists=finalists,
                rejection_reasons=rejection_reasons,
            ),
            error=PixelsmithError(code=code, message=message),
        ).model_dump()

    def _audition_item_finalist(
        self,
        *,
        finalist_id: str,
        parsed: PixelsmithInput,
        prompt: str,
        rejection_reasons: dict[str, str],
    ) -> PixelsmithHiddenAuditionFinalist | None:
        generation_mode, reference_url, endpoint = self._resolve_generation_mode(
            generation_mode=parsed.generation_mode,
            reference_image_url=parsed.reference_image_url,
        )
        orientation = _resolve_weapon_orientation(parsed.sub_type)

        if generation_mode == "image_to_image" and reference_url:
            render_prompt = build_img2img_prompt(
                parsed.visuals.description,
                reference_url,
                orientation=orientation,
            )
        else:
            render_prompt = build_prompt(
                parsed.visuals.description,
                lora_loaded=self._lora_loaded,
                orientation=orientation,
            )

        strategy = map_art_direction_profile(parsed.visuals.art_direction_profile)
        variant_count = max(strategy.variant_count, HIDDEN_AUDITION_MIN_VARIANTS)
        if generation_mode == "image_to_image" and reference_url:
            variant_count = max(variant_count, IMG2IMG_VARIANTS)

        surviving_candidates: list[dict[str, object]] = []

        for index in range(variant_count):
            candidate_id = f"{finalist_id}-art-{index + 1:03d}"
            raw_image = self._run_pipeline(
                render_prompt,
                generation_mode=generation_mode,
                reference_image_url=reference_url,
                endpoint=endpoint,
            )
            processed = remove_background(raw_image).convert("RGBA")
            processed = downscale(processed, tuple(parsed.visuals.icon_size))
            gate_report = evaluate_sprite_gates(processed, sprite_kind="item")

            candidate_record = {
                "candidate_id": candidate_id,
                "sprite_gate_report": gate_report.model_dump(),
                "image": processed,
            }
            if gate_report.passed:
                surviving_candidates.append(candidate_record)
                continue

            failed_checks = ", ".join(
                sorted(
                    name
                    for name, check in gate_report.checks.items()
                    if not check.passed
                )
            )
            rejection_reasons[candidate_id] = (
                f"failed deterministic sprite gates: {failed_checks}"
            )

        if not surviving_candidates:
            rejection_reasons[finalist_id] = (
                "no art candidate survived deterministic sprite gates"
            )
            return None

        judged = judge_surviving_candidates(
            [candidate["image"] for candidate in surviving_candidates],
            prompt=prompt,
            family_hint=parsed.visuals.description,
        )
        winner_index = int(judged.get("winner_index", 0))
        if winner_index < 0 or winner_index >= len(surviving_candidates):
            winner_index = 0

        scores = judged.get("scores", [])
        for index, candidate in enumerate(surviving_candidates):
            score = scores[index] if index < len(scores) else {}
            candidate["motif_strength"] = float(score.get("motif_strength", 0.0))
            candidate["family_coherence"] = float(score.get("family_coherence", 0.0))
            candidate["judge_notes"] = str(score.get("notes", ""))

        winner = surviving_candidates[winner_index]
        for candidate in surviving_candidates:
            if candidate["candidate_id"] == winner["candidate_id"]:
                continue
            rejection_reasons[candidate["candidate_id"]] = (
                f"lost art judging to {winner['candidate_id']}"
            )

        out_path = self.output_dir / _hidden_audition_item_output_name(
            parsed.item_name, finalist_id
        )
        winner["image"].save(out_path)

        projectile_sprite_path = ""
        if parsed.projectile_visuals is not None:
            projectile_sprite_path = self._generate_projectile(
                parsed, parsed.model_dump(mode="json")
            )

        return PixelsmithHiddenAuditionFinalist.model_validate(
            {
                "finalist_id": finalist_id,
                "item_name": parsed.item_name,
                "item_sprite_path": str(out_path),
                "projectile_sprite_path": projectile_sprite_path,
                "item_visual_summary": "",
                "projectile_visual_summary": "",
                "observed_art_signals": {
                    "item_motif_strength": winner["motif_strength"],
                    "item_family_coherence": winner["family_coherence"],
                    "item_sprite_gate_passed": bool(
                        winner["sprite_gate_report"].get("passed", False)
                    ),
                },
                "winner_candidate_id": winner["candidate_id"],
                "winner_art_scores": {
                    "motif_strength": winner["motif_strength"],
                    "family_coherence": winner["family_coherence"],
                    "notes": winner["judge_notes"],
                },
                "winner_sprite_gate_report": winner["sprite_gate_report"],
                "surviving_candidates": [
                    {key: value for key, value in candidate.items() if key != "image"}
                    for candidate in surviving_candidates
                ],
            }
        )

    def _build_fal_input(
        self,
        prompt: str,
        *,
        generation_mode: str = "text_to_image",
        reference_image_url: str | None = None,
    ) -> dict:
        loras = []
        if self._lora_path:
            loras.append({"path": self._lora_path, "scale": LORA_SCALE})

        if generation_mode == "image_to_image" and reference_image_url:
            # Edit endpoint has a narrower schema — only include supported fields
            payload = {
                "prompt": prompt,
                "guidance_scale": 5,
                "num_inference_steps": 28,
                "image_size": GENERATION_SIZE,
                "num_images": 1,
                "enable_safety_checker": True,
                "output_format": "png",
                "loras": loras,
                "image_urls": [reference_image_url],
            }
        else:
            payload = {
                "prompt": prompt,
                "negative_prompt": "",
                "guidance_scale": 5,
                "num_inference_steps": 28,
                "image_size": GENERATION_SIZE,
                "num_images": 1,
                "acceleration": "regular",
                "enable_safety_checker": True,
                "output_format": "png",
                "loras": loras,
            }
        return payload

    def _resolve_generation_mode(
        self,
        *,
        generation_mode: str,
        reference_image_url: str | None,
    ) -> tuple[str, str | None, str]:
        if generation_mode != "image_to_image":
            return "text_to_image", None, FAL_MODEL_ENDPOINT

        if not reference_image_url:
            logger.info(
                "image_to_image requested without reference URL; falling back to text_to_image"
            )
            return "text_to_image", None, FAL_MODEL_ENDPOINT

        if not self._image_to_image_enabled:
            logger.info(
                "image_to_image requested but disabled by config; falling back to text_to_image"
            )
            return "text_to_image", None, FAL_MODEL_ENDPOINT

        return "image_to_image", reference_image_url, FAL_IMG2IMG_ENDPOINT

    def _run_pipeline(
        self,
        prompt: str,
        *,
        generation_mode: str = "text_to_image",
        reference_image_url: str | None = None,
        endpoint: str = FAL_MODEL_ENDPOINT,
    ) -> Image.Image:
        if not NODE_RUNNER.exists():
            raise RuntimeError(f"Missing Node runner script: {NODE_RUNNER}")

        with tempfile.TemporaryDirectory() as tmp:
            payload_path = Path(tmp) / "payload.json"
            output_path = Path(tmp) / "result.png"
            payload = {
                "endpoint": endpoint,
                "input": self._build_fal_input(
                    prompt,
                    generation_mode=generation_mode,
                    reference_image_url=reference_image_url,
                ),
                "output_path": str(output_path),
            }
            payload_path.write_text(json.dumps(payload), encoding="utf-8")

            env = os.environ.copy()
            env["FAL_KEY"] = self._fal_key

            proc = subprocess.run(
                ["node", str(NODE_RUNNER), str(payload_path)],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            if proc.returncode != 0:
                details = proc.stderr.strip() or proc.stdout.strip() or "unknown error"
                raise RuntimeError(f"fal runner failed: {details}")
            if not output_path.exists():
                raise RuntimeError(
                    "fal runner succeeded but no output image was produced."
                )

            with Image.open(output_path) as img:
                return img.convert("RGBA").copy()

    def _generate_with_variants(
        self,
        prompt: str,
        *,
        generation_mode: str,
        reference_url: str | None,
        endpoint: str,
        n_variants: int = 1,
    ) -> Image.Image:
        """Generate n_variants images and pick the best one (or just one if text-to-image)."""
        if n_variants <= 1 or generation_mode != "image_to_image" or not reference_url:
            return self._run_pipeline(
                prompt,
                generation_mode=generation_mode,
                reference_image_url=reference_url,
                endpoint=endpoint,
            )

        logger.info("Generating %d variants for best-of-N selection", n_variants)
        candidates = []
        for i in range(n_variants):
            img = self._run_pipeline(
                prompt,
                generation_mode=generation_mode,
                reference_image_url=reference_url,
                endpoint=endpoint,
            )
            candidates.append(img)
            logger.info("Generated variant %d/%d", i + 1, n_variants)

        best_idx = select_best_variant(candidates, reference_url)
        logger.info("Selected variant %d as best match", best_idx + 1)

        return candidates[best_idx]

    def _generate_standard_item(self, parsed: PixelsmithInput) -> Path:
        generation_mode, reference_url, endpoint = self._resolve_generation_mode(
            generation_mode=parsed.generation_mode,
            reference_image_url=parsed.reference_image_url,
        )

        # Resolve orientation from weapon sub_type
        orientation = _resolve_weapon_orientation(parsed.sub_type)

        # Build prompt: img2img uses color-aware prompt, text2img uses standard
        if generation_mode == "image_to_image" and reference_url:
            prompt = build_img2img_prompt(
                parsed.visuals.description, reference_url, orientation=orientation
            )
            n_variants = IMG2IMG_VARIANTS
        else:
            prompt = build_prompt(
                parsed.visuals.description,
                lora_loaded=self._lora_loaded,
                orientation=orientation,
            )
            n_variants = 1

        logger.info("Prompt: %s", prompt)

        raw_image = self._generate_with_variants(
            prompt,
            generation_mode=generation_mode,
            reference_url=reference_url,
            endpoint=endpoint,
            n_variants=n_variants,
        )

        processed = remove_background(raw_image).convert("RGBA")
        target = tuple(parsed.visuals.icon_size)
        processed = downscale(processed, target)

        out_path = self.output_dir / f"{parsed.item_name}.png"
        processed.save(out_path)
        logger.info("Saved item sprite → %s", out_path)
        return out_path

    def _generate_armor(self, parsed: PixelsmithInput) -> Path:
        generation_mode, reference_url, endpoint = self._resolve_generation_mode(
            generation_mode=parsed.generation_mode,
            reference_image_url=parsed.reference_image_url,
        )

        orientation = _resolve_weapon_orientation(parsed.sub_type)

        if generation_mode == "image_to_image" and reference_url:
            prompt = build_img2img_prompt(
                parsed.visuals.description, reference_url, orientation=orientation
            )
        else:
            prompt = build_prompt(
                parsed.visuals.description,
                lora_loaded=self._lora_loaded,
                orientation=orientation,
            )

        raw_image = self._run_pipeline(
            prompt,
            generation_mode=generation_mode,
            reference_image_url=reference_url,
            endpoint=endpoint,
        )

        texture = remove_background(raw_image)
        texture = downscale(texture, (FRAME_WIDTH, FRAME_HEIGHT))
        sheet = composite_armor(texture)

        out_path = self.output_dir / f"{parsed.item_name}_Body.png"
        sheet.save(out_path)
        logger.info("Saved armor sheet → %s", out_path)
        return out_path

    def _generate_projectile(self, parsed: PixelsmithInput, raw_manifest: dict) -> str:
        proj = parsed.projectile_visuals
        assert proj is not None

        generation_mode, reference_url, endpoint = self._resolve_generation_mode(
            generation_mode=parsed.generation_mode,
            reference_image_url=parsed.reference_image_url,
        )

        # Infer projectile orientation from its description keywords
        proj_orientation = _resolve_projectile_orientation(proj.description)

        if generation_mode == "image_to_image" and reference_url:
            prompt = build_img2img_prompt(
                proj.description, reference_url, orientation=proj_orientation
            )
            n_variants = IMG2IMG_VARIANTS
        else:
            prompt = build_prompt(
                proj.description,
                lora_loaded=self._lora_loaded,
                orientation=proj_orientation,
            )
            n_variants = 1

        logger.info("Projectile prompt: %s", prompt)

        raw_image = self._generate_with_variants(
            prompt,
            generation_mode=generation_mode,
            reference_url=reference_url,
            endpoint=endpoint,
            n_variants=n_variants,
        )

        proj_name = _extract_projectile_name(raw_manifest)

        processed = remove_background(raw_image).convert("RGBA")
        target = tuple(proj.icon_size)
        processed = downscale(processed, target)

        out_path = self.output_dir / f"{proj_name}.png"
        processed.save(out_path)
        logger.info("Saved projectile sprite → %s", out_path)
        return str(out_path)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    agent = ArtistAgent()

    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            manifest = json.load(f)
    else:
        manifest = {
            "item_name": "GelatinousBlade",
            "type": "Weapon",
            "visuals": {
                "description": "A translucent green sword with dripping slime effects.",
                "color_palette": ["#00FF00", "#FFFFFF"],
                "icon_size": [32, 32],
            },
            "projectile_visuals": {
                "description": "A spinning green star",
                "icon_size": [16, 16],
            },
            "mechanics": {
                "shoot_projectile": "ModContent.ProjectileType<SpinningSlimeStar>()",
            },
        }

    result = agent.generate_asset(manifest)
    print(json.dumps(result, indent=2))
