import re
from urllib.parse import urlparse

from backend.app.schemas import (
    CalendarEvent, FilterOptions, GraphData, GraphLink, GraphNode,
    Milestone, OfficialSource, Regulation,
)

ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
REL_PRIORITY = {"HAS_OFFICIAL_TEXT": 0, "PUBLISHED_AT": 1, "SOURCED_FROM": 2}


def normalize_date(raw: object) -> str | None:
    """为什么：图谱的 Milestone.date 含范围/'(Approx.)'/HTML 残留，legislation_date 还有
    仅年份('2023')；契约只允许 YYYY-MM-DD 或 null。取首个 ISO 起始日期（需求 §7.4），
    仅年份/无法解析返回 None——不伪造 01-01，避免给合规研究虚假精确日期。"""
    if not raw:
        return None
    m = ISO_RE.search(str(raw))
    return m.group(0) if m else None


def _domain(url: str) -> str:
    return urlparse(url).netloc if url else ""


def normalize_domain(raw: str | None, url: str) -> str:
    # D2：domain 一律后端算，Source.domain 缺失时从 url 兜底
    return raw or _domain(url)


def map_official_sources(raw: list[dict]) -> list[OfficialSource]:
    """≤3 条；按 URL 去重（26/30 条法规的 official_text_url 与 publication_url 相同，
    不去重会渲染重复链接）；同一 URL 保留优先级更高的真实 rel_type。"""
    best: dict[str, tuple[int, str, str]] = {}
    for item in raw or []:
        url = item.get("url") or ""
        if not url:
            continue
        rel = item.get("rel_type") or "SOURCED_FROM"
        p = REL_PRIORITY.get(rel, 9)
        if url not in best or p < best[url][0]:
            best[url] = (p, rel, item.get("domain"))
    ordered = sorted(best.items(), key=lambda kv: (kv[1][0], kv[0]))[:3]
    return [OfficialSource(url=u, domain=normalize_domain(d, u), rel_type=rel)
            for u, (_, rel, d) in ordered]


def map_milestones(raw: list[dict]) -> list[Milestone]:
    # title ← m.name（M2）；归一后按 date 升序，null 排末尾（契约要求升序）
    out = [Milestone(date=normalize_date(x.get("date")), title=x.get("title") or "",
                     notes=x.get("notes"))
           for x in (raw or [])]
    return sorted(out, key=lambda m: (m.date is None, m.date or ""))


def map_regulation(rec: dict) -> Regulation:
    """列表/详情共用（D1），唯一 Regulation 构造入口。"""
    return Regulation(
        instrument_id = rec["instrument_id"],
        name          = rec.get("name") or "",
        jurisdiction  = rec.get("jurisdiction") or "",
        type          = rec.get("type") or "",
        legal_force   = rec.get("legal_force") or "",
        legislation_date = normalize_date(rec.get("legislation_date")),
        description   = rec.get("description"),
        record_url    = rec.get("record_url") or "",
        official_sources = map_official_sources(rec.get("official_sources_raw")),
        topics        = sorted({t for t in (rec.get("topics") or []) if t}),
        milestones    = map_milestones(rec.get("milestones_raw")),
        last_modified = rec.get("last_modified"),
        resume        = rec.get("resume"),
        official_text_url = rec.get("official_text_url"),
        publication_url   = rec.get("publication_url"),
        plain_english = rec.get("plain_english"),
        overview = rec.get("overview"),
        definitions = rec.get("definitions"),
        governance_framework = rec.get("governance_framework"),
        key_focus_areas = rec.get("key_focus_areas"),
        implementation_framework = rec.get("implementation_framework"),
        # Rich content fields
        summary = rec.get("summary"),
        monitoring_evaluation = rec.get("monitoring_evaluation"),
        penalties_liability = rec.get("penalties_liability"),
        relationship_to_other = rec.get("relationship_to_other"),
        international_alignment = rec.get("international_alignment"),
        implementation_timeline = rec.get("implementation_timeline"),
        requirements_must_do = rec.get("requirements_must_do") or [],
        requirements_should_do = rec.get("requirements_should_do") or [],
        requirements_must_not_do = rec.get("requirements_must_not_do") or [],
        requirements_should_not_do = rec.get("requirements_should_not_do") or [],
        obligations = rec.get("obligations") or [],
    )


def map_calendar_event(rec: dict) -> CalendarEvent | None:
    # M2: id ← m.uid；M5: 归一失败才跳过（F-004）
    date = normalize_date(rec.get("date_raw"))
    if date is None:
        return None
    return CalendarEvent(
        id=rec["id"], date=date, title=rec.get("title") or "",
        instrument_id=rec["instrument_id"],
        regulation_name=rec.get("regulation_name") or "",
        jurisdiction=rec.get("jurisdiction") or "",
        source_url=rec.get("source_url") or None,
    )


def apply_date_filter(items: list, date_from: str, date_to: str, key: str) -> list:
    """为什么放在映射层而不是 Cypher：legislation_date / Milestone.date 都是脏文本，
    必须'先归一再比较'；Cypher 里对 '2023'、'2024-07-18 to ...' 做字符串 >= 会出错。
    30/213 行数据量下无性能代价，且日期值根本不进入 Cypher，注入面为零。
    空串(无日期条件)直接返回全量并保留 None 日期行——默认视图须返回 30 条法规，
    而非凭空丢 9 条仅年份的法规；仅显式给定区间才裁剪。
    API-003 用 key='legislation_date'，API-005 用 key='date'，两处共用同一实现。"""
    if not date_from and not date_to:   # 无日期条件 = 不过滤，保留含 None 日期的行
        return list(items)
    out = []
    for it in items:
        d = it.get(key) if isinstance(it, dict) else getattr(it, key)
        if d is None:                      # 无法归一的日期不参与任何日期区间
            continue
        if date_from and d < date_from:
            continue
        if date_to and d > date_to:
            continue
        out.append(it)
    return out


def map_filters(rec: dict) -> FilterOptions:
    def clean(xs): return sorted(v for v in (xs or []) if v)
    return FilterOptions(jurisdictions=clean(rec.get("jurisdictions")),
                         types=clean(rec.get("types")),
                         legal_forces=clean(rec.get("legal_forces")),
                         topics=clean(rec.get("topics")))


def map_graph(rows: list[dict], max_nodes: int = 100) -> GraphData:
    """节点优先级 regulation > jurisdiction > topic > source；总上限 max_nodes。
    为什么必须'先定节点、再生成 link'：d3.forceLink 会把 link.source/target 解析为节点，
    若 link 指向被裁掉的节点，d3 会凭空造出幽灵节点或直接报错。"""
    nodes: list[GraphNode] = []
    seen: set[str] = set()
    def add(nid: str, label: str, ntype: str) -> None:
        if nid and nid not in seen and len(nodes) < max_nodes:
            seen.add(nid)
            nodes.append(GraphNode(id=nid, label=label or "", type=ntype))

    # 第一轮先把所有法规锚点放进去，保证点 Regulation 能跳详情
    for row in rows:
        add(row["rid"], row["rname"], "regulation")
    # 后续按类型优先级补邻居
    for row in rows:
        for n in row.get("jurs") or []:    add(n["id"], n["label"], "jurisdiction")
    for row in rows:
        for n in row.get("topics") or []:  add(n["id"], n["label"], "topic")
    for row in rows:
        for n in row.get("sources") or []: add(n["id"], n["label"], "source")

    links: list[GraphLink] = []
    def link(src: str, tgt: str, ltype: str) -> None:
        if src in seen and tgt in seen:    # ★ 丢弃悬空边
            links.append(GraphLink(source=src, target=tgt, type=ltype))
    for row in rows:
        rid = row["rid"]
        for n in row.get("jurs") or []:    link(rid, n["id"], "IN_JURISDICTION")
        for n in row.get("topics") or []:  link(rid, n["id"], "HAS_TOPIC")
        for n in row.get("sources") or []: link(rid, n["id"], "SOURCED_FROM")

    # 去重：同一对节点可能因多个法规共享同一个 Jurisdiction/Topic 产生重复 link 描述
    uniq = {(l.source, l.target, l.type) for l in links}
    links = [GraphLink(source=s, target=t, type=k) for (s, t, k) in sorted(uniq)]
    return GraphData(nodes=nodes, links=links)
