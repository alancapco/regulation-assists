#!/usr/bin/env python3
"""把 213 条真实日历事件加载为独立 :CalendarEvent 节点（无关系、无伪造 Regulation）。
必须在 neo4j_loader.py --reset 之后运行，否则 --reset 会清空本脚本写入的节点。
用法：uv run python research/poc/load_calendar_events.py --uri bolt://localhost:7688
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from neo4j import GraphDatabase

CONSTRAINT = (
    "CREATE CONSTRAINT calendar_event_uid IF NOT EXISTS "
    "FOR (e:CalendarEvent) REQUIRE e.uid IS UNIQUE"
)
LOAD = """
UNWIND $rows AS row
MERGE (e:CalendarEvent {uid: row.uid})
SET e.date = row.date,
    e.title = row.title,
    e.instrument_id = row.instrument_id,
    e.regulation_name = row.regulation_name,
    e.jurisdiction = row.jurisdiction,
    e.jur_filter = row.jur_filter,
    e.source_url = row.source_url
"""


def rows(path: str) -> list[dict]:
    out = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        out.append(
            {
                "uid": f"cal-{c['position']:03d}",  # position 唯一稳定，作主键
                "date": c["date"],  # 源数据已是 ISO
                "title": c["event_label"],  # 短事件名；regulation_name 另给，避免重复
                "instrument_id": c["instrument_id"],
                "regulation_name": c["instrument_title"],
                "jurisdiction": c["jurisdiction"],  # 原始细粒度值，用于展示
                # 为什么用 country 做过滤键：日历有 59 种细粒度 jurisdiction，
                # 而 /api/filters 只下发 13 个法规管辖区；country 是归一后的宽口径，
                # 让 P-003 的 Select 能命中 156/213 条，且不新增任何契约字段。
                "jur_filter": c.get("country") or c["jurisdiction"],
                "source_url": c.get("official_source_url") or None,
            }
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", default="research/data/calendar_events.jsonl")
    # 为什么默认值也设为 7688：loader 的默认是 7687（共享库），误用会写共享库。
    ap.add_argument("--uri", default="bolt://localhost:7688")
    ap.add_argument("--user", default="neo4j")
    ap.add_argument("--password", default="capco-graph-change-me")
    a = ap.parse_args()

    driver = GraphDatabase.driver(a.uri, auth=(a.user, a.password))
    driver.verify_connectivity()
    with driver.session() as s:
        s.run(CONSTRAINT)  # 自持约束，不改 research/poc/neo4j_schema.cypher
        data = rows(a.infile)
        s.run(LOAD, rows=data)
        n = s.run("MATCH (e:CalendarEvent) RETURN count(e) AS c").single()["c"]
        print(f"loaded {len(data)} rows; CalendarEvent nodes now: {n}")
    driver.close()


if __name__ == "__main__":
    main()
