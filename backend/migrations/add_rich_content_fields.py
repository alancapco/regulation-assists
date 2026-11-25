#!/usr/bin/env python3
"""
Migration: Add rich content fields to regulations table.

Adds:
- Text fields: summary, monitoring_evaluation, penalties_liability,
  relationship_to_other, international_alignment, implementation_timeline
- JSONB fields: requirements_must_do, requirements_should_do,
  requirements_must_not_do, requirements_should_not_do, obligations
"""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

import asyncio
import os

import asyncpg


async def migrate():
    conn = await asyncpg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5433")),
        user=os.getenv("POSTGRES_USER", "capco"),
        password=os.getenv("POSTGRES_PASSWORD", "capco-regulation-change-me"),
        database=os.getenv("POSTGRES_DB", "regulation_assistant"),
    )

    try:
        print("Adding new columns to regulations table...")

        await conn.execute("""
            ALTER TABLE regulations
            ADD COLUMN IF NOT EXISTS summary TEXT DEFAULT '',
            ADD COLUMN IF NOT EXISTS monitoring_evaluation TEXT DEFAULT '',
            ADD COLUMN IF NOT EXISTS penalties_liability TEXT DEFAULT '',
            ADD COLUMN IF NOT EXISTS relationship_to_other TEXT DEFAULT '',
            ADD COLUMN IF NOT EXISTS international_alignment TEXT DEFAULT '',
            ADD COLUMN IF NOT EXISTS implementation_timeline TEXT DEFAULT '';
        """)

        print("✓ Added text fields")

        await conn.execute("""
            ALTER TABLE regulations
            ADD COLUMN IF NOT EXISTS requirements_must_do JSONB DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS requirements_should_do JSONB DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS requirements_must_not_do JSONB DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS requirements_should_not_do JSONB DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS obligations JSONB DEFAULT '[]'::jsonb;
        """)

        print("✓ Added JSONB fields")

        columns = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'regulations'
            ORDER BY column_name;
        """)

        print(f"\n✓ Migration complete. Table now has {len(columns)} columns:")
        for col in columns:
            print(f"  - {col['column_name']}: {col['data_type']}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
