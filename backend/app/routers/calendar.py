from fastapi import APIRouter, Depends

from backend.app.db_postgres import get_pool
from backend.app.deps import calendar_params
from backend.app.mapping import apply_date_filter, normalize_date
from backend.app.schemas import CalendarEvent, CalendarQuery

router = APIRouter()

_SQL_CALENDAR = """
SELECT m.instrument_id, m.title, m.date, m.notes, m.sort_order,
       r.name AS regulation_name, r.jurisdiction,
       s.url AS source_url
FROM milestones m
JOIN regulations r ON r.instrument_id = m.instrument_id
LEFT JOIN source_links s ON s.instrument_id = m.instrument_id AND s.sort_order = 0
WHERE m.date IS NOT NULL AND m.date != ''
  AND ($1 = '' OR r.jurisdiction = $1)
ORDER BY m.date, m.instrument_id
"""


@router.get("/api/calendar")
async def list_calendar(
    params: CalendarQuery = Depends(calendar_params),
) -> list[CalendarEvent]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(_SQL_CALENDAR, params.jurisdiction)

    items = []
    for i, row in enumerate(rows):
        date = normalize_date(row["date"])
        if date is None:
            continue
        items.append(CalendarEvent(
            id=f"{row['instrument_id']}_{i}",
            date=date,
            title=row["title"] or "",
            instrument_id=row["instrument_id"],
            regulation_name=row["regulation_name"] or "",
            jurisdiction=row["jurisdiction"] or "",
            source_url=row["source_url"] or None,
        ))

    items = apply_date_filter(items, params.date_from, params.date_to, key="date")
    return sorted(items, key=lambda e: e.date)
