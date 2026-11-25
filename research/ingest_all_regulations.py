"""
Download and ingest ALL regulations from instruments.csv into Postgres.

This processes all 1,175 regulations in batches of ~147 (8 batches total).
Uses the same approach as the original ingestion but for the full dataset.

Usage:
    uv run python research/ingest_all_regulations.py
"""

import research._env  # noqa: F401  # load repo-root .env
import asyncio
import csv
import logging
import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
RECORDS_DIR = Path(__file__).parent / "sources" / "records"
INSTRUMENTS_CSV = DATA_DIR / "instruments.csv"

# Batch configuration
BATCH_SIZE = 147  # 1175 / 8 ≈ 147 per batch
BATCH_DELAY = 5  # seconds between batches


def extract_sections_from_html(html: str) -> dict:
    """Extract structured sections from regulations.ai HTML using regex."""
    sections = {}
    
    # Plain English
    match = re.search(r'<h2[^>]*>\s*Plain English\s*</h2>(.*?)(?=<h2|$)', html, re.DOTALL | re.IGNORECASE)
    if match:
        text = re.sub(r'<[^>]+>', ' ', match.group(1))
        text = re.sub(r'\s+', ' ', text).strip()
        if text:
            sections['plain_english'] = text
    
    # Overview
    match = re.search(r'<h2[^>]*>\s*Overview\s*</h2>(.*?)(?=<h2|$)', html, re.DOTALL | re.IGNORECASE)
    if match:
        text = re.sub(r'<[^>]+>', ' ', match.group(1))
        text = re.sub(r'\s+', ' ', text).strip()
        if text:
            sections['overview'] = text
    
    # Definitions
    match = re.search(r'<h2[^>]*>\s*Definitions?\s*</h2>(.*?)(?=<h2|$)', html, re.DOTALL | re.IGNORECASE)
    if match:
        text = re.sub(r'<[^>]+>', ' ', match.group(1))
        text = re.sub(r'\s+', ' ', text).strip()
        if text:
            sections['definitions'] = text
    
    # Governance and Institutional Framework
    match = re.search(r'<h2[^>]*>\s*Governance and Institutional Framework\s*</h2>(.*?)(?=<h2|$)', html, re.DOTALL | re.IGNORECASE)
    if match:
        text = re.sub(r'<[^>]+>', ' ', match.group(1))
        text = re.sub(r'\s+', ' ', text).strip()
        if text:
            sections['governance_framework'] = text
    
    # Key Focus Areas
    match = re.search(r'<h2[^>]*>\s*Key Focus Areas\s*</h2>(.*?)(?=<h2|$)', html, re.DOTALL | re.IGNORECASE)
    if match:
        text = re.sub(r'<[^>]+>', ' ', match.group(1))
        text = re.sub(r'\s+', ' ', text).strip()
        if text:
            sections['key_focus_areas'] = text
    
    # Implementation Framework
    match = re.search(r'<h2[^>]*>\s*Implementation Framework\s*</h2>(.*?)(?=<h2|$)', html, re.DOTALL | re.IGNORECASE)
    if match:
        text = re.sub(r'<[^>]+>', ' ', match.group(1))
        text = re.sub(r'\s+', ' ', text).strip()
        if text:
            sections['implementation_framework'] = text
    
    return sections


async def download_regulation(instrument_id: str, record_url: str, client: httpx.AsyncClient, max_retries: int = 3) -> str | None:
    """Download HTML from regulations.ai with retry logic for 403 errors."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://regulations.ai/',
    }
    
    for attempt in range(max_retries):
        try:
            response = await client.get(record_url, headers=headers, timeout=30.0, follow_redirects=True)
            if response.status_code == 200:
                return response.text
            elif response.status_code == 403:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 2s, 4s, 6s
                    logger.warning(f"{instrument_id}: HTTP 403, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                else:
                    logger.warning(f"{instrument_id}: HTTP 403 after {max_retries} attempts, skipping")
                    return None
            else:
                logger.warning(f"{instrument_id}: HTTP {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"{instrument_id}: Download failed - {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
            else:
                return None
    
    return None


async def process_batch(
    batch: list[dict],
    batch_num: int,
    total_batches: int,
    pool: asyncpg.Pool
) -> tuple[int, int]:
    """Process one batch. Returns (success_count, skip_count)."""
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Batch {batch_num}/{total_batches}: Processing {len(batch)} regulations")
    logger.info(f"{'='*60}")
    
    success_count = 0
    skip_count = 0
    
    async with httpx.AsyncClient() as client:
        for row in batch:
            instrument_id = row['instrument_id']
            record_url = row['record_url']
            
            # Check if already exists in database
            async with pool.acquire() as conn:
                exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM regulations WHERE instrument_id = $1)",
                    instrument_id
                )
            
            if exists:
                logger.info(f"⏭️  {instrument_id}: Already in database, skipping")
                skip_count += 1
                continue
            
            logger.info(f"📥 {instrument_id}: Downloading...")
            
            # Download HTML
            html = await download_regulation(instrument_id, record_url, client)
            if not html:
                skip_count += 1
                continue
            
            # Save HTML to disk
            reg_dir = RECORDS_DIR / instrument_id
            reg_dir.mkdir(parents=True, exist_ok=True)
            (reg_dir / "article.html").write_text(html, encoding='utf-8')
            
            # Extract sections
            sections = extract_sections_from_html(html)
            
            # Insert into database (basic info + sections)
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO regulations (
                        instrument_id, name, jurisdiction, type, legal_force,
                        record_url, plain_english, overview, definitions,
                        governance_framework, key_focus_areas, implementation_framework
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    ON CONFLICT (instrument_id) DO UPDATE SET
                        plain_english = EXCLUDED.plain_english,
                        overview = EXCLUDED.overview,
                        definitions = EXCLUDED.definitions,
                        governance_framework = EXCLUDED.governance_framework,
                        key_focus_areas = EXCLUDED.key_focus_areas,
                        implementation_framework = EXCLUDED.implementation_framework
                """,
                    instrument_id,
                    row.get('title', ''),
                    row.get('jurisdiction', ''),
                    row.get('instrument_type', ''),
                    row.get('status', ''),
                    record_url,
                    sections.get('plain_english'),
                    sections.get('overview'),
                    sections.get('definitions'),
                    sections.get('governance_framework'),
                    sections.get('key_focus_areas'),
                    sections.get('implementation_framework')
                )
            
            section_count = len([v for v in sections.values() if v])
            logger.info(f"✅ {instrument_id}: Saved with {section_count} sections")
            success_count += 1
            
            # Small delay between requests - increased to avoid rate limiting
            await asyncio.sleep(1.5)
    
    return success_count, skip_count


async def main():
    """Main ingestion workflow."""
    
    # Read instruments.csv
    if not INSTRUMENTS_CSV.exists():
        logger.error(f"instruments.csv not found at {INSTRUMENTS_CSV}")
        return
    
    regulations = []
    with open(INSTRUMENTS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        regulations = list(reader)
    
    total = len(regulations)
    logger.info(f"Loaded {total} regulations from instruments.csv")
    
    # Connect to Postgres
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5433"))
    user = os.getenv("POSTGRES_USER", "capco")
    password = os.getenv("POSTGRES_PASSWORD", "capco-regulation-change-me")
    database = os.getenv("POSTGRES_DB", "regulation_assistant")
    
    pool = await asyncpg.create_pool(
        host=host, port=port, user=user, password=password, database=database,
        min_size=2, max_size=10
    )
    
    try:
        # Split into 8 batches
        batches = [regulations[i:i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
        logger.info(f"Split into {len(batches)} batches (batch size: ~{BATCH_SIZE})")
        
        total_success = 0
        total_skip = 0
        
        # Process each batch
        for i, batch in enumerate(batches, 1):
            success, skip = await process_batch(batch, i, len(batches), pool)
            total_success += success
            total_skip += skip
            
            # Delay between batches (except last)
            if i < len(batches):
                logger.info(f"\n⏳ Waiting {BATCH_DELAY}s before next batch...")
                await asyncio.sleep(BATCH_DELAY)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"INGESTION COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"  ✅ Successfully ingested: {total_success}/{total}")
        logger.info(f"  ⏭️  Skipped (already exist): {total_skip}/{total}")
        logger.info(f"{'='*60}")
        
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
