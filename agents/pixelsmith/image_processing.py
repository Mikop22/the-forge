"""Image post-processing pipeline for the Pixelsmith agent.

Steps (in order):
1. remove_background  – strip white/coloured background → transparent RGBA
2. downscale          – nearest-neighbor resize to target sprite size
3. enforce_outline    – add a dark pixel-art border around the silhouette
4. process_image      – convenience function chaining all three steps
"""

from __future__ import annotations

import numpy as np
from PIL import Image


# ---------------------------------------------------------------------------
# 1. Background removal
# ---------------------------------------------------------------------------

def remove_background(
    image: Image.Image,
    *,
    tolerance: int = 20,
) -> Image.Image:
    """Remove the white background via flood-fill from edges.

    Starts from every edge pixel that is near-white and flood-fills inward,
    marking connected near-white pixels as transparent.  This preserves any
    white/light details *inside* the weapon (highlights, reflections) because
    they aren't connected to the edge.

    Parameters
    ----------
    image : Image.Image
        Source image (any mode — will be converted to RGBA).
    tolerance : int
        Max distance from pure white (255,255,255) for a pixel to count as
        "background".  Default 20 means RGB values >= 235 are background.
    """
    img = image.convert("RGBA")
    arr = np.array(img)
    h, w = arr.shape[:2]

    # Build a mask of near-white pixels
    rgb = arr[:, :, :3].astype(np.int16)
    white_mask = (
        (rgb[:, :, 0] >= 255 - tolerance)
        & (rgb[:, :, 1] >= 255 - tolerance)
        & (rgb[:, :, 2] >= 255 - tolerance)
    )

    # Flood-fill from all edge pixels that are near-white
    from collections import deque

    visited = np.zeros((h, w), dtype=bool)
    queue: deque[tuple[int, int]] = deque()

    # Seed from all four edges
    for x in range(w):
        for y in (0, h - 1):
            if white_mask[y, x] and not visited[y, x]:
                visited[y, x] = True
                queue.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if white_mask[y, x] and not visited[y, x]:
                visited[y, x] = True
                queue.append((y, x))

    # BFS flood-fill
    while queue:
        cy, cx = queue.popleft()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and white_mask[ny, nx]:
                visited[ny, nx] = True
                queue.append((ny, nx))

    # Set background pixels to transparent
    arr[visited, 3] = 0

    return Image.fromarray(arr)


# ---------------------------------------------------------------------------
# 2. Nearest-neighbor downscale
# ---------------------------------------------------------------------------

def downscale(image: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    """Resize *image* to *target_size* using **Nearest Neighbor** interpolation.

    This is the only correct resampling method for pixel art — it preserves
    hard edges and avoids anti-aliased "mixels".

    Parameters
    ----------
    image : Image.Image
        Source image (any size).
    target_size : tuple[int, int]
        ``(width, height)`` of the output.
    """
    return image.resize(target_size, resample=Image.Resampling.NEAREST)


# ---------------------------------------------------------------------------
# 3. Outline enforcement
# ---------------------------------------------------------------------------

DEFAULT_OUTLINE_COLOR = (26, 26, 46, 255)  # #1a1a2e, fully opaque


def enforce_outline(
    image: Image.Image,
    color: tuple[int, int, int, int] = DEFAULT_OUTLINE_COLOR,
    thickness: int = 1,
) -> Image.Image:
    """Add a dark outline around non-transparent pixels.

    Works by dilating the alpha mask by *thickness* pixels in the four
    cardinal directions.  Newly-opaque pixels that were previously
    transparent are filled with *color*.

    Parameters
    ----------
    image : Image.Image
        RGBA image to outline.
    color : tuple
        ``(R, G, B, A)`` colour for the outline pixels.
    thickness : int
        Width of the outline in pixels (default 1).
    """
    image = image.convert("RGBA")
    arr = np.array(image)
    alpha = arr[:, :, 3]

    # Build the dilated mask by shifting in each cardinal direction.
    dilated = alpha.copy()
    for _step in range(thickness):
        shifted = dilated.copy()
        # Shift up
        shifted[:-1, :] = np.maximum(shifted[:-1, :], dilated[1:, :])
        # Shift down
        shifted[1:, :] = np.maximum(shifted[1:, :], dilated[:-1, :])
        # Shift left
        shifted[:, :-1] = np.maximum(shifted[:, :-1], dilated[:, 1:])
        # Shift right
        shifted[:, 1:] = np.maximum(shifted[:, 1:], dilated[:, :-1])
        dilated = shifted

    # Outline pixels = dilated but not originally opaque.
    outline_mask = (dilated > 0) & (alpha == 0)

    # Apply the outline colour.
    arr[outline_mask] = color
    return Image.fromarray(arr)


# ---------------------------------------------------------------------------
# 4. Combined pipeline
# ---------------------------------------------------------------------------

def process_image(
    image: Image.Image,
    target_size: tuple[int, int],
    *,
    add_outline: bool = True,
    outline_color: tuple[int, int, int, int] = DEFAULT_OUTLINE_COLOR,
    outline_thickness: int = 1,
) -> Image.Image:
    """Run the full post-processing pipeline on a raw generated image.

    Pipeline order:
        1. Background removal (rembg)
        2. Nearest-neighbor downscale to *target_size*
        3. Outline enforcement (optional)

    Returns an RGBA PIL Image ready to save as a ``.png``.
    """
    img = remove_background(image)
    img = downscale(img, target_size)
    if add_outline:
        img = enforce_outline(img, color=outline_color, thickness=outline_thickness)
    return img
