from pydantic import BaseModel, ConfigDict, Field

from intentguard_core.models import (
    DesiredStatePolicySpec,
    HomeAssistantEntityState,
    HomeAssistantSnapshot,
)
from intentguard_core.risk import RiskAssessment
from intentguard_core.validation import ValidationIssue, ValidationResult


class HomeAssistantSnapshotEntityInput(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    entity_id: str = Field(min_length=1)
    state: str | None = None
    domain: str | None = None
    friendly_name: str | None = None
    area: str | None = None
    device_class: str | None = None

    def to_core_model(self) -> HomeAssistantEntityState:
        return HomeAssistantEntityState(
            entity_id=self.entity_id,
            state=self.state,
            domain=self.domain,
            friendly_name=self.friendly_name,
            area=self.area,
            device_class=self.device_class,
        )


class HomeAssistantSnapshotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entities: list[HomeAssistantSnapshotEntityInput] = Field(default_factory=list)

    def to_core_model(self) -> HomeAssistantSnapshot:
        return HomeAssistantSnapshot(
            entities=[entity.to_core_model() for entity in self.entities],
        )


class DesiredStateValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy: DesiredStatePolicySpec
    ha_snapshot: HomeAssistantSnapshotInput


class ValidationResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)

    @classmethod
    def from_core_result(cls, result: ValidationResult) -> "ValidationResultResponse":
        return cls(
            valid=result.is_valid,
            issues=result.issues,
        )


class DesiredStateValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    validation: ValidationResultResponse
    risk: RiskAssessment | None = None
    deployable_in_principle: bool
