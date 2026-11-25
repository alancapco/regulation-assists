from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from neo4j.exceptions import ServiceUnavailable

from backend.app.main import app


def make_driver(rows=None, raise_on_run=None):
    """Mock Neo4j driver. Only session.run / result.data are async."""
    mock_result = AsyncMock()
    mock_result.data.return_value = rows or []
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = False
    if raise_on_run is not None:
        mock_session.run.side_effect = raise_on_run
    else:
        mock_session.run.return_value = mock_result
    driver = MagicMock()
    driver.session.return_value = mock_session
    return driver


def make_pg_pool(count: int = 30, filters: dict | None = None):
    """Minimal asyncpg pool mock for status/filters."""
    row_count = {"regulation_count": count}
    filter_row = filters or {
        "jurisdictions": ["EU"],
        "types": ["Act"],
        "legal_forces": ["InForce"],
        "topics": ["risk_management"],
    }

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=lambda sql, *a: (
        row_count if "regulation_count" in sql or "count(*)" in sql.lower() else filter_row
    ))

    # status uses SELECT count(*) AS regulation_count
    async def fetchrow(sql, *args):
        s = sql.lower()
        if "count(*)" in s:
            return row_count
        return filter_row

    conn.fetchrow = fetchrow

    cm = AsyncMock()
    cm.__aenter__.return_value = conn
    cm.__aexit__.return_value = False

    pool = MagicMock()
    pool.acquire.return_value = cm
    return pool


@pytest.mark.asyncio
async def test_status_connected():
    app.state.driver = make_driver([{"ok": 1}])
    transport = httpx.ASGITransport(app=app)
    with patch("backend.app.routers.meta.get_pool", AsyncMock(return_value=make_pg_pool(30))):
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as ac:
            resp = await ac.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["connected"] is True
    assert body["regulation_count"] == 30
    assert body["total_count"] == 1174


@pytest.mark.asyncio
async def test_status_disconnected_returns_200_false():
    # /api/status degrades to 200 connected:false — never 5xx for Neo4j down
    app.state.driver = make_driver(raise_on_run=ServiceUnavailable("down"))
    transport = httpx.ASGITransport(app=app)
    with patch("backend.app.routers.meta.get_pool", AsyncMock(side_effect=RuntimeError("no pg"))):
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as ac:
            resp = await ac.get("/api/status")
    assert resp.status_code == 200
    assert resp.json() == {"connected": False, "regulation_count": 0, "total_count": 1174}


@pytest.mark.asyncio
async def test_filters_disconnected_returns_503():
    # /api/filters requires Postgres; unavailable → 503 POSTGRES_UNAVAILABLE
    transport = httpx.ASGITransport(app=app)
    with patch("backend.app.routers.meta.get_pool", AsyncMock(side_effect=RuntimeError("down"))):
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as ac:
            resp = await ac.get("/api/filters")
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "POSTGRES_UNAVAILABLE"


@pytest.mark.asyncio
async def test_regulations_bad_date_returns_400():
    app.state.driver = make_driver()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as ac:
        resp = await ac.get("/api/regulations?date_from=2026-13-01")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_llm_test_invalid_url_returns_400():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as ac:
        resp = await ac.post("/api/llm/test",
                             json={"base_url": "ftp://x", "api_key": "k", "model": "m"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
