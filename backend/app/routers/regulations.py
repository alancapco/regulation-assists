from fastapi import APIRouter, Depends

from backend.app.deps import regulation_params
from backend.app.db_postgres import get_pool
from backend.app.errors import AppError
from backend.app.mapping import apply_date_filter, map_regulation
from backend.app.schemas import Regulation, RegulationQuery

router = APIRouter()

# Postgres query: joins regulations with milestones and source_links,
# aggregates them into pipe-delimited arrays for efficient single-query retrieval.
# Use subquery + ORDER BY then array_agg to preserve sort order correctly.
_SQL_LIST = """
SELECT r.instrument_id, r.name, r.jurisdiction, r.type, r.legal_force,
       r.legislation_date, r.description, r.resume, r.last_modified,
       r.official_text_url, r.publication_url, r.record_url, r.topics,
       (SELECT array_agg(val)
        FROM (SELECT m2.title || '|' || COALESCE(m2.date,'') || '|' || COALESCE(m2.notes,'') AS val
              FROM milestones m2 WHERE m2.instrument_id = r.instrument_id ORDER BY m2.sort_order) ms) AS milestones_arr,
       (SELECT array_agg(val)
        FROM (SELECT s2.url || '|' || COALESCE(s2.domain,'') || '|' || s2.rel_type AS val
              FROM source_links s2 WHERE s2.instrument_id = r.instrument_id ORDER BY s2.sort_order) sl) AS sources_arr
FROM regulations r
WHERE ($1 = '' OR r.jurisdiction = $1)
  AND ($2 = '' OR r.type = $2)
  AND ($3 = '' OR r.legal_force = $3)
  AND ($4 = '' OR $4 = ANY(r.topics))
  AND ($5 = '' OR lower(r.name) LIKE lower('%' || $5 || '%')
       OR lower(coalesce(r.description,'')) LIKE lower('%' || $5 || '%'))
ORDER BY r.name
"""

_SQL_ONE = """
SELECT r.instrument_id, r.name, r.jurisdiction, r.type, r.legal_force,
       r.legislation_date, r.description, r.resume, r.last_modified,
       r.official_text_url, r.publication_url, r.record_url, r.topics,
       r.plain_english, r.overview, r.definitions, r.governance_framework,
       r.key_focus_areas, r.implementation_framework,
       r.summary, r.monitoring_evaluation, r.penalties_liability,
       r.relationship_to_other, r.international_alignment, r.implementation_timeline,
       r.requirements_must_do, r.requirements_should_do,
       r.requirements_must_not_do, r.requirements_should_not_do, r.obligations,
       (SELECT array_agg(val)
        FROM (SELECT m2.title || '|' || COALESCE(m2.date,'') || '|' || COALESCE(m2.notes,'') AS val
              FROM milestones m2 WHERE m2.instrument_id = r.instrument_id ORDER BY m2.sort_order) ms) AS milestones_arr,
       (SELECT array_agg(val)
        FROM (SELECT s2.url || '|' || COALESCE(s2.domain,'') || '|' || s2.rel_type AS val
              FROM source_links s2 WHERE s2.instrument_id = r.instrument_id ORDER BY s2.sort_order) sl) AS sources_arr
FROM regulations r
WHERE r.instrument_id = $1
"""


def _parse_row(row: dict) -> dict:
    """Convert a Postgres row into the dict shape that map_regulation expects."""
    milestones_raw = []
    for entry in (row.get("milestones_arr") or []):
        parts = entry.split("|", 2)
        milestones_raw.append({
            "title": parts[0] if len(parts) > 0 else "",
            "date": parts[1] if len(parts) > 1 and parts[1] else None,
            "notes": parts[2] if len(parts) > 2 and parts[2] else None,
        })

    official_sources_raw = []
    for entry in (row.get("sources_arr") or []):
        parts = entry.split("|", 2)
        official_sources_raw.append({
            "url": parts[0] if len(parts) > 0 else "",
            "domain": parts[1] if len(parts) > 1 else None,
            "rel_type": parts[2] if len(parts) > 2 and parts[2] else "SOURCED_FROM",
        })

    return {
        "instrument_id": row["instrument_id"],
        "name": row["name"],
        "jurisdiction": row["jurisdiction"],
        "type": row["type"],
        "legal_force": row["legal_force"],
        "legislation_date": row["legislation_date"],
        "description": row["description"],
        "resume": row["resume"],
        "last_modified": row["last_modified"],
        "official_text_url": row["official_text_url"],
        "publication_url": row["publication_url"],
        "record_url": row["record_url"],
        "topics": list(row["topics"] or []),
        "milestones_raw": milestones_raw,
        "official_sources_raw": official_sources_raw,
        "plain_english": row.get("plain_english"),
        "overview": row.get("overview"),
        "definitions": row.get("definitions"),
        "governance_framework": row.get("governance_framework"),
        "key_focus_areas": row.get("key_focus_areas"),
        "implementation_framework": row.get("implementation_framework"),
        "summary": row.get("summary"),
        "monitoring_evaluation": row.get("monitoring_evaluation"),
        "penalties_liability": row.get("penalties_liability"),
        "relationship_to_other": row.get("relationship_to_other"),
        "international_alignment": row.get("international_alignment"),
        "implementation_timeline": row.get("implementation_timeline"),
        "requirements_must_do": _parse_jsonb(row.get("requirements_must_do")),
        "requirements_should_do": _parse_jsonb(row.get("requirements_should_do")),
        "requirements_must_not_do": _parse_jsonb(row.get("requirements_must_not_do")),
        "requirements_should_not_do": _parse_jsonb(row.get("requirements_should_not_do")),
        "obligations": _parse_jsonb(row.get("obligations")),
    }


def _parse_jsonb(value):
    """Parse JSONB field that might be returned as a string from Postgres."""
    import json
    if value is None:
        return []
    if isinstance(value, str):
        try:
            return json.loads(value)
        except:
            return []
    return value  # Already parsed list/dict


@router.get("/api/regulations")
async def list_regulations(
    params: RegulationQuery = Depends(regulation_params),
) -> list[Regulation]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            _SQL_LIST, params.jurisdiction, params.type, params.legal_force,
            params.topic, params.q,
        )
    items = [map_regulation(_parse_row(dict(row))) for row in rows]
    return apply_date_filter(items, params.date_from, params.date_to, key="legislation_date")


@router.get("/api/regulations/{instrument_id}")
async def get_regulation(instrument_id: str) -> Regulation:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_SQL_ONE, instrument_id)
    if row is None:
        raise AppError(404, "NOT_FOUND", "未找到该法规")
    return map_regulation(_parse_row(dict(row)))
