#!/usr/bin/env python3
"""Generate JSONL from all 1,174 regulation article.html files for Neo4j loading."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from download_sources import parse_record

ROOT = Path(__file__).resolve().parents[2]
KEYS = [
    "instrument_id", "record_url", "name", "legislation_type", "jurisdiction",
    "legislation_date", "legal_force", "description", "official_publication_url",
    "official_text_url", "in_language", "date_modified", "license",
    "sd_date_published", "topic_keywords", "full_analysis_is_free", "breadcrumb",
    "milestones", "source_links",
]


def build() -> list[dict]:
    records_dir = ROOT / "research/sources/records"
    out = []
    failed = []
    
    # Get all regulation IDs from directory names
    for reg_dir in sorted(records_dir.iterdir()):
        if not reg_dir.is_dir():
            continue
        
        rid = reg_dir.name
        html_file = reg_dir / "article.html"
        
        if not html_file.exists():
            failed.append(f"{rid}: no article.html")
            continue
        
        try:
            html = html_file.read_text(errors="ignore")
            rec = parse_record(html)
            
            # Add derived fields
            rec.update({
                "instrument_id": rid,
                "record_url": f"https://regulations.ai/regulations/{rid}",
                "sd_date_published": "",
                "full_analysis_is_free": False,
                "breadcrumb": "",
            })
            
            out.append({k: rec.get(k, "") for k in KEYS})
        except Exception as e:
            failed.append(f"{rid}: {e}")
    
    if failed:
        print(f"Failed to parse {len(failed)} regulations:")
        for f in failed[:10]:  # Show first 10
            print(f"  - {f}")
        if len(failed) > 10:
            print(f"  ... and {len(failed) - 10} more")
    
    return out


def main() -> None:
    rows = build()
    dest = ROOT / "research/data/regulation_records_full.jsonl"
    dest.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    print(f"Wrote {len(rows)} records -> {dest}")


if __name__ == "__main__":
    main()
