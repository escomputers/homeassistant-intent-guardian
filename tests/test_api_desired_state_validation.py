import pytest

from addon.app.storage import upsert_entity_classification
from intentguard_core.models import (
    EntityClassification,
    EntityPermissions,
    ImpactLevel,
)
from intentguard_core.validation import ValidationErrorCode
from tests.api_test_support import api_client


@pytest.mark.anyio
async def test_validate_desired_state_policy_for_valid_low_impact_light(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "desired-state-valid.db"
    upsert_entity_classification(
        build_classification(
            entity_id="light.luci_giardino",
            impact=ImpactLevel.LOW,
            permissions=EntityPermissions(
                turn_on=True,
                turn_off=True,
                auto_modify=True,
            ),
        ),
        db_path=db_path,
    )

    async with api_client(tmp_path, monkeypatch, db_path.name) as client:
        response = await client.post(
            "/policies/desired-state/validate",
            json=build_validation_request(
                target_entity_id="light.luci_giardino",
                desired_state="on",
                notify=["person.emiliano"],
                snapshot_entities=[
                    {
                        "entity_id": "light.luci_giardino",
                        "domain": "light",
                        "friendly_name": "Luci giardino",
                        "area": "Esterno",
                        "device_class": None,
                    }
                ],
            ),
        )

    body = response.json()

    assert response.status_code == 200
    assert body["valid"] is True
    assert body["validation"]["valid"] is True
    assert body["validation"]["issues"] == []
    assert body["risk"]["auto_deploy_allowed"] is True
    assert body["deployable_in_principle"] is True


@pytest.mark.anyio
async def test_validate_desired_state_policy_returns_entity_not_found(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "desired-state-missing-entity.db"
    upsert_entity_classification(
        build_classification(
            entity_id="light.luci_giardino",
            permissions=EntityPermissions(
                turn_on=True,
                turn_off=True,
                auto_modify=True,
            ),
        ),
        db_path=db_path,
    )

    async with api_client(tmp_path, monkeypatch, db_path.name) as client:
        response = await client.post(
            "/policies/desired-state/validate",
            json=build_validation_request(
                target_entity_id="light.luci_giardino",
                desired_state="on",
                notify=["person.emiliano"],
                snapshot_entities=[
                    {
                        "entity_id": "light.kitchen",
                        "domain": "light",
                    }
                ],
            ),
        )

    issue_codes = [issue["code"] for issue in response.json()["validation"]["issues"]]

    assert response.status_code == 200
    assert ValidationErrorCode.ENTITY_NOT_FOUND.value in issue_codes


@pytest.mark.anyio
async def test_validate_desired_state_policy_returns_entity_not_classified(
    tmp_path, monkeypatch
) -> None:
    async with api_client(tmp_path, monkeypatch, "desired-state-unclassified.db") as client:
        response = await client.post(
            "/policies/desired-state/validate",
            json=build_validation_request(
                target_entity_id="light.luci_giardino",
                desired_state="on",
                notify=["person.emiliano"],
                snapshot_entities=[
                    {
                        "entity_id": "light.luci_giardino",
                        "domain": "light",
                    }
                ],
            ),
        )

    body = response.json()
    issue_codes = [issue["code"] for issue in body["validation"]["issues"]]

    assert response.status_code == 200
    assert body["valid"] is False
    assert ValidationErrorCode.ENTITY_NOT_CLASSIFIED.value in issue_codes
    assert body["risk"] is None
    assert body["deployable_in_principle"] is False


@pytest.mark.anyio
async def test_validate_desired_state_policy_returns_action_not_permitted(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "desired-state-denied.db"
    upsert_entity_classification(
        build_classification(
            entity_id="switch.pump",
            impact=ImpactLevel.MEDIUM,
            permissions=EntityPermissions(
                turn_off=True,
                auto_modify=True,
            ),
        ),
        db_path=db_path,
    )

    async with api_client(tmp_path, monkeypatch, db_path.name) as client:
        response = await client.post(
            "/policies/desired-state/validate",
            json=build_validation_request(
                target_entity_id="switch.pump",
                desired_state="on",
                notify=["person.owner"],
                snapshot_entities=[
                    {
                        "entity_id": "switch.pump",
                        "domain": "switch",
                    }
                ],
            ),
        )

    issue_codes = [issue["code"] for issue in response.json()["validation"]["issues"]]

    assert response.status_code == 200
    assert ValidationErrorCode.ACTION_NOT_PERMITTED.value in issue_codes
    assert response.json()["deployable_in_principle"] is False


@pytest.mark.anyio
async def test_validate_desired_state_policy_reports_high_impact_confirmation(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "desired-state-high-impact.db"
    upsert_entity_classification(
        build_classification(
            entity_id="switch.well_pump",
            impact=ImpactLevel.HIGH,
            permissions=EntityPermissions(
                turn_on=True,
                turn_off=True,
                auto_modify=True,
            ),
        ),
        db_path=db_path,
    )

    async with api_client(tmp_path, monkeypatch, db_path.name) as client:
        response = await client.post(
            "/policies/desired-state/validate",
            json=build_validation_request(
                target_entity_id="switch.well_pump",
                desired_state="on",
                notify=["person.owner"],
                snapshot_entities=[
                    {
                        "entity_id": "switch.well_pump",
                        "domain": "switch",
                    }
                ],
            ),
        )

    body = response.json()

    assert response.status_code == 200
    assert body["valid"] is True
    assert body["risk"]["requires_explicit_confirmation"] is True
    assert body["risk"]["auto_deploy_allowed"] is False
    assert body["deployable_in_principle"] is False


@pytest.mark.anyio
async def test_validate_desired_state_policy_blocks_unsafe_critical_entity(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "desired-state-critical.db"
    upsert_entity_classification(
        build_classification(
            entity_id="switch.main_alarm",
            impact=ImpactLevel.CRITICAL,
            category="alarm",
            permissions=EntityPermissions(
                turn_off=True,
                auto_modify=False,
            ),
        ),
        db_path=db_path,
    )

    async with api_client(tmp_path, monkeypatch, db_path.name) as client:
        response = await client.post(
            "/policies/desired-state/validate",
            json=build_validation_request(
                target_entity_id="switch.main_alarm",
                desired_state="off",
                notify=["person.security"],
                snapshot_entities=[
                    {
                        "entity_id": "switch.main_alarm",
                        "domain": "switch",
                    }
                ],
            ),
        )

    body = response.json()
    blocking_issue_codes = [
        issue["code"]
        for issue in body["validation"]["issues"]
        if issue["severity"] == "blocking"
    ]

    assert response.status_code == 200
    assert body["valid"] is False
    assert ValidationErrorCode.ACTION_NOT_PERMITTED.value in blocking_issue_codes
    assert body["risk"]["requires_explicit_confirmation"] is True
    assert body["deployable_in_principle"] is False


def build_classification(
    entity_id: str,
    permissions: EntityPermissions,
    impact: ImpactLevel = ImpactLevel.LOW,
    category: str = "light",
) -> EntityClassification:
    return EntityClassification(
        entity_id=entity_id,
        real_world_name=entity_id.replace(".", " ").replace("_", " ").title(),
        category=category,
        impact=impact,
        permissions=permissions,
    )


def build_validation_request(
    target_entity_id: str,
    desired_state: str,
    notify: list[str],
    snapshot_entities: list[dict],
) -> dict:
    return {
        "policy": {
            "policy_id": "desired-state-policy",
            "name": "Desired state policy",
            "pattern_type": "desired_state",
            "target_entity_id": target_entity_id,
            "desired_state": desired_state,
            "active_when": {
                "sun": "below_horizon",
                "before_time": "23:30",
            },
            "reconciliation": {
                "on_homeassistant_start": True,
                "interval": "10m",
            },
            "failure_handling": {
                "retries": 3,
                "retry_delay": "30s",
                "notify": notify,
            },
        },
        "ha_snapshot": {
            "entities": snapshot_entities,
        },
    }
