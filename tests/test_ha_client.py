import json
from contextlib import asynccontextmanager

import httpx
import pytest

from addon.app.ha_client import (
    HomeAssistantConfigurationError,
    HomeAssistantRegistryUnavailableError,
    fetch_homeassistant_snapshot,
)


@pytest.mark.anyio
async def test_fetch_homeassistant_snapshot_populates_area_from_entity_registry() -> None:
    transport = httpx.MockTransport(
        build_states_handler(
            [
                {
                    "entity_id": "light.luci_giardino",
                    "state": "on",
                    "attributes": {
                        "friendly_name": "Luci giardino",
                        "device_class": None,
                    },
                }
            ]
        )
    )

    async with httpx.AsyncClient(transport=transport) as client:
        snapshot = await fetch_homeassistant_snapshot(
            base_url="http://ha.local/api",
            websocket_url="ws://ha.local/api/websocket",
            token="test-token",
            client=client,
            websocket_connect=build_fake_websocket_connect(
                areas=[{"area_id": "garden", "name": "Giardino"}],
                devices=[],
                entities=[
                    {
                        "entity_id": "light.luci_giardino",
                        "area_id": "garden",
                    }
                ],
            ),
        )

    assert snapshot.entities[0].entity_id == "light.luci_giardino"
    assert snapshot.entities[0].area == "Giardino"


@pytest.mark.anyio
async def test_fetch_homeassistant_snapshot_inherits_area_from_device_registry() -> None:
    transport = httpx.MockTransport(
        build_states_handler(
            [
                {
                    "entity_id": "light.tapo_l530_smart_bulb",
                    "state": "off",
                    "attributes": {
                        "friendly_name": "Tapo L530 smart bulb",
                        "device_class": None,
                    },
                }
            ]
        )
    )

    async with httpx.AsyncClient(transport=transport) as client:
        snapshot = await fetch_homeassistant_snapshot(
            base_url="http://ha.local/api",
            websocket_url="ws://ha.local/api/websocket",
            token="test-token",
            client=client,
            websocket_connect=build_fake_websocket_connect(
                areas=[{"area_id": "garden", "name": "Giardino"}],
                devices=[{"id": "device-1", "area_id": "garden"}],
                entities=[
                    {
                        "entity_id": "light.tapo_l530_smart_bulb",
                        "device_id": "device-1",
                    }
                ],
            ),
        )

    assert snapshot.entities[0].area == "Giardino"


@pytest.mark.anyio
async def test_fetch_homeassistant_snapshot_leaves_area_null_without_registry_match() -> None:
    transport = httpx.MockTransport(
        build_states_handler(
            [
                {
                    "entity_id": "light.tapo_l530_smart_bulb",
                    "state": "off",
                    "attributes": {
                        "friendly_name": "Tapo L530 smart bulb",
                        "device_class": None,
                    },
                }
            ]
        )
    )

    async with httpx.AsyncClient(transport=transport) as client:
        snapshot = await fetch_homeassistant_snapshot(
            base_url="http://ha.local/api",
            websocket_url="ws://ha.local/api/websocket",
            token="test-token",
            client=client,
            websocket_connect=build_fake_websocket_connect(
                areas=[{"area_id": "garden", "name": "Giardino"}],
                devices=[],
                entities=[{"entity_id": "light.tapo_l530_smart_bulb"}],
            ),
        )

    assert snapshot.entities[0].area is None


@pytest.mark.anyio
async def test_fetch_homeassistant_snapshot_handles_empty_area_registry() -> None:
    transport = httpx.MockTransport(
        build_states_handler(
            [
                {
                    "entity_id": "light.tapo_l530_smart_bulb",
                    "state": "off",
                    "attributes": {
                        "friendly_name": "Tapo L530 smart bulb",
                        "device_class": None,
                    },
                }
            ]
        )
    )

    async with httpx.AsyncClient(transport=transport) as client:
        snapshot = await fetch_homeassistant_snapshot(
            base_url="http://ha.local/api",
            websocket_url="ws://ha.local/api/websocket",
            token="test-token",
            client=client,
            websocket_connect=build_fake_websocket_connect(
                areas=[],
                devices=[{"id": "device-1"}],
                entities=[
                    {
                        "entity_id": "light.tapo_l530_smart_bulb",
                        "device_id": "device-1",
                    }
                ],
            ),
        )

    assert snapshot.entities[0].area is None


@pytest.mark.anyio
async def test_fetch_homeassistant_snapshot_handles_entities_without_area_id() -> None:
    transport = httpx.MockTransport(
        build_states_handler(
            [
                {
                    "entity_id": "light.tapo_l530_smart_bulb",
                    "state": "off",
                    "attributes": {
                        "friendly_name": "Tapo L530 smart bulb",
                        "device_class": None,
                    },
                }
            ]
        )
    )

    async with httpx.AsyncClient(transport=transport) as client:
        snapshot = await fetch_homeassistant_snapshot(
            base_url="http://ha.local/api",
            websocket_url="ws://ha.local/api/websocket",
            token="test-token",
            client=client,
            websocket_connect=build_fake_websocket_connect(
                areas=[{"area_id": "garden", "name": "Giardino"}],
                devices=[{"id": "device-1"}],
                entities=[
                    {
                        "entity_id": "light.tapo_l530_smart_bulb",
                        "device_id": "device-1",
                    }
                ],
            ),
        )

    assert snapshot.entities[0].area is None


@pytest.mark.anyio
async def test_fetch_homeassistant_snapshot_degrades_gracefully_when_registry_unavailable() -> None:
    transport = httpx.MockTransport(
        build_states_handler(
            [
                {
                    "entity_id": "sensor.freezer",
                    "state": "-18",
                    "attributes": {
                        "friendly_name": "Freezer",
                        "device_class": "temperature",
                    },
                }
            ]
        )
    )

    @asynccontextmanager
    async def failing_websocket_connect(_url: str):
        raise OSError("websocket unavailable")
        yield

    async with httpx.AsyncClient(transport=transport) as client:
        snapshot = await fetch_homeassistant_snapshot(
            base_url="http://ha.local/api",
            websocket_url="ws://ha.local/api/websocket",
            token="test-token",
            client=client,
            websocket_connect=failing_websocket_connect,
        )

    assert snapshot.entities[0].entity_id == "sensor.freezer"
    assert snapshot.entities[0].area is None


@pytest.mark.anyio
async def test_fetch_homeassistant_snapshot_requires_token(monkeypatch) -> None:
    monkeypatch.delenv("INTENTGUARD_HA_TOKEN", raising=False)
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)

    with pytest.raises(HomeAssistantConfigurationError):
        await fetch_homeassistant_snapshot(base_url="http://ha.local/api")


def build_states_handler(states_payload: list[dict]) -> callable:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/states"
        assert request.headers["Authorization"] == "Bearer test-token"
        return httpx.Response(
            status_code=200,
            json=states_payload,
        )

    return handler


def build_fake_websocket_connect(
    *,
    areas: list[dict],
    devices: list[dict],
    entities: list[dict],
):
    websocket = FakeWebSocket(
        [
            {"type": "auth_required"},
            {"type": "auth_ok"},
            {
                "id": 1,
                "type": "result",
                "success": True,
                "result": areas,
            },
            {
                "id": 2,
                "type": "result",
                "success": True,
                "result": devices,
            },
            {
                "id": 3,
                "type": "result",
                "success": True,
                "result": entities,
            },
        ]
    )

    @asynccontextmanager
    async def fake_websocket_connect(_url: str):
        yield websocket

    return fake_websocket_connect


class FakeWebSocket:
    def __init__(self, messages: list[dict]) -> None:
        self._messages = [json.dumps(message) for message in messages]
        self.sent_messages: list[dict] = []

    async def recv(self) -> str:
        if not self._messages:
            raise HomeAssistantRegistryUnavailableError("No more WebSocket messages.")
        return self._messages.pop(0)

    async def send(self, payload: str) -> None:
        self.sent_messages.append(json.loads(payload))
