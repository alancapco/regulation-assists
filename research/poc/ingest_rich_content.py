#!/usr/bin/env python3
"""
Re-ingest all 1,174 regulations with rich content from article.html files.

This script:
1. Reads all article.html files from research/sources/records/
2. Parses rich content using parse_rich_content_v3.py
3. Updates Postgres with the new data
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any

import asyncpg
from bs4 import BeautifulSoup

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from parse_rich_content_v3 import parse_rich_content


async def update_regulation_rich_content(conn: asyncpg.Connection, instrument_id: str, rich_data: Dict[str, Any]):
    """Update a regulation with rich content data."""
    # asyncpg automatically converts Python lists/dicts to JSONB when the column type is jsonb
    await conn.execute("""
        UPDATE regulations SET
            summary = $2,
            monitoring_evaluation = $3,
            penalties_liability = $4,
            relationship_to_other = $5,
            international_alignment = $6,
            implementation_timeline = $7,
            requirements_must_do = $8,
            requirements_should_do = $9,
            requirements_must_not_do = $10,
            requirements_should_not_do = $11,
            obligations = $12
        WHERE instrument_id = $1
    """,
        instrument_id,
        rich_data['summary'],
        rich_data['monitoring_evaluation'],
        rich_data['penalties_liability'],
        rich_data['relationship_to_other'],
        rich_data['international_alignment'],
        rich_data['implementation_timeline'],
        rich_data['requirements_must_do'],
        rich_data['requirements_should_do'],
        rich_data['requirements_must_not_do'],
        rich_data['requirements_should_not_do'],
        rich_data['obligations'],
    )


async def main():
    ROOT = Path(__file__).resolve().parents[2]  # Go up 2 levels: poc -> research -> project root
    records_dir = ROOT / "research/sources/records"
    
    if not records_dir.exists():
        print(f"ERROR: Records directory not found: {records_dir}")
        return
    
    # Get all regulation directories
    reg_dirs = sorted([d for d in records_dir.iterdir() if d.is_dir()])
    print(f"Found {len(reg_dirs)} regulation directories")
    
    # Connect to Postgres
    conn = await asyncpg.connect(
        host='localhost',
        port=5433,
        user='capco',
        password='capco-regulation-change-me',
        database='regulation_assistant'
    )
    
    try:
        success_count = 0
        fail_count = 0
        no_html_count = 0
        
        for i, reg_dir in enumerate(reg_dirs, 1):
            instrument_id = reg_dir.name
            html_file = reg_dir / "article.html"
            
            if not html_file.exists():
                no_html_count += 1
                if i % 100 == 0:
                    print(f"  [{i}/{len(reg_dirs)}] {instrument_id}: no article.html")
                continue
            
            try:
                # Parse rich content
                rich_data = parse_rich_content(html_file)
                
                # Update database
                await update_regulation_rich_content(conn, instrument_id, rich_data)
                
                success_count += 1
                
                # Progress update
                if i % 100 == 0:
                    print(f"  [{i}/{len(reg_dirs)}] Processed {success_count} successfully, {fail_count} failed, {no_html_count} missing HTML")
                
            except Exception as e:
                fail_count += 1
                if fail_count <= 10:  # Show first 10 errors
                    print(f"  ERROR processing {instrument_id}: {e}")
        
        print(f"\n=== Final Summary ===")
        print(f"Total regulations: {len(reg_dirs)}")
        print(f"Successfully updated: {success_count}")
        print(f"Failed: {fail_count}")
        print(f"Missing article.html: {no_html_count}")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
