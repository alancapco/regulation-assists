"""
Update topics for all regulations from regulation_records_full.jsonl.

This script reads the topic_keywords field from the JSONL file and updates
the topics array in the Postgres database.

Usage:
    uv run python research/update_topics.py
"""
import asyncio
import json
import logging
import os
from pathlib import Path

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
RECORDS_FILE = DATA_DIR / "regulation_records_full.jsonl"


async def update_topics():
    """Update topics for all regulations from the JSONL file."""
    pg_host = os.environ.get("POSTGRES_HOST", "localhost")
    pg_port = int(os.environ.get("POSTGRES_PORT", "5433"))
    pg_user = os.environ.get("POSTGRES_USER", "capco")
    pg_pass = os.environ.get("POSTGRES_PASSWORD", "capco-regulation-change-me")
    pg_db = os.environ.get("POSTGRES_DB", "regulation_assistant")

    conn = await asyncpg.connect(
        host=pg_host, port=pg_port, user=pg_user, password=pg_pass, database=pg_db
    )

    try:
        updated = 0
        skipped = 0
        not_found = 0

        with open(RECORDS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                record = json.loads(line.strip())
                instrument_id = record.get("instrument_id")
                topic_keywords = record.get("topic_keywords", "")

                if not instrument_id:
                    skipped += 1
                    continue

                # Parse topic_keywords: comma-separated string
                if topic_keywords:
                    topics = [t.strip() for t in topic_keywords.split(",") if t.strip()]
                else:
                    topics = []

                # Update the database
                result = await conn.execute(
                    "UPDATE regulations SET topics = $1 WHERE instrument_id = $2",
                    topics,
                    instrument_id
                )

                # Check if row was actually updated
                if result == "UPDATE 1":
                    updated += 1
                    if topics:
                        logger.info(f"✓ {instrument_id}: {len(topics)} topics")
                else:
                    not_found += 1
                    logger.warning(f"✗ {instrument_id}: not found in database")

        logger.info(f"\nSummary:")
        logger.info(f"  Updated: {updated}")
        logger.info(f"  Skipped (no instrument_id): {skipped}")
        logger.info(f"  Not found in DB: {not_found}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(update_topics())
