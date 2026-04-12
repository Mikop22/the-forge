"""Gatekeeper result models."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class RoslynError(BaseModel):
    """Compiler error parsed from build output."""

    code: str = Field(description="Compiler error code, e.g. 'CS0103'.")
    message: str = Field(description="Full error message text.")
    line: Optional[int] = None
    file: Optional[str] = None


class GatekeeperResult(BaseModel):
    """Result of ``Integrator.build_and_verify()``."""

    status: Literal["success", "error"]
    item_name: str
    attempts: int
    errors: Optional[list[RoslynError]] = None
    error_message: Optional[str] = None
