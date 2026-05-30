"""Pure core models and helpers for IntentGuard."""

from intentguard_core.compiler import CompilationPreview, build_compilation_preview
from intentguard_core.matching import match_entity_candidates
from intentguard_core.models import (
    ActiveWindow,
    DesiredState,
    DesiredStatePolicySpec,
    EntityCandidate,
    EntityCatalog,
    EntityClassification,
    EntityMatchRequest,
    EntityPermissions,
    FailureHandling,
    HomeAssistantEntityState,
    HomeAssistantSnapshot,
    ImpactLevel,
    MatchConfidence,
    PatternType,
    PolicySpec,
    ReconciliationConfig,
)
from intentguard_core.risk import (
    RiskAssessment,
    assess_entity_risk,
    assess_policy_risk,
)
from intentguard_core.validation import (
    SUPPORTED_PATTERN_TYPES,
    ValidationErrorCode,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
    validate_policy_spec,
)

__all__ = [
    "ActiveWindow",
    "CompilationPreview",
    "DesiredState",
    "DesiredStatePolicySpec",
    "EntityCandidate",
    "EntityCatalog",
    "EntityClassification",
    "EntityMatchRequest",
    "EntityPermissions",
    "FailureHandling",
    "HomeAssistantEntityState",
    "HomeAssistantSnapshot",
    "ImpactLevel",
    "MatchConfidence",
    "PatternType",
    "PolicySpec",
    "ReconciliationConfig",
    "RiskAssessment",
    "SUPPORTED_PATTERN_TYPES",
    "ValidationErrorCode",
    "ValidationIssue",
    "ValidationResult",
    "ValidationSeverity",
    "assess_entity_risk",
    "assess_policy_risk",
    "build_compilation_preview",
    "match_entity_candidates",
    "validate_policy_spec",
]
