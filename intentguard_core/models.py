"""Pure core models for the first IntentGuard vertical slice."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ImpactLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PatternType(StrEnum):
    DESIRED_STATE = "desired_state"


class DesiredState(StrEnum):
    ON = "on"
    OFF = "off"


class MatchConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EntityPermissions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    read: bool = True
    notify: bool = True
    turn_on: bool = False
    turn_off: bool = False
    auto_modify: bool = False


class EntityClassification(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    entity_id: str = Field(min_length=1)
    real_world_name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    impact: ImpactLevel
    permissions: EntityPermissions = Field(default_factory=EntityPermissions)


class PolicySpec(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    policy_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    pattern_type: str = Field(min_length=1)
    target_entity_id: str = Field(min_length=1)


class ActiveWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    sun: str | None = None
    before_time: str | None = None


class ReconciliationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    on_homeassistant_start: bool = True
    interval: str = "10m"


class FailureHandling(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    retries: int = Field(default=3, ge=0)
    retry_delay: str = Field(default="30s", min_length=1)
    notify: list[str] = Field(default_factory=list)


class DesiredStatePolicySpec(PolicySpec):
    pattern_type: Literal["desired_state"] = PatternType.DESIRED_STATE.value
    desired_state: DesiredState
    active_when: ActiveWindow | None = None
    reconciliation: ReconciliationConfig = Field(default_factory=ReconciliationConfig)
    failure_handling: FailureHandling = Field(default_factory=FailureHandling)


class HomeAssistantEntityState(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    entity_id: str = Field(min_length=1)
    state: str | None = None
    domain: str | None = None
    friendly_name: str | None = None
    area: str | None = None
    device_class: str | None = None


class HomeAssistantSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entities: list[HomeAssistantEntityState] = Field(default_factory=list)

    def has_entity(self, entity_id: str) -> bool:
        return any(entity.entity_id == entity_id for entity in self.entities)


class EntityCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classifications: list[EntityClassification] = Field(default_factory=list)

    def get_classification(self, entity_id: str) -> EntityClassification | None:
        for classification in self.classifications:
            if classification.entity_id == entity_id:
                return classification
        return None


class EntityMatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: str = Field(min_length=1)
    requested_domain: str | None = None
    requested_category: str | None = None
    limit: int = Field(default=10, ge=1)


class EntityCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    domain: str | None = None
    friendly_name: str | None = None
    area: str | None = None
    device_class: str | None = None
    score: float = Field(ge=0.0, le=1.0)
    confidence: MatchConfidence
    already_classified: bool
    existing_classification: EntityClassification | None = None
    reasons: list[str] = Field(default_factory=list)
