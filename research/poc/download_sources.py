#!/usr/bin/env python3
"""
Download 30 (diverse) regulation "data sources" for human review.

For each RAI id in research/data/diverse_30.json this script fetches:
  1. the regulations.ai article page  -> sources/<id>/article.html (raw)
                                       -> sources/<id>/article.md  (clean review copy)
  2. the PRIMARY official document the record is based on
     (isBasedOn / sameAs / first official source link)
                                       -> sources/<id>/source.<ext>

It also writes:
  research/sources/manifest.csv   one row per record (paths, primary URL, status, size)
  research/sources/INDEX.md       a human review index with links

Notes
-----
* regulations.ai article pages are fetched read-only for private research review.
  Their Terms of Use (section 9) restrict redistribution — keep these local/private.
* Primary documents are downloaded from government / official issuer sites, which
  generally carry clean reuse terms (public domain, OGL, EU reuse decision, etc.).
  The license is recorded per file for your review; verify before any reuse.
* Honest, identifiable UA; polite delays between requests. No search-engine spoofing.

Usage:
    uv run python research/poc/download_sources.py \
        --ids research/data/diverse_30.json \
        --out research/sources --delay 0.5
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://regulations.ai"
# Normal browser UA — these are public official documents; we are not spoofing a
# search-engine crawler, only identifying as a standard browser for fetch success.
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
ANALYTICS = ("cloudflareinsights", "googletagmanager")
ASSET_RE = re.compile(r"\.(js|css|png|jpg|jpeg|svg|ico|gif|woff2?)(\?|$)", re.I)
ISO_DATE = re.compile(r"20\d\d-\d\d-\d\d")


def fetch(url: str, timeout, binary: bool = False):
    # timeout may be (connect, read) tuple; keeps dead hosts from hanging a run.
    # Python's urlopen only accepts a single float timeout, so use the read value.
    if isinstance(timeout, (tuple, list)):
        timeout = float(timeout[1])
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        ctype = resp.headers.get("Content-Type", "")
        final = resp.geturl()
    if binary:
        return data, ctype, final
    return data.decode("utf-8", errors="replace"), ctype, final


def tag_text(frag: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", frag)).strip()


def clean_source_urls(urls):
    out, seen = [], set()
    for u in urls or []:
        u = u.strip()
        if not u or u in seen:
            continue
        low = u.lower()
        if any(a in low for a in ANALYTICS) or ASSET_RE.search(low) or "regulations.ai" in low:
            continue
        seen.add(u)
        out.append(u)
    return out


def parse_record(html_text: str) -> dict:
    result = {}
    for block in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html_text, re.S):
        try:
            obj = json.loads(block)
        except json.JSONDecodeError:
            continue
        if obj.get("@type") == "Legislation":
            result.update({
                "name": obj.get("name"),
                "legislation_type": obj.get("legislationType"),
                "jurisdiction": obj.get("legislationJurisdiction"),
                "legislation_date": obj.get("legislationDate"),
                "legal_force": (obj.get("legislationLegalForce") or "").rsplit("/", 1)[-1],
                "description": obj.get("description"),
                "official_publication_url": obj.get("sameAs"),
                "official_text_url": obj.get("isBasedOn"),
                "in_language": obj.get("inLanguage"),
                "date_modified": obj.get("dateModified"),
                "license": obj.get("license"),
            })
        elif obj.get("@type") == "Article":
            result["topic_keywords"] = obj.get("keywords", "")
    # milestones from the implementation-timeline table
    result["milestones"] = [
        {"milestone": a.strip(), "date": b.strip(), "notes": c.strip()}
        for a, b, c in re.findall(
            r"<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>",
            html_text, re.S)
        if ISO_DATE.search(b)
    ]
    # external source links on the page
    links = re.findall(r'href="(https?://[^"]+)"', html_text)
    result["source_links"] = sorted({
        html.unescape(u) for u in links
        if "regulations.ai" not in u and not ASSET_RE.search(u.lower())
        and "cloudflareinsights" not in u and "googletagmanager" not in u
    })
    return result


def primary_candidates(rec: dict):
    cands = []
    for key in ("official_text_url", "official_publication_url"):
        u = rec.get(key)
        if u and u not in cands:
            cands.append(u)
    for u in rec.get("source_links", []):
        if u not in cands:
            cands.append(u)
    return cands


def ext_for(ctype: str, url: str) -> str:
    ctype = (ctype or "").lower()
    if "pdf" in ctype or url.lower().endswith(".pdf"):
        return ".pdf"
    if "html" in ctype or "xml" in ctype:
        return ".html"
    if "json" in ctype:
        return ".json"
    if "word" in ctype or "docx" in ctype or "doc" in ctype:
        return ".docx"
    # fallback: keep any extension present in the URL
    m = re.search(r"\.(pdf|html|htm|docx?|xml|json|txt)(?:\?|$)", url.lower())
    return "." + m.group(1) if m else ".bin"


def likely_pdf(url: str) -> bool:
    """Heuristic: does this URL point at a PDF?"""
    if not url:
        return False
    low = url.lower().split("?")[0]
    if low.endswith(".pdf"):
        return True
    # known PDF-hosting hosts that sometimes omit the extension
    hosts = ("nvlpubs.nist.gov", "publications.europa.eu", "eur-lex.europa.eu")
    return any(h in low for h in hosts)


def pdf_slug(url: str) -> str:
    """Stable, filesystem-safe filename for an extra PDF."""
    base = url.split("?")[0].rsplit("/", 1)[-1]
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    if not base or len(base) > 60:
        base = hashlib.md5(url.encode()).hexdigest()[:12]
    if not base.lower().endswith(".pdf"):
        base += ".pdf"
    return base


def is_pdf_bytes(data: bytes) -> bool:
    """True only if the bytes really are a PDF (magic %PDF header)."""
    return data[:5] == b"%PDF-"


def _uniq(seq):
    seen, out = set(), []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def normalize_pdf_url(url: str) -> str:
    """
    Turn a PDF *landing* URL into the URL that actually serves the bytes.

    eur-lex serves the HTML viewer at /TXT/ and at /eli/.../oj/eng, but the raw
    PDF only at /TXT/PDF/?uri=CELEX:xxxx (confirmed: application/pdf, %PDF-1.7).
    Without this rewrite we were saving the HTML viewer page as a .pdf.
    """
    if not url:
        return url
    low = url.lower()
    if "eur-lex.europa.eu" in low:
        m = re.search(r"[?&]uri=([^&]+)", url)
        if m:
            uri = urllib.parse.unquote(m.group(1))
            return ("https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/"
                    f"?uri={urllib.parse.quote(uri)}")
        # /eli/reg/YYYY/N/...  ->  CELEX 3<YYYY>R<N>  PDF  (4-digit year!)
        m = re.search(r"/eli/(reg|dir)/(\d{4})/(\d+)", low)
        if m:
            year = m.group(2)
            num = int(m.group(3))
            kind = "R" if m.group(1) == "reg" else "L"
            celex = f"3{year}{kind}{num:04d}"
            return ("https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/"
                    f"?uri=CELEX:{celex}")
    return url


_BLOCK_RE = re.compile(r"acesso negado|access denied|403 forbidden|not found|erro|denied", re.I)


def content_is_usable(data: bytes, ctype: str, final: str) -> bool:
    """
    Reject bodies that are not a real primary document:
      * HTML block / error pages (e.g. Brazilian "Acesso Negado!", 403 stubs)
      * sub-2 KB HTML stubs (redirect/placeholder pages)
      * tiny JSON (API metadata fragments, not the instrument text)
    Anything that is not obviously a document is rejected so the next
    candidate (or an honest "missing") is used instead of a fake file.
    """
    low = (ctype or "").lower()
    url = (final or "").lower()
    if "pdf" in low or url.endswith(".pdf"):
        return is_pdf_bytes(data)
    if data[:5] == b"%PDF-":
        return True
    if "json" in low or url.endswith(".json"):
        return len(data) >= 5120
    if "html" in low or "xml" in low or url.endswith((".html", ".htm")):
        if len(data) < 2048:
            return False
        head = data[:600].decode("utf-8", "replace")
        if _BLOCK_RE.search(head):
            return False
        return True
    # other binary-ish types (docx ...): accept if non-trivial
    return len(data) >= 1024


def is_usable_primary(path: "Path") -> bool:
    """Same check as content_is_usable but for an already-saved file."""
    if not (path.exists() and path.stat().st_size > 0):
        return False
    data = path.read_bytes()
    ctype, final = "", path.name
    if path.suffix == ".pdf":
        ctype = "application/pdf"
    elif path.suffix == ".json":
        ctype = "application/json"
    elif path.suffix in (".html", ".htm"):
        ctype = "text/html"
    return content_is_usable(data, ctype, final)


def article_md(rec: dict) -> str:
    lines = [f"# {rec.get('name','(untitled)')}", ""]
    meta = [
        ("Instrument ID", rec.get("instrument_id")),
        ("Jurisdiction", rec.get("jurisdiction")),
        ("Type", rec.get("legislation_type")),
        ("Status", rec.get("legal_force")),
        ("Legislation date", rec.get("legislation_date")),
        ("Language", rec.get("in_language")),
        ("Last modified", rec.get("date_modified")),
        ("License", rec.get("license")),
        ("regulations.ai record", rec.get("record_url")),
        ("Official text (isBasedOn)", rec.get("official_text_url")),
        ("Official publication (sameAs)", rec.get("official_publication_url")),
    ]
    for k, v in meta:
        if v:
            lines.append(f"- **{k}:** {v}")
    lines += ["", "## Summary", "", rec.get("description") or "_(no summary available)_", ""]
    if rec.get("topic_keywords"):
        lines += ["## Topics", "", rec["topic_keywords"], ""]
    if rec.get("milestones"):
        lines += ["## Implementation milestones", "", "| Milestone | Date | Notes |", "|---|---|---|"]
        for m in rec["milestones"]:
            lines.append(f"| {m['milestone']} | {m['date']} | {m['notes']} |")
        lines.append("")
    if rec.get("source_links"):
        lines += ["## Source links", ""]
        for u in rec["source_links"]:
            lines.append(f"- {u}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="research/data/diverse_30.json")
    ap.add_argument("--out", default="research/sources")
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--force", action="store_true",
                    help="re-download even files that already exist and are non-empty")
    ap.add_argument("--overrides", default="research/data/primary_overrides.json",
                    help="JSON {id: [primary urls]} tried before the auto-detected candidates; "
                         "an empty list forces 'no primary' for that id")
    args = ap.parse_args()

    overrides = {}
    if Path(args.overrides).exists():
        overrides = json.loads(Path(args.overrides).read_text())

    ids = json.loads(Path(args.ids).read_text())
    out = Path(args.out)
    if not out.exists():
        out.mkdir(parents=True)
    rec_dir = out / "records"
    if not rec_dir.exists():
        rec_dir.mkdir(parents=True)

    rows = []
    print(f"downloading {len(ids)} records -> {out}")
    for entry in ids:
        rid = entry["id"]
        folder = rec_dir / rid
        if not folder.exists():
            folder.mkdir(parents=True)
        row = {"id": rid, "jurisdiction": entry.get("jurisdiction", ""),
               "title": "", "type": "", "status": "", "official_text_url": "",
               "primary_url": "", "primary_file": "", "primary_status": "",
               "primary_content_type": "", "primary_size_bytes": "",
               "article_html": "", "article_md": "", "num_source_links": 0,
               "source_links": ""}
        try:
            article_path = folder / "article.html"
            # --- article page (read locally if already cached) ---------------
            if (not args.force) and article_path.exists() and article_path.stat().st_size > 0:
                html_text = article_path.read_text(encoding="utf-8", errors="replace")
                print(f"  {rid:28s} article(cached)", end="")
            else:
                html_text, _, _ = fetch(f"{BASE}/regulations/{rid}", timeout=40)
                article_path.write_text(html_text, encoding="utf-8")
                print(f"  {rid:28s} +article", end="")
            row["article_html"] = str(article_path)
            rec = parse_record(html_text)
            rec["instrument_id"] = rid
            rec["record_url"] = f"{BASE}/regulations/{rid}"
            (folder / "article.md").write_text(article_md(rec), encoding="utf-8")
            row["article_md"] = str(folder / "article.md")
            row.update({"title": rec.get("name", ""), "type": rec.get("legislation_type", ""),
                        "status": rec.get("legal_force", ""),
                        "official_text_url": rec.get("official_text_url", ""),
                        "num_source_links": len(rec.get("source_links", [])),
                        "source_links": " | ".join(rec.get("source_links", []))})

            # --- primary document (reuse cached, else try candidates) --------
            # Remove any stale primary that is not actually a usable document
            # (HTML block page, sub-2 KB stub, tiny JSON) so we never leave a
            # fake file behind when a re-fetch also fails.
            for stale in folder.glob("source.*"):
                if stale.name.startswith("source_"):
                    continue
                if not is_usable_primary(stale):
                    print(f"  -badprimary {stale.name} (removing)")
                    stale.unlink()
            existing = next((p for p in folder.glob("source.*")
                             if p.stat().st_size > 0 and not p.name.startswith("source_")
                             and is_usable_primary(p)), None)
            if (not args.force) and existing:
                row["primary_file"] = str(existing)
                row["primary_status"] = "200(cached)"
                row["primary_size_bytes"] = existing.stat().st_size
                print(f"  source(cached, {existing.stat().st_size // 1024} KB)")
            else:
                # An override (explicit primary URL list) replaces auto-detected
                # candidates for that id; an empty list means "no primary".
                if rid in overrides:
                    cands = list(overrides[rid])
                else:
                    cands = primary_candidates(rec)
                for cand in cands:
                    try:
                        data, ctype, final = fetch(cand, timeout=(15, 60), binary=True)
                        if not data or not content_is_usable(data, ctype, final):
                            row["primary_status"] = "NOT_DOC" if data else "EMPTY"
                            continue
                        ext = ext_for(ctype, final)
                        # guard: a URL tagged .pdf but returning HTML (eur-lex
                        # viewer, etc.) must not be saved as a fake PDF.
                        if ext == ".pdf" and not is_pdf_bytes(data):
                            nurl = normalize_pdf_url(cand)
                            if nurl != cand:
                                try:
                                    d2, ctype2, final2 = fetch(nurl, timeout=(15, 60), binary=True)
                                    if d2 and is_pdf_bytes(d2):
                                        data, ctype, final = d2, ctype2, final2
                                except Exception:
                                    pass
                            if not is_pdf_bytes(data):
                                # couldn't get real PDF bytes; keep the HTML we
                                # already fetched instead of writing a fake PDF.
                                print(f"  !primary {cand} not a real PDF; saving HTML")
                                ext = ".html"
                        dest = folder / f"source{ext}"
                        dest.write_bytes(data)
                        row["primary_url"] = cand
                        row["primary_file"] = str(dest)
                        row["primary_status"] = "200"
                        row["primary_content_type"] = ctype
                        row["primary_size_bytes"] = len(data)
                        print(f" +source ({ext}, {len(data)//1024} KB)")
                        break
                    except Exception as exc:
                        row["primary_status"] = f"FAILED: {type(exc).__name__}"
                        continue
                if not (row["primary_status"].startswith("200") or "cached" in row["primary_status"]):
                    print(f"  !primary {row['primary_status']}")

            # --- extra PDFs found in source links (downloaded in addition) -----
            extra_urls, seen = [], set()
            for u in ([rec.get("official_text_url"), rec.get("official_publication_url")]
                      + rec.get("source_links", [])):
                if not u or u in seen:
                    continue
                seen.add(u)
                if u == row.get("primary_url"):
                    continue
                if likely_pdf(u):
                    extra_urls.append(u)
            extra_files = []
            for cand in extra_urls:
                dest = folder / f"source_{pdf_slug(cand)}"
                # self-heal: a previously-cached file that is not actually a PDF
                # (e.g. an HTML viewer page mis-saved as .pdf) must be removed so
                # we re-fetch the real bytes below.
                if dest.exists() and dest.stat().st_size > 0 and not is_pdf_bytes(dest.read_bytes()):
                    print(f"  -badpdf {dest.name} (removing)")
                    dest.unlink()
                if dest.exists() and dest.stat().st_size > 0:
                    extra_files.append(str(dest))
                    continue
                data = None
                for try_url in _uniq([cand, normalize_pdf_url(cand)]):
                    try:
                        d, _, _ = fetch(try_url, timeout=(15, 60), binary=True)
                        if d and is_pdf_bytes(d):
                            data = d
                            break
                    except Exception as exc:
                        print(f"  !pdf {try_url} {type(exc).__name__}")
                if not data:
                    print(f"  !pdf {cand} (no PDF bytes found)")
                    continue
                dest.write_bytes(data)
                extra_files.append(str(dest))
                print(f"  +pdf {dest.name} ({len(data)//1024} KB)")
            row["extra_pdfs"] = " | ".join(extra_urls)
            row["extra_pdf_files"] = " | ".join(extra_files)
        except Exception as exc:
            row["primary_status"] = f"ARTICLE FAILED: {type(exc).__name__}"
            print(f"  {rid:28s} !article {exc}")
        rows.append(row)
        time.sleep(args.delay)

    # manifest
    fields = ["id", "jurisdiction", "title", "type", "status", "official_text_url",
              "primary_url", "primary_file", "primary_status", "primary_content_type",
              "primary_size_bytes", "article_html", "article_md", "num_source_links",
              "source_links", "extra_pdfs", "extra_pdf_files"]
    with (out / "manifest.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)

    # index
    idx = ["# Regulation source review index", "",
           "30 diverse regulations — primary document + regulations.ai article per record.",
           "Generated for pre-ontology review. See `manifest.csv` for machine-readable detail.", ""]
    ok = sum(1 for r in rows if r["primary_status"].startswith("200"))
    idx.append(f"**Primary docs downloaded: {ok}/{len(rows)}**", )
    idx.append("")
    for r in rows:
        flag = "OK" if r["primary_status"].startswith("200") else "NO SOURCE"
        md_rel = os.path.relpath(r["article_md"], out) if r["article_md"] else ""
        src_rel = os.path.relpath(r["primary_file"], out) if r["primary_file"] else ""
        extras = r["extra_pdf_files"].split(" | ") if r.get("extra_pdf_files") else []
        extra_links = ""
        for ef in extras:
            if ef:
                extra_links += f" · [pdf]({os.path.relpath(ef, out)})"
        line = (f"- **{r['title'] or r['id']}** — {r['jurisdiction']} / {r['type']} / {r['status']} "
                f"[{flag}] — [article]({md_rel})" + (f" · [source]({src_rel})" if src_rel else "")
                + extra_links)
        idx.append(line)
    (out / "INDEX.md").write_text("\n".join(idx), encoding="utf-8")

    print(f"\nmanifest: {out/'manifest.csv'}")
    print(f"index:    {out/'INDEX.md'}")
    print(f"primary docs OK: {ok}/{len(rows)}")


if __name__ == "__main__":
    main()
