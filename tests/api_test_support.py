from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from addon.app.main import app


@asynccontextmanager
async def api_client(
    tmp_path,
    monkeypatch,
    database_name: str,
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv("INTENTGUARD_DB_PATH", str(tmp_path / database_name))
    transport = httpx.ASGITransport(app=app)

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client
