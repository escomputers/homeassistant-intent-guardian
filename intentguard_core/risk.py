"""Pure risk helpers for the desired_state vertical slice."""

from pydantic import BaseModel, ConfigDict, Field

from intentguard_core.models import (
    DesiredState,
    DesiredStatePolicySpec,
    EntityClassification,
    ImpactLevel,
)


class RiskAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    impact: ImpactLevel
    requires_explicit_confirmation: bool
    auto_deploy_allowed: bool
    reasons: list[str] = Field(default_factory=list)


def assess_entity_risk(classification: EntityClassification) -> RiskAssessment:
    """Assess baseline risk from the entity classification alone."""
    return RiskAssessment(
        impact=classification.impact,
        requires_explicit_confirmation=classification.impact
        in {ImpactLevel.HIGH, ImpactLevel.CRITICAL},
        auto_deploy_allowed=classification.impact
        not in {ImpactLevel.HIGH, ImpactLevel.CRITICAL},
        reasons=[
            f"Entity '{classification.real_world_name}' is classified as "
            f"{classification.impact.value} impact."
        ],
    )


def assess_policy_risk(
    spec: DesiredStatePolicySpec, classification: EntityClassification
) -> RiskAssessment:
    """Assess risk for a desired_state policy without runtime dependencies."""
    reasons = [
        f"Entity '{classification.real_world_name}' is classified as "
        f"{classification.impact.value} impact.",
        f"Requested automatic state change is '{spec.desired_state.value}'.",
    ]
    auto_deploy_allowed = classification.impact not in {
        ImpactLevel.HIGH,
        ImpactLevel.CRITICAL,
    }

    if spec.desired_state is DesiredState.ON and not classification.permissions.turn_on:
        auto_deploy_allowed = False
        reasons.append("Entity permissions do not allow automatic turn on.")

    if spec.desired_state is DesiredState.OFF and not classification.permissions.turn_off:
        auto_deploy_allowed = False
        reasons.append("Entity permissions do not allow automatic turn off.")

    if classification.impact in {ImpactLevel.HIGH, ImpactLevel.CRITICAL}:
        reasons.append("High-impact entities require explicit confirmation.")
        reasons.append("High-impact entities are not eligible for auto-deploy.")

    if (
        classification.impact is ImpactLevel.CRITICAL
        and not classification.permissions.auto_modify
    ):
        auto_deploy_allowed = False
        reasons.append(
            "Critical entities require explicit auto_modify permission "
            "before automatic changes are allowed."
        )

    return RiskAssessment(
        impact=classification.impact,
        requires_explicit_confirmation=classification.impact
        in {ImpactLevel.HIGH, ImpactLevel.CRITICAL},
        auto_deploy_allowed=auto_deploy_allowed,
        reasons=reasons,
    )
