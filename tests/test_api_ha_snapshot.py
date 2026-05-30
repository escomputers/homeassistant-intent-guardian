import pytest

from addon.app import ha_client
from intentguard_core.models import HomeAssistantEntityState, HomeAssistantSnapshot
from tests.api_test_support import api_client


@pytest.mark.anyio
async def test_ha_snapshot_endpoint_returns_normalized_snapshot(
    tmp_path, monkeypatch
) -> None:
    async def fake_snapshot() -> HomeAssistantSnapshot:
        return HomeAssistantSnapshot(
            entities=[
                HomeAssistantEntityState(
                    entity_id="light.luci_giardino",
                    state="on",
                    domain="light",
                    friendly_name="Luci giardino",
                    area="Esterno",
                    device_class=None,
                )
            ]
        )

    monkeypatch.setattr(ha_client, "fetch_homeassistant_snapshot", fake_snapshot)

    async with api_client(tmp_path, monkeypatch, "ha-snapshot.db") as client:
        response = await client.get("/ha/snapshot")

    assert response.status_code == 200
    assert response.json() == {
        "entities": [
            {
                "entity_id": "light.luci_giardino",
                "state": "on",
                "domain": "light",
                "friendly_name": "Luci giardino",
                "area": "Esterno",
                "device_class": None,
            }
        ]
    }


@pytest.mark.anyio
async def test_ha_snapshot_endpoint_enriches_area_from_registry_data(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("INTENTGUARD_HA_TOKEN", "test-token")

    async def fake_states(**_kwargs) -> list[dict]:
        return [
            {
                "entity_id": "light.tapo_l530_smart_bulb",
                "state": "off",
                "attributes": {
                    "friendly_name": "Tapo L530 smart bulb",
                    "device_class": None,
                },
            }
        ]

    async def fake_registry_data(**_kwargs) -> ha_client.HomeAssistantRegistryData:
        return ha_client.HomeAssistantRegistryData(
            areas=[{"area_id": "garden", "name": "Giardino"}],
            devices=[{"id": "device-1", "area_id": "garden"}],
            entities=[
                {
                    "entity_id": "light.tapo_l530_smart_bulb",
                    "device_id": "device-1",
                }
            ],
        )

    monkeypatch.setattr(ha_client, "fetch_homeassistant_states", fake_states)
    monkeypatch.setattr(ha_client, "fetch_homeassistant_registry_data", fake_registry_data)

    async with api_client(tmp_path, monkeypatch, "ha-snapshot-area.db") as client:
        response = await client.get("/ha/snapshot")

    assert response.status_code == 200
    assert response.json() == {
        "entities": [
            {
                "entity_id": "light.tapo_l530_smart_bulb",
                "state": "off",
                "domain": "light",
                "friendly_name": "Tapo L530 smart bulb",
                "area": "Giardino",
                "device_class": None,
            }
        ]
    }


@pytest.mark.anyio
async def test_ha_snapshot_endpoint_degrades_gracefully_when_registry_data_is_unavailable(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("INTENTGUARD_HA_TOKEN", "test-token")

    async def fake_states(**_kwargs) -> list[dict]:
        return [
            {
                "entity_id": "light.tapo_l530_smart_bulb",
                "state": "off",
                "attributes": {
                    "friendly_name": "Tapo L530 smart bulb",
                    "device_class": None,
                },
            }
        ]

    async def failing_registry_data(**_kwargs) -> ha_client.HomeAssistantRegistryData:
        raise ha_client.HomeAssistantRegistryUnavailableError(
            "Home Assistant registry enrichment is unavailable."
        )

    monkeypatch.setattr(ha_client, "fetch_homeassistant_states", fake_states)
    monkeypatch.setattr(
        ha_client,
        "fetch_homeassistant_registry_data",
        failing_registry_data,
    )

    async with api_client(tmp_path, monkeypatch, "ha-snapshot-area-fallback.db") as client:
        response = await client.get("/ha/snapshot")

    assert response.status_code == 200
    assert response.json() == {
        "entities": [
            {
                "entity_id": "light.tapo_l530_smart_bulb",
                "state": "off",
                "domain": "light",
                "friendly_name": "Tapo L530 smart bulb",
                "area": None,
                "device_class": None,
            }
        ]
    }


@pytest.mark.anyio
async def test_ha_snapshot_endpoint_handles_empty_area_registry_without_error(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("INTENTGUARD_HA_TOKEN", "test-token")

    async def fake_states(**_kwargs) -> list[dict]:
        return [
            {
                "entity_id": "light.tapo_l530_smart_bulb",
                "state": "off",
                "attributes": {
                    "friendly_name": "Tapo L530 smart bulb",
                    "device_class": None,
                },
            }
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

    async with api_client(tmp_path, monkeypatch, "ha-snapshot-empty-areas.db") as client:
        response = await client.get("/ha/snapshot")

    assert response.status_code == 200
    assert response.json() == {
        "entities": [
            {
                "entity_id": "light.tapo_l530_smart_bulb",
                "state": "off",
                "domain": "light",
                "friendly_name": "Tapo L530 smart bulb",
                "area": None,
                "device_class": None,
            }
        ]
    }


@pytest.mark.anyio
async def test_ha_snapshot_endpoint_returns_controlled_unavailable_error(
    tmp_path, monkeypatch
) -> None:
    async def failing_snapshot() -> HomeAssistantSnapshot:
        raise ha_client.HomeAssistantUnavailableError(
            "Home Assistant state snapshot is unavailable."
        )

    monkeypatch.setattr(ha_client, "fetch_homeassistant_snapshot", failing_snapshot)

    async with api_client(tmp_path, monkeypatch, "ha-snapshot-error.db") as client:
        response = await client.get("/ha/snapshot")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Home Assistant state snapshot is unavailable."
    }


@pytest.mark.anyio
async def test_ha_snapshot_endpoint_returns_controlled_missing_token_error(
    tmp_path, monkeypatch
) -> None:
    async def missing_token_snapshot() -> HomeAssistantSnapshot:
        raise ha_client.HomeAssistantConfigurationError(
            "Home Assistant token is not configured. "
            "Set INTENTGUARD_HA_TOKEN or SUPERVISOR_TOKEN."
        )

    monkeypatch.setattr(ha_client, "fetch_homeassistant_snapshot", missing_token_snapshot)

    async with api_client(tmp_path, monkeypatch, "ha-snapshot-no-token.db") as client:
        response = await client.get("/ha/snapshot")

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "Home Assistant token is not configured. "
            "Set INTENTGUARD_HA_TOKEN or SUPERVISOR_TOKEN."
        )
    }
