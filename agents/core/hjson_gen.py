"""Deterministic Terraria localization (hjson) generation."""
from __future__ import annotations

import json
import textwrap


def generate_hjson(
    item_name: str,
    display_name: str,
    tooltip: str,
    mod_name: str = "ForgeGeneratedMod",
) -> str:
    """Produce a Terraria mod localization hjson file.

    DisplayName and Tooltip are emitted as JSON string literals so newlines,
    closing braces, and Terraria markup like ``[c/rrggbb:...]`` cannot break
    the hjson structure.
    """
    quoted_display = json.dumps(display_name, ensure_ascii=False)
    quoted_tooltip = json.dumps(tooltip, ensure_ascii=False)
    return textwrap.dedent(f"""\
        Mods: {{
        \t{mod_name}: {{
        \t\tItems: {{
        \t\t\t{item_name}: {{
        \t\t\t\tDisplayName: {quoted_display}
        \t\t\t\tTooltip: {quoted_tooltip}
        \t\t\t}}
        \t\t}}
        \t}}
        }}""")
