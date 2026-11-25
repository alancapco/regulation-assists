#!/usr/bin/env python3
"""由 30 份缓存 article.html 生成 neo4j_loader.py 可直接消费的 19 键 JSONL。
用法：uv run python research/poc/build_app_records.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from download_sources import parse_record  # 复用既有解析，禁止重写正则

ROOT = Path(__file__).resolve().parents[2]
KEYS = [
    "instrument_id", "record_url", "name", "legislation_type", "jurisdiction",
    "legislation_date", "legal_force", "description", "official_publication_url",
    "official_text_url", "in_language", "date_modified", "license",
    "sd_date_published", "topic_keywords", "full_analysis_is_free", "breadcrumb",
    "milestones", "source_links",
]


def build() -> list[dict]:
    ids = [
        x["id"]
        for x in json.loads((ROOT / "research/data/diverse_30.json").read_text())
    ]
    out = []
    for rid in ids:
        html = (ROOT / f"research/sources/records/{rid}/article.html").read_text(
            errors="ignore"
        )
        rec = parse_record(html)  # 14 键
        # 5 个派生键：MVP 后端不消费 sd_date_published / full_analysis_is_free /
        # breadcrumb，给中性默认值即可；record_url 由 id 按站点固定规则拼装。
        rec.update(
            {
                "instrument_id": rid,
                "record_url": f"https://regulations.ai/regulations/{rid}",
                "sd_date_published": "",
                "full_analysis_is_free": False,
                "breadcrumb": "",
            }
        )
        out.append({k: rec.get(k, "") for k in KEYS})
    return out


def main() -> None:
    rows = build()
    dest = ROOT / "research/data/app_records.jsonl"
    dest.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    print(f"wrote {len(rows)} records -> {dest}")


if __name__ == "__main__":
    main()
