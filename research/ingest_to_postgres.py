"""
Ingest all 30 regulation article.md files into Postgres (regulations, milestones, source_links).
Then optionally generate OpenAI text-embedding-3-small embeddings (1536-dim).

Usage:
    uv run python research/ingest_to_postgres.py

Env vars:
    OPENAI_API_KEY   — if set, embeddings are generated; otherwise skipped with a warning
    POSTGRES_HOST    — default localhost
    POSTGRES_PORT    — default 5433
    POSTGRES_USER    — default capco
    POSTGRES_PASSWORD — default capco-regulation-change-me
    POSTGRES_DB      — default regulation_assistant
"""
import asyncio
import logging
import os
import re
from pathlib import Path

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RECORDS_DIR = Path(__file__).parent / "sources" / "records"

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _field(text: str, key: str) -> str:
    m = re.search(rf'\*\*{re.escape(key)}[^:]*:\*\*\s*(.+)', text)
    return m.group(1).strip() if m else ""


def parse_article_md(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")

    instrument_id = _field(text, "Instrument ID")
    jurisdiction = _field(text, "Jurisdiction")
    reg_type = _field(text, "Type")
    status = _field(text, "Status")
    leg_date = _field(text, "Legislation date")
    last_modified = _field(text, "Last modified")

    record_url_m = re.search(r'\*\*regulations\.ai record[^:]*:\*\*\s*(https?://\S+)', text)
    record_url = record_url_m.group(1) if record_url_m else ""

    official_text_m = re.search(r'\*\*Official text[^:]*:\*\*\s*(https?://\S+)', text)
    official_text_url = official_text_m.group(1) if official_text_m else None

    pub_m = re.search(r'\*\*Official publication[^:]*:\*\*\s*(https?://\S+)', text)
    publication_url = pub_m.group(1) if pub_m else None

    # Title from H1
    title_m = re.search(r'^#\s+(.+)', text, re.MULTILINE)
    name = title_m.group(1).strip() if title_m else instrument_id

    # Résumé / Summary section (files use "## Summary" in ASCII despite display as "Résumé")
    resume_m = re.search(r'##\s+(?:R[eé]sum[eé]|Summary)\s*\n+([\s\S]+?)(?=\n##|\Z)', text)
    resume = resume_m.group(1).strip() if resume_m else ""

    # Topics
    topics_m = re.search(r'##\s+Topics\s*\n+([\s\S]+?)(?=\n##|\Z)', text)
    topics_raw = topics_m.group(1).strip() if topics_m else ""
    topics = [t.strip() for t in topics_raw.split(",") if t.strip()]

    # Milestones — parse markdown table, tolerating embedded HTML fragments
    milestones = []
    ms_m = re.search(r'##\s+Implementation milestones\s*\n+([\s\S]+?)(?=\n##|\Z)', text)
    if ms_m:
        section = ms_m.group(1)
        # Rows may use HTML </td></tr><tr><td> as cell separators — normalise first
        section = re.sub(r'</td></tr><tr><td>', ' | ', section)
        section = re.sub(r'<[^>]+>', '', section)  # strip any remaining HTML tags
        for row in re.finditer(r'\|([^|]+)\|([^|]+)\|([^|]*)\|?', section):
            title = row.group(1).strip()
            date = row.group(2).strip()
            notes = row.group(3).strip()
            if title and title not in ("Milestone", "---", ":---", ":-"):
                milestones.append({
                    "title": title,
                    "date": date if date and date not in ("---", "") else None,
                    "notes": notes or None,
                })

    # Source links
    sources = []
    src_m = re.search(r'##\s+Source links\s*\n+([\s\S]+?)(?=\n##|\Z)', text)
    if src_m:
        for url in re.findall(r'https?://\S+', src_m.group(1)):
            # strip trailing punctuation / markdown artefacts
            url = url.rstrip(").,>")
            domain = re.sub(r'^www\.', '', url.split("/")[2]) if "/" in url else url
            sources.append({"url": url, "domain": domain})

    return {
        "instrument_id": instrument_id,
        "name": name,
        "jurisdiction": jurisdiction,
        "type": reg_type,
        "legal_force": status,
        "legislation_date": leg_date or None,
        "resume": resume or None,
        "last_modified": last_modified or None,
        "official_text_url": official_text_url,
        "publication_url": publication_url,
        "record_url": record_url,
        "topics": topics,
        "milestones": milestones,
        "sources": sources,
    }


# ---------------------------------------------------------------------------
# DB upsert
# ---------------------------------------------------------------------------

async def upsert_regulation(conn: asyncpg.Connection, reg: dict) -> None:
    await conn.execute(
        """
        INSERT INTO regulations
            (instrument_id, name, jurisdiction, type, legal_force, legislation_date,
             resume, last_modified, official_text_url, publication_url, record_url, topics)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
        ON CONFLICT (instrument_id) DO UPDATE SET
            name              = EXCLUDED.name,
            jurisdiction      = EXCLUDED.jurisdiction,
            type              = EXCLUDED.type,
            legal_force       = EXCLUDED.legal_force,
            legislation_date  = EXCLUDED.legislation_date,
            resume            = EXCLUDED.resume,
            last_modified     = EXCLUDED.last_modified,
            official_text_url = EXCLUDED.official_text_url,
            publication_url   = EXCLUDED.publication_url,
            record_url        = EXCLUDED.record_url,
            topics            = EXCLUDED.topics
        """,
        reg["instrument_id"], reg["name"], reg["jurisdiction"], reg["type"],
        reg["legal_force"], reg["legislation_date"], reg["resume"],
        reg["last_modified"], reg["official_text_url"], reg["publication_url"],
        reg["record_url"], reg["topics"],
    )

    # Idempotent: delete then re-insert milestones
    await conn.execute("DELETE FROM milestones WHERE instrument_id = $1", reg["instrument_id"])
    for i, ms in enumerate(reg["milestones"]):
        await conn.execute(
            "INSERT INTO milestones (instrument_id, title, date, notes, sort_order) VALUES ($1,$2,$3,$4,$5)",
            reg["instrument_id"], ms["title"], ms["date"], ms["notes"], i,
        )

    # Idempotent: delete then re-insert source_links
    await conn.execute("DELETE FROM source_links WHERE instrument_id = $1", reg["instrument_id"])
    for i, src in enumerate(reg["sources"]):
        await conn.execute(
            "INSERT INTO source_links (instrument_id, url, domain, rel_type, sort_order) VALUES ($1,$2,$3,$4,$5)",
            reg["instrument_id"], src["url"], src["domain"], "SOURCED_FROM", i,
        )


# ---------------------------------------------------------------------------
# Embedding pass
# ---------------------------------------------------------------------------

async def generate_embeddings(conn: asyncpg.Connection) -> int:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set — skipping embedding generation")
        return 0

    try:
        from openai import OpenAI
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        client = OpenAI(api_key=api_key, base_url=base_url)
    except ImportError:
        logger.warning("openai package not available — skipping embeddings")
        return 0

    rows = await conn.fetch(
        "SELECT instrument_id, name, jurisdiction, resume, description, topics "
        "FROM regulations WHERE embedding IS NULL"
    )
    if not rows:
        logger.info("All embeddings already present, skipping")
        return 0

    count = 0
    for row in rows:
        topics_str = ", ".join(row["topics"] or [])
        content = row["resume"] or row["description"] or ""
        embed_text = f"{row['name']}. {row['jurisdiction']}. {content}. Topics: {topics_str}"
        try:
            resp = client.embeddings.create(model="text-embedding-ada-002", input=[embed_text])
            vector = resp.data[0].embedding
            # Convert list to pgvector string format: '[x,y,z,...]'
            vector_str = "[" + ",".join(str(v) for v in vector) + "]"
            await conn.execute(
                "UPDATE regulations SET embedding = $1 WHERE instrument_id = $2",
                vector_str, row["instrument_id"],
            )
            count += 1
        except Exception as exc:
            logger.warning(f"Embedding failed for {row['instrument_id']}: {exc}")

    return count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    pg_host = os.environ.get("POSTGRES_HOST", "localhost")
    pg_port = int(os.environ.get("POSTGRES_PORT", "5433"))
    pg_user = os.environ.get("POSTGRES_USER", "capco")
    pg_pass = os.environ.get("POSTGRES_PASSWORD", "capco-regulation-change-me")
    pg_db   = os.environ.get("POSTGRES_DB", "regulation_assistant")

    conn = await asyncpg.connect(
        host=pg_host, port=pg_port, user=pg_user, password=pg_pass, database=pg_db,
    )

    # Bootstrap schema (idempotent)
    await conn.execute("""
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
""")

    record_dirs = sorted(RECORDS_DIR.iterdir())
    ingested = 0
    errors = 0

    for rec_dir in record_dirs:
        article = rec_dir / "article.md"
        if not article.exists():
            logger.warning(f"No article.md in {rec_dir.name}, skipping")
            continue
        try:
            reg = parse_article_md(article)
            await upsert_regulation(conn, reg)
            print(f"✓ {reg['instrument_id']}: {len(reg['milestones'])} milestones, {len(reg['sources'])} sources")
            ingested += 1
        except Exception as exc:
            logger.error(f"Failed to ingest {rec_dir.name}: {exc}")
            errors += 1

    # Embedding pass
    embed_count = await generate_embeddings(conn)

    await conn.close()

    total = len(record_dirs)
    print(f"\nIngested {ingested}/{total} regulations, generated {embed_count} embeddings")
    if errors:
        print(f"WARNING: {errors} errors encountered")


if __name__ == "__main__":
    asyncio.run(main())
