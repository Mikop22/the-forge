"""Capability declarations for the instant runtime."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LoopFamilyLiteral = Literal["mark_cashout"]


class RuntimeCapabilityMatrix(BaseModel):
    """Small, explicit list of loop families the runtime can express today."""

    model_config = ConfigDict(frozen=True)

    supported_loop_families: dict[str, dict[str, tuple[LoopFamilyLiteral, ...]]] = (
        Field(default_factory=dict)
    )

    @classmethod
    def default(cls) -> "RuntimeCapabilityMatrix":
        return cls(
            supported_loop_families={
                "Weapon": {
                    "Staff": ("mark_cashout",),
                },
            }
        )

    def supports(self, *, content_type: str, sub_type: str, loop_family: str) -> bool:
        return loop_family in self.supported_loop_families.get(content_type, {}).get(
            sub_type, ()
        )
