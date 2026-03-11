"""Extract dominant colors from a reference image using k-means clustering."""

from __future__ import annotations

from collections import Counter

import numpy as np
from PIL import Image
from sklearn.cluster import KMeans

# Named color map for mapping RGB centroids to human-readable names
_COLOR_NAMES = {
    "black": (0, 0, 0),
    "dark gray": (64, 64, 64),
    "gray": (128, 128, 128),
    "silver": (192, 192, 192),
    "white": (255, 255, 255),
    "dark red": (139, 0, 0),
    "red": (255, 0, 0),
    "crimson": (220, 20, 60),
    "dark brown": (60, 30, 10),
    "brown": (139, 69, 19),
    "tan": (210, 180, 140),
    "gold": (212, 175, 55),
    "dark gold": (180, 140, 30),
    "yellow": (255, 255, 0),
    "yellow-green": (154, 205, 50),
    "chartreuse": (127, 255, 0),
    "dark green": (0, 100, 0),
    "green": (0, 180, 0),
    "lime green": (50, 205, 50),
    "bright green": (0, 255, 0),
    "olive": (107, 142, 35),
    "teal": (0, 128, 128),
    "cyan": (0, 255, 255),
    "dark blue": (0, 0, 139),
    "blue": (0, 0, 255),
    "light blue": (135, 206, 235),
    "purple": (128, 0, 128),
    "magenta": (255, 0, 255),
    "pink": (255, 105, 180),
    "orange": (255, 165, 0),
    "dark orange": (200, 100, 0),
}

# Colors that are too generic to be "accent" colors
_NEUTRAL_COLORS = {"black", "dark gray", "gray", "silver", "white", "dark brown", "brown", "tan"}


def _rgb_distance(c1: tuple, c2: tuple) -> float:
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5


def _nearest_color_name(rgb: tuple) -> str:
    best_name = "unknown"
    best_dist = float("inf")
    for name, ref in _COLOR_NAMES.items():
        d = _rgb_distance(rgb, ref)
        if d < best_dist:
            best_dist = d
            best_name = name
    return best_name


def extract_colors(img: Image.Image, n_clusters: int = 8) -> list[dict]:
    """Extract dominant colors via k-means, ignoring transparent/white pixels.

    Returns list of dicts sorted by percentage (descending):
        [{"name": "black", "hex": "#020202", "rgb": (2,2,2), "percentage": 24.3}, ...]
    """
    rgba = img.convert("RGBA")
    pixels = np.array(rgba).reshape(-1, 4)

    # Filter: not transparent, not near-white
    mask = pixels[:, 3] > 128
    rgb_sum = pixels[:, 0].astype(int) + pixels[:, 1].astype(int) + pixels[:, 2].astype(int)
    mask = mask & (rgb_sum < 700)

    rgb_pixels = pixels[mask][:, :3].astype(float)
    if len(rgb_pixels) < n_clusters:
        return []

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    kmeans.fit(rgb_pixels)

    counts = Counter(kmeans.labels_)
    total = len(kmeans.labels_)

    results = []
    for cluster_id, count in counts.most_common():
        center = tuple(int(x) for x in kmeans.cluster_centers_[cluster_id])
        results.append({
            "name": _nearest_color_name(center),
            "hex": "#{:02x}{:02x}{:02x}".format(*center),
            "rgb": center,
            "percentage": round(count / total * 100, 1),
        })
    return results


def get_accent_colors(colors: list[dict], min_pct: float = 3.0) -> list[str]:
    """Return deduplicated list of non-neutral accent color names.

    These are the distinctive colors (greens, blues, golds, etc.) that
    differentiate this weapon from a generic dark sword.
    """
    seen: set[str] = set()
    accents: list[str] = []
    for c in colors:
        if c["percentage"] < min_pct:
            continue
        if c["name"] in _NEUTRAL_COLORS:
            continue
        if c["name"] not in seen:
            seen.add(c["name"])
            accents.append(c["name"])
    return accents


def get_color_palette_string(colors: list[dict], min_pct: float = 3.0) -> str:
    """Return deduplicated comma-separated string of all significant color names."""
    seen: set[str] = set()
    names: list[str] = []
    for c in colors:
        if c["percentage"] < min_pct:
            continue
        if c["name"] not in seen:
            seen.add(c["name"])
            names.append(c["name"])
    return ", ".join(names)
