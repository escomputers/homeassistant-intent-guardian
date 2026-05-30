import pytest
from pydantic import ValidationError

from intentguard_core.models import (
    EntityClassification,
    EntityPermissions,
    ImpactLevel,
)


def test_entity_classification_can_be_created() -> None:
    classification = EntityClassification(
        entity_id="light.garden_lights",
        real_world_name="Garden lights",
        category="light",
        impact=ImpactLevel.LOW,
        permissions=EntityPermissions(turn_on=True, turn_off=True, auto_modify=True),
    )

    assert classification.entity_id == "light.garden_lights"
    assert classification.impact is ImpactLevel.LOW
    assert classification.permissions.turn_on is True
    assert classification.permissions.auto_modify is True


def test_entity_permissions_have_safe_defaults() -> None:
    permissions = EntityPermissions()

    assert permissions.read is True
    assert permissions.notify is True
    assert permissions.turn_on is False
    assert permissions.turn_off is False
    assert permissions.auto_modify is False


def test_invalid_impact_values_are_rejected() -> None:
    with pytest.raises(ValidationError):
        EntityClassification(
            entity_id="switch.critical_pump",
            real_world_name="Critical pump",
            category="pump",
            impact="dangerous",
        )
