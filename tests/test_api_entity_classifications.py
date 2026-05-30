import pytest

from tests.api_test_support import api_client


@pytest.mark.anyio
async def test_health_endpoint_returns_ok(tmp_path, monkeypatch) -> None:
    async with api_client(tmp_path, monkeypatch, "health.db") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_entity_classification_crud_endpoints(tmp_path, monkeypatch) -> None:
    payload = {
        "entity_id": "light.garden_lights",
        "real_world_name": "Garden lights",
        "category": "light",
        "impact": "low",
        "permissions": {
            "read": True,
            "notify": True,
            "turn_on": True,
            "turn_off": True,
            "auto_modify": True,
        },
    }

    async with api_client(
        tmp_path,
        monkeypatch,
        "entity-classifications.db",
    ) as client:
        put_response = await client.put(
            "/entity-classifications/light.garden_lights",
            json=payload,
        )
        get_response = await client.get("/entity-classifications/light.garden_lights")
        list_response = await client.get("/entity-classifications")
        delete_response = await client.delete("/entity-classifications/light.garden_lights")
        missing_response = await client.get("/entity-classifications/light.garden_lights")

    assert put_response.status_code == 200
    assert put_response.json() == payload
    assert get_response.status_code == 200
    assert get_response.json() == payload
    assert list_response.status_code == 200
    assert list_response.json() == [payload]
    assert delete_response.status_code == 204
    assert missing_response.status_code == 404


@pytest.mark.anyio
async def test_put_entity_classification_rejects_mismatched_entity_id(
    tmp_path, monkeypatch
) -> None:
    payload = {
        "entity_id": "light.kitchen",
        "real_world_name": "Kitchen light",
        "category": "light",
        "impact": "low",
        "permissions": {
            "read": True,
            "notify": True,
            "turn_on": True,
            "turn_off": True,
            "auto_modify": True,
        },
    }

    async with api_client(tmp_path, monkeypatch, "mismatch.db") as client:
        response = await client.put(
            "/entity-classifications/light.garden_lights",
            json=payload,
        )

    assert response.status_code == 400
