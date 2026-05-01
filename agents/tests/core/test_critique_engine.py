"""Smoke tests for core.critique_engine — verbatim moved from forge_master/critique.py."""
from __future__ import annotations

from core.critique_engine import CritiqueContext, critique_generated_code


def test_critique_context_constructs() -> None:
    ctx = CritiqueContext(manifest={"item_name": "Foo"})
    assert ctx.manifest["item_name"] == "Foo"


def test_critique_generated_code_returns_result() -> None:
    ctx = CritiqueContext(manifest={"item_name": "Foo"})
    result = critique_generated_code("// empty", ctx)
    # Function returns a CritiqueResult with an iterable issues list; verify it doesn't raise.
    assert hasattr(result, "issues")
    list(result.issues)
