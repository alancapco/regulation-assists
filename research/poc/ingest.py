#!/usr/bin/env python3
"""
Proof-of-concept ingester for the regulations.ai AI-regulation corpus.

IMPORTANT (legal): this script deliberately uses ONLY the machine-readable
channels that the publisher exposes for AI agents and crawlers:

    /okf/index.md                     Open Knowledge Format bulk corpus index
    /okf/jurisdictions/<slug>.md      one Markdown file per jurisdiction
    /calendar                         schema.org Event JSON-LD (213 deadlines)
    /resources                        curated list of official source links
    /sitemap.xml                      URL discovery with lastmod
    /regulations/<RAI-id>             schema.org Legislation JSON-LD per record
    /api/mcp/v1                       MCP server (query-time, not bulk)

It does NOT send a generic crawler user-agent. regulations.ai/robots.txt
disallows `User-agent: *` and the Terms of Use (section 9) prohibit scraping
without prior written consent. Obtain written consent before storing or
redistributing the corpus beyond personal/private research use.

Usage:
    python3 ingest.py --mode inventory --out ../data
    python3 ingest.py --mode records   --out ../data --limit 25
    python3 ingest.py --mode all       --out ../data --limit 25

Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://regulations.ai"
# An honest, identifiable UA. Do NOT spoof an allow-listed search-engine UA.
USER_AGENT = "CapcoRegulationResearch/0.1 (private research; contact: alan@example.com)"
REQUEST_DELAY = 1.0  # seconds between requests; be polite to the origin
TIMEOUT = 40


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def fetch(path: str) -> str:
    url = path if path.startswith("http") else BASE + path
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read()
    return raw.decode("utf-8", errors="replace")


def tag_text(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  wrote {path.name:38s} {len(rows):5d} rows")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"  wrote {path.name:38s} {len(rows):5d} rows")


# --------------------------------------------------------------------------- #
# 1. OKF bulk corpus: one Markdown file per jurisdiction
# --------------------------------------------------------------------------- #
def parse_okf_index() -> list[dict]:
    text = fetch("/okf/index.md")
    rows = []
    for name, slug, count in re.findall(
        r"^- \[([^\]]+)\]\(/jurisdictions/([^)]+\.md)\) - (\d+) instruments\.?",
        text,
        re.M,
    ):
        rows.append(
            {
                "jurisdiction": name,
                "okf_slug": slug,
                "instrument_count": int(count),
                "okf_url": f"{BASE}/okf/jurisdictions/{slug}",
            }
        )
    return rows


def parse_okf_jurisdiction(row: dict) -> list[dict]:
    """Parse the instrument table of one OKF jurisdiction profile."""
    text = fetch(f"/okf/jurisdictions/{row['okf_slug']}")
    instruments = []
    for line in text.splitlines():
        if not line.startswith("| ["):
            continue
        # Column 6 is normally [source](url); a small number of records have
        # an em dash instead, i.e. no official source on file.
        m = re.match(
            r"\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|"
            r"\s*([^|]*?)\s*\|\s*(?:\[source\]\(([^)]+)\)|—|-)?\s*\|",
            line,
        )
        if not m:
            continue
        title, record_url, itype, status, checked, source = (
            (x or "").strip() for x in m.groups()
        )
        rid = record_url.rstrip("/").split("/")[-1]
        instruments.append(
            {
                "instrument_id": rid,
                "title": title,
                "record_url": record_url,
                "instrument_type": itype,
                "status": status,
                "status_checked": "" if checked == "not checked" else checked,
                "official_source_url": source,
                "jurisdiction": row["jurisdiction"],
            }
        )
    # Frontmatter provenance block: every official source used by this profile.
    fm_sources = re.findall(r"^\s+- resource:\s*(\S+)", text, re.M)
    for inst in instruments:
        inst["jurisdiction_source_count"] = len(fm_sources)
    return instruments


# --------------------------------------------------------------------------- #
# 2. /resources -> the upstream official source links
# --------------------------------------------------------------------------- #
def parse_resources() -> list[dict]:
    page = fetch("/resources")
    token = re.compile(
        r"<h3[^>]*>(.*?)</h3>|<h4[^>]*>(.*?)</h4>|"
        r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        re.S,
    )
    group, country, summary_url = "", "", ""
    rows, seen = [], set()
    for m in token.finditer(page):
        h3, h4, href, label = m.groups()
        if h3 is not None:
            group = tag_text(h3)
            continue
        if h4 is not None:
            country = tag_text(h4)
            summary_url = ""
            continue
        if href is None:
            continue
        text = tag_text(label)
        if href.startswith("/regulations/"):
            if "Summary" in text or "SUMMARY" in href:
                summary_url = BASE + href
            continue
        if not href.startswith("http") or "regulations.ai" in href:
            continue
        key = (country, href)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "region_group": group,
                "jurisdiction_or_org": country,
                "resource_label": text,
                "official_url": href,
                "domain": urllib.parse.urlparse(href).netloc,
                "rai_summary_url": summary_url,
            }
        )
    return rows


# --------------------------------------------------------------------------- #
# 3. /calendar -> schema.org Event JSON-LD (the regulation calendar)
# --------------------------------------------------------------------------- #
def _balanced_array(text: str, start: int) -> str:
    """Return the JSON array beginning at text[start] == '['."""
    depth, in_string, escaped = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ValueError("unbalanced array in RSC payload")


def parse_calendar() -> list[dict]:
    """
    The /calendar page advertises 213 upcoming events, but its schema.org
    CollectionPage JSON-LD is capped at 100 ListItems. The complete array lives
    in the React Server Component flight payload (self.__next_f.push) as
    {"events":[{date,label,regId,title,jurisdiction,country,status,type,
    sourceUrl,verified}, ...]}. We parse that first and fall back to JSON-LD.
    """
    page = fetch("/calendar")
    unescaped = page.replace('\\"', '"').replace("\\\\", "\\")
    marker = '"events":['
    p = unescaped.find(marker)
    if p != -1:
        try:
            raw = json.loads(_balanced_array(unescaped, p + len(marker) - 1))
            events = [
                {
                    "position": i,
                    "date": e.get("date"),
                    "event_name": f'{e.get("title", "")} — {e.get("label", "")}',
                    "event_label": e.get("label"),
                    "instrument_title": e.get("title"),
                    "instrument_id": e.get("regId"),
                    "record_url": f'{BASE}/regulations/{e.get("regId")}'
                    if e.get("regId") else "",
                    "jurisdiction": e.get("jurisdiction"),
                    "country": e.get("country"),
                    "instrument_status": e.get("status"),
                    "instrument_type": e.get("type"),
                    "official_source_url": e.get("sourceUrl"),
                    "verified": e.get("verified"),
                }
                for i, e in enumerate(raw, 1)
            ]
            return events
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"  ! RSC calendar parse failed ({exc}); falling back to JSON-LD")

    # Fallback: schema.org Event JSON-LD (first 100 only).
    events = []
    for block in re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S
    ):
        try:
            obj = json.loads(block)
        except json.JSONDecodeError:
            continue
        if obj.get("@type") != "CollectionPage":
            continue
        for element in obj.get("mainEntity", {}).get("itemListElement", []):
            item = element.get("item", {})
            if item.get("@type") != "Event":
                continue
            url, desc = item.get("url", ""), item.get("description", "")
            events.append(
                {
                    "position": element.get("position"),
                    "date": item.get("startDate"),
                    "event_name": item.get("name"),
                    "event_label": "",
                    "instrument_title": "",
                    "instrument_id": url.rstrip("/").split("/")[-1],
                    "record_url": url,
                    "jurisdiction": desc.rsplit(" in ", 1)[-1].rstrip(".").strip()
                    if " in " in desc else "",
                    "country": "",
                    "instrument_status": "",
                    "instrument_type": "",
                    "official_source_url": "",
                    "verified": "",
                }
            )
    return events


# --------------------------------------------------------------------------- #
# 4. sitemap -> URL discovery + incremental refresh via lastmod
# --------------------------------------------------------------------------- #
def parse_sitemap() -> list[dict]:
    xml = fetch("/sitemap.xml")
    pairs = re.findall(r"<url>\s*<loc>(.*?)</loc>\s*(?:<lastmod>(.*?)</lastmod>)?", xml, re.S)
    rows = []
    for loc, lastmod in pairs:
        path = urllib.parse.urlparse(loc).path.strip("/")
        rid = path.split("/")[-1] if path.startswith("regulations/") else ""
        rows.append(
            {
                "url": loc.strip(),
                "section": path.split("/")[0] if path else "(root)",
                "record_id": rid if rid.startswith("RAI-") else "",
                "lastmod": lastmod.strip(),
            }
        )
    return rows


# --------------------------------------------------------------------------- #
# 5. page-by-page: schema.org Legislation JSON-LD for each instrument
# --------------------------------------------------------------------------- #
def parse_record(rid: str) -> dict:
    page = fetch(f"/regulations/{rid}")
    result = {"instrument_id": rid, "record_url": f"{BASE}/regulations/{rid}"}
    for block in re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S
    ):
        try:
            obj = json.loads(block)
        except json.JSONDecodeError:
            continue
        if obj.get("@type") == "Legislation":
            result.update(
                {
                    "name": obj.get("name"),
                    "legislation_type": obj.get("legislationType"),
                    "jurisdiction": obj.get("legislationJurisdiction"),
                    "legislation_date": obj.get("legislationDate"),
                    "legal_force": obj.get("legislationLegalForce", "").rsplit("/", 1)[-1],
                    "description": obj.get("description"),
                    "official_publication_url": obj.get("sameAs"),
                    "official_text_url": obj.get("isBasedOn"),
                    "in_language": obj.get("inLanguage"),
                    "date_modified": obj.get("dateModified"),
                    "license": obj.get("license"),
                    "sd_date_published": obj.get("sdDatePublished"),
                }
            )
        elif obj.get("@type") == "Article":
            result["topic_keywords"] = obj.get("keywords", "")
            result["full_analysis_is_free"] = obj.get("isAccessibleForFree")
        elif obj.get("@type") == "BreadcrumbList":
            crumbs = [x.get("name") for x in obj.get("itemListElement", [])]
            result["breadcrumb"] = " > ".join(x for x in crumbs if x)
    # Implementation Timeline milestones rendered as a table on the record page.
    result["milestones"] = [
        {"milestone": a.strip(), "date": b.strip(), "notes": c.strip()}
        for a, b, c in re.findall(
            r"<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>",
            page,
            re.S,
        )
        if re.search(r"20\d\d-\d\d-\d\d", b)
    ]
    # Every external official link on the page (source, full text, press material).
    links = re.findall(r'href="(https?://[^"]+)"', page)
    result["source_links"] = sorted(
        {
            html.unescape(u)
            for u in links
            if "regulations.ai" not in u
            and not re.search(r"\.(js|css|png|jpg|svg|ico)(\?|$)", u, re.I)
            and "cloudflareinsights" not in u
            and "googletagmanager" not in u
        }
    )
    return result


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def run(mode: str, out: Path, limit: int, delay: float) -> None:
    global REQUEST_DELAY
    REQUEST_DELAY = delay
    instruments: list[dict] = []

    if mode in ("inventory", "all"):
        print("[1/5] OKF jurisdiction index")
        juris = parse_okf_index()
        time.sleep(delay)
        write_csv(out / "okf_jurisdictions.csv", juris,
                  ["jurisdiction", "okf_slug", "instrument_count", "okf_url"])

        print("[2/5] Upstream official source links from /resources")
        time.sleep(delay)
        links = parse_resources()
        write_csv(out / "resources_official_links.csv", links,
                  ["region_group", "jurisdiction_or_org", "resource_label",
                   "official_url", "domain", "rai_summary_url"])

        print("[3/5] Compliance calendar events from /calendar JSON-LD")
        time.sleep(delay)
        events = parse_calendar()
        write_csv(out / "calendar_events.csv", events,
                  ["position", "date", "event_name", "event_label",
                   "instrument_title", "instrument_id", "jurisdiction", "country",
                   "instrument_status", "instrument_type", "official_source_url",
                   "verified", "record_url"])
        write_jsonl(out / "calendar_events.jsonl", events)

        print("[4/5] Sitemap index")
        time.sleep(delay)
        urls = parse_sitemap()
        write_csv(out / "sitemap_index.csv", urls,
                  ["url", "section", "record_id", "lastmod"])

        print("[5/5] OKF instrument tables (all jurisdictions)")
        for i, j in enumerate(juris, 1):
            try:
                instruments.extend(parse_okf_jurisdiction(j))
            except Exception as exc:  # keep going; report at the end
                print(f"  ! {j['jurisdiction']}: {exc}")
            time.sleep(delay)
            if i % 20 == 0:
                print(f"  ... {i}/{len(juris)} jurisdictions")
        write_csv(out / "instruments.csv", instruments,
                  ["instrument_id", "title", "jurisdiction", "instrument_type",
                   "status", "status_checked", "official_source_url", "record_url"])
        write_jsonl(out / "instruments.jsonl", instruments)
        print(f"  total instruments parsed: {len(instruments)}")

    if mode in ("records", "all"):
        if not instruments:
            print("[records] loading inventory from instruments.jsonl")
            p = out / "instruments.jsonl"
            if not p.exists():
                raise SystemExit("Run --mode inventory first, or use --mode all")
            instruments = [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
        targets = [x["instrument_id"] for x in instruments[:limit]]
        print(f"[records] fetching {len(targets)} regulation detail pages (page by page)")
        records = []
        for i, rid in enumerate(targets, 1):
            try:
                records.append(parse_record(rid))
            except Exception as exc:
                print(f"  ! {rid}: {exc}")
            time.sleep(delay)
            if i % 10 == 0:
                print(f"  ... {i}/{len(targets)}")
        write_jsonl(out / "regulation_records.jsonl", records)

    print("done.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["inventory", "records", "all"], default="inventory")
    ap.add_argument("--out", type=Path, default=Path("../data"))
    ap.add_argument("--limit", type=int, default=25,
                    help="max regulation detail pages to fetch in records/all mode")
    ap.add_argument("--delay", type=float, default=REQUEST_DELAY,
                    help="seconds between requests (default 1.0)")
    args = ap.parse_args()
    run(args.mode, args.out.resolve(), args.limit, args.delay)


if __name__ == "__main__":
    main()
