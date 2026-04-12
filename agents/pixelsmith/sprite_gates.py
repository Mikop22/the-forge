"""Deterministic image-based readability gates for Pixelsmith sprites."""

from __future__ import annotations

from collections import deque

from PIL import Image

try:
    from pixelsmith.models import SpriteGateCheck, SpriteGateReport, SpriteKindLiteral
except ImportError:
    from models import SpriteGateCheck, SpriteGateReport, SpriteKindLiteral


def _background_reference(image: Image.Image) -> tuple[int, int, int, int]:
    width, height = image.size
    corners = [
        image.getpixel((0, 0)),
        image.getpixel((width - 1, 0)),
        image.getpixel((0, height - 1)),
        image.getpixel((width - 1, height - 1)),
    ]
    counts: dict[tuple[int, int, int, int], int] = {}
    best = corners[0]
    best_count = 0

    for corner in corners:
        counts[corner] = counts.get(corner, 0) + 1
        if counts[corner] > best_count:
            best = corner
            best_count = counts[corner]

    return best


def _is_background_like(
    pixel: tuple[int, int, int, int], reference: tuple[int, int, int, int]
) -> bool:
    if pixel[3] == 0:
        return True
    return (
        max(abs(channel - ref) for channel, ref in zip(pixel[:3], reference[:3])) <= 4
    )


def _foreground_mask(image: Image.Image) -> list[list[bool]]:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    reference = _background_reference(rgba)
    background = [[False for _ in range(width)] for _ in range(height)]
    queue: deque[tuple[int, int]] = deque()

    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))

    while queue:
        x, y = queue.popleft()
        if background[y][x]:
            continue
        if not _is_background_like(rgba.getpixel((x, y)), reference):
            continue

        background[y][x] = True
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height and not background[ny][nx]:
                queue.append((nx, ny))

    return [
        [rgba.getpixel((x, y))[3] > 0 and not background[y][x] for x in range(width)]
        for y in range(height)
    ]


def _foreground_points(mask: list[list[bool]]) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    for y, row in enumerate(mask):
        for x, value in enumerate(row):
            if value:
                points.append((x, y))
    return points


def _bbox(points: list[tuple[int, int]]) -> list[int]:
    if not points:
        return []
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return [min(xs), min(ys), max(xs), max(ys)]


def _connected_components(mask: list[list[bool]]) -> list[list[tuple[int, int]]]:
    height = len(mask)
    width = len(mask[0]) if mask else 0
    visited: set[tuple[int, int]] = set()
    components: list[list[tuple[int, int]]] = []

    for y in range(height):
        for x in range(width):
            if not mask[y][x] or (x, y) in visited:
                continue

            component: list[tuple[int, int]] = []
            queue: deque[tuple[int, int]] = deque([(x, y)])
            visited.add((x, y))

            while queue:
                cx, cy = queue.popleft()
                component.append((cx, cy))
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if (
                        0 <= nx < width
                        and 0 <= ny < height
                        and mask[ny][nx]
                        and (nx, ny) not in visited
                    ):
                        visited.add((nx, ny))
                        queue.append((nx, ny))

            components.append(component)

    return components


def _largest_component_ratio(components: list[list[tuple[int, int]]]) -> float:
    if not components:
        return 0.0

    largest_component = max(components, key=len)
    noise_floor = max(4, (len(largest_component) + 19) // 20)
    significant_pixels = sum(
        len(component) for component in components if len(component) >= noise_floor
    )
    return len(largest_component) / max(significant_pixels, 1)


def _border_foreground_ratio(mask: list[list[bool]]) -> float:
    height = len(mask)
    width = len(mask[0]) if mask else 0
    if width == 0 or height == 0:
        return 0.0

    border_positions: set[tuple[int, int]] = set()
    for x in range(width):
        border_positions.add((x, 0))
        border_positions.add((x, height - 1))
    for y in range(height):
        border_positions.add((0, y))
        border_positions.add((width - 1, y))

    border_foreground = sum(1 for x, y in border_positions if mask[y][x])
    return border_foreground / len(border_positions)


def _contrast_delta(image: Image.Image, points: list[tuple[int, int]]) -> float:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    fg_lookup = set(points)
    fg_values: list[float] = []
    bg_values: list[float] = []

    for y in range(height):
        for x in range(width):
            r, g, b, _ = rgba.getpixel((x, y))
            value = (r + g + b) / 3
            if (x, y) in fg_lookup:
                fg_values.append(value)
            else:
                bg_values.append(value)

    if not fg_values or not bg_values:
        return 0.0
    return abs((sum(bg_values) / len(bg_values)) - (sum(fg_values) / len(fg_values)))


def _build_min_check(value: float, threshold: float, detail: str) -> SpriteGateCheck:
    return SpriteGateCheck(
        passed=value >= threshold,
        value=round(value, 4),
        threshold=threshold,
        comparator="min",
        detail=detail,
    )


def _build_max_check(value: float, threshold: float, detail: str) -> SpriteGateCheck:
    return SpriteGateCheck(
        passed=value <= threshold,
        value=round(value, 4),
        threshold=threshold,
        comparator="max",
        detail=detail,
    )


def evaluate_sprite_gates(
    image: Image.Image, sprite_kind: SpriteKindLiteral = "item"
) -> SpriteGateReport:
    """Evaluate bounded readability gates against a raster sprite candidate."""
    width, height = image.size
    border_pixel_budget = (
        1 / max((2 * width) + (2 * height) - 4, 1) if sprite_kind == "item" else 0.0
    )
    mask = _foreground_mask(image)
    points = _foreground_points(mask)
    components = _connected_components(mask)
    largest_component = max(components, key=len, default=[])
    occupancy = len(points) / max(width * height, 1)
    largest_component_ratio = _largest_component_ratio(components)
    contrast_delta = _contrast_delta(image, points)
    border_ratio = _border_foreground_ratio(mask)
    largest_bbox = _bbox(largest_component)
    largest_width = 0 if not largest_bbox else largest_bbox[2] - largest_bbox[0] + 1
    largest_height = 0 if not largest_bbox else largest_bbox[3] - largest_bbox[1] + 1

    occupancy_floor = 0.08 if sprite_kind == "item" else 0.08
    checks = {
        "occupancy": _build_min_check(
            occupancy,
            occupancy_floor,
            "Foreground coverage must stay above the minimum readability floor.",
        ),
        "silhouette_readability": _build_min_check(
            largest_component_ratio,
            0.9,
            "Most foreground pixels should belong to one dominant silhouette.",
        ),
        "contrast_value_floor": _build_min_check(
            contrast_delta,
            40.0,
            "Foreground values must separate clearly from the background.",
        ),
        "center_background_cleanup": _build_max_check(
            border_ratio,
            border_pixel_budget,
            "Sprite should preserve a clean background margin and avoid touching the canvas edge.",
        ),
        "projectile_size_readability": _build_min_check(
            float(max(largest_width, largest_height))
            if sprite_kind == "projectile"
            else 1.0,
            5.0 if sprite_kind == "projectile" else 1.0,
            "Projectile sprites need a minimum readable dominant dimension.",
        ),
    }

    return SpriteGateReport(
        sprite_kind=sprite_kind,
        passed=all(check.passed for check in checks.values()),
        foreground_bbox=_bbox(points),
        checks=checks,
    )
