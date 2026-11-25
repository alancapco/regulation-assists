"""
Scrape ALL information from regulations.ai for all 30 regulations using Firecrawl.
Processes in 8 batches to manage rate limits and resources.

Set FIRECRAWL_API_KEY in the environment.

Usage:
    uv run python research/scrape_regulations_ai.py
    
Output:
    - Updates article.html with latest content
    - Creates article_full.json with structured data
    - Updates Postgres with all extracted sections
"""

import research._env  # noqa: F401  # load repo-root .env
import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx
import asyncpg

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RECORDS_DIR = Path(__file__).parent / "sources" / "records"

FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
FIRECRAWL_BASE_URL = "https://api.firecrawl.dev/v1"

# Batch configuration
BATCH_SIZE = 4  # 30 regulations / 8 batches ≈ 4 per batch
BATCH_DELAY = 5  # seconds between batches


async def scrape_with_firecrawl(url: str, client: httpx.AsyncClient) -> dict | None:
    """
    Scrape a URL using Firecrawl API.
    Returns structured content including markdown, HTML, and metadata.
    """
    try:
        response = await client.post(
            f"{FIRECRAWL_BASE_URL}/scrape",
            json={
                "url": url,
                "formats": ["markdown", "html", "rawHtml"],
                "onlyMainContent": False,  # Get everything
                "waitFor": 2000,  # Wait 2s for dynamic content
            },
            headers={
                "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("data", {})
        else:
            logger.error(f"Firecrawl error {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to scrape {url}: {e}")
        return None


def extract_sections_from_firecrawl(data: dict) -> dict:
    """
    Extract structured sections from Firecrawl response.
    Uses both markdown and HTML content.
    """
    sections = {}
    
    markdown = data.get("markdown", "")
    html = data.get("html", "")
    
    # Extract sections from markdown (cleaner)
    import re
    
    # Plain English
    match = re.search(r'##\s*Plain English\s*\n(.*?)(?=\n##|\Z)', markdown, re.DOTALL | re.IGNORECASE)
    if match:
        sections['plain_english'] = match.group(1).strip()
    
    # Overview
    match = re.search(r'##\s*Overview\s*\n(.*?)(?=\n##|\Z)', markdown, re.DOTALL | re.IGNORECASE)
    if match:
        sections['overview'] = match.group(1).strip()
    
    # Definitions
    match = re.search(r'##\s*Definitions?\s*\n(.*?)(?=\n##|\Z)', markdown, re.DOTALL | re.IGNORECASE)
    if match:
        sections['definitions'] = match.group(1).strip()
    
    # Governance and Institutional Framework
    match = re.search(r'##\s*Governance and Institutional Framework\s*\n(.*?)(?=\n##|\Z)', markdown, re.DOTALL | re.IGNORECASE)
    if match:
        sections['governance_framework'] = match.group(1).strip()
    
    # Key Focus Areas
    match = re.search(r'##\s*Key Focus Areas\s*\n(.*?)(?=\n##|\Z)', markdown, re.DOTALL | re.IGNORECASE)
    if match:
        sections['key_focus_areas'] = match.group(1).strip()
    
    # Implementation Framework
    match = re.search(r'##\s*Implementation Framework\s*\n(.*?)(?=\n##|\Z)', markdown, re.DOTALL | re.IGNORECASE)
    if match:
        sections['implementation_framework'] = match.group(1).strip()
    
    # Monitoring and Evaluation
    match = re.search(r'##\s*Monitoring and Evaluation\s*\n(.*?)(?=\n##|\Z)', markdown, re.DOTALL | re.IGNORECASE)
    if match:
        sections['monitoring_evaluation'] = match.group(1).strip()
    
    # Penalties and Liability
    match = re.search(r'##\s*Penalties.*Liability.*Appeals?\s*\n(.*?)(?=\n##|\Z)', markdown, re.DOTALL | re.IGNORECASE)
    if match:
        sections['penalties_liability'] = match.group(1).strip()
    
    # Relationship to Other Instruments
    match = re.search(r'##\s*Relationship to Other Instruments\s*\n(.*?)(?=\n##|\Z)', markdown, re.DOTALL | re.IGNORECASE)
    if match:
        sections['relationship_other'] = match.group(1).strip()
    
    # International Alignment
    match = re.search(r'##\s*International Alignment\s*\n(.*?)(?=\n##|\Z)', markdown, re.DOTALL | re.IGNORECASE)
    if match:
        sections['international_alignment'] = match.group(1).strip()
    
    # Compliance Checklist
    match = re.search(r'##\s*Compliance Checklist\s*\n(.*?)(?=\n##|\Z)', markdown, re.DOTALL | re.IGNORECASE)
    if match:
        sections['compliance_checklist'] = match.group(1).strip()
    
    return sections


async def process_batch(
    batch: list[tuple[str, Path]], 
    batch_num: int, 
    total_batches: int,
    pool: asyncpg.Pool
) -> tuple[int, int]:
    """Process one batch of regulations. Returns (success_count, skip_count)."""
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Batch {batch_num}/{total_batches}: Processing {len(batch)} regulations")
    logger.info(f"{'='*60}")
    
    success_count = 0
    skip_count = 0
    
    async with httpx.AsyncClient() as client:
        for instrument_id, reg_dir in batch:
            record_url = f"https://regulations.ai/regulations/{instrument_id}"
            logger.info(f"Scraping {instrument_id}...")
            
            # Scrape with Firecrawl
            data = await scrape_with_firecrawl(record_url, client)
            
            if not data:
                logger.warning(f"⚠️  {instrument_id}: Scraping failed")
                skip_count += 1
                continue
            
            # Save full response
            full_json_path = reg_dir / "article_full.json"
            with open(full_json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Save updated HTML
            if 'html' in data:
                html_path = reg_dir / "article.html"
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(data['html'])
            
            # Extract sections
            sections = extract_sections_from_firecrawl(data)
            
            if not sections:
                logger.warning(f"⚠️  {instrument_id}: No sections extracted")
                skip_count += 1
                continue
            
            # Update Postgres
            async with pool.acquire() as conn:
                # Build dynamic UPDATE query for available sections
                update_fields = []
                values = [instrument_id]
                param_num = 2
                
                section_mapping = {
                    'plain_english': sections.get('plain_english'),
                    'overview': sections.get('overview'),
                    'definitions': sections.get('definitions'),
                    'governance_framework': sections.get('governance_framework'),
                    'key_focus_areas': sections.get('key_focus_areas'),
                    'implementation_framework': sections.get('implementation_framework'),
                    'monitoring_evaluation': sections.get('monitoring_evaluation'),
                    'penalties_liability': sections.get('penalties_liability'),
                    'relationship_other': sections.get('relationship_other'),
                    'international_alignment': sections.get('international_alignment'),
                    'compliance_checklist': sections.get('compliance_checklist'),
                }
                
                for col, val in section_mapping.items():
                    if val:
                        update_fields.append(f"{col} = ${param_num}")
                        values.append(val)
                        param_num += 1
                
                if update_fields:
                    query = f"""
                        UPDATE regulations 
                        SET {', '.join(update_fields)}
                        WHERE instrument_id = $1
                    """
                    await conn.execute(query, *values)
            
            section_names = ', '.join(sections.keys())
            logger.info(f"✅ {instrument_id}: Updated with {len(sections)} sections: {section_names}")
            success_count += 1
            
            # Small delay between requests
            await asyncio.sleep(1)
    
    return success_count, skip_count


async def main():
    """Main scraping workflow."""
    
    # Connect to Postgres
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5433"))
    user = os.getenv("POSTGRES_USER", "capco")
    password = os.getenv("POSTGRES_PASSWORD", "capco-regulation-change-me")
    database = os.getenv("POSTGRES_DB", "regulation_assistant")
    
    pool = await asyncpg.create_pool(
        host=host, port=port, user=user, password=password, database=database,
        min_size=1, max_size=5
    )
    
    try:
        # Ensure additional columns exist
        async with pool.acquire() as conn:
            await conn.execute("""
                ALTER TABLE regulations 
                ADD COLUMN IF NOT EXISTS monitoring_evaluation TEXT,
                ADD COLUMN IF NOT EXISTS penalties_liability TEXT,
                ADD COLUMN IF NOT EXISTS relationship_other TEXT,
                ADD COLUMN IF NOT EXISTS international_alignment TEXT,
                ADD COLUMN IF NOT EXISTS compliance_checklist TEXT
            """)
            logger.info("✅ Schema updated with additional columns")
        
        # Get all regulation directories
        reg_dirs = [(d.name, d) for d in RECORDS_DIR.iterdir() if d.is_dir()]
        reg_dirs.sort()  # Consistent order
        
        total = len(reg_dirs)
        logger.info(f"Found {total} regulations")
        
        # Split into 8 batches
        batch_size = (total + 7) // 8  # Ceiling division
        batches = [reg_dirs[i:i + batch_size] for i in range(0, total, batch_size)]
        
        logger.info(f"Split into {len(batches)} batches (batch size: {batch_size})")
        
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
        logger.info(f"SCRAPING COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"  ✅ Successfully scraped: {total_success}/{total}")
        logger.info(f"  ⚠️  Skipped/failed: {total_skip}/{total}")
        logger.info(f"{'='*60}")
        
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
