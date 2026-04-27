"""Armor sprite-sheet compositor for Terraria tModLoader.

Terraria body armor sprites are laid out as a vertical strip of 20 frames,
each 40×56 pixels, producing a final sheet of 40×1120 px.  AI cannot
generate this layout reliably, so we:

1. Generate a *single* chestplate texture (40×56 after downscale).
2. Paste that texture into each frame slot of a blank template.

The coordinate map is derived from the Terraria wiki body armor frame layout.
"""

from __future__ import annotations


from PIL import Image

# ---------------------------------------------------------------------------
# Frame layout constants
# ---------------------------------------------------------------------------

FRAME_WIDTH = 40
FRAME_HEIGHT = 56
FRAME_COUNT = 20
SHEET_WIDTH = FRAME_WIDTH                     # 40 px
SHEET_HEIGHT = FRAME_HEIGHT * FRAME_COUNT     # 1120 px

# Coordinate map: frame_index → (x, y) top-left corner in the sprite sheet.
# Terraria body sprites stack vertically with no padding.
ARMOR_FRAME_COORDS: dict[int, tuple[int, int]] = {
    i: (0, i * FRAME_HEIGHT) for i in range(FRAME_COUNT)
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_blank_template() -> Image.Image:
    """Create a blank (fully transparent) armor sprite-sheet template.

    Returns a 40×1120 RGBA image with alpha 0 everywhere.
    """
    return Image.new("RGBA", (SHEET_WIDTH, SHEET_HEIGHT), (0, 0, 0, 0))


def composite_armor(
    texture: Image.Image,
    template: Image.Image | None = None,
) -> Image.Image:
    """Paste *texture* into every frame slot of the armor template.

    Parameters
    ----------
    texture : Image.Image
        A single chestplate frame, expected to be 40×56 px RGBA.  If the
        size differs it is resized to (40, 56) with nearest-neighbor.
    template : Image.Image | None
        Optional pre-loaded template (40×1120 RGBA).  A blank one is
        created when ``None``.

    Returns
    -------
    Image.Image
        The completed sprite sheet (40×1120 RGBA).
    """
    texture = texture.convert("RGBA")

    # Ensure texture is exactly one frame in size.
    if texture.size != (FRAME_WIDTH, FRAME_HEIGHT):
        texture = texture.resize(
            (FRAME_WIDTH, FRAME_HEIGHT),
            resample=Image.Resampling.NEAREST,
        )

    if template is None:
        template = create_blank_template()
    else:
        template = template.copy().convert("RGBA")

    for _frame_idx, (x, y) in ARMOR_FRAME_COORDS.items():
        template.paste(texture, (x, y), mask=texture)

    return template
