from intentguard_core.models import (
    ActiveWindow,
    DesiredState,
    DesiredStatePolicySpec,
    EntityCatalog,
    EntityClassification,
    EntityPermissions,
    FailureHandling,
    HomeAssistantEntityState,
    HomeAssistantSnapshot,
    ImpactLevel,
    PolicySpec,
    ReconciliationConfig,
)
from intentguard_core.risk import assess_policy_risk
from intentguard_core.validation import (
    ValidationErrorCode,
    ValidationSeverity,
    validate_policy_spec,
)


def test_valid_low_impact_light_desired_state_on() -> None:
    classification = EntityClassification(
        entity_id="light.garden_lights",
        real_world_name="Garden lights",
        category="light",
        impact=ImpactLevel.LOW,
        permissions=EntityPermissions(turn_on=True, turn_off=True, auto_modify=True),
    )
    policy = build_desired_state_policy(
        target_entity_id="light.garden_lights",
        desired_state=DesiredState.ON,
        active_when=ActiveWindow(sun="below_horizon", before_time="23:30"),
        failure_handling=FailureHandling(notify=["person.emiliano"]),
    )

    result = validate_policy_spec(
        policy,
        ha_snapshot=build_snapshot("light.garden_lights"),
        catalog=build_catalog(classification),
    )
    risk = assess_policy_risk(policy, classification)

    assert result.is_valid is True
    assert result.issues == []
    assert risk.requires_explicit_confirmation is False
    assert risk.auto_deploy_allowed is True


def test_entity_exists_but_is_not_classified() -> None:
    policy = build_desired_state_policy(target_entity_id="light.garden_lights")

    result = validate_policy_spec(
        policy,
        ha_snapshot=build_snapshot("light.garden_lights"),
        catalog=build_catalog(),
    )

    assert result.is_valid is False
    assert result.issues[0].code is ValidationErrorCode.ENTITY_NOT_CLASSIFIED
    assert result.issues[0].severity is ValidationSeverity.BLOCKING


def test_entity_not_found_in_home_assistant_snapshot() -> None:
    classification = EntityClassification(
        entity_id="light.garden_lights",
        real_world_name="Garden lights",
        category="light",
        impact=ImpactLevel.LOW,
        permissions=EntityPermissions(turn_on=True, turn_off=True, auto_modify=True),
    )
    policy = build_desired_state_policy(target_entity_id="light.garden_lights")

    result = validate_policy_spec(
        policy,
        ha_snapshot=build_snapshot("light.kitchen"),
        catalog=build_catalog(classification),
    )

    assert result.is_valid is False
    assert result.issues[0].code is ValidationErrorCode.ENTITY_NOT_FOUND


def test_turn_on_requested_but_permission_is_false() -> None:
    classification = EntityClassification(
        entity_id="switch.pump",
        real_world_name="Well pump",
        category="pump",
        impact=ImpactLevel.MEDIUM,
        permissions=EntityPermissions(turn_off=True, auto_modify=True),
    )
    policy = build_desired_state_policy(
        target_entity_id="switch.pump",
        desired_state=DesiredState.ON,
    )

    result = validate_policy_spec(
        policy,
        ha_snapshot=build_snapshot("switch.pump"),
        catalog=build_catalog(classification),
    )

    assert result.is_valid is False
    assert result.issues[0].code is ValidationErrorCode.ACTION_NOT_PERMITTED


def test_high_impact_entity_requires_explicit_confirmation() -> None:
    classification = EntityClassification(
        entity_id="switch.well_pump",
        real_world_name="Well pump",
        category="pump",
        impact=ImpactLevel.HIGH,
        permissions=EntityPermissions(turn_on=True, turn_off=True, auto_modify=True),
    )
    policy = build_desired_state_policy(
        target_entity_id="switch.well_pump",
        desired_state=DesiredState.ON,
        failure_handling=FailureHandling(notify=["person.owner"]),
    )

    risk = assess_policy_risk(policy, classification)

    assert risk.impact is ImpactLevel.HIGH
    assert risk.requires_explicit_confirmation is True
    assert any("explicit confirmation" in reason for reason in risk.reasons)


def test_critical_entity_blocks_auto_deploy() -> None:
    classification = EntityClassification(
        entity_id="switch.main_alarm",
        real_world_name="Main alarm",
        category="alarm",
        impact=ImpactLevel.CRITICAL,
        permissions=EntityPermissions(turn_off=True, auto_modify=True),
    )
    policy = build_desired_state_policy(
        target_entity_id="switch.main_alarm",
        desired_state=DesiredState.OFF,
        failure_handling=FailureHandling(notify=["person.security"]),
    )

    risk = assess_policy_risk(policy, classification)

    assert risk.requires_explicit_confirmation is True
    assert risk.auto_deploy_allowed is False


def test_invalid_pattern_is_rejected() -> None:
    policy = PolicySpec(
        policy_id="freezer_offline",
        name="Freezer offline",
        pattern_type="offline_monitor",
        target_entity_id="sensor.freezer",
    )

    result = validate_policy_spec(
        policy,
        ha_snapshot=build_snapshot("sensor.freezer"),
        catalog=build_catalog(),
    )

    assert result.is_valid is False
    assert result.issues[0].code is ValidationErrorCode.UNSUPPORTED_PATTERN
    assert result.issues[0].severity is ValidationSeverity.BLOCKING


def test_high_impact_missing_failure_notification_emits_warning() -> None:
    classification = EntityClassification(
        entity_id="switch.well_pump",
        real_world_name="Well pump",
        category="pump",
        impact=ImpactLevel.HIGH,
        permissions=EntityPermissions(turn_off=True, auto_modify=True),
    )
    policy = build_desired_state_policy(
        target_entity_id="switch.well_pump",
        desired_state=DesiredState.OFF,
        failure_handling=FailureHandling(notify=[]),
    )

    result = validate_policy_spec(
        policy,
        ha_snapshot=build_snapshot("switch.well_pump"),
        catalog=build_catalog(classification),
    )

    assert result.is_valid is True
    assert result.issues[0].code is ValidationErrorCode.MISSING_FAILURE_NOTIFICATION
    assert result.issues[0].severity is ValidationSeverity.WARNING


def test_critical_entity_without_auto_modify_permission_is_blocked() -> None:
    classification = EntityClassification(
        entity_id="switch.main_alarm",
        real_world_name="Main alarm",
        category="alarm",
        impact=ImpactLevel.CRITICAL,
        permissions=EntityPermissions(turn_off=True, auto_modify=False),
    )
    policy = build_desired_state_policy(
        target_entity_id="switch.main_alarm",
        desired_state=DesiredState.OFF,
        failure_handling=FailureHandling(notify=["person.security"]),
    )

    result = validate_policy_spec(
        policy,
        ha_snapshot=build_snapshot("switch.main_alarm"),
        catalog=build_catalog(classification),
    )

    assert result.is_valid is False
    assert result.issues[0].code is ValidationErrorCode.ACTION_NOT_PERMITTED


def test_invalid_reconciliation_interval_is_blocking() -> None:
    classification = EntityClassification(
        entity_id="light.garden_lights",
        real_world_name="Garden lights",
        category="light",
        impact=ImpactLevel.LOW,
        permissions=EntityPermissions(turn_on=True, turn_off=True, auto_modify=True),
    )
    policy = build_desired_state_policy(
        target_entity_id="light.garden_lights",
        reconciliation=ReconciliationConfig(interval="soon"),
        failure_handling=FailureHandling(notify=["person.emiliano"]),
    )

    result = validate_policy_spec(
        policy,
        ha_snapshot=build_snapshot("light.garden_lights"),
        catalog=build_catalog(classification),
    )

    assert result.is_valid is False
    assert result.issues[0].code is ValidationErrorCode.INVALID_RECONCILIATION_INTERVAL
    assert result.issues[0].severity is ValidationSeverity.BLOCKING


def build_desired_state_policy(**overrides) -> DesiredStatePolicySpec:
    payload = {
        "policy_id": "garden_lights_after_sunset",
        "name": "Garden lights after sunset",
        "target_entity_id": "light.garden_lights",
        "desired_state": DesiredState.ON,
        "reconciliation": ReconciliationConfig(),
        "failure_handling": FailureHandling(),
    }
    payload.update(overrides)
    return DesiredStatePolicySpec(**payload)


def build_snapshot(*entity_ids: str) -> HomeAssistantSnapshot:
    return HomeAssistantSnapshot(
        entities=[
            HomeAssistantEntityState(entity_id=entity_id, state="unknown")
            for entity_id in entity_ids
        ]
    )


def build_catalog(*classifications: EntityClassification) -> EntityCatalog:
    return EntityCatalog(classifications=list(classifications))
