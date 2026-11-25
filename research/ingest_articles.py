"""
Ingest article.md files from research/sources/records/ into Neo4j.
Enriches existing Regulation nodes with richer data from markdown files.
"""

import os
import re
import sys
from pathlib import Path

from neo4j import GraphDatabase

RECORDS_DIR = Path(__file__).parent / "sources" / "records"
NEO4J_URI = "bolt://localhost:7688"
NEO4J_AUTH = ("neo4j", "capco-graph-change-me")


def parse_article(path: Path) -> dict:
    """Parse an article.md file into a structured dict."""
    text = path.read_text(encoding="utf-8")
    result = {}

    # --- metadata fields ---
    def get_meta(label: str) -> str | None:
        m = re.search(rf"\*\*{re.escape(label)}:\*\*\s*(.+)", text)
        return m.group(1).strip() if m else None

    result["instrument_id"] = get_meta("Instrument ID")
    result["last_modified"] = get_meta("Last modified")
    result["official_text_url"] = get_meta("Official text \\(isBasedOn\\)")
    result["publication_url"] = get_meta("Official publication \\(sameAs\\)")

    # official_text_url with the escaped parens needs special handling
    if result["official_text_url"] is None:
        m = re.search(r"\*\*Official text \(isBasedOn\):\*\*\s*(.+)", text)
        result["official_text_url"] = m.group(1).strip() if m else None
    if result["publication_url"] is None:
        m = re.search(r"\*\*Official publication \(sameAs\):\*\*\s*(.+)", text)
        result["publication_url"] = m.group(1).strip() if m else None

    # --- Résumé section ---
    resume_match = re.search(
        r"##\s+R[eé]sum[eé]\s*\n+(.*?)(?=\n##\s|\Z)", text, re.DOTALL | re.IGNORECASE
    )
    result["resume"] = resume_match.group(1).strip() if resume_match else None

    # --- Milestones ---
    milestones = []
    ms_section = re.search(
        r"##\s+Implementation milestones\s*\n+(.*?)(?=\n##\s|\Z)", text, re.DOTALL | re.IGNORECASE
    )
    if ms_section:
        table_text = ms_section.group(1)
        for row in re.finditer(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|$",
                               table_text, re.MULTILINE):
            title = row.group(1).strip()
            date = row.group(2).strip()
            notes = row.group(3).strip()
            # skip header / separator rows
            if title.lower() in ("milestone", "---", "") or re.match(r"^-+$", title):
                continue
            milestones.append({"name": title, "date": date, "notes": notes or None})
    result["milestones"] = milestones

    # --- Source links ---
    sources = []
    src_section = re.search(
        r"##\s+Source links\s*\n+(.*?)(?=\n##\s|\Z)", text, re.DOTALL | re.IGNORECASE
    )
    if src_section:
        for m in re.finditer(r"^\s*-\s*(https?://\S+)", src_section.group(1), re.MULTILINE):
            sources.append(m.group(1).strip())
    result["sources"] = sources

    return result


def rel_type_for_url(url: str) -> str:
    lower = url.lower()
    if any(k in lower for k in ("official", "legislation.gov", "eur-lex", "parliament", "congress", "leginfo")):
        return "HAS_OFFICIAL_TEXT"
    return "SOURCED_FROM"


def ingest_regulation(session, data: dict) -> tuple[int, int]:
    """Write enrichment data for one regulation. Returns (milestones_added, sources_added)."""
    iid = data["instrument_id"]

    # Update scalar fields on the Regulation node
    session.run(
        """
        MATCH (r:Regulation {instrument_id: $iid})
        WHERE r.instrument_id IS NOT NULL
        SET r.last_modified   = $last_modified,
            r.resume          = $resume,
            r.official_text_url = $official_text_url,
            r.publication_url = $publication_url
        """,
        iid=iid,
        last_modified=data["last_modified"],
        resume=data["resume"],
        official_text_url=data["official_text_url"],
        publication_url=data["publication_url"],
    )

    # Milestones
    ms_count = 0
    for ms in data["milestones"]:
        session.run(
            """
            MATCH (r:Regulation {instrument_id: $iid})
            WHERE r.instrument_id IS NOT NULL
            MERGE (m:Milestone {name: $name, instrument_id: $iid})
            SET m.date  = $date,
                m.notes = $notes
            MERGE (r)-[:HAS_MILESTONE]->(m)
            """,
            iid=iid,
            name=ms["name"],
            date=ms["date"],
            notes=ms["notes"],
        )
        ms_count += 1

    # Source links
    src_count = 0
    for url in data["sources"]:
        rel = rel_type_for_url(url)
        session.run(
            f"""
            MATCH (r:Regulation {{instrument_id: $iid}})
            WHERE r.instrument_id IS NOT NULL
            MERGE (s:Source {{url: $url}})
            MERGE (r)-[:{rel}]->(s)
            """,
            iid=iid,
            url=url,
        )
        src_count += 1

    return ms_count, src_count


def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)

    dirs = sorted(p for p in RECORDS_DIR.iterdir() if p.is_dir())
    total = len(dirs)
    processed = 0
    total_milestones = 0
    total_sources = 0

    with driver.session() as session:
        for d in dirs:
            md_path = d / "article.md"
            if not md_path.exists():
                print(f"  [SKIP] {d.name}: article.md not found")
                continue
            try:
                data = parse_article(md_path)
                if not data.get("instrument_id"):
                    print(f"  [SKIP] {d.name}: no instrument_id found")
                    continue
                ms_n, src_n = ingest_regulation(session, data)
                total_milestones += ms_n
                total_sources += src_n
                processed += 1
                print(f"  [OK]   {data['instrument_id']} — {ms_n} milestones, {src_n} sources")
            except Exception as e:
                print(f"  [ERR]  {d.name}: {e}", file=sys.stderr)

    driver.close()
    print(f"\nProcessed {processed}/{total}, updated {total_milestones} milestones, {total_sources} sources")


if __name__ == "__main__":
    main()
