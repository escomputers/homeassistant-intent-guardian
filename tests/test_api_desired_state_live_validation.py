import pytest

from addon.app import ha_client
from addon.app.storage import upsert_entity_classification
from intentguard_core.models import (
    EntityClassification,
    EntityPermissions,
    HomeAssistantEntityState,
    HomeAssistantSnapshot,
    ImpactLevel,
)
from intentguard_core.validation import ValidationErrorCode
from tests.api_test_support import api_client


@pytest.mark.anyio
async def test_validate_live_desired_state_policy_for_valid_low_impact_light(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "desired-state-live-valid.db"
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

    async def fake_snapshot() -> HomeAssistantSnapshot:
        return build_snapshot(
            HomeAssistantEntityState(
                entity_id="light.luci_giardino",
                domain="light",
                friendly_name="Luci giardino",
                area="Esterno",
            )
        )

    monkeypatch.setattr(ha_client, "fetch_homeassistant_snapshot", fake_snapshot)

    async with api_client(tmp_path, monkeypatch, db_path.name) as client:
        response = await client.post(
            "/policies/desired-state/validate-live",
            json=build_policy(
                target_entity_id="light.luci_giardino",
                desired_state="on",
                notify=["person.emiliano"],
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
async def test_validate_live_desired_state_policy_returns_controlled_ha_error(
    tmp_path, monkeypatch
) -> None:
    async def failing_snapshot() -> HomeAssistantSnapshot:
        raise ha_client.HomeAssistantUnavailableError(
            "Home Assistant state snapshot is unavailable."
        )

    monkeypatch.setattr(ha_client, "fetch_homeassistant_snapshot", failing_snapshot)

    async with api_client(tmp_path, monkeypatch, "desired-state-live-error.db") as client:
        response = await client.post(
            "/policies/desired-state/validate-live",
            json=build_policy(
                target_entity_id="light.luci_giardino",
                desired_state="on",
                notify=["person.emiliano"],
            ),
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Home Assistant state snapshot is unavailable."
    }


@pytest.mark.anyio
async def test_validate_live_desired_state_policy_returns_entity_not_classified(
    tmp_path, monkeypatch
) -> None:
    async def fake_snapshot() -> HomeAssistantSnapshot:
        return build_snapshot(
            HomeAssistantEntityState(
                entity_id="light.luci_giardino",
                domain="light",
            )
        )

    monkeypatch.setattr(ha_client, "fetch_homeassistant_snapshot", fake_snapshot)

    async with api_client(tmp_path, monkeypatch, "desired-state-live-unclassified.db") as client:
        response = await client.post(
            "/policies/desired-state/validate-live",
            json=build_policy(
                target_entity_id="light.luci_giardino",
                desired_state="on",
                notify=["person.emiliano"],
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
async def test_validate_live_desired_state_policy_returns_entity_not_found(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "desired-state-live-missing-entity.db"
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

    async def fake_snapshot() -> HomeAssistantSnapshot:
        return build_snapshot(
            HomeAssistantEntityState(
                entity_id="light.cucina",
                domain="light",
            )
        )

    monkeypatch.setattr(ha_client, "fetch_homeassistant_snapshot", fake_snapshot)

    async with api_client(tmp_path, monkeypatch, db_path.name) as client:
        response = await client.post(
            "/policies/desired-state/validate-live",
            json=build_policy(
                target_entity_id="light.luci_giardino",
                desired_state="on",
                notify=["person.emiliano"],
            ),
        )

    issue_codes = [issue["code"] for issue in response.json()["validation"]["issues"]]

    assert response.status_code == 200
    assert ValidationErrorCode.ENTITY_NOT_FOUND.value in issue_codes


@pytest.mark.anyio
async def test_validate_live_desired_state_policy_reports_high_impact_confirmation(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "desired-state-live-high-impact.db"
    upsert_entity_classification(
        build_classification(
            entity_id="switch.well_pump",
            impact=ImpactLevel.HIGH,
            category="pump",
            permissions=EntityPermissions(
                turn_on=True,
                turn_off=True,
                auto_modify=True,
            ),
        ),
        db_path=db_path,
    )

    async def fake_snapshot() -> HomeAssistantSnapshot:
        return build_snapshot(
            HomeAssistantEntityState(
                entity_id="switch.well_pump",
                domain="switch",
                friendly_name="Pompa pozzo",
            )
        )

    monkeypatch.setattr(ha_client, "fetch_homeassistant_snapshot", fake_snapshot)

    async with api_client(tmp_path, monkeypatch, db_path.name) as client:
        response = await client.post(
            "/policies/desired-state/validate-live",
            json=build_policy(
                target_entity_id="switch.well_pump",
                desired_state="on",
                notify=["person.owner"],
            ),
        )

    body = response.json()

    assert response.status_code == 200
    assert body["valid"] is True
    assert body["risk"]["requires_explicit_confirmation"] is True
    assert body["risk"]["auto_deploy_allowed"] is False
    assert body["deployable_in_principle"] is False


@pytest.mark.anyio
async def test_non_live_desired_state_validation_endpoint_still_works_without_live_ha(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "desired-state-non-live-still-works.db"
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

    async def failing_snapshot() -> HomeAssistantSnapshot:
        raise AssertionError("The non-live endpoint should not fetch Home Assistant.")

    monkeypatch.setattr(ha_client, "fetch_homeassistant_snapshot", failing_snapshot)

    async with api_client(tmp_path, monkeypatch, db_path.name) as client:
        response = await client.post(
            "/policies/desired-state/validate",
            json=build_non_live_validation_request(
                target_entity_id="light.luci_giardino",
                desired_state="on",
                notify=["person.emiliano"],
                snapshot_entities=[
                    {
                        "entity_id": "light.luci_giardino",
                        "domain": "light",
                        "friendly_name": "Luci giardino",
                    }
                ],
            ),
        )

    assert response.status_code == 200
    assert response.json()["valid"] is True


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


def build_snapshot(*entities: HomeAssistantEntityState) -> HomeAssistantSnapshot:
    return HomeAssistantSnapshot(entities=list(entities))


def build_policy(
    target_entity_id: str,
    desired_state: str,
    notify: list[str],
) -> dict:
    return {
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
    }


def build_non_live_validation_request(
    target_entity_id: str,
    desired_state: str,
    notify: list[str],
    snapshot_entities: list[dict],
) -> dict:
    return {
        "policy": build_policy(
            target_entity_id=target_entity_id,
            desired_state=desired_state,
            notify=notify,
        ),
        "ha_snapshot": {
            "entities": snapshot_entities,
        },
    }
