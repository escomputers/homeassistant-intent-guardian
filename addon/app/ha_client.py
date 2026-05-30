import json
from dataclasses import dataclass
from typing import Any

import httpx
import websockets
from websockets.exceptions import WebSocketException

from addon.app.settings import (
    get_ha_api_base_url,
    get_ha_token,
    get_ha_websocket_url,
)
from intentguard_core.models import HomeAssistantEntityState, HomeAssistantSnapshot


@dataclass(frozen=True)
class HomeAssistantRegistryData:
    areas: list[dict[str, Any]]
    devices: list[dict[str, Any]]
    entities: list[dict[str, Any]]


class HomeAssistantConfigurationError(RuntimeError):
    """Raised when the runtime is missing the HA API configuration it needs."""


class HomeAssistantUnavailableError(RuntimeError):
    """Raised when the HA API cannot be reached or returns an unexpected error."""


class HomeAssistantRegistryUnavailableError(RuntimeError):
    """Raised when HA registry enrichment cannot be loaded."""


async def fetch_homeassistant_snapshot(
    *,
    base_url: str | None = None,
    websocket_url: str | None = None,
    token: str | None = None,
    client: httpx.AsyncClient | None = None,
    websocket_connect=None,
) -> HomeAssistantSnapshot:
    resolved_base_url = (base_url or get_ha_api_base_url()).rstrip("/")
    resolved_websocket_url = (websocket_url or get_ha_websocket_url()).rstrip("/")
    resolved_token = token if token is not None else get_ha_token()
    if not resolved_token:
        raise HomeAssistantConfigurationError(
            "Home Assistant token is not configured. "
            "Set INTENTGUARD_HA_TOKEN or SUPERVISOR_TOKEN."
        )

    states_payload = await fetch_homeassistant_states(
        base_url=resolved_base_url,
        token=resolved_token,
        client=client,
    )

    entity_areas: dict[str, str] = {}
    try:
        registry_data = await fetch_homeassistant_registry_data(
            websocket_url=resolved_websocket_url,
            token=resolved_token,
            websocket_connect=websocket_connect,
        )
        entity_areas = build_entity_area_lookup(registry_data)
    except HomeAssistantRegistryUnavailableError:
        entity_areas = {}

    return map_states_payload_to_snapshot(
        states_payload,
        entity_areas=entity_areas,
    )


async def fetch_homeassistant_states(
    *,
    base_url: str | None = None,
    token: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    resolved_base_url = (base_url or get_ha_api_base_url()).rstrip("/")
    resolved_token = token if token is not None else get_ha_token()
    if not resolved_token:
        raise HomeAssistantConfigurationError(
            "Home Assistant token is not configured. "
            "Set INTENTGUARD_HA_TOKEN or SUPERVISOR_TOKEN."
        )

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=10.0)

    try:
        response = await client.get(
            f"{resolved_base_url}/states",
            headers={"Authorization": f"Bearer {resolved_token}"},
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HomeAssistantUnavailableError(
            "Home Assistant state snapshot is unavailable."
        ) from exc
    finally:
        if owns_client and client is not None:
            await client.aclose()

    return payload


async def fetch_homeassistant_registry_data(
    *,
    websocket_url: str | None = None,
    token: str | None = None,
    websocket_connect=None,
) -> HomeAssistantRegistryData:
    resolved_websocket_url = (websocket_url or get_ha_websocket_url()).rstrip("/")
    resolved_token = token if token is not None else get_ha_token()
    if not resolved_token:
        raise HomeAssistantConfigurationError(
            "Home Assistant token is not configured. "
            "Set INTENTGUARD_HA_TOKEN or SUPERVISOR_TOKEN."
        )

    connect = websocket_connect or websockets.connect

    try:
        async with connect(resolved_websocket_url) as websocket:
            await _authenticate_websocket(websocket, resolved_token)
            areas = await _call_websocket_command(
                websocket,
                message_id=1,
                command_type="config/area_registry/list",
            )
            devices = await _call_websocket_command(
                websocket,
                message_id=2,
                command_type="config/device_registry/list",
            )
            entities = await _call_websocket_command(
                websocket,
                message_id=3,
                command_type="config/entity_registry/list",
            )
    except HomeAssistantConfigurationError:
        raise
    except HomeAssistantRegistryUnavailableError:
        raise
    except (OSError, ValueError, WebSocketException) as exc:
        raise HomeAssistantRegistryUnavailableError(
            "Home Assistant registry enrichment is unavailable."
        ) from exc

    return HomeAssistantRegistryData(
        areas=areas,
        devices=devices,
        entities=entities,
    )


def build_entity_area_lookup(
    registry_data: HomeAssistantRegistryData,
) -> dict[str, str]:
    area_name_by_id = {
        area["area_id"]: area["name"]
        for area in registry_data.areas
        if area.get("area_id") and area.get("name")
    }
    device_area_id_by_id = {
        device["id"]: device.get("area_id")
        for device in registry_data.devices
        if device.get("id")
    }

    entity_area_lookup: dict[str, str] = {}
    for entity in registry_data.entities:
        entity_id = entity.get("entity_id")
        if not entity_id:
            continue

        area_id = entity.get("area_id")
        if not area_id and entity.get("device_id"):
            area_id = device_area_id_by_id.get(entity["device_id"])

        if not area_id:
            continue

        area_name = area_name_by_id.get(area_id)
        if area_name:
            entity_area_lookup[entity_id] = area_name

    return entity_area_lookup


def map_states_payload_to_snapshot(
    payload: list[dict[str, Any]],
    *,
    entity_areas: dict[str, str] | None = None,
) -> HomeAssistantSnapshot:
    resolved_areas = entity_areas or {}
    entities = [
        map_state_item_to_entity(
            item,
            resolved_area=resolved_areas.get(item["entity_id"]),
        )
        for item in payload
    ]
    return HomeAssistantSnapshot(entities=entities)


def map_state_item_to_entity(
    item: dict[str, Any],
    *,
    resolved_area: str | None = None,
) -> HomeAssistantEntityState:
    attributes = item.get("attributes") or {}
    entity_id = item["entity_id"]
    return HomeAssistantEntityState(
        entity_id=entity_id,
        state=item.get("state"),
        domain=_extract_domain(entity_id),
        friendly_name=attributes.get("friendly_name"),
        area=resolved_area or attributes.get("area"),
        device_class=attributes.get("device_class"),
    )


async def _authenticate_websocket(websocket, token: str) -> None:
    auth_required = _load_websocket_message(await websocket.recv())
    if auth_required.get("type") != "auth_required":
        raise HomeAssistantRegistryUnavailableError(
            "Home Assistant WebSocket authentication did not start correctly."
        )

    await websocket.send(
        json.dumps(
            {
                "type": "auth",
                "access_token": token,
            }
        )
    )

    auth_response = _load_websocket_message(await websocket.recv())
    if auth_response.get("type") == "auth_ok":
        return

    raise HomeAssistantRegistryUnavailableError(
        "Home Assistant WebSocket authentication failed."
    )


async def _call_websocket_command(
    websocket,
    *,
    message_id: int,
    command_type: str,
) -> list[dict[str, Any]]:
    await websocket.send(
        json.dumps(
            {
                "id": message_id,
                "type": command_type,
            }
        )
    )

    while True:
        response = _load_websocket_message(await websocket.recv())
        if response.get("type") != "result" or response.get("id") != message_id:
            continue

        if not response.get("success"):
            raise HomeAssistantRegistryUnavailableError(
                f"Home Assistant WebSocket command '{command_type}' failed."
            )

        result = response.get("result")
        if not isinstance(result, list):
            raise HomeAssistantRegistryUnavailableError(
                f"Home Assistant WebSocket command '{command_type}' returned "
                "an unexpected payload."
            )

        return result


def _load_websocket_message(message: str | bytes) -> dict[str, Any]:
    if isinstance(message, bytes):
        message = message.decode("utf-8")

    payload = json.loads(message)
    if not isinstance(payload, dict):
        raise HomeAssistantRegistryUnavailableError(
            "Home Assistant WebSocket returned an unexpected message."
        )

    return payload


def _extract_domain(entity_id: str) -> str | None:
    return entity_id.split(".", 1)[0] if "." in entity_id else None
