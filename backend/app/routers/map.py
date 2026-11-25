from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.db_postgres import get_pool

router = APIRouter()

# International org prefixes — jurisdiction names starting with these are flagged
_INTL_PREFIXES = ("European Union", "United Nations", "ISO", "IEEE", "OECD", "WEF",
                  "Council of Europe", "G7", "G20", "APEC", "ASEAN", "African Union")


class JurisdictionCount(BaseModel):
    jurisdiction: str
    count: int
    is_international: bool


class MapData(BaseModel):
    countries: list[JurisdictionCount]
    total_regulations: int


@router.get("/map")
async def get_map() -> MapData:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT jurisdiction, count(*) AS count FROM regulations "
            "WHERE jurisdiction != '' GROUP BY jurisdiction ORDER BY count DESC"
        )
    countries = [
        JurisdictionCount(
            jurisdiction=r["jurisdiction"],
            count=r["count"],
            is_international=any(r["jurisdiction"].startswith(p) for p in _INTL_PREFIXES),
        )
        for r in rows
    ]
    total = sum(c.count for c in countries)
    return MapData(countries=countries, total_regulations=total)
