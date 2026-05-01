"""Shared C# source slicing helpers for critique and validation.

Strip comments and extract brace-balanced regions without a full parser —
used to inspect generated ModProjectile.SetDefaults bodies for hitbox checks.
"""

from __future__ import annotations

import re


def strip_csharp_comments(code: str) -> str:
    """Remove block and line comments so brace matching ignores commented `{`/`}`."""
    code = re.sub(r"/\*[\s\S]*?\*/", "", code)
    return re.sub(r"//.*", "", code)


def balanced_brace_block(text: str, open_idx: int) -> str:
    """Return inner source between `{` at open_idx and its matching closing `}`."""
    depth = 0
    for idx in range(open_idx, len(text)):
        char = text[idx]
        if char == "{":
            depth += 1
            continue
        if char != "}":
            continue
        depth -= 1
        if depth == 0:
            return text[open_idx + 1 : idx]
    return ""


def first_modprojectile_setdefaults_body(cs_code: str) -> str:
    """Body of the first ModProjectile.SetDefaults() in cs_code, or empty string."""
    code = strip_csharp_comments(cs_code)
    for class_match in re.finditer(
        r"class\s+\w+\s*:\s*(?:[\w.]+\.)?ModProjectile\b", code
    ):
        class_open = code.find("{", class_match.end())
        if class_open == -1:
            continue
        class_body = balanced_brace_block(code, class_open)
        method_match = re.search(r"override\s+void\s+SetDefaults\s*\(\s*\)", class_body)
        if not method_match:
            continue
        method_open = class_body.find("{", method_match.end())
        if method_open == -1:
            continue
        return balanced_brace_block(class_body, method_open)
    return ""
