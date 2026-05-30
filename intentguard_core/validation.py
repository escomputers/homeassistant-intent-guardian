"""Pure validation helpers for the desired_state vertical slice."""

import re
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from intentguard_core.models import (
    DesiredState,
    DesiredStatePolicySpec,
    EntityCatalog,
    HomeAssistantSnapshot,
    ImpactLevel,
    PatternType,
    PolicySpec,
)

SUPPORTED_PATTERN_TYPES: Final[frozenset[str]] = frozenset(
    {PatternType.DESIRED_STATE.value}
)

INTERVAL_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[1-9]\d*[smhd]$")


class ValidationSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class ValidationErrorCode(StrEnum):
    ENTITY_NOT_FOUND = "ENTITY_NOT_FOUND"
    ENTITY_NOT_CLASSIFIED = "ENTITY_NOT_CLASSIFIED"
    ACTION_NOT_PERMITTED = "ACTION_NOT_PERMITTED"
    UNSUPPORTED_PATTERN = "UNSUPPORTED_PATTERN"
    MISSING_FAILURE_NOTIFICATION = "MISSING_FAILURE_NOTIFICATION"
    INVALID_RECONCILIATION_INTERVAL = "INVALID_RECONCILIATION_INTERVAL"


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    severity: ValidationSeverity
    code: ValidationErrorCode
    message: str = Field(min_length=1)


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)


def validate_policy_spec(
    spec: PolicySpec,
    ha_snapshot: HomeAssistantSnapshot,
    catalog: EntityCatalog,
) -> ValidationResult:
    """Validate a policy spec using only in-memory inputs."""
    if spec.pattern_type not in SUPPORTED_PATTERN_TYPES:
        return _build_result(
            [
                ValidationIssue(
                    severity=ValidationSeverity.BLOCKING,
                    code=ValidationErrorCode.UNSUPPORTED_PATTERN,
                    message=(
                        f"Pattern type '{spec.pattern_type}' is not supported "
                        "by the current core vertical slice."
                    ),
                )
            ]
        )

    if not isinstance(spec, DesiredStatePolicySpec):
        return _build_result(
            [
                ValidationIssue(
                    severity=ValidationSeverity.BLOCKING,
                    code=ValidationErrorCode.UNSUPPORTED_PATTERN,
                    message=(
                        "The desired_state validator requires a typed "
                        "DesiredStatePolicySpec."
                    ),
                )
            ]
        )

    issues: list[ValidationIssue] = []

    if not _is_valid_interval(spec.reconciliation.interval):
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.BLOCKING,
                code=ValidationErrorCode.INVALID_RECONCILIATION_INTERVAL,
                message=(
                    "Reconciliation interval must be a positive duration such "
                    "as '10m' or '30s'."
                ),
            )
        )

    if not ha_snapshot.has_entity(spec.target_entity_id):
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.BLOCKING,
                code=ValidationErrorCode.ENTITY_NOT_FOUND,
                message=(
                    f"Target entity '{spec.target_entity_id}' was not found "
                    "in the supplied Home Assistant snapshot."
                ),
            )
        )

    classification = catalog.get_classification(spec.target_entity_id)
    if classification is None:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.BLOCKING,
                code=ValidationErrorCode.ENTITY_NOT_CLASSIFIED,
                message=(
                    f"Target entity '{spec.target_entity_id}' is not present "
                    "in the supplied semantic catalog."
                ),
            )
        )
        return _build_result(issues)

    if not _is_action_permitted(spec.desired_state, classification.permissions):
        action_name = "turn on" if spec.desired_state is DesiredState.ON else "turn off"
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.BLOCKING,
                code=ValidationErrorCode.ACTION_NOT_PERMITTED,
                message=(
                    f"Permissions for '{spec.target_entity_id}' do not allow "
                    f"automatic {action_name}."
                ),
            )
        )

    if (
        classification.impact is ImpactLevel.CRITICAL
        and not classification.permissions.auto_modify
    ):
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.BLOCKING,
                code=ValidationErrorCode.ACTION_NOT_PERMITTED,
                message=(
                    f"Critical entity '{spec.target_entity_id}' cannot be "
                    "modified automatically without explicit auto_modify "
                    "permission."
                ),
            )
        )

    if not spec.failure_handling.notify and classification.impact in {
        ImpactLevel.HIGH,
        ImpactLevel.CRITICAL,
    }:
        severity = (
            ValidationSeverity.WARNING
            if classification.impact is ImpactLevel.HIGH
            else ValidationSeverity.BLOCKING
        )
        issues.append(
            ValidationIssue(
                severity=severity,
                code=ValidationErrorCode.MISSING_FAILURE_NOTIFICATION,
                message=(
                    f"High-impact policy '{spec.policy_id}' should define at "
                    "least one failure notification target."
                ),
            )
        )

    return _build_result(issues)


def _is_valid_interval(value: str) -> bool:
    return bool(INTERVAL_PATTERN.fullmatch(value))


def _is_action_permitted(desired_state: DesiredState, permissions) -> bool:
    if desired_state is DesiredState.ON:
        return permissions.turn_on
    return permissions.turn_off


def _build_result(issues: list[ValidationIssue]) -> ValidationResult:
    has_blocking_issue = any(
        issue.severity is ValidationSeverity.BLOCKING for issue in issues
    )
    return ValidationResult(is_valid=not has_blocking_issue, issues=issues)
