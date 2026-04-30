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

def _edge_background_references(
    arr: np.ndarray,
    *,
    tolerance: int,
) -> list[tuple[int, int, int]]:
    """Pick significant flat background colors from the image border."""
    h, w = arr.shape[:2]
    rgb = arr[:, :, :3].astype(np.int16)
    edge_pixels = []

    for x in range(w):
        edge_pixels.append(tuple(int(value) for value in rgb[0, x]))
        edge_pixels.append(tuple(int(value) for value in rgb[h - 1, x]))
    for y in range(1, h - 1):
        edge_pixels.append(tuple(int(value) for value in rgb[y, 0]))
        edge_pixels.append(tuple(int(value) for value in rgb[y, w - 1]))

    bucket_size = max(tolerance + 1, 1)
    buckets: dict[tuple[int, int, int], list[tuple[int, int, int]]] = {}
    for pixel in edge_pixels:
        bucket = tuple(channel // bucket_size for channel in pixel)
        buckets.setdefault(bucket, []).append(pixel)

    min_bucket_count = max(4, int(round(len(edge_pixels) * 0.1)))
    significant_buckets = [
        pixels for pixels in buckets.values() if len(pixels) >= min_bucket_count
    ]
    if not significant_buckets:
        significant_buckets = [max(buckets.values(), key=len)]

    return [
        tuple(
            int(round(sum(pixel[channel] for pixel in pixels) / len(pixels)))
            for channel in range(3)
        )
        for pixels in significant_buckets
    ]


def remove_background(
    image: Image.Image,
    *,
    tolerance: int = 20,
) -> Image.Image:
    """Remove the flat background via flood-fill from edges.

    Starts from every edge pixel that matches a significant border color and
    flood-fills inward, marking connected background pixels as transparent.
    This preserves matching details inside the weapon because they aren't
    connected to the edge.

    Parameters
    ----------
    image : Image.Image
        Source image (any mode — will be converted to RGBA).
    tolerance : int
        Max per-channel distance from a significant border color for a pixel to
        count as "background".
    """
    img = image.convert("RGBA")
    arr = np.array(img)
    h, w = arr.shape[:2]

    # Build a mask of pixels that match significant flat border colors.
    rgb = arr[:, :, :3].astype(np.int16)
    references = np.array(_edge_background_references(arr, tolerance=tolerance))
    deltas = np.max(np.abs(rgb[:, :, np.newaxis, :] - references), axis=3)
    background_mask = np.any(deltas <= tolerance, axis=2)

    # Flood-fill from all edge pixels that match a background reference.
    from collections import deque

    visited = np.zeros((h, w), dtype=bool)
    queue: deque[tuple[int, int]] = deque()

    # Seed from all four edges
    for x in range(w):
        for y in (0, h - 1):
            if background_mask[y, x] and not visited[y, x]:
                visited[y, x] = True
                queue.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if background_mask[y, x] and not visited[y, x]:
                visited[y, x] = True
                queue.append((y, x))

    # BFS flood-fill
    while queue:
        cy, cx = queue.popleft()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = cy + dy, cx + dx
            if (
                0 <= ny < h
                and 0 <= nx < w
                and not visited[ny, nx]
                and background_mask[ny, nx]
            ):
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
