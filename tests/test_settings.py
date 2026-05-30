from addon.app.settings import (
    get_data_dir,
    get_db_path,
    get_ha_api_base_url,
    get_ha_token,
    get_ha_websocket_url,
)


def test_get_db_path_defaults_to_data_directory(monkeypatch) -> None:
    monkeypatch.delenv("INTENTGUARD_DB_PATH", raising=False)
    monkeypatch.delenv("INTENTGUARD_DATA_DIR", raising=False)

    assert get_db_path().as_posix() == "/data/intentguard.db"


def test_get_db_path_honors_explicit_db_path(monkeypatch, tmp_path) -> None:
    expected_path = tmp_path / "custom.db"
    monkeypatch.setenv("INTENTGUARD_DB_PATH", str(expected_path))
    monkeypatch.delenv("INTENTGUARD_DATA_DIR", raising=False)

    assert get_db_path() == expected_path


def test_get_data_dir_honors_environment_override(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTENTGUARD_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("INTENTGUARD_DB_PATH", raising=False)

    assert get_data_dir() == tmp_path
    assert get_db_path() == tmp_path / "intentguard.db"


def test_get_ha_api_base_url_defaults_to_supervisor_proxy(monkeypatch) -> None:
    monkeypatch.delenv("INTENTGUARD_HA_API_BASE_URL", raising=False)

    assert get_ha_api_base_url() == "http://supervisor/core/api"


def test_get_ha_websocket_url_defaults_to_supervisor_proxy(monkeypatch) -> None:
    monkeypatch.delenv("INTENTGUARD_HA_API_BASE_URL", raising=False)
    monkeypatch.delenv("INTENTGUARD_HA_WEBSOCKET_URL", raising=False)

    assert get_ha_websocket_url() == "ws://supervisor/core/websocket"


def test_get_ha_websocket_url_can_be_derived_from_direct_api_base_url(monkeypatch) -> None:
    monkeypatch.setenv("INTENTGUARD_HA_API_BASE_URL", "http://ha.local:8123/api")
    monkeypatch.delenv("INTENTGUARD_HA_WEBSOCKET_URL", raising=False)

    assert get_ha_websocket_url() == "ws://ha.local:8123/api/websocket"


def test_get_ha_websocket_url_honors_explicit_override(monkeypatch) -> None:
    monkeypatch.setenv("INTENTGUARD_HA_WEBSOCKET_URL", "wss://ha.local/api/websocket")

    assert get_ha_websocket_url() == "wss://ha.local/api/websocket"


def test_get_ha_token_prefers_intentguard_override(monkeypatch) -> None:
    monkeypatch.setenv("SUPERVISOR_TOKEN", "supervisor-token")
    monkeypatch.setenv("INTENTGUARD_HA_TOKEN", "intentguard-token")

    assert get_ha_token() == "intentguard-token"


def test_get_ha_token_falls_back_to_supervisor_token(monkeypatch) -> None:
    monkeypatch.delenv("INTENTGUARD_HA_TOKEN", raising=False)
    monkeypatch.setenv("SUPERVISOR_TOKEN", "supervisor-token")

    assert get_ha_token() == "supervisor-token"
