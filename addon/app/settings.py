import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

DEFAULT_DATA_DIR = Path("/data")
DEFAULT_DB_FILENAME = "intentguard.db"
DEFAULT_HA_API_BASE_URL = "http://supervisor/core/api"
DEFAULT_HA_WEBSOCKET_URL = "ws://supervisor/core/websocket"


def get_data_dir() -> Path:
    configured_data_dir = os.getenv("INTENTGUARD_DATA_DIR")
    return Path(configured_data_dir) if configured_data_dir else DEFAULT_DATA_DIR


def get_db_path() -> Path:
    configured_db_path = os.getenv("INTENTGUARD_DB_PATH")
    if configured_db_path:
        return Path(configured_db_path)

    return get_data_dir() / DEFAULT_DB_FILENAME


def get_ha_api_base_url() -> str:
    return os.getenv("INTENTGUARD_HA_API_BASE_URL", DEFAULT_HA_API_BASE_URL)


def get_ha_websocket_url() -> str:
    configured_websocket_url = os.getenv("INTENTGUARD_HA_WEBSOCKET_URL")
    if configured_websocket_url:
        return configured_websocket_url

    return _derive_ha_websocket_url(get_ha_api_base_url())


def get_ha_token() -> str | None:
    return os.getenv("INTENTGUARD_HA_TOKEN") or os.getenv("SUPERVISOR_TOKEN")


def _derive_ha_websocket_url(api_base_url: str) -> str:
    if api_base_url == DEFAULT_HA_API_BASE_URL:
        return DEFAULT_HA_WEBSOCKET_URL

    parsed = urlparse(api_base_url.rstrip("/"))
    websocket_scheme = "wss" if parsed.scheme == "https" else "ws"
    normalized_path = parsed.path.rstrip("/")
    if normalized_path.endswith("/core/api"):
        websocket_path = f"{normalized_path[:-len('/api')]}/websocket"
    elif normalized_path.endswith("/api"):
        websocket_path = f"{normalized_path}/websocket"
    else:
        websocket_path = f"{normalized_path}/api/websocket"

    return urlunparse(
        (
            websocket_scheme,
            parsed.netloc,
            websocket_path,
            "",
            "",
            "",
        )
    )
