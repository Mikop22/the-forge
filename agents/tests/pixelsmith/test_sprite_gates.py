from __future__ import annotations

from PIL import Image, ImageDraw

from pixelsmith.sprite_gates import _background_reference, evaluate_sprite_gates


def _make_item_sprite() -> Image.Image:
    image = Image.new("RGBA", (32, 32), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 6, 21, 25), fill=(20, 20, 20, 255))
    return image


def _make_bright_item_sprite() -> Image.Image:
    image = Image.new("RGBA", (32, 32), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle(
        (10, 6, 21, 25), outline=(30, 30, 30, 255), fill=(255, 255, 255, 255)
    )
    return image


def _make_off_center_clean_item_sprite() -> Image.Image:
    image = Image.new("RGBA", (32, 32), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((6, 6, 17, 25), fill=(20, 20, 20, 255))
    return image


def _make_item_sprite_with_detached_noise() -> Image.Image:
    image = Image.new("RGBA", (32, 32), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((14, 5, 17, 26), fill=(20, 20, 20, 255))
    for point in (
        (6, 6),
        (7, 6),
        (6, 7),
        (24, 8),
        (25, 8),
        (24, 9),
        (7, 21),
        (8, 21),
        (7, 22),
        (24, 23),
        (25, 23),
        (24, 24),
    ):
        draw.point(point, fill=(20, 20, 20, 255))
    return image


def _make_fragmented_item_sprite() -> Image.Image:
    image = Image.new("RGBA", (32, 32), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((5, 8, 11, 23), fill=(20, 20, 20, 255))
    draw.rectangle((20, 8, 26, 23), fill=(20, 20, 20, 255))
    return image


def _make_item_sprite_with_tiny_edge_contact() -> Image.Image:
    image = _make_item_sprite()
    draw = ImageDraw.Draw(image)
    draw.point((0, 16), fill=(20, 20, 20, 255))
    return image


def _make_bad_projectile_sprite() -> Image.Image:
    image = Image.new("RGBA", (16, 16), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.point((0, 1), fill=(225, 225, 225, 255))
    draw.rectangle((6, 6, 9, 9), fill=(245, 245, 245, 255))
    return image


def _make_tied_corner_background_sprite() -> Image.Image:
    image = Image.new("RGBA", (8, 8), (255, 255, 255, 255))
    image.putpixel((0, 0), (240, 240, 240, 255))
    image.putpixel((7, 0), (241, 241, 241, 255))
    image.putpixel((0, 7), (240, 240, 240, 255))
    image.putpixel((7, 7), (241, 241, 241, 255))
    return image


def test_sprite_gate_report_passes_for_readable_centered_item() -> None:
    report = evaluate_sprite_gates(_make_item_sprite(), sprite_kind="item")

    assert report.passed is True
    assert report.checks["occupancy"].passed is True
    assert report.checks["silhouette_readability"].passed is True
    assert report.checks["contrast_value_floor"].passed is True
    assert report.checks["center_background_cleanup"].passed is True


def test_sprite_gate_report_keeps_bright_enclosed_pixels_as_foreground() -> None:
    report = evaluate_sprite_gates(_make_bright_item_sprite(), sprite_kind="item")

    assert report.passed is True
    assert report.checks["occupancy"].passed is True
    assert report.foreground_bbox == [10, 6, 21, 25]


def test_sprite_gate_report_allows_clean_but_not_perfectly_centered_sprite() -> None:
    report = evaluate_sprite_gates(
        _make_off_center_clean_item_sprite(), sprite_kind="item"
    )

    assert report.passed is True
    assert report.checks["center_background_cleanup"].passed is True


def test_sprite_gate_report_allows_tiny_edge_contact_for_otherwise_readable_item() -> (
    None
):
    report = evaluate_sprite_gates(
        _make_item_sprite_with_tiny_edge_contact(), sprite_kind="item"
    )

    assert report.passed is True
    assert report.checks["center_background_cleanup"].passed is True


def test_silhouette_readability_ignores_tiny_detached_noise_clusters() -> None:
    report = evaluate_sprite_gates(
        _make_item_sprite_with_detached_noise(), sprite_kind="item"
    )

    assert report.checks["silhouette_readability"].passed is True


def test_silhouette_readability_still_rejects_genuinely_fragmented_sprite() -> None:
    report = evaluate_sprite_gates(_make_fragmented_item_sprite(), sprite_kind="item")

    assert report.checks["silhouette_readability"].passed is False


def test_background_reference_uses_stable_corner_order_on_tie() -> None:
    reference = _background_reference(_make_tied_corner_background_sprite())

    assert reference == (240, 240, 240, 255)


def test_sprite_gate_report_flags_deterministic_projectile_failures() -> None:
    report = evaluate_sprite_gates(
        _make_bad_projectile_sprite(), sprite_kind="projectile"
    )

    assert report.passed is False
    assert report.checks["occupancy"].passed is False
    assert report.checks["contrast_value_floor"].passed is False
    assert report.checks["center_background_cleanup"].passed is False
    assert report.checks["projectile_size_readability"].passed is False
