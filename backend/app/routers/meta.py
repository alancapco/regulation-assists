from fastapi import APIRouter, Depends
from neo4j import AsyncDriver
from neo4j.exceptions import AuthError, Neo4jError, ServiceUnavailable

from backend.app import cypher
from backend.app.config import settings
from backend.app.db_postgres import get_pool
from backend.app.deps import get_driver, run
from backend.app.errors import AppError
from backend.app.mapping import map_filters
from backend.app.schemas import AppStatus, FilterOptions

router = APIRouter()

_SQL_FILTERS = """
SELECT
    array_agg(DISTINCT jurisdiction ORDER BY jurisdiction) FILTER (WHERE jurisdiction != '') AS jurisdictions,
    array_agg(DISTINCT type ORDER BY type) FILTER (WHERE type != '') AS types,
    array_agg(DISTINCT legal_force ORDER BY legal_force) FILTER (WHERE legal_force != '') AS legal_forces,
    (SELECT array_agg(DISTINCT unnested_topic ORDER BY unnested_topic)
     FROM regulations, LATERAL unnest(topics) AS unnested_topic) AS topics
FROM regulations
"""

_SQL_COUNT = "SELECT count(*) AS regulation_count FROM regulations"


@router.get("/api/status")
async def status(driver: AsyncDriver = Depends(get_driver)) -> AppStatus:
    # Neo4j probe for connected flag; count comes from Postgres
    try:
        await run(driver, cypher.Q_PING)
        neo4j_connected = True
    except (ServiceUnavailable, Neo4jError, AuthError):
        neo4j_connected = False

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(_SQL_COUNT)
        regulation_count = row["regulation_count"] if row else 0
    except Exception:
        regulation_count = 0

    return AppStatus(
        connected=neo4j_connected,
        regulation_count=regulation_count,
        total_count=settings.total_count,
    )


@router.get("/api/filters")
async def filters() -> FilterOptions:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(_SQL_FILTERS)
    except Exception as exc:
        raise AppError(503, "POSTGRES_UNAVAILABLE", "无法连接到 Postgres，请检查服务状态") from exc

    if not row:
        return FilterOptions()
    return map_filters({
        "jurisdictions": list(row["jurisdictions"] or []),
        "types": list(row["types"] or []),
        "legal_forces": list(row["legal_forces"] or []),
        "topics": list(row["topics"] or []),
    })
