from __future__ import annotations

from PIL import Image, ImageDraw

from pixelsmith.image_processing import remove_background


def test_remove_background_isolates_edge_connected_flat_dark_background() -> None:
    image = Image.new("RGBA", (8, 8), (43, 43, 43, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((2, 2, 5, 5), fill=(210, 92, 32, 255))

    processed = remove_background(image)

    assert processed.getpixel((0, 0))[3] == 0
    assert processed.getpixel((7, 7))[3] == 0
    assert processed.getpixel((3, 3)) == (210, 92, 32, 255)


def test_remove_background_isolates_multiple_flat_edge_background_regions() -> None:
    image = Image.new("RGBA", (8, 8), (43, 43, 43, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((4, 0, 7, 7), fill=(255, 255, 255, 255))
    draw.rectangle((2, 2, 5, 5), fill=(210, 92, 32, 255))

    processed = remove_background(image)

    assert processed.getpixel((0, 0))[3] == 0
    assert processed.getpixel((7, 7))[3] == 0
    assert processed.getpixel((3, 3)) == (210, 92, 32, 255)
