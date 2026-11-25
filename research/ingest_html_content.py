"""
Enhanced ingestion: Parse article.html to extract detailed sections from regulations.ai
(Plain English, Overview, Definitions, Governance, etc.) and store in Postgres.

This supplements the existing article.md ingestion with rich analytical content.

Usage:
    uv run python research/ingest_html_content.py
"""
import asyncio
import logging
import os
import re
from pathlib import Path
from html.parser import HTMLParser

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RECORDS_DIR = Path(__file__).parent / "sources" / "records"

# ---------------------------------------------------------------------------
# HTML Parser
# ---------------------------------------------------------------------------

class RegulationHTMLParser(HTMLParser):
    """Extract sections from regulations.ai article.html"""
    
    def __init__(self):
        super().__init__()
        self.sections = {}
        self.current_section = None
        self.current_text = []
        self.in_summary = False
        self.in_section = False
        
    def handle_starttag(self, tag, attrs):
        # Look for section headers
        if tag in ('h2', 'h3'):
            self.in_section = True
            self.current_text = []
    
    def handle_endtag(self, tag):
        if tag in ('h2', 'h3') and self.in_section:
            section_title = ''.join(self.current_text).strip()
            if section_title:
                self.current_section = section_title
                self.sections[section_title] = []
            self.in_section = False
            self.current_text = []
        elif tag == 'p' and self.current_section:
            text = ''.join(self.current_text).strip()
            if text:
                self.sections[self.current_section].append(text)
            self.current_text = []
    
    def handle_data(self, data):
        self.current_text.append(data)


def extract_sections_from_html(html_path: Path) -> dict:
    """
    Extract structured sections from regulations.ai HTML.
    Returns dict with keys like 'Plain English', 'Overview', 'Definitions', etc.
    """
    html_content = html_path.read_text(encoding='utf-8')
    
    # Use regex to extract key sections (more reliable than HTML parser for this specific structure)
    sections = {}
    
    # Extract Plain English section
    plain_english_match = re.search(
        r'<h2[^>]*>Plain English</h2>(.*?)(?=<h2|$)', 
        html_content, 
        re.DOTALL | re.IGNORECASE
    )
    if plain_english_match:
        # Clean HTML tags
        text = re.sub(r'<[^>]+>', ' ', plain_english_match.group(1))
        text = re.sub(r'\s+', ' ', text).strip()
        sections['plain_english'] = text
    
    # Extract Overview
    overview_match = re.search(
        r'<h2[^>]*>Overview</h2>(.*?)(?=<h2|$)', 
        html_content, 
        re.DOTALL | re.IGNORECASE
    )
    if overview_match:
        text = re.sub(r'<[^>]+>', ' ', overview_match.group(1))
        text = re.sub(r'\s+', ' ', text).strip()
        sections['overview'] = text
    
    # Extract Definitions
    definitions_match = re.search(
        r'<h2[^>]*>Definitions</h2>(.*?)(?=<h2|$)', 
        html_content, 
        re.DOTALL | re.IGNORECASE
    )
    if definitions_match:
        text = re.sub(r'<[^>]+>', ' ', definitions_match.group(1))
        text = re.sub(r'\s+', ' ', text).strip()
        sections['definitions'] = text
    
    # Extract Governance and Institutional Framework
    governance_match = re.search(
        r'<h2[^>]*>Governance and Institutional Framework</h2>(.*?)(?=<h2|$)', 
        html_content, 
        re.DOTALL | re.IGNORECASE
    )
    if governance_match:
        text = re.sub(r'<[^>]+>', ' ', governance_match.group(1))
        text = re.sub(r'\s+', ' ', text).strip()
        sections['governance_framework'] = text
    
    # Extract Key Focus Areas
    focus_match = re.search(
        r'<h2[^>]*>Key Focus Areas</h2>(.*?)(?=<h2|$)', 
        html_content, 
        re.DOTALL | re.IGNORECASE
    )
    if focus_match:
        text = re.sub(r'<[^>]+>', ' ', focus_match.group(1))
        text = re.sub(r'\s+', ' ', text).strip()
        sections['key_focus_areas'] = text
    
    # Extract Implementation Framework
    impl_match = re.search(
        r'<h2[^>]*>Implementation Framework</h2>(.*?)(?=<h2|$)', 
        html_content, 
        re.DOTALL | re.IGNORECASE
    )
    if impl_match:
        text = re.sub(r'<[^>]+>', ' ', impl_match.group(1))
        text = re.sub(r'\s+', ' ', text).strip()
        sections['implementation_framework'] = text
    
    return sections


# ---------------------------------------------------------------------------
# Database schema update
# ---------------------------------------------------------------------------

async def ensure_sections_columns(pool: asyncpg.Pool):
    """Add columns for detailed sections to regulations table"""
    async with pool.acquire() as conn:
        # Check if columns exist
        cols = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'regulations' 
            AND column_name IN ('plain_english', 'overview', 'definitions', 
                                'governance_framework', 'key_focus_areas', 
                                'implementation_framework')
        """)
        existing = {row['column_name'] for row in cols}
        
        # Add missing columns
        columns_to_add = {
            'plain_english': 'TEXT',
            'overview': 'TEXT',
            'definitions': 'TEXT',
            'governance_framework': 'TEXT',
            'key_focus_areas': 'TEXT',
            'implementation_framework': 'TEXT'
        }
        
        for col_name, col_type in columns_to_add.items():
            if col_name not in existing:
                logger.info(f"Adding column: {col_name}")
                await conn.execute(f"""
                    ALTER TABLE regulations 
                    ADD COLUMN {col_name} {col_type}
                """)
        
        logger.info("✅ Schema updated with section columns")


# ---------------------------------------------------------------------------
# Main ingestion
# ---------------------------------------------------------------------------

async def ingest_html_sections():
    """Parse all article.html files and update regulations table with detailed sections"""
    
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
        await ensure_sections_columns(pool)
        
        # Process each regulation directory
        reg_dirs = [d for d in RECORDS_DIR.iterdir() if d.is_dir()]
        logger.info(f"Found {len(reg_dirs)} regulation directories")
        
        success_count = 0
        skip_count = 0
        
        for reg_dir in sorted(reg_dirs):
            instrument_id = reg_dir.name
            html_path = reg_dir / "article.html"
            
            if not html_path.exists():
                logger.warning(f"⚠️  {instrument_id}: No article.html")
                skip_count += 1
                continue
            
            # Extract sections
            sections = extract_sections_from_html(html_path)
            
            if not sections:
                logger.warning(f"⚠️  {instrument_id}: No sections extracted")
                skip_count += 1
                continue
            
            # Update database
            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE regulations
                    SET plain_english = $2,
                        overview = $3,
                        definitions = $4,
                        governance_framework = $5,
                        key_focus_areas = $6,
                        implementation_framework = $7
                    WHERE instrument_id = $1
                """, instrument_id, 
                    sections.get('plain_english'),
                    sections.get('overview'),
                    sections.get('definitions'),
                    sections.get('governance_framework'),
                    sections.get('key_focus_areas'),
                    sections.get('implementation_framework'))
            
            section_names = ', '.join(sections.keys())
            logger.info(f"✅ {instrument_id}: Updated with sections: {section_names}")
            success_count += 1
        
        logger.info(f"\n{'='*60}")
        logger.info(f"HTML Ingestion Complete:")
        logger.info(f"  ✅ Updated: {success_count}")
        logger.info(f"  ⚠️  Skipped: {skip_count}")
        logger.info(f"{'='*60}")
        
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(ingest_html_sections())
