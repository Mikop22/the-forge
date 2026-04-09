"""Shared utilities used across multiple agents."""

from __future__ import annotations

import re


def to_pascal_case(name: str) -> str:
    """Sanitize a string into a valid PascalCase C# identifier."""
    cleaned = re.sub(r"[^a-zA-Z0-9]", " ", name)
    cleaned = re.sub(r"([a-z])([A-Z])", r"\1 \2", cleaned)
    return "".join(word.capitalize() for word in cleaned.split())
