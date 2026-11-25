"""
Retry ingestion for failed regulations with improved rate limiting and retry logic.
Uses longer delays, browser-like headers, and exponential backoff.

Usage:
    uv run python research/ingest_retry_failed.py
"""

import research._env  # noqa: F401  # load repo-root .env
import asyncio
import csv
import logging
import os
import re
import time
from pathlib import Path
import random

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
RECORDS_DIR = Path(__file__).parent / "sources" / "records"
INSTRUMENTS_CSV = DATA_DIR / "instruments.csv"

# Improved rate limiting
MIN_DELAY = 2.0  # Minimum 2 seconds between requests
MAX_DELAY = 4.0  # Maximum 4 seconds between requests
BATCH_SIZE = 50  # Smaller batches
BATCH_DELAY = 10  # 10 seconds between batches
MAX_RETRIES = 3  # Retry failed requests up to 3 times

# Rotate through multiple user agents
USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]


def extract_sections_from_html(html: str) -> dict:
    """Extract structured sections from regulations.ai HTML using regex."""
    sections = {}
    
    section_patterns = [
        ('plain_english', r'<h2[^>]*>\s*Plain English\s*</h2>(.*?)(?=<h2|$)'),
        ('overview', r'<h2[^>]*>\s*Overview\s*</h2>(.*?)(?=<h2|$)'),
        ('definitions', r'<h2[^>]*>\s*Definitions?\s*</h2>(.*?)(?=<h2|$)'),
        ('governance_framework', r'<h2[^>]*>\s*Governance and Institutional Framework\s*</h2>(.*?)(?=<h2|$)'),
        ('key_focus_areas', r'<h2[^>]*>\s*Key Focus Areas\s*</h2>(.*?)(?=<h2|$)'),
        ('implementation_framework', r'<h2[^>]*>\s*Implementation Framework\s*</h2>(.*?)(?=<h2|$)'),
    ]
    
    for key, pattern in section_patterns:
        match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
        if match:
            text = re.sub(r'<[^>]+>', ' ', match.group(1))
            text = re.sub(r'\s+', ' ', text).strip()
            if text and len(text) > 50:  # Only keep substantial sections
                sections[key] = text
    
    return sections


async def download_with_retry(instrument_id: str, record_url: str, client: httpx.AsyncClient) -> str | None:
    """Download with exponential backoff retry logic."""
    
    for attempt in range(MAX_RETRIES):
        # Rotate user agent
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            # Don't set Accept-Encoding - let httpx handle compression automatically
            'Referer': 'https://regulations.ai/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        try:
            response = await client.get(record_url, headers=headers, timeout=30.0, follow_redirects=True)
            
            if response.status_code == 200:
                return response.text
            elif response.status_code == 403:
                if attempt < MAX_RETRIES - 1:
                    # Exponential backoff: 5s, 15s, 30s
                    wait_time = 5 * (3 ** attempt)
                    logger.warning(f"{instrument_id}: 403 Forbidden, waiting {wait_time}s (attempt {attempt + 1}/{MAX_RETRIES})")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"{instrument_id}: 403 after {MAX_RETRIES} attempts")
                    return None
            elif response.status_code == 429:  # Rate limit
                wait_time = 30
                logger.warning(f"{instrument_id}: Rate limited (429), waiting {wait_time}s")
                await asyncio.sleep(wait_time)
            else:
                logger.warning(f"{instrument_id}: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"{instrument_id}: {type(e).__name__}: {e}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(3)
    
    return None


async def process_batch(
    batch: list[dict],
    batch_num: int,
    total_batches: int,
    pool: asyncpg.Pool
) -> tuple[int, int]:
    """Process one batch with improved rate limiting."""
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Batch {batch_num}/{total_batches}: Processing {len(batch)} regulations")
    logger.info(f"{'='*60}")
    
    success_count = 0
    skip_count = 0
    
    async with httpx.AsyncClient() as client:
        for idx, row in enumerate(batch, 1):
            instrument_id = row['instrument_id']
            record_url = row['record_url']
            
            # Check if already exists
            async with pool.acquire() as conn:
                exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM regulations WHERE instrument_id = $1)",
                    instrument_id
                )
            
            if exists:
                skip_count += 1
                continue
            
            logger.info(f"[{idx}/{len(batch)}] 📥 {instrument_id}")
            
            # Download with retry
            html = await download_with_retry(instrument_id, record_url, client)
            if not html:
                skip_count += 1
                continue
            
            # Save HTML
            reg_dir = RECORDS_DIR / instrument_id
            reg_dir.mkdir(parents=True, exist_ok=True)
            (reg_dir / "article.html").write_text(html, encoding='utf-8')
            
            # Extract sections
            sections = extract_sections_from_html(html)
            
            # Insert into database
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
            logger.info(f"   ✅ Saved with {section_count} sections")
            success_count += 1
            
            # Random delay between requests to appear more human-like
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            await asyncio.sleep(delay)
    
    return success_count, skip_count


async def main():
    """Main retry workflow - only process regulations not yet in database."""
    
    # Read instruments.csv
    if not INSTRUMENTS_CSV.exists():
        logger.error(f"instruments.csv not found at {INSTRUMENTS_CSV}")
        return
    
    regulations = []
    with open(INSTRUMENTS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        regulations = list(reader)
    
    logger.info(f"Loaded {len(regulations)} regulations from CSV")
    
    # Connect to Postgres
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5433"))
    user = os.getenv("POSTGRES_USER", "capco")
    password = os.getenv("POSTGRES_PASSWORD", "capco-regulation-change-me")
    database = os.getenv("POSTGRES_DB", "regulation_assistant")
    
    pool = await asyncpg.create_pool(
        host=host, port=port, user=user, password=password, database=database,
        min_size=2, max_size=5
    )
    
    try:
        # Get list of already-ingested regulations
        async with pool.acquire() as conn:
            existing_ids = await conn.fetch("SELECT instrument_id FROM regulations")
            existing_set = {row['instrument_id'] for row in existing_ids}
        
        logger.info(f"Found {len(existing_set)} regulations already in database")
        
        # Filter to only missing regulations
        missing = [r for r in regulations if r['instrument_id'] not in existing_set]
        logger.info(f"Need to fetch {len(missing)} missing regulations")
        
        if not missing:
            logger.info("✅ All regulations already in database!")
            return
        
        # Split into batches
        batches = [missing[i:i + BATCH_SIZE] for i in range(0, len(missing), BATCH_SIZE)]
        logger.info(f"Split into {len(batches)} batches of ~{BATCH_SIZE}")
        
        total_success = 0
        total_skip = 0
        
        # Process each batch
        for i, batch in enumerate(batches, 1):
            success, skip = await process_batch(batch, i, len(batches), pool)
            total_success += success
            total_skip += skip
            
            # Longer delay between batches
            if i < len(batches):
                logger.info(f"\n⏳ Waiting {BATCH_DELAY}s before next batch...")
                await asyncio.sleep(BATCH_DELAY)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"RETRY INGESTION COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"  ✅ Successfully ingested: {total_success}/{len(missing)}")
        logger.info(f"  ❌ Failed/skipped: {total_skip}/{len(missing)}")
        logger.info(f"{'='*60}")
        
        # Final database count
        async with pool.acquire() as conn:
            final_count = await conn.fetchval("SELECT COUNT(*) FROM regulations")
            logger.info(f"📊 Total regulations in database: {final_count}")
        
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
