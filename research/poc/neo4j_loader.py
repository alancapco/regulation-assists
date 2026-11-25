#!/usr/bin/env python3
"""
Load regulations.ai regulation records into Neo4j as a knowledge graph.

Reads the JSONL produced by ingest.py (--mode records) and builds:
    Regulation -[:IN_JURISDICTION]-> Jurisdiction
    Regulation -[:OF_TYPE]-> InstrumentType
    Regulation -[:HAS_TOPIC]-> Topic
    Regulation -[:SOURCED_FROM|HAS_OFFICIAL_TEXT|PUBLISHED_AT]-> Source
    Regulation -[:HAS_MILESTONE]-> Milestone

Design notes
------------
* Idempotent + safe to re-run: the graph is rebuilt from scratch each run
  (this is a fresh, loader-owned subgraph). Adjust `reset` if you want to
  merge incrementally instead.
* All structure is derived from the source record — no LLM-generated Cypher
  is executed here or at query time (question templates only).
* Data cleaning fixes two known ingest artifacts:
    - analytics/JS URLs (cloudflareinsights, googletagmanager) leak into
      source_links; they are dropped.
    - some milestone `date` fields captured HTML (</td>...); trimmed.

Usage
-----
    uv run python research/poc/neo4j_loader.py \
        --in research/data/regulation_records.jsonl \
        --uri bolt://localhost:7687 --user neo4j --password capco-graph-change-me
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from neo4j import GraphDatabase
    from neo4j.exceptions import ServiceUnavailable, AuthError
except ImportError:  # pragma: no cover
    sys.exit("neo4j driver not installed — run inside the uv project (uv sync).")

ANALYTICS = ("cloudflareinsights", "googletagmanager")
ASSET_RE = re.compile(r"\.(js|css|png|jpg|jpeg|svg|ico|gif|woff2?)(\?|$)", re.I)
DATE_RE = re.compile(r"20\d\d-\d\d-\d\d")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def clean_source_urls(urls: list[str]) -> list[str]:
    out, seen = [], set()
    for u in urls or []:
        u = u.strip()
        if not u or u in seen:
            continue
        low = u.lower()
        if any(a in low for a in ANALYTICS):
            continue
        if ASSET_RE.search(low):
            continue
        seen.add(u)
        out.append(u)
    return out


def clean_milestones(milestones: list[dict]) -> list[dict]:
    out = []
    for m in milestones or []:
        date = (m.get("date") or "").strip()
        name = (m.get("milestone") or "").strip()
        notes = (m.get("notes") or "").strip()
        if "<" in date:  # HTML leaked from the record page table
            date = date.split("<")[0].strip()
        if not name or not date:
            continue
        out.append({"name": name, "date": date, "notes": notes})
    return out


def load(tx, rec: dict) -> None:
    rid = rec.get("instrument_id")
    if not rid:
        return

    # --- Regulation node -----------------------------------------------------
    tx.run(
        """
        MERGE (r:Regulation {instrument_id: $rid})
        SET r.name = $name,
            r.legislation_type = $ltype,
            r.legislation_date = $ldate,
            r.legal_force = $force,
            r.description = $desc,
            r.in_language = $lang,
            r.date_modified = $modified,
            r.official_publication_url = $pub,
            r.official_text_url = $text,
            r.license = $lic,
            r.breadcrumb = $crumb,
            r.full_analysis_free = $free,
            r.record_url = $rec_url
        """,
        rid=rid,
        name=rec.get("name"),
        ltype=rec.get("legislation_type"),
        ldate=rec.get("legislation_date"),
        force=rec.get("legal_force") or None,
        desc=rec.get("description"),
        lang=rec.get("in_language"),
        modified=rec.get("date_modified"),
        pub=rec.get("official_publication_url"),
        text=rec.get("official_text_url"),
        lic=rec.get("license"),
        crumb=rec.get("breadcrumb"),
        free=bool(rec.get("full_analysis_is_free")),
        rec_url=rec.get("record_url"),
    )

    # --- Jurisdiction --------------------------------------------------------
    jur = rec.get("jurisdiction")
    if jur:
        tx.run(
            "MERGE (j:Jurisdiction {name: $name}) "
            "MERGE (r:Regulation {instrument_id: $rid}) "
            "MERGE (r)-[:IN_JURISDICTION]->(j)",
            name=jur, rid=rid,
        )

    # --- InstrumentType ------------------------------------------------------
    itype = rec.get("legislation_type")
    if itype:
        tx.run(
            "MERGE (t:InstrumentType {name: $name}) "
            "MERGE (r:Regulation {instrument_id: $rid}) "
            "MERGE (r)-[:OF_TYPE]->(t)",
            name=itype, rid=rid,
        )

    # --- Topics --------------------------------------------------------------
    topics = [t.strip() for t in (rec.get("topic_keywords") or "").split(",") if t.strip()]
    for t in topics:
        tx.run(
            "MERGE (tp:Topic {name: $name}) "
            "MERGE (r:Regulation {instrument_id: $rid}) "
            "MERGE (r)-[:HAS_TOPIC]->(tp)",
            name=t, rid=rid,
        )

    # --- Sources -------------------------------------------------------------
    # official text + publication get their own typed relationships
    for rel, url in (
        ("HAS_OFFICIAL_TEXT", rec.get("official_text_url")),
        ("PUBLISHED_AT", rec.get("official_publication_url")),
    ):
        if url:
            tx.run(
                f"MERGE (s:Source {{url: $url}}) SET s.domain = $domain "
                f"MERGE (r:Regulation {{instrument_id: $rid}}) "
                f"MERGE (r)-[:{rel}]->(s)",
                url=url, domain=_domain(url), rid=rid,
            )
    for url in clean_source_urls(rec.get("source_links", [])):
        tx.run(
            "MERGE (s:Source {url: $url}) SET s.domain = $domain "
            "MERGE (r:Regulation {instrument_id: $rid}) "
            "MERGE (r)-[:SOURCED_FROM]->(s)",
            url=url, domain=_domain(url), rid=rid,
        )

    # --- Milestones ----------------------------------------------------------
    for m in clean_milestones(rec.get("milestones", [])):
        uid = f"{rid}|{m['name']}|{m['date']}"
        tx.run(
            "MERGE (m:Milestone {uid: $uid}) "
            "SET m.name = $name, m.date = $date, m.notes = $notes "
            "MERGE (r:Regulation {instrument_id: $rid}) "
            "MERGE (r)-[:HAS_MILESTONE]->(m)",
            uid=uid, name=m["name"], date=m["date"], notes=m["notes"], rid=rid,
        )


def _domain(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).netloc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True, help="regulation_records.jsonl")
    ap.add_argument("--uri", default="bolt://localhost:7687")
    ap.add_argument("--user", default="neo4j")
    ap.add_argument("--password", default="capco-graph-change-me")
    ap.add_argument("--reset", action="store_true", default=False,
                    help="clear the ENTIRE graph (DETACH DELETE all nodes) before "
                         "loading. Off by default so we add to an existing DB "
                         "without destroying prior data.")
    args = ap.parse_args()

    records = [json.loads(x) for x in Path(args.infile).read_text().splitlines() if x.strip()]
    print(f"loaded {len(records)} records from {args.infile}")

    try:
        driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
        driver.verify_connectivity()
    except (ServiceUnavailable, AuthError) as exc:
        sys.exit(f"! cannot connect to Neo4j at {args.uri}: {exc}\n"
                 f"  Start it with: docker compose up -d")

    with driver.session() as session:
        if args.reset:
            print("resetting graph (detach delete all nodes)…")
            session.run("MATCH (n) DETACH DELETE n")
        # ensure constraints/indexes exist
        schema = Path(__file__).with_name("neo4j_schema.cypher").read_text()
        # Drop full-line comments first — they may contain ';' (e.g. inside prose)
        # which would otherwise be mis-split into a bogus statement.
        code_lines = [ln for ln in schema.splitlines() if not ln.strip().startswith("//")]
        for stmt in (s.strip() for s in "\n".join(code_lines).split(";")):
            if stmt:
                session.run(stmt)
        for rec in records:
            session.execute_write(load, rec)
        # summary
        summary = session.run(
            "MATCH (r:Regulation) WITH count(r) AS regs "
            "MATCH (j:Jurisdiction) WITH regs, count(j) AS juris "
            "MATCH (t:InstrumentType) WITH regs, juris, count(t) AS types "
            "MATCH (tp:Topic) WITH regs, juris, types, count(tp) AS topics "
            "MATCH (s:Source) WITH regs, juris, types, topics, count(s) AS src "
            "MATCH (m:Milestone) RETURN regs, juris, types, topics, src, count(m) AS miles"
        ).single()
        print("graph now contains:", dict(summary))

    driver.close()
    print("done.")


if __name__ == "__main__":
    main()
