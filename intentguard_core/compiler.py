"""Placeholder compile-time structures for the walking skeleton.

This module intentionally does not generate Home Assistant YAML yet.
"""

from pydantic import BaseModel, ConfigDict

from intentguard_core.models import PolicySpec


class CompilationPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: str
    name: str
    pattern_type: str
    target_entity_id: str


def build_compilation_preview(spec: PolicySpec) -> CompilationPreview:
    """Return a pure preview object until real YAML compilation exists."""
    return CompilationPreview(
        policy_id=spec.policy_id,
        name=spec.name,
        pattern_type=spec.pattern_type,
        target_entity_id=spec.target_entity_id,
    )
