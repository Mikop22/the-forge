"""Shared warning filters for LangChain + Pydantic structured-output quirks."""

from __future__ import annotations

import warnings


def suppress_langchain_pydantic_warnings() -> None:
    """Silence known-safe Pydantic serializer noise from LangChain structured output.

    Some LangChain versions call ``with_structured_output(..., strict=True)``, which
    triggers intermediate Pydantic serialization warnings. Main codegen paths avoid
    ``strict`` where the installed LangChain build does not support it; other call
    sites (e.g. ``forge_master/reviewer.py``) may still pass ``strict=True`` when
    supported. This filter suppresses the legacy ``UserWarning`` from pydantic
    during structured parsing wherever it appears.
    """
    warnings.filterwarnings(
        "ignore",
        message="Pydantic serializer warnings",
        category=UserWarning,
        module="pydantic",
    )
