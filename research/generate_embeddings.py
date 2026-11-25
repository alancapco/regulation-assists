"""
Generate OpenAI embeddings for all regulations missing embeddings in Postgres.

Usage:
    uv run python research/generate_embeddings.py

Env vars:
    OPENAI_API_KEY   — required for embedding generation
    POSTGRES_HOST    — default localhost
    POSTGRES_PORT    — default 5433
    POSTGRES_USER    — default capco
    POSTGRES_PASSWORD — default capco-regulation-change-me
    POSTGRES_DB      — default regulation_assistant
"""
import research._env  # noqa: F401  # load repo-root .env

import asyncio
import logging
import os
import sys

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def generate_embeddings(conn: asyncpg.Connection) -> int:
    """Generate embeddings for all regulations where embedding IS NULL."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        logger.error("OPENAI_API_KEY not set — cannot generate embeddings")
        return 0

    try:
        from openai import OpenAI
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        client = OpenAI(api_key=api_key, base_url=base_url)
    except ImportError:
        logger.error("openai package not available — please install: pip install openai")
        return 0

    # Query regulations missing embeddings
    rows = await conn.fetch(
        "SELECT instrument_id, name, jurisdiction, resume, description, topics "
        "FROM regulations WHERE embedding IS NULL"
    )
    
    if not rows:
        logger.info("All embeddings already present, nothing to generate")
        return 0

    total = len(rows)
    logger.info(f"Found {total} regulations missing embeddings")

    count = 0
    failed = 0
    
    for idx, row in enumerate(rows, 1):
        # Build embedding text from multiple fields
        topics_str = ", ".join(row["topics"] or [])
        content = row["resume"] or row["description"] or ""
        embed_text = f"{row['name']}. {row['jurisdiction']}. {content}. Topics: {topics_str}"
        
        try:
            # Use text-embedding-3-small (1536 dimensions)
            resp = client.embeddings.create(
                model="text-embedding-3-small",
                input=[embed_text]
            )
            vector = resp.data[0].embedding
            
            # Convert list to pgvector string format: '[x,y,z,...]'
            vector_str = "[" + ",".join(str(v) for v in vector) + "]"
            
            await conn.execute(
                "UPDATE regulations SET embedding = $1 WHERE instrument_id = $2",
                vector_str, row["instrument_id"],
            )
            count += 1
            
            # Progress indicator
            if count % 10 == 0 or count == total:
                logger.info(f"Progress: {count}/{total} completed ({count*100//total}%)")
                
        except Exception as exc:
            logger.warning(f"Embedding failed for {row['instrument_id']}: {exc}")
            failed += 1

    logger.info(f"Successfully generated {count} embeddings")
    if failed > 0:
        logger.warning(f"Failed to generate {failed} embeddings")
    
    return count


async def main() -> None:
    pg_host = os.environ.get("POSTGRES_HOST", "localhost")
    pg_port = int(os.environ.get("POSTGRES_PORT", "5433"))
    pg_user = os.environ.get("POSTGRES_USER", "capco")
    pg_pass = os.environ.get("POSTGRES_PASSWORD", "capco-regulation-change-me")
    pg_db   = os.environ.get("POSTGRES_DB", "regulation_assistant")

    logger.info(f"Connecting to Postgres at {pg_host}:{pg_port}/{pg_db}")
    
    try:
        conn = await asyncpg.connect(
            host=pg_host, port=pg_port, user=pg_user, password=pg_pass, database=pg_db,
        )
    except Exception as exc:
        logger.error(f"Failed to connect to database: {exc}")
        sys.exit(1)

    # Check current status
    total_regs = await conn.fetchval("SELECT COUNT(*) FROM regulations")
    with_embeddings = await conn.fetchval("SELECT COUNT(*) FROM regulations WHERE embedding IS NOT NULL")
    without_embeddings = total_regs - with_embeddings
    
    logger.info(f"Database status: {total_regs} total regulations")
    logger.info(f"  - {with_embeddings} with embeddings ({with_embeddings*100//total_regs if total_regs else 0}%)")
    logger.info(f"  - {without_embeddings} missing embeddings ({without_embeddings*100//total_regs if total_regs else 0}%)")
    
    # Generate embeddings
    embed_count = await generate_embeddings(conn)

    # Final status
    with_embeddings_after = await conn.fetchval("SELECT COUNT(*) FROM regulations WHERE embedding IS NOT NULL")
    
    await conn.close()

    print(f"\n{'='*60}")
    print(f"SUMMARY:")
    print(f"  Total regulations: {total_regs}")
    print(f"  Before: {with_embeddings} with embeddings")
    print(f"  After:  {with_embeddings_after} with embeddings")
    print(f"  Generated: {embed_count} new embeddings")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
