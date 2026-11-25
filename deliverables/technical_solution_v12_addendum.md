# 技术方案 v1.2 附录 · 隔离容器 + 全量数据（数据面基线）

**架构师：** 高见远　|　**版本：** v1.2 附录（不重写 v1.1 正文 1304 行）　|　**日期：** 2026-11-11
**上游：** `technical_solution.md` v1.1（§5/§6/§7 冻结面不变）、`product_design_specification.md` v1.1
**读者：** team-lead → feature-planner → 全体 fullstack-dev。**本附录是数据面 + 配置的唯一权威基线。**
**落盘：** 本文 `deliverables/technical_solution_v12_addendum.md`；`docker-compose.app.yml`、`research/poc/build_app_records.py`、`research/poc/load_calendar_events.py` 均已落盘。

> 四原则：① 简洁为荣、冗余为耻（复用 `parse_record` / `neo4j_loader.py`，不重写解析正则、不复制投影）；② 注释只在关键处（中文，解释「为什么」）；③ 契约冻结；④ 交付必须落盘。

## 0. 锁定决策与适用范围

| 项 | 裁定 | 影响面 |
|---|---|---|
| **R4** | **`links[].type` 保留 `type`**（team-lead 的 "kind" 为转录笔误） | **零变更**，无契约变更、无需升版 |
| **R2** | 加载 `research/data/calendar_events.jsonl` 的**真实 213 条**事件 | 数据面 + `cypher.py::Q_CALENDAR` |
| **R3** | 加载 `diverse_30.json` 的 **30 条**法规（含 EU AI Act / eur-lex） | 数据面，F-002/F-003 验收示例恢复可用 |
| 用户决策 | **隔离容器 + 全量数据**；对共享库 `capco-graph-neo4j` **零写入** | §1–§4 |

**v1.1 中哪些被取代**：§4.3 / §4.4 / §12.2 的节点计数、枚举值、61 条 Milestone、APEC/African Union/Argentina，及 §12.1 活库冒烟清单的 `regulation_count=30` / `filters 3/5/3/10`，均为**旧共享库**口径，对应用侧失效，以本附录 §6 为准。v1.1 的 §5（契约）、§6（C1/C2/C3/C5/C6）、§7（映射规则）、§9–§14 **继续有效**；**例外**：§6.0「C2–C6 全含 `r.instrument_id IS NOT NULL`」对 C4 作废、§12.1 护栏按条件触发，见 §7 末条。

## 1. 隔离容器 `docker-compose.app.yml`（已落盘，全文如下）

```yaml
name: regulation-app          # 显式 project，避免同 project 下 service=neo4j 被 Compose 误判替换
services:
  neo4j:
    image: neo4j:5.26-community
    container_name: capco-app-neo4j
    ports:
      - "7475:7474"           # HTTP browser（共享容器占 7474）
      - "7688:7687"           # Bolt（共享容器占 7687）；后端连此端口
    environment:
      NEO4J_AUTH: "neo4j/capco-graph-change-me"   # 与共享容器同密码 → 切回只需改 URI 一行
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_dbms_security_auth__minimum__password__length: "6"
      NEO4J_dbms_memory_heap_initial__size: "512m"
      NEO4J_dbms_memory_heap_max__size: "1G"
      NEO4J_dbms_memory_pagecache_size: "512m"
    volumes:
      - ./neo4j-app/data:/data
      - ./neo4j-app/logs:/logs
      - ./neo4j-app/import:/var/lib/neo4j/import
    healthcheck:
      test: ["CMD-SHELL", "cypher-shell -u neo4j -p capco-graph-change-me 'RETURN 1' >/dev/null 2>&1 || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 30
      start_period: 60s
    restart: unless-stopped
```

- **隔离三重保证**：不同 project（`regulation-app` vs 共享的 `regulation-assits`）／不同容器名／不同端口／不同 volume 目录 `./neo4j-app/`。共享容器 `capco-graph-neo4j` **不在本 compose 内**，本附录所有命令都不对它执行 up/down/stop 或写数据。
- 已用 `docker compose -f docker-compose.app.yml config` 验证：project、容器名、7475/7688、`neo4j-app/*` volume 均正确；两端口当前空闲。
- **环境观测**：落盘时 `docker ps -a` 显示共享容器为 `Exited (0)`（核验 v1.1 时我曾启动过）。按「不改动共享容器运行时」要求**我未重启**；如需恢复由共享库属主执行 `docker start capco-graph-neo4j`。应用连 7688，不受影响。

## 2. 后端配置（指向 7688）

`.env.example` 与 v1.1 §3.1 **只改一行**（其余 9 项原样）：
```dotenv
NEO4J_URI=bolt://localhost:7688      # 隔离容器 Bolt；改回 7687 即切回共享库，仅此一行
```
`backend/app/config.py`：`neo4j_uri: str = "bolt://7688"` 同步改为 `bolt://localhost:7688`，其余字段与 v1.1 §3.2 完全一致；`Settings` 走 `pydantic-settings`，**`NEO4J_URI` 环境变量优先** → 切换数据源是**一行 env 改动、零代码改动**。仍**不设** `LLM_*` 环境变量（凭据只在前端 localStorage）。

## 3. 三处旧密码修复（已落盘）

| 文件 | 行 | 修改 |
|---|---|---|
| `docker-compose.yml` | 36 | healthcheck `regpass123` → `capco-graph-change-me` |
| `research/poc/neo4j_loader.py` | 28 | docstring 示例密码同上 |
| `research/poc/neo4j_loader.py` | 192 | `--password` 默认值同上 |

全仓已无 `regpass123` 残留。**未改动共享容器的 `NEO4J_AUTH`、未重建容器、未写其数据**；修复只让 healthcheck 凭据与既有认证一致（原先恒 unhealthy）。

## 4. 数据准备流水线（脚本已落盘，Batch-0 只需运行）

### 4.1 脚本 A：`research/poc/build_app_records.py` → `research/data/app_records.jsonl`

复用 `download_sources.parse_record(html_text)`（已实测对 30 份缓存 `article.html` 全部成功、恰好返回 14 键），补齐 5 个派生键，输出与 `regulation_records.jsonl` **同序 19 键**。伪码（全文已落盘）：
```python
KEYS19 = ["instrument_id","record_url","name","legislation_type","jurisdiction",
          "legislation_date","legal_force","description","official_publication_url",
          "official_text_url","in_language","date_modified","license","sd_date_published",
          "topic_keywords","full_analysis_is_free","breadcrumb","milestones","source_links"]
for rid in [x["id"] for x in diverse_30.json]:
    rec = parse_record(read(f"research/sources/records/{rid}/article.html"))   # 14 键
    # 5 个派生键：MVP 后端不消费 sd_date_published/full_analysis_is_free/breadcrumb，
    # 给中性默认值即可；record_url 由 id 按站点固定规则拼装
    rec |= dict(instrument_id=rid, record_url=f"https://regulations.ai/regulations/{rid}",
                sd_date_published="", full_analysis_is_free=False, breadcrumb="")
    emit({k: rec.get(k, "") for k in KEYS19})
```
> `parse_record` 的 `milestones` 元素为 `{milestone,date,notes}`，与 loader 的 `clean_milestones()` 读取的键完全一致，无需适配。**已离线跑通：30 行 / 19 键顺序完全一致 / EU AI Act 与 eur-lex 均在。**

### 4.2 运行既有 loader（隔离库）

```bash
uv run python research/poc/neo4j_loader.py \
  --in research/data/app_records.jsonl \
  --uri bolt://localhost:7688 \
  --user neo4j --password capco-graph-change-me --reset
```
- `--reset` 先清空**隔离库**，随后 loader 自动读取并执行同目录 `neo4j_schema.cypher` 的全部约束/索引（**无需手工跑 cypher-shell**），再写入 30 条记录。
- **⚠️ 边界**：loader 的 `--uri` 默认仍是 `bolt://localhost:7687`（共享库）。**每次必须显式带 `--uri bolt://localhost:7688`**，误用默认值会写共享库、违反本次决策。执行前 `docker ps` 确认 `capco-app-neo4j` 在跑。

### 4.3 脚本 B：`research/poc/load_calendar_events.py` → 213 个 `:CalendarEvent` 节点

**必须在 4.2 之后运行**（`--reset` 会清库）。独立节点、**不建关系、不伪造 Regulation 节点**：213 条事件涉及 121 个 `instrument_id`，仅 8 个在 diverse_30 中有 `Regulation` 节点；JSONL 已自带 `instrument_title` / `jurisdiction`，无需 join。伪码（全文已落盘）：
```python
CONSTRAINT = "CREATE CONSTRAINT calendar_event_uid IF NOT EXISTS FOR (e:CalendarEvent) REQUIRE e.uid IS UNIQUE"
LOAD = """UNWIND $rows AS row
MERGE (e:CalendarEvent {uid: row.uid})
SET e.date=row.date, e.title=row.title, e.instrument_id=row.instrument_id,
    e.regulation_name=row.regulation_name, e.jurisdiction=row.jurisdiction,
    e.jur_filter=row.jur_filter, e.source_url=row.source_url"""
row = dict(uid=f"cal-{c['position']:03d}", date=c["date"], title=c["event_label"],
           instrument_id=c["instrument_id"], regulation_name=c["instrument_title"],
           jurisdiction=c["jurisdiction"],       # 原始细粒度值，用于展示
           # 为什么用 country 做过滤键：日历有 59 种细粒度 jurisdiction，
           # 而 /api/filters 只下发 13 个法规管辖区；country 是归一后的宽口径，
           # 让 P-003 的 Select 命中 156/213 条，且不新增任何契约字段
           jur_filter=c.get("country") or c["jurisdiction"],
           source_url=c.get("official_source_url") or None)
```
运行：`uv run python research/poc/load_calendar_events.py --uri bolt://localhost:7688`（脚本默认 URI 已设为 7688，仍建议显式带）。约束由脚本自持，**不改 `research/poc/neo4j_schema.cypher`**。**已离线验证行生成器：213 行 / uid 全唯一 / `jur_filter` 覆盖 156 条 / `source_url` 无 null。**

## 5. 213 事件方案与 `Q_CALENDAR`（C4）Cypher delta

**选型：独立 `:CalendarEvent` 节点（方案 a），不复用 `:Milestone`。** 理由：`:Milestone` 由 4.2 从 `record.milestones` 生成 110 个节点、且靠 `HAS_MILESTONE` 挂在 `Regulation` 下；若混入日历，C4 必须加标记属性 + 放宽 MATCH，且 121 个无 `Regulation` 的 instrument 会被关系过滤掉。独立节点让 C4 变成一条平铺查询，**映射层零改动**。record 里程碑仍只服务 C3 的 `Regulation.milestones[]`，两套互不干扰、不重复计数。

冻结字段映射（全部来自 JSONL，无 join）：`id←uid`(position→`cal-NNN`)｜`date←date`(已 ISO)｜`title←event_label`｜`instrument_id←instrument_id`｜`regulation_name←instrument_title`｜`jurisdiction←jurisdiction`(原始值)｜`source_url←official_source_url`(空→null)。内部属性 `jur_filter←country` **不在契约中**。

**`backend/app/cypher.py::Q_CALENDAR` 全文替换为**（v1.1 §6 C4 作废）：
```cypher
MATCH (e:CalendarEvent)
WHERE ($jurisdiction = '' OR e.jur_filter = $jurisdiction)
RETURN
  e.uid             AS id,
  e.date            AS date_raw,
  e.title           AS title,
  e.instrument_id   AS instrument_id,
  e.regulation_name AS regulation_name,
  e.jurisdiction    AS jurisdiction,
  e.source_url      AS source_url
ORDER BY e.date
```
**变更点（仅此一处常量）**：① `MATCH (r)-[:HAS_MILESTONE]->(m)` → `MATCH (e:CalendarEvent)`，去掉关系 join；② 去掉 `WHERE r.instrument_id IS NOT NULL`（本查询不碰 `:Regulation`，隔离库无外来节点；若误连共享库会安全返回 `[]`）；③ 管辖区过滤由 `EXISTS{...}` → `e.jur_filter = $jurisdiction`。
**7 个 RETURN 别名与 v1.1 完全一致** → `map_calendar_event()` / `normalize_date()` / `apply_date_filter()` / 排序 / `source_url` 空值处理**全部零改动**；API-005 默认仍不传 `date_from/date_to`（返回全量 213 条、按日期升序），「未来 12 个月」仍是前端快捷按钮，**计数动态、禁止硬编码 213**。

## 6. 隔离库计数（**已在 7688 隔离库实测**，与离线推算逐项吻合）

| 项 | 期望值 |
|---|---|
| `/api/status` | `{"connected": true, "regulation_count": 30, "total_count": 1174}` |
| `/api/filters` | jurisdictions **13**（diverse_30，含 EU / US / China…，不再是 APEC/African Union/Argentina）；types **6**（Act/Bill/Decree/Guideline/Policy/Regulation）；legal_forces **2**（InForce/PartiallyInForce）；topics **11** |
| `/api/regulations` | 30 条，含 `RAI-EU-NA-E2AIXXX-2024`（Regulation (EU) 2024/1689、eur-lex.europa.eu） |
| `/api/calendar` | **213** 条（默认无日期过滤），2026-11-27 → 2045-12-31，全部 ISO |
| `/api/graph` | 候选约 30+13+11+130 = 184 节点 > 100 → **截断规则仍生效**，悬空边仍由 `map_graph` 丢弃 |
| 图内其它 | Source 130 / Milestone 110 / InstrumentType 6 / CalendarEvent 213 |

> `Milestone` 110 个**只进 C3 的 `Regulation.milestones[]`**，不再进日历；`InstrumentType` 仍按 M4 排除在 `/api/graph` 之外。9/30 条 `legislation_date` 为仅年份（如 `2026`）→ 仍按 v1.1 §7 归一为 `null`。

## 7. 契约影响声明（⛔ 冻结确认）

- **字段名 / 类型 / 枚举 / 端点路径 / 查询参数：零变更。** `Regulation` / `CalendarEvent` / `GraphData`（`links[].type` 保持 `type`，3 值）/ `AppStatus` / `FilterOptions`（仍 4 个列表）/ `ErrorEnvelope` / `LlmConfig` 全部照 v1.1 §5.2 与设计师 §8。
- **仅新增数据面内部物**：新图标签 `:CalendarEvent`、内部属性 `e.jur_filter`、新约束 `calendar_event_uid`、2 个已落盘脚本；`backend/app/cypher.py` 只有 `Q_CALENDAR` 一个常量被替换。
- `schemas.py` / `frontend/src/types/contract.ts` **无需改动**；无需新增测试（v1.1 §12.1 的 `test_mapping.py` 仍覆盖映射层）。
- **R4 已由 team-lead 确认 `type`，不升契约版本**；本附录是 v1.2 **数据面**附录，v1.1 契约继续冻结。今后任何字段名/类型/枚举变更仍走 v1.1 §14 并由我签字。
- **与 v1.1 §6.0 / §12.1 的口径衔接**：§6.0「C2–C6 全含 `r.instrument_id IS NOT NULL`」对 C4 **作废**（新 C4 无 `r` 别名，硬套会 `Variable r not defined`），C2/C3/C5/C6 仍保留该条件作为误连共享库 7687 的防御；§12.1 `test_cypher.py` 护栏本就是「含 `MATCH (r:Regulation)` 才断言」，C4 天然跳过，**不得改成「每条模板一律断言」再给 C4 开白名单**（会削弱 R1 护栏）。
- **治理收口**：v1.1 §15 列的 3 项待决至此全部关闭 —— R4 由 team-lead 确认 `type`；R2（213 条）、R3（diverse_30 / EU AI Act）由本附录数据面落地。v1.1 §15 该行措辞以本条为准，v1.1 正文不改写。

## 8. Batch-0 执行顺序（严格按序，完成前不解锁并行开发）

1. `docker compose -f docker-compose.app.yml up -d` → `docker ps` 确认 `capco-app-neo4j` 在 7475/7688；**共享容器不动**。
2. `uv run python research/poc/build_app_records.py` → `research/data/app_records.jsonl`（30 行 / 19 键）。
3. `uv run python research/poc/neo4j_loader.py --in research/data/app_records.jsonl --uri bolt://localhost:7688 --user neo4j --password capco-graph-change-me --reset`（约束由 loader 自动建）。
4. `uv run python research/poc/load_calendar_events.py --uri bolt://localhost:7688`（**必须在 3 之后**，`--reset` 会清库）。
5. 冒烟核对：`MATCH (n) RETURN labels(n)[0], count(n)` → Regulation 30 / CalendarEvent 213 / Jurisdiction 13 / Topic 11 / Source 130；并跑一次新 `Q_CALENDAR` 空过滤确认 213 行、7 键齐全。
6. **后端 T0**（v1.1 §10 #1–#6，一名开发一次性落地）：`schemas.py`、`config.py`（7688）、`errors.py`、`deps.py`、`cypher.py`（**用本附录 §5 的新 C4**）、`mapping.py`；扩展根 `pyproject.toml` 后 `uv sync`。
7. **前端 T0**（v1.1 §10 #8–#13）：`types/contract.ts`、`api/client.ts`、`hooks/useApi.ts`、`hooks/useLlmConfig.ts`、`components.json` + shadcn init、`Shell/StatusBar/EmptyState/ErrorState`；`npm install`。
8. **最小闭环验收**：`uv run uvicorn backend.app.main:app --reload --port 8000` → `curl /api/status`（30/1174）、`/api/regulations`（30 条含 EU AI Act）、`/api/calendar`（213 条）、`/api/filters`（13/6/2/11）。
9. 第 8 步通过 → **解锁并行开发**（routers/*、pages/*、D3ForceGraph 各一人）；未通过不得开工。

**架构师已预执行并实测步骤 1–5**（隔离容器 `capco-app-neo4j` 已在 7475/7688 运行、30 条法规 + 213 事件已加载；全部写操作仅针对 7688，共享库零写入）：节点计数 `Regulation 30 / CalendarEvent 213 / Jurisdiction 13 / Topic 11 / Source 130 / Milestone 110 / InstrumentType 6`；`Q_CALENDAR` 空过滤返回 213 行且 7 个键齐全、`jurisdiction=European Union` 返回 38 行；EU AI Act 与 eur-lex 链接已就位。**dev 可直接从步骤 6 开始**；若需重跑数据面，顺序仍为 1→2→3→4（`--reset` 后必须重跑 4），全部命令幂等。

## 9. 风险与边界（中文注释只写这些「为什么」）

| 风险 | 应对 |
|---|---|
| loader `--uri` 默认 7687 指向共享库 | §4.2/4.3/步骤 3–4 全部**显式 `--uri 7688`**；执行前 `docker ps` 二次确认 |
| `--reset` 清空整个隔离库 | 日历 loader **固定排在步骤 4**；任何重跑主 loader 后必须重跑步骤 4 |
| 日历 jurisdiction 有 59 种细粒度值，`/api/filters` 只有 13 个法规管辖区 | 用 `country` 派生 `jur_filter`（156/213 可筛）；其余 57 条仅在「全部」视图可见。**不改契约、不给 FilterOptions 加第 5 个列表**（否则 P-001 过滤器被污染） |
| 日历 121 个 instrument_id 只有 8 个有 `Regulation` 节点 | 独立节点、不建关系、**不造假的 Regulation**；`regulation_name/jurisdiction` 直接取 JSONL |
| 图谱候选 184 > 100 | v1.1 §7.5 `map_graph` 截断 + 丢悬空边 + 前端 `nodes.length>=100` 提示，不变 |
| 共享容器当前 `Exited(0)` | 我未重启（遵守不改其运行时）；应用连 7688 不受影响 |

---
**文档状态：** 已完成并冻结，交付 team-lead / feature-planner / 全体 fullstack-dev
**落盘：** `deliverables/technical_solution_v12_addendum.md`；配套 `docker-compose.app.yml`、2 个数据准备脚本已落盘，3 处旧密码已修复。
