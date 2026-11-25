"""
PostgreSQL async connection pool + schema bootstrap.
Content source of truth: regulations, milestones, source_links.
pgvector extension for semantic similarity search on embeddings.
"""
import asyncpg
import logging
from backend.app.config import settings

logger = logging.getLogger("backend.app.db_postgres")

_pool: asyncpg.Pool | None = None

SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS regulations (
    instrument_id     TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    jurisdiction      TEXT NOT NULL DEFAULT '',
    type              TEXT NOT NULL DEFAULT '',
    legal_force       TEXT NOT NULL DEFAULT '',
    legislation_date  TEXT,
    description       TEXT,
    resume            TEXT,
    last_modified     TEXT,
    official_text_url TEXT,
    publication_url   TEXT,
    record_url        TEXT NOT NULL DEFAULT '',
    topics            TEXT[] DEFAULT '{}',
    embedding         vector(1536)
);

CREATE TABLE IF NOT EXISTS milestones (
    id            SERIAL PRIMARY KEY,
    instrument_id TEXT NOT NULL REFERENCES regulations(instrument_id) ON DELETE CASCADE,
    title         TEXT NOT NULL,
    date          TEXT,
    notes         TEXT,
    sort_order    INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS source_links (
    id            SERIAL PRIMARY KEY,
    instrument_id TEXT NOT NULL REFERENCES regulations(instrument_id) ON DELETE CASCADE,
    url           TEXT NOT NULL,
    domain        TEXT,
    rel_type      TEXT DEFAULT 'SOURCED_FROM',
    sort_order    INT DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_regulations_jurisdiction ON regulations(jurisdiction);
CREATE INDEX IF NOT EXISTS idx_regulations_type ON regulations(type);
CREATE INDEX IF NOT EXISTS idx_regulations_legal_force ON regulations(legal_force);
CREATE INDEX IF NOT EXISTS idx_milestones_instrument ON milestones(instrument_id);
CREATE INDEX IF NOT EXISTS idx_source_links_instrument ON source_links(instrument_id);
CREATE INDEX IF NOT EXISTS idx_regulations_embedding ON regulations
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
"""


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        raise RuntimeError("Postgres pool not initialised")
    return _pool


async def init_pool():
    global _pool
    _pool = await asyncpg.create_pool(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
        min_size=2,
        max_size=10,
    )
    async with _pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)
    logger.info("Postgres pool initialised and schema applied")


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
