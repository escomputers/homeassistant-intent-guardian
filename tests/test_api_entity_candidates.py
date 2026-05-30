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
from tests.api_test_support import api_client


@pytest.mark.anyio
async def test_entity_candidates_endpoint_returns_ranked_candidates(
    tmp_path, monkeypatch
) -> None:
    async def fake_snapshot() -> HomeAssistantSnapshot:
        return HomeAssistantSnapshot(
            entities=[
                HomeAssistantEntityState(
                    entity_id="light.luci_giardino",
                    state="off",
                    domain="light",
                    friendly_name="Luci giardino",
                    area="Esterno",
                    device_class=None,
                ),
                HomeAssistantEntityState(
                    entity_id="switch.shelly_garden_01",
                    state="on",
                    domain="switch",
                    friendly_name="Shelly giardino",
                    area="Esterno",
                    device_class=None,
                ),
            ]
        )

    monkeypatch.setattr(ha_client, "fetch_homeassistant_snapshot", fake_snapshot)

    async with api_client(tmp_path, monkeypatch, "entity-candidates.db") as client:
        response = await client.get(
            "/entities/candidates",
            params={"q": "Luci giardino"},
        )

    body = response.json()

    assert response.status_code == 200
    assert len(body) == 2
    assert body[0]["entity_id"] == "light.luci_giardino"
    assert body[0]["friendly_name"] == "Luci giardino"
    assert body[0]["area"] == "Esterno"
    assert body[0]["confidence"] == "high"
    assert body[0]["score"] >= body[1]["score"]


@pytest.mark.anyio
async def test_entity_candidates_endpoint_applies_domain_as_hard_filter(
    tmp_path, monkeypatch
) -> None:
    async def fake_snapshot() -> HomeAssistantSnapshot:
        return HomeAssistantSnapshot(
            entities=[
                HomeAssistantEntityState(
                    entity_id="automation.luci_giardino_on_20_30_everyday",
                    state="on",
                    domain="automation",
                    friendly_name="Luci giardino",
                    area="Esterno",
                    device_class=None,
                ),
                HomeAssistantEntityState(
                    entity_id="light.tapo_l530_smart_bulb",
                    state="off",
                    domain="light",
                    friendly_name="Tapo L530 smart bulb",
                    device_class=None,
                ),
            ]
        )

    monkeypatch.setattr(ha_client, "fetch_homeassistant_snapshot", fake_snapshot)

    async with api_client(tmp_path, monkeypatch, "entity-candidates-domain-filter.db") as client:
        response = await client.get(
            "/entities/candidates",
            params={"q": "luci giardino", "domain": "light"},
        )

    body = response.json()

    assert response.status_code == 200
    assert [candidate["entity_id"] for candidate in body] == [
        "light.tapo_l530_smart_bulb"
    ]
    assert body[0]["domain"] == "light"
    assert body[0]["confidence"] == "low"


@pytest.mark.anyio
async def test_entity_candidates_endpoint_uses_registry_area_to_improve_matching(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("INTENTGUARD_HA_TOKEN", "test-token")

    async def fake_states(**_kwargs) -> list[dict]:
        return [
            {
                "entity_id": "automation.luci_giardino_on_20_30_everyday",
                "state": "on",
                "attributes": {
                    "friendly_name": "Luci giardino",
                    "device_class": None,
                },
            },
            {
                "entity_id": "light.tapo_l530_smart_bulb",
                "state": "off",
                "attributes": {
                    "friendly_name": "Tapo L530 smart bulb",
                    "device_class": None,
                },
            },
            {
                "entity_id": "light.tapo_l530_smart_bulb_2",
                "state": "off",
                "attributes": {
                    "friendly_name": "Tapo L530 smart bulb",
                    "device_class": None,
                },
            },
        ]

    async def fake_registry_data(**_kwargs) -> ha_client.HomeAssistantRegistryData:
        return ha_client.HomeAssistantRegistryData(
            areas=[{"area_id": "garden", "name": "Giardino"}],
            devices=[{"id": "device-1", "area_id": "garden"}],
            entities=[
                {
                    "entity_id": "light.tapo_l530_smart_bulb",
                    "device_id": "device-1",
                },
                {
                    "entity_id": "light.tapo_l530_smart_bulb_2",
                },
            ],
        )

    monkeypatch.setattr(ha_client, "fetch_homeassistant_states", fake_states)
    monkeypatch.setattr(ha_client, "fetch_homeassistant_registry_data", fake_registry_data)

    async with api_client(tmp_path, monkeypatch, "entity-candidates-area.db") as client:
        response = await client.get(
            "/entities/candidates",
            params={"q": "luci giardino", "domain": "light"},
        )

    body = response.json()

    assert response.status_code == 200
    assert [candidate["entity_id"] for candidate in body] == [
        "light.tapo_l530_smart_bulb",
        "light.tapo_l530_smart_bulb_2",
    ]
    assert body[0]["area"] == "Giardino"
    assert body[0]["confidence"] == "low"
    assert body[0]["score"] > body[1]["score"]
    assert "Query token matches area." in body[0]["reasons"]
    assert all(candidate["domain"] == "light" for candidate in body)


@pytest.mark.anyio
async def test_entity_candidates_endpoint_handles_missing_areas_without_error(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("INTENTGUARD_HA_TOKEN", "test-token")

    async def fake_states(**_kwargs) -> list[dict]:
        return [
            {
                "entity_id": "automation.luci_giardino_on_20_30_everyday",
                "state": "on",
                "attributes": {
                    "friendly_name": "Luci giardino",
                    "device_class": None,
                },
            },
            {
                "entity_id": "light.tapo_l530_smart_bulb",
                "state": "off",
                "attributes": {
                    "friendly_name": "Tapo L530 smart bulb",
                    "device_class": None,
                },
            },
        ]

    async def fake_registry_data(**_kwargs) -> ha_client.HomeAssistantRegistryData:
        return ha_client.HomeAssistantRegistryData(
            areas=[],
            devices=[{"id": "device-1"}],
            entities=[
                {
                    "entity_id": "light.tapo_l530_smart_bulb",
                    "device_id": "device-1",
                }
            ],
        )

    monkeypatch.setattr(ha_client, "fetch_homeassistant_states", fake_states)
    monkeypatch.setattr(ha_client, "fetch_homeassistant_registry_data", fake_registry_data)

    async with api_client(tmp_path, monkeypatch, "entity-candidates-no-areas.db") as client:
        response = await client.get(
            "/entities/candidates",
            params={"q": "luci giardino", "domain": "light"},
        )

    body = response.json()

    assert response.status_code == 200
    assert [candidate["entity_id"] for candidate in body] == [
        "light.tapo_l530_smart_bulb"
    ]
    assert body[0]["area"] is None
    assert body[0]["confidence"] == "low"


@pytest.mark.anyio
async def test_entity_candidates_endpoint_includes_existing_classification(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "entity-candidates-classified.db"
    upsert_entity_classification(
        EntityClassification(
            entity_id="switch.pompa_pozzo",
            real_world_name="Pompa pozzo",
            category="pump",
            impact=ImpactLevel.HIGH,
            permissions=EntityPermissions(
                turn_off=True,
                auto_modify=False,
            ),
        ),
        db_path=db_path,
    )

    async def fake_snapshot() -> HomeAssistantSnapshot:
        return HomeAssistantSnapshot(
            entities=[
                HomeAssistantEntityState(
                    entity_id="switch.pompa_pozzo",
                    state="on",
                    domain="switch",
                    friendly_name="Shelly pozzo",
                    area="Giardino",
                    device_class=None,
                )
            ]
        )

    monkeypatch.setattr(ha_client, "fetch_homeassistant_snapshot", fake_snapshot)

    async with api_client(tmp_path, monkeypatch, db_path.name) as client:
        response = await client.get(
            "/entities/candidates",
            params={"q": "pozzo", "category": "pump"},
        )

    body = response.json()

    assert response.status_code == 200
    assert body[0]["already_classified"] is True
    assert body[0]["existing_classification"] == {
        "entity_id": "switch.pompa_pozzo",
        "real_world_name": "Pompa pozzo",
        "category": "pump",
        "impact": "high",
        "permissions": {
            "read": True,
            "notify": True,
            "turn_on": False,
            "turn_off": True,
            "auto_modify": False,
        },
    }


@pytest.mark.anyio
async def test_entity_candidates_endpoint_returns_controlled_unavailable_error(
    tmp_path, monkeypatch
) -> None:
    async def failing_snapshot() -> HomeAssistantSnapshot:
        raise ha_client.HomeAssistantUnavailableError(
            "Home Assistant state snapshot is unavailable."
        )

    monkeypatch.setattr(ha_client, "fetch_homeassistant_snapshot", failing_snapshot)

    async with api_client(tmp_path, monkeypatch, "entity-candidates-error.db") as client:
        response = await client.get(
            "/entities/candidates",
            params={"q": "garden"},
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Home Assistant state snapshot is unavailable."
    }


@pytest.mark.anyio
async def test_entity_candidates_endpoint_respects_limit(
    tmp_path, monkeypatch
) -> None:
    async def fake_snapshot() -> HomeAssistantSnapshot:
        return HomeAssistantSnapshot(
            entities=[
                HomeAssistantEntityState(
                    entity_id="light.garden_path",
                    state="off",
                    domain="light",
                    friendly_name="Garden path",
                    area="Esterno",
                    device_class=None,
                ),
                HomeAssistantEntityState(
                    entity_id="switch.garden_pump",
                    state="on",
                    domain="switch",
                    friendly_name="Garden pump",
                    area="Esterno",
                    device_class=None,
                ),
                HomeAssistantEntityState(
                    entity_id="sensor.garden_temperature",
                    state="18",
                    domain="sensor",
                    friendly_name="Garden temperature",
                    area="Esterno",
                    device_class="temperature",
                ),
            ]
        )

    monkeypatch.setattr(ha_client, "fetch_homeassistant_snapshot", fake_snapshot)

    async with api_client(tmp_path, monkeypatch, "entity-candidates-limit.db") as client:
        response = await client.get(
            "/entities/candidates",
            params={"q": "garden", "limit": 1},
        )

    body = response.json()

    assert response.status_code == 200
    assert len(body) == 1
