# 功能单元任务卡 · AI Regulation Corpus Explorer

**拆分师：** 拆得细 (feature-planner)　|　**版本：** v1.0　|　**日期：** 2026-11-11
**上游（冻结，按权威顺序）：** `technical_solution_v12_addendum.md` v1.2（数据面 / 隔离库 / 新 C4 / Batch-0 顺序，**最权威**）＞ `technical_solution.md` v1.1（§5 契约 / §6 Cypher / §7 映射 / §10 T0 / §11 前端 / §14 风险）＞ `product_design_specification.md` v1.1（§8 冻结契约 / §4 页面）＞ `requirements_specification.md` v1.0（§6 验收）。
**读者：** 多名 `fullstack-dev` 并行开工。**每张卡自包含：拿到卡即可写码，不得再问接口是什么、字段是什么。文中一律引用 API-XXX / 文档章节号，不重抄接口定义、不贴大段代码。**

---

## 0. 全局四原则（所有卡强制，写进每张卡的 Code Review 检查表）

1. **简洁为荣，冗余为耻** — 公共能力只由 U-000 实现一次；各卡只 import，禁止另写一套模型 / 映射 / fetch / 控件；不设 Repository / Service / 统一包装层 / 缓存 / Redux / TanStack Query。
2. **注释只在关键处** — 仅核心逻辑、边界、易错点写**中文**注释，解释「**为什么**」；禁止逐行旁白、禁止英文 narration。允许位置见 v1.1 §13。
3. **契约冻结** — §5 / §6 / §7 / 设计稿 §8 全部冻结；任何字段名 / 类型 / 枚举 / 端点 / 查询参数变更，卡片**立即 STOP 并上报 team-lead**，走 v1.1 §14，禁止口头约定、禁止只改代码不改文档。
4. **交付必须落盘** — 代码落在 v1.1 §2.2 指定路径；本文档已落盘 `deliverables/feature_task_cards.md`。

### 0.1 已验证状态（team-lead 实测，视为事实，勿重复核验）

- 隔离容器 `capco-app-neo4j` **Up (healthy)**，宿主端口 **7475 HTTP / 7688 Bolt**，认证 `neo4j/capco-graph-change-me`。共享容器 `capco-graph-neo4j` **Exited，全程不得 up / start / 写数据**。
- 隔离库实测：`Regulation 30` / `CalendarEvent 213` / `Jurisdiction 13` / `Topic 11` / `Source 130` / `Milestone 110` / `InstrumentType 6`；含 `RAI-EU-NA-E2AIXXX-2024`（EU AI Act）与 eur-lex 链接。
- **v1.2 §8 步骤 1–5（数据面）已由架构师跑完并实测通过，dev 从步骤 6（后端 T0）/ 7（前端 T0）开始。** 3 处 `regpass123` 已修复，无残留。
- 数据准备脚本已落盘：`research/poc/build_app_records.py`、`research/poc/load_calendar_events.py`、`research/data/app_records.jsonl`、`docker-compose.app.yml`。**本批次任务卡不修改 `research/` 与 `docker-compose*.yml`。**

### 0.2 冻结契约速查（**仅索引，不是定义**；定义见 v1.1 §5.2 / 设计稿 §8）

| API-ID | Method + Path | 返回模型 | Cypher |
|---|---|---|---|
| API-001 | GET `/api/status` | `AppStatus` | C1+C2 |
| API-002 | GET `/api/filters` | `FilterOptions` | C6 |
| API-003 | GET `/api/regulations` | `Regulation[]`（完整对象，D1） | C3 |
| API-004 | GET `/api/regulations/{instrument_id}` | `Regulation`（单对象） | C3 |
| API-005 | GET `/api/calendar` | `CalendarEvent[]` | **C4（v1.2 §5 新版）** |
| API-006 | GET `/api/graph` | `GraphData` | C5 |
| API-007 | POST `/api/llm/test` | `LlmTestResponse`（恒 200） | 无 |
| API-008 | POST `/api/llm/ask` | `LlmAskResponse`（恒 200，A-004） | 复用 C3 |

查询参数（冻结）：`q, jurisdiction, type, legal_force, topic, date_from, date_to`（空串 = 不过滤；日期 `YYYY-MM-DD`）。
模型：`Regulation` / `CalendarEvent` / `GraphData{nodes,links}` / `AppStatus` / `FilterOptions` / `ErrorEnvelope` / `LlmConfig` / `LlmTestResponse` / `LlmAskResponse`。
**铁律**：`links[].type` = `type`（**不是 `kind`**，R4 已裁定）；`total_count=1174` 是**唯一**允许固化的计数（后端常量），其余数量一律动态；数组字段恒为数组不返回 `null`；所有 `MATCH (r:Regulation)` 必带 `WHERE r.instrument_id IS NOT NULL`（C4 新版除外，见 §6）。

### 0.3 稳定注册模式（**解决共享文件写冲突的核心约定**）

`main.py` 与 `App.tsx` **只由 U-000 写一次，之后永久冻结**，Batch 1/2 **禁止修改**：

- **后端**：U-000 在 `main.py` 用固定清单一次性 `app.include_router(...)` 挂好 5 个 `routers/*.py` 模块（每模块导出 `router = APIRouter()`）。U-000 同时创建这 5 个文件（4 条最小闭包端点 + 空 stub）。Batch 1 后端卡**只在自己那一个 router 文件内补路由**，不改 `main.py`。
- **前端**：U-000 在 `App.tsx` 按 v1.1 §11.1 写死全部 5 条路由并 import 5 个 page 组件；U-000 同时创建 5 个 page **占位 stub**。Batch 1 前端卡**只替换自己那一个 page 文件**，不改 `App.tsx`。
- **顺序交接不算并行写冲突**：U-000 → Batch 1 是「先交付后补全」的串行交接（同一文件被前后两张卡写，但不同时）；**文件不相交性只检查同一批次内并行卡之间**（见 §4）。
- U-000 的 4 条最小闭包端点刻意**只做正向只读黄金路径**（无参数校验、无异常分支），用于证明 T0 模块接线正确；Batch 1 各卡把所属 router 补全为生产实现（校验 / 异常 / 第二端点）。**不得因此再写第二套映射或模型。**

---

## 1. 批次总览

| 批次 | 说明 | 单元数 | 可否并行 | 前置 |
|---|---|---:|---|---|
| **Batch 0** | T0 公共基础（前后端脚手架 + 全量公共模块 + 最小闭环冒烟） | **1**（U-000，**1 人独占**） | 否 | 无（数据面步骤 1–5 已完成） |
| **Batch 1** | 后端 5 端点卡 + 前端 6 页面/组件卡，实现期 | **11** | **全部两两并行（最大并发 11）** | **U-000 冒烟门禁通过（硬阻塞）** |
| **Batch 2** | 后端 pytest 套件 + 前端 typecheck/build/响应式/a11y 验收 | **2** | 2 卡互相并行 | 各自对应的 Batch 1 卡全部完成 |

依赖边显式声明：
- `U-000 → 全部 Batch 1 卡`（硬阻塞，**门禁未过不得开工**）。
- `U-BE-01..05 → U-BE-06`；`U-FE-01..06 → U-FE-07`（验收依赖）。
- `U-FE-04 ⇢ U-FE-05`：**契约依赖，非阻塞**（GraphPage 按 v1.1 §11.4 冻结 Props 编码，与 D3ForceGraph 同时写，QA gate 联调）。
- **前后端跨层零等待**：靠 §0.2 冻结契约 + U-000 的 `api/client.ts` 类型化端点解耦，联调统一放在 QA gate。

---

## 2. 依赖关系图

```
                 ┌──────────────────────────────────────────────┐
  Batch 0        │ U-000  T0 公共基础（1 人）                    │
  (串行, 门禁)   │ 后端 #1–#6 + main.py + 5 router stub          │
                 │ 前端 #8–#13 + App.tsx + 5 page stub + shadcn  │
                 │ ✅ 冒烟门禁（§3 U-000 自测）通过才解锁         │
                 └────────────────────┬─────────────────────────┘
                                      │ 硬阻塞（全部）
        ┌─────────────────────────────┴──────────────────────────────┐
        ▼ 后端 5 卡（并行）                                          ▼ 前端 6 卡（并行）
  U-BE-01 meta        (API-001/002)                          U-FE-01 RegulationsPage
  U-BE-02 regulations (API-003/004)                          U-FE-02 RegulationDetailPage
  U-BE-03 calendar    (API-005 / 新 C4)                       U-FE-03 CalendarPage
  U-BE-04 graph       (API-006)                              U-FE-04 GraphPage ──┐
  U-BE-05 llm         (API-007/008 + llm.py)                 U-FE-05 D3ForceGraph ◄┘ §11.4 Props 契约，非阻塞
                                                              U-FE-06 SettingsPage
        └─────────────────────────────┬──────────────────────────────┘
                                      ▼
  Batch 2   U-BE-06 后端 pytest 套件      ‖      U-FE-07 typecheck/build + 响应式/a11y
  (并行)    写 backend/tests/* 唯一        ‖      写 frontend/src/index.css + 验收报告
                                      ▼
             每张卡：fullstack-dev → code-reviewer → qa-verifier（§5 QA gate）
```

---

## 3. 任务卡

### 【U-000】T0 公共基础 + 最小闭环冒烟　★ Batch 0 · **指定 1 名 dev 先做，独占**

- **批次 / 负责人**：Batch 0 / 全栈 1 人（**唯一负责人，公共模块不得拆给多人**）。**此卡未通过门禁，其余 13 张卡一律不得开工。**
- **独占写路径（后端）**：`pyproject.toml`(改) / `uv.lock`(生成) / `.env.example` / `backend/__init__.py` / `backend/app/__init__.py` / `backend/app/routers/__init__.py` / `backend/app/{main,config,schemas,errors,deps,cypher,mapping}.py` / `backend/app/routers/{meta,regulations,calendar,graph,llm}.py`(stub)。
- **独占写路径（前端）**：`frontend/{package.json,package-lock.json,vite.config.ts,tsconfig.json,tsconfig.node.json,tailwind.config.ts,postcss.config.js,index.html,components.json}` / `frontend/src/{main.tsx,App.tsx,index.css,lib/utils.ts}` / `frontend/src/types/contract.ts` / `frontend/src/api/client.ts` / `frontend/src/hooks/{useApi,useLlmConfig}.ts` / `frontend/src/components/{Shell,StatusBar,EmptyState,ErrorState}.tsx` / `frontend/src/components/ui/*`(shadcn CLI) / `frontend/src/pages/{RegulationsPage,RegulationDetailPage,CalendarPage,GraphPage,SettingsPage}.tsx`(5 个占位 stub)。
- **落地内容（引用章节，不重抄）**：后端 v1.1 §10 #1–#6 全部 + `main.py` 应用工厂（lifespan 建单例 `AsyncGraphDatabase` + 共享 `httpx.AsyncClient()` 挂 `app.state`、§9.1 全局异常处理器、§9.3 CORS、§0.3 固定清单 `include_router`）+ `deps.py` 内含 `regulation_params`/`calendar_params`/`graph_params`/`_opt_date`（v1.1 §5.2 的唯一校验入口，供所有 router `Depends` 复用）。**`cypher.py` 的 `Q_CALENDAR` 必须用 v1.2 §5 新版**（独立 `:CalendarEvent`、`e.jur_filter`、7 个 RETURN 别名不变）；C1/C2/C3/C5/C6 用 v1.1 §6；**`mapping.py` 须完整实现 v1.1 §7.2 全部函数，含 `map_graph` 的 100 节点上限与悬空边丢弃**（后续卡只调用，不得改）。`config.py` 的 `neo4j_uri` 默认 **`bolt://localhost:7688`**（v1.2 §2），`.env.example` 同步，**不设任何 `LLM_*` 环境变量**。
- **前端落地**：`contract.ts` 是 `schemas.py` 逐字段 TS 镜像（唯一定义处）；`api/client.ts` 按 v1.1 §11.2 提供全部 8 个类型化端点函数（`qs()` 空串不发送）；`useApi.ts`（§11.3，`alive` 标志）、`useLlmConfig.ts`（§11.6，localStorage `regulation-corpus:llm-config` + Base64）；`components.json` 按 §11.5 + `npx shadcn@latest init -d` + **一次性 add 全部 12 个基础件**（table card badge button input select tabs tooltip skeleton separator switch sonner，**不装 Dialog**）；`Shell`（4 个 NavLink + `<Outlet/>`）、`StatusBar`（F-008，数字**动态**取 `api.status()`，Shell 挂载与 `window.focus` 各取一次、不轮询）、`EmptyState`/`ErrorState`；`App.tsx` 按 §11.1 写死 5 条路由 + `/` 与 `*` 重定向。
- **4 条最小闭包端点（仅正向路径，放在对应 router 文件，无校验/无异常分支）**：`/api/status`、`/api/filters`、`/api/regulations`(空参列表)、`/api/calendar`(空参全量) 直接调 `cypher.py` + `mapping.py` 返回裸对象/裸数组；`/api/graph`、`/api/llm/*` 留空 stub。
- **命令**：`uv sync`（扩展根 `pyproject.toml`，**不建 `backend/pyproject.toml`**）；`npm install`。
- **输入契约**：§0.2 全部冻结模型 / 8 端点 / 7 查询参数；验收基线见 v1.2 §6。
- **依赖**：无（数据面 1–5 已完成）。**执行前 `docker ps` 二次确认 `capco-app-neo4j` Up(7475/7688)、共享容器 Exited。**
- **验收标准（§3 门禁，逐项必须全绿）**：见下方「自测方法」；另 `main.py`/`App.tsx` 之后冻结、`schema` 与 `contract.ts` 逐字段一致、无重复实现。
- **自测方法（最小闭环冒烟，精确命令）**：
  ```
  uv run uvicorn backend.app.main:app --reload --port 8000
  curl -s localhost:8000/api/status       → {"connected":true,"regulation_count":30,"total_count":1174}
  curl -s localhost:8000/api/regulations  → 30 条；含 instrument_id=RAI-EU-NA-E2AIXXX-2024；其 official_sources 含 eur-lex.europa.eu；每条数组字段为数组
  curl -s localhost:8000/api/calendar     → 213 条；全部 date 为 YYYY-MM-DD 且升序；7 个字段齐全
  curl -s localhost:8000/api/filters      → jurisdictions 13 / types 6 / legal_forces 2 / topics 11
  curl -s "localhost:8000/api/regulations?q=AI%20Act" → 命中 EU AI Act
  npm run dev → :5173 打开，状态条显示 30/1174，5 个 NavLink 可切换（页面为占位 stub 即可）
  ```
  **全部通过 → 通知 team-lead 解锁 Batch 1；任一失败不得解锁。**
- **禁止**：写死 30/213/13/6/2/11 到前端或业务代码；改 `research/` / `docker-compose*.yml` / 共享容器；用同步 `.run(` 或未 await 的协程；把 `links[].type` 写成 `kind`。

---

### 【U-BE-01】状态 + 过滤器字典端点（API-001 / API-002）
- **批次 / 角色**：Batch 1 · 后端（fullstack-dev）。
- **独占写路径**：`backend/app/routers/meta.py`（**仅此一个文件**）。
- **只读依赖**：`schemas.py`(`AppStatus`,`FilterOptions`) / `deps.py` / `cypher.py`(`Q_PING`,`Q_STATUS`,`Q_FILTERS`) / `mapping.py`(`map_filters`) / `errors.py` / `config.py`(`settings.total_count`)；契约 v1.1 §5.3、§5.4、§9.2，设计稿 §8。
- **功能描述**：把 U-000 的两条最小闭包端点补全为生产实现。`/api/status`：`Q_PING` 探测 → `connected`；`Q_STATUS` 取动态 `regulation_count`；`total_count=settings.total_count`。**断连时仍 HTTP 200** 返回 `{connected:false, regulation_count:0, total_count:1174}`，绝不抛错。`/api/filters`：C6 从**本子图关联边**聚合 4 个字典（`map_filters` 已 `sorted` + 去空），空库返回 4 个 `[]`。
- **输入 / 输出**：无参数 → 裸 `AppStatus` / 裸 `FilterOptions`；失败 → `ErrorEnvelope`（`503 NEO4J_UNAVAILABLE` / `500 INTERNAL_ERROR`）。
- **依赖**：U-000（硬阻塞）；与 U-FE-01/03/04 靠冻结契约并行，联调在 QA gate。
- **验收标准**：需求 §6 F-008（顶部状态条 `30/1174`）；设计稿 §2 流程1（`/api/filters` 503 时 4 个 Select 降级为「全部」，不阻塞搜索 → 前端侧，本卡只保证 503 形状正确）；v1.2 §6 filters 13/6/2/11。
- **自测方法**：`curl /api/status` → 30/1174；`curl /api/filters` → 4 列表长度 13/6/2/11、已排序、无空串；临时 `docker stop capco-app-neo4j`（**测完立即 up -d，勿动共享容器**）后 `curl -i /api/status` → **200** 且 `connected:false`，`curl -i /api/filters` → 503 + `ErrorEnvelope`；其余 6 端点行为由各卡自测。
- **禁止**：改 `main.py`/`mapping.py`/`cypher.py`/`schemas.py`；硬编码任何计数（除 `settings.total_count`）；全标签扫描 `MATCH (j:Jurisdiction)` / `MATCH (t:Topic)` 取 facet（会混入外来节点，R1）。

### 【U-BE-02】法规列表 + 详情端点（API-003 / API-004）
- **批次 / 角色**：Batch 1 · 后端。
- **独占写路径**：`backend/app/routers/regulations.py`（**仅此一个文件**）。
- **只读依赖**：`deps.py`(`regulation_params`) / `cypher.py`(`Q_REGULATIONS`) / `mapping.py`(`map_regulation`,`apply_date_filter`) / `schemas.py` / `errors.py`；契约 v1.1 §5.4 API-003/004、§6 C3、§7 M1/M2/M5；设计稿 §8 `Regulation`。
- **功能描述**：列表用 `Depends(regulation_params)` 接 7 个冻结参数（日期 ISO 校验、区间倒置 → `400 VALIDATION_ERROR`；`q` 只 `strip()`+`max_length=200`、**不转义**，参数化是唯一防注入手段）；C3 传 `$instrument_id=''`，**日期过滤在映射层** `apply_date_filter(key='legislation_date')`；返回 `map_regulation` 后的完整对象数组，按 `name` 升序。详情**复用同一 C3 与同一 `map_regulation`**，仅把 `$instrument_id` 置为路径值，返回**单个对象**；查无 → `404 NOT_FOUND`「未找到该法规」。
- **输入 / 输出**：7 查询参数（空串不过滤）→ `Regulation[]`；路径 `instrument_id` → `Regulation`；0 结果 = `200 []` **不是错误**；错误码 `400/404/503/500`。
- **依赖**：U-000（硬阻塞）；与 U-FE-01/FE-02 契约并行。
- **验收标准**：需求 §6 F-001（首页 30 条；`q="AI Act"` 命中；`jurisdiction=European Union` 只返回该管辖区）、F-002（EU AI Act `2024/1689` 详情含名称/描述/类型/生效日期/≥1 官方来源带 eur-lex 域名标签/record_url/≥1 时间线）、F-003；需求 §5 异常（特殊字符 `' " ;` 参数化防注入、空结果前端空态由 U-FE-01 负责）。**v1.2 §0 R3 已恢复 EU AI Act + eur-lex，设计稿 v1.1 §4 P-002「改用 Argentina 真实 ID」的警告作废，本卡验收直接用 EU AI Act。**
- **自测方法**：`curl "/api/regulations?q=AI%20Act"` → 命中 EU AI Act；`curl "/api/regulations?jurisdiction=European%20Union"` → 子集且全为该管辖区；`curl "/api/regulations?date_from=2026-13-01"` → 400 + `VALIDATION_ERROR`；`curl "/api/regulations?date_from=2027-01-01&date_to=2026-01-01"` → 400；`curl "/api/regulations?q=%27%20OR%201%3D1%20//"` → **0 行且无 500**（R1 注入护栏）；`curl /api/regulations/RAI-EU-NA-E2AIXXX-2024` → 单对象、`official_sources` ≤3 且含 `domain=eur-lex.europa.eu`、`topics`/`milestones` 为数组；`curl /api/regulations/NO-SUCH-ID` → 404。
- **禁止**：为详情复制第二份 C3 投影 / 第二套字段命名（D1）；改 `mapping.py`/`cypher.py`/`main.py`；把日期参数拼进 Cypher；硬编码 30。

### 【U-BE-03】日历端点（API-005 · **v1.2 新 C4**）
- **批次 / 角色**：Batch 1 · 后端。
- **独占写路径**：`backend/app/routers/calendar.py`（**仅此一个文件**）。
- **只读依赖**：`deps.py`(`calendar_params`) / `cypher.py`(`Q_CALENDAR`，**v1.2 §5 新版**) / `mapping.py`(`map_calendar_event`,`normalize_date`,`apply_date_filter`) / `schemas.py` / `errors.py`；契约 v1.1 §5.4 API-005、v1.2 §5、设计稿 §4 P-003 / §8 `CalendarEvent`。
- **功能描述**：`Depends(calendar_params)` 接 `jurisdiction, date_from, date_to`（全可选，空串不过滤）；调 `Q_CALENDAR` → `map_calendar_event`（归一失败返回 `None` 则跳过）→ `apply_date_filter(key='date')` → 按归一后 `date` 升序返回裸数组。**默认不传日期参数返回全量 213 条**；「未来 12 个月」是前端快捷按钮（U-FE-03），后端不设默认窗口。
- **输入 / 输出**：3 参数 → `CalendarEvent[]`；0 结果 `200 []`；错误码 `400/503/500`。
- **依赖**：U-000（硬阻塞，且 `Q_CALENDAR` 新常量已由 U-000 落好）；与 U-FE-03 契约并行。
- **验收标准**：需求 §6 F-004（**213 个事件、按日期升序**；`date_from=2026-11-01&date_to=2027-12-31` 只返回区间内）；设计稿 §4 P-003（默认全量 + 计数动态「共 N 个事件」）；v1.2 §6（213 条、2026-11-27 → 2045-12-31、全 ISO）。
- **自测方法**：`curl /api/calendar` → **213 条**、7 字段齐全、`date` 全 `YYYY-MM-DD` 且升序、`source_url` 允许 `null`；`curl "/api/calendar?date_from=2026-11-01&date_to=2027-12-31"` → 子集且全部落在区间；`curl "/api/calendar?jurisdiction=European%20Union"` → 子集（**用 `e.jur_filter` 命中，v1.2 实测 38 行**）；`curl "/api/calendar?date_from=bad"` → 400。**注意：v1.2 §6 已覆盖 v1.1 §12.2 的 61 条旧口径，任何「默认 61」的期望都是错的。**
- **禁止**：改 `cypher.py`（新 C4 是 U-000 的唯一常量，本卡只引用）；把 `e.jur_filter` 写进任何契约字段 / `FilterOptions` 第 5 个列表（v1.2 §9）；给 C4 加回 `WHERE r.instrument_id IS NOT NULL`（新版不碰 `:Regulation`）；硬编码 213。

### 【U-BE-04】图谱端点 + 100 节点上限（API-006）
- **批次 / 角色**：Batch 1 · 后端。
- **独占写路径**：`backend/app/routers/graph.py`（**仅此一个文件**）。
- **只读依赖**：`deps.py`(`graph_params`) / `cypher.py`(`Q_GRAPH` C5) / `mapping.py`(**`map_graph` 已实现 100 上限 + 丢悬空边**) / `config.py`(`settings.graph_max_nodes`, `graph_reg_limit`) / `schemas.py` / `errors.py`；契约 v1.1 §5.4 API-006、§6 C5、§7.4；设计稿 §4 P-004。
- **功能描述**：`Depends(graph_params)` 接 `jurisdiction, topic`；C5 传 `$reg_limit=settings.graph_reg_limit`(40)；**直接调 `map_graph(rows, max_nodes=settings.graph_max_nodes)`**，返回裸 `GraphData`。节点 id 前缀规则（`regulation` 不加前缀 / `jur:` / `topic:` / `src:`）、优先级 `regulation>jurisdiction>topic>source`、丢弃悬空边、`links[].type` 三值常量，**全部在 U-000 的 `map_graph` 内，本卡不得重实现**。
- **输入 / 输出**：2 参数 → `GraphData`；0 结果 `200 {"nodes":[],"links":[]}`；错误码 `503/500`。
- **依赖**：U-000（硬阻塞）；与 U-FE-04/FE-05 契约并行。
- **验收标准**：需求 §6 F-005（图谱节点/边可渲染、hover tooltip、点 Regulation 跳详情）；v1.1 §5.4（**`links[].type` 而非 `kind`**、`source`/`target` 恒引用 `nodes[].id`、无第 5 枚举值、不投影 `InstrumentType`/`OF_TYPE`）；v1.2 §6（隔离库候选约 184 节点 > 100 → **必然截断**）。**需求 §6 写的「3 个 Jurisdiction / 39 个 Topic」是旧共享库口径，已被 v1.2 §6 取代；本卡按「100 上限 + 截断」验收，禁止照抄 3/39。**
- **自测方法**：`curl /api/graph` → `nodes.length <= 100`；断言每条 `link.source`/`link.target` 都在 `nodes[].id` 中（**无悬空边**）；断言 `nodes[].type ⊆ {regulation,jurisdiction,topic,source}`、`links[].type ⊆ {IN_JURISDICTION,HAS_TOPIC,SOURCED_FROM}`、且字段名是 `type` 不是 `kind`；`curl "/api/graph?jurisdiction=European%20Union"` → 子集；`curl "/api/graph?topic=governance_oversight"` → 子集。
- **禁止**：在 router 内自己截断节点或拼 `GraphLink`（重复实现）；改 `mapping.py`/`cypher.py`/`main.py`；新增 `truncated` 字段（R9，契约无此字段，前端按 `nodes.length>=100` 判定）；硬编码 100/148/184。

### 【U-BE-05】LLM test / ask + httpx 客户端（API-007 / API-008）
- **批次 / 角色**：Batch 1 · 后端。
- **独占写路径**：`backend/app/llm.py`（v1.1 §10 #7）+ `backend/app/routers/llm.py`（**仅这两个文件**）。
- **只读依赖**：`main.py` 的 `app.state.http`（U-000 lifespan 创建的共享 `httpx.AsyncClient()`）/ `schemas.py`(`LlmConfig`,`LlmTestResponse`,`LlmAskRequest`,`LlmAskResponse`) / `config.py`(`llm_timeout_test`,`llm_timeout_ask`) / `cypher.py`(`Q_REGULATIONS` C3，ask 取上下文) / `mapping.py`(`map_regulation`) / `errors.py`；契约 v1.1 §5.4 API-007/008、§8、§8.4。
- **功能描述**：`llm.py` 实现 `build_request(cfg, messages, max_tokens)`（§8.2：`base_url` `^https?://` + `netloc` 非空校验；Azure `openai.azure.com` 分支用 `api-key` 头 + 部署路径；否则 `Authorization: Bearer`；**允许空 `api_key`** 供 Ollama/vLLM）；超时逐请求覆盖 10s/30s；任何 `httpx.HTTPError` / 非 2xx / JSON 异常 → `ok=false, error=str(exc)`。两个端点**恒 HTTP 200**，失败绝不升级成 5xx。`ask` 若带 `instrument_id` 复用 C3 取 `Regulation` 拼纯文本上下文；**模型输出只作 `answer` 字符串返回，绝不解析 / eval / 执行 / 生成 Cypher**（`llm.py` 不持有 driver、不接触 session，§8.4 Code Review 硬检查）。
- **输入 / 输出**：`LlmConfig` 平铺 body（**不加 `config` 包装**）→ `LlmTestResponse`；`LlmAskRequest = LlmConfig + {question, instrument_id?}` → `LlmAskResponse`。
- **依赖**：U-000（硬阻塞）；与 U-FE-06 契约并行。
- **验收标准**：需求 §6 F-006（保存配置 → localStorage 由前端负责）、需求 §5 异常（Key 错误 / 超时 / URL 非法显示错误且**不阻塞其他 5 个页面**）；v1.1 §9.2（`/api/llm/*` 不受 Neo4j 断连影响，照常 200）。
- **自测方法**：本地起任意 OpenAI 兼容 mock（或指向不可达地址）：`curl -X POST /api/llm/test -H 'Content-Type: application/json' -d '{"base_url":"https://api.openai.com/v1","api_key":"sk-bad","model":"gpt-4"}'` → **200** 且 `ok:false` + `error` 非空；`-d '{"base_url":"ftp://x",...}'` → 400 `VALIDATION_ERROR`「请输入有效的URL」；`POST /api/llm/ask` 带 `instrument_id=RAI-EU-NA-E2AIXXX-2024` → 200 形状 `{ok,answer,error}`；`docker stop capco-app-neo4j`（测完恢复）后 `/api/llm/test` 仍 200。全程**不写服务端磁盘 / 日志 / env 中的 key**。
- **禁止**：在服务端持久化 / 缓存 / 记录 `api_key`；`llm.py` import `cypher.py` 之外再持有 driver（ask 上下文走 router 层 C3，不进 `llm.py`）；把 `/api/llm/*` 失败抛成 5xx。

### 【U-BE-06】后端 pytest 套件
- **批次 / 角色**：Batch 2 · 后端（可自 U-BE-01 起提前起草，但**转绿验收须等 U-BE-01..05 全部完成**）。
- **独占写路径**：`backend/tests/{conftest,test_mapping,test_cypher,test_api}.py`（**仅此 4 个文件 + 目录**）。
- **只读依赖**：`main.py` 的 `app` / `deps.py` / 全部 router / `mapping.py` / `cypher.py` / `schemas.py`（**只 import，不改**）。
- **功能描述**：按 v1.1 §12.1 落地三层测试，全部可**离线**跑（无真 Neo4j / 无真 LLM）。`conftest.py`：`AsyncMock` 驱动 + `httpx.AsyncClient(transport=ASGITransport(app=app))`。`test_mapping.py`：`normalize_date`（ISO/范围/`(Approx.)`/HTML/仅年份→None）、`map_official_sources`（≤3 / URL 去重 / 优先级 / 真实 `rel_type` / domain 兜底）、`map_milestones`（升序、null 末尾）、`map_regulation`（M1 扁平化、数组恒数组）、`map_calendar_event`（异常跳过）、**`map_graph`（100 上限、无悬空边、无第 5 枚举值、id 前缀）**、`apply_date_filter`。`test_cypher.py`：静态断言 6 条模板**无用户输入插值**、每条 `MATCH (r:Regulation)` 后含 `r.instrument_id IS NOT NULL`（**R1 回归护栏**；断言按 `if "MATCH (r:Regulation)" in q` 条件触发，C4 天然跳过）、可选 `NEO4J_TEST_URI` 活库冒烟（未设则 skip）。`test_api.py`：8 端点 200 形状、空结果 `[]`、404、400 日期非法、503 模拟 `ServiceUnavailable`、`/api/status` 断连仍 200 且 `connected=false`、`/api/llm/test` 上游失败仍 200 且 `ok=false`。
- **日历 mock 数据**：`test_api.py` 的 `/api/calendar` 预置行仍用新 C4 的 **7 个别名**（`id, date_raw, title, instrument_id, regulation_name, jurisdiction, source_url`）——别名未变，mock 数据无需改，只去掉写死条数。
- **依赖**：U-BE-01..05（验收依赖）。
- **自测方法**：`uv run pytest backend/tests -q` → 全绿、无真实网络调用；`NEO4J_TEST_URI=bolt://localhost:7688 uv run pytest backend/tests -q` → 活库冒烟通过（**必须显式 7688**）。
- **禁止**：改任何 `backend/app/*` 源文件（测试只能 import）；把断言写死 30/213/13/6/2/11（用形状与不变量断言）；连接 7687。
- **隔离护栏按条件生效（无白名单）**：`test_cypher.py` 断言写成 `if "MATCH (r:Regulation)" in q: assert "WHERE r.instrument_id IS NOT NULL" in q`（v1.1 §6.0 原意）。v1.2 新 `Q_CALENDAR` 全文 `MATCH (e:CalendarEvent)`、不含 `r:Regulation`，**天然跳过断言**，无需白名单 / SKIP / noqa。**禁止**给护栏加白名单（削弱 R1 防护、给以后裸 `MATCH (r:Regulation)` 开后门），也**禁止**给 C4 补回 `WHERE r.instrument_id IS NOT NULL`（会过滤掉全部 213 条事件）。

### 【U-FE-01】法规列表页（P-001 / F-001, F-007, F-008）
- **批次 / 角色**：Batch 1 · 前端。
- **独占写路径**：`frontend/src/pages/RegulationsPage.tsx`（**仅此一个文件**，替换 U-000 占位 stub）。
- **只读依赖**：`api/client.ts`(`api.regulations`, `api.filters`) / `hooks/useApi.ts` / `types/contract.ts` / `components/{EmptyState,ErrorState}.tsx` / `@/components/ui/*`；设计稿 §4 P-001、§5、§6、§7；需求 §6 F-001。
- **功能描述**：SearchFilterBar（搜索框 + 4 个 Select + 日期区间 + 搜索/重置）→ 结果计数 → Table（列冻结：`name|jurisdiction|type|legislation_date|legal_force|操作`），**无分页**。4 个 Select 选项**一律来自 `api.filters()`**，禁止硬编码枚举；`q` 防抖 300ms 或点搜索；`useSearchParams` 写 URL query（可分享/可后退）；表头点 `name`/`legislation_date` 前端排序；行单击 = 点「查看详情」→ `/regulations/:instrument_id`。空值 `""`/`null` 显示「—」，`legal_force` 用 Badge 且不渲染空 Badge。
- **状态**：加载 5 行 Skeleton / 空 `EmptyState`「未找到匹配的法规…」+ 清除筛选 / 错误红色 Alert「无法连接到图数据库…」+ 重试且**搜索按钮禁用** / 成功「共 N 条法规」（N 动态）。`/api/filters` 503 时 4 个 Select **降级为仅「全部」，不阻塞搜索**。
- **依赖**：U-000（硬阻塞）；与 U-BE-01/02 契约并行。
- **验收标准**：需求 §6 F-001（30 行表格；`AI Act` 搜索；`jurisdiction=European Union` 过滤）；F-007（1024×768 无页面级横向滚动，表格自身 `overflow-x-auto`）；F-008 状态条由 U-000 Shell 负责。
- **自测方法**：`npm run dev` → `/regulations` 首屏 30 行、状态条 30/1174；输入 `AI Act` → 命中 EU AI Act 且 <2s；选 `European Union` → 子集；刷新后 URL query 保留筛选；把后端停掉 → 红灯 + 禁用搜索；`curl` 层面由 U-BE-02 保证。**禁止写死 30 / 任何枚举值 / 任何计数。**

### 【U-FE-02】法规详情页（P-002 / F-002, F-003）
- **批次 / 角色**：Batch 1 · 前端。
- **独占写路径**：`frontend/src/pages/RegulationDetailPage.tsx`（**仅此一个文件**）。
- **只读依赖**：`api/client.ts`(`api.regulation`) / `useApi` / `contract.ts` / `EmptyState`/`ErrorState` / `@/components/ui/*`（Tabs/Card/Badge/Separator）；设计稿 §4 P-002、§5、§8；需求 §6 F-002/F-003。
- **功能描述**：面包屑 → H1 + 状态 Badge → Tabs（概览/时间线）→ 三张 Card（基本信息 / 官方来源 / 主题标签）+ 桌面右侧元信息卡。外链一律 `target="_blank" rel="noopener noreferrer"`；`record_url` 文案「在 regulations.ai 查看记录」；`official_sources[]` **直接渲染后端算好的 `{url,domain,rel_type}`（≤3、已去重），前端勿再截断、勿自行解析 URL**；`milestones[]` 按 `date` 升序、`null` 排末尾显示「—」（契约无原始日期文本字段，不显示原始文本，R6）；`topics[]` 可点 Badge → 跳 P-001 并预置 `?topic=xxx`；返回用 `navigate(-1)` 保留来源。
- **状态**：加载 Skeleton / 404 →「未找到该法规」+ 返回列表 / 错误 → `ErrorState` + 重试；`description` 空显示「暂无描述」，`legislation_date:null` 显示「—」。
- **依赖**：U-000（硬阻塞）；与 U-BE-02 契约并行。
- **验收标准**：需求 §6 F-002（EU AI Act `2024/1689`：名称/描述/类型/生效日期/≥1 官方来源带 `eur-lex.europa.eu` 域名标签/record_url/≥1 时间线）、F-003（新标签打开 eur-lex；来源缺失显示「官方来源：未提供」且 record_url 仍显示）。**验收用 EU AI Act（v1.2 R3 已恢复），设计稿 v1.1 §4 P-002 的替代 ID 警告作废。**
- **自测方法**：打开 `/regulations/RAI-EU-NA-E2AIXXX-2024` → 三卡齐全、官方源 ≤3 且域名标签正确、时间线 ≥1；点第一个官方链接 → 新标签打开 eur-lex；打开一个无来源的真实 ID →「官方来源：未提供」但 record_url 可点；访问 `/regulations/NO-SUCH-ID` → 404 态。

### 【U-FE-03】法规日历页（P-003 / F-004）
- **批次 / 角色**：Batch 1 · 前端。
- **独占写路径**：`frontend/src/pages/CalendarPage.tsx`（**仅此一个文件**）。
- **只读依赖**：`api/client.ts`(`api.calendar`, `api.filters`) / `useApi` / `contract.ts` / `EmptyState`/`ErrorState` / `@/components/ui/*`（Tabs/Table/Card/Button/Select）；设计稿 §4 P-003（**默认视图已定稿**）、§5、§6；v1.2 §5/§6；需求 §6 F-004。
- **功能描述**：过滤栏（日期起止 + 管辖区 Select + Tabs 时间轴/列表）→ 事件计数 → 按年月分组竖向时间轴或紧凑 Table。**默认不传 `date_from`/`date_to`** → 返回全量 213 条按 `date` 升序；「未来 12 个月」为**快捷按钮**，把算好的 ISO 起止一并写入 URL query（重置日期清除）；Tabs 切换**只换呈现、不重新请求**；`regulation_name` → P-002，「查看原文」→ 外链新标签（`source_url` 为 `null` 时不渲染按钮）。
- **状态**：加载 Skeleton×6 / 空「该范围内暂无里程碑事件」+ 重置日期 / 错误 + 重试 / 成功「共 N 个事件」（**N 动态，禁止写死 213/61**）。
- **依赖**：U-000（硬阻塞）；与 U-BE-03 契约并行。
- **验收标准**：需求 §6 F-004（213 事件、按日期升序；`2026-11-01~2027-12-31` 只显示区间内）；设计稿 §4 P-003 定稿口径；v1.2 §6（213 条全 ISO）。
- **无障碍**：键盘可达 / `focus-visible` / `aria-label` 遵循设计稿 §7 与 U-FE-07 全站 a11y 验收；Tabs、Select、Button 使用 shadcn 默认可访问行为，不新增组件或字段。
- **自测方法**：`/calendar` 首屏事件数动态显示 213、日期升序；点「未来 12 个月」→ URL 出现 ISO 起止且刷新可复现；切 Tabs 不触发新请求（Network 面板核对）；设区间 → 子集；清空 → 恢复全量。

### 【U-FE-04】知识图谱页（P-004 / F-005）
- **批次 / 角色**：Batch 1 · 前端。
- **独占写路径**：`frontend/src/pages/GraphPage.tsx`（**仅此一个文件**）。
- **只读依赖**：`api.graph`, `api.filters` / `useApi` / `contract.ts` / `components/D3ForceGraph.tsx`（**按 v1.1 §11.4 冻结 Props 编码**）/ `EmptyState`/`ErrorState` / `@/components/ui/*`；设计稿 §4 P-004、§5、§6、§7。
- **功能描述**：过滤栏（管辖区 / 主题 Select + 重置视图 + 节点计数）→ `D3ForceGraph` 画布 → 图例 4 类。页面负责：组装 `GraphQuery` 请求、过滤变化时**重新请求**后把新 `nodes/links` 传给组件（组件不含过滤状态，`filters` prop 已移除）、`onNodeClick` 仅对 `type==='regulation'` 跳 `/regulations/${node.id}`（**id 无前缀，直接拼**）；hover Tooltip（name + type）；重置视图恢复默认筛选与缩放。
- **状态**：加载中央 Spinner「正在渲染图谱…」/ 空「没有符合筛选条件的节点」/ **`nodes.length >= 100` 即视为截断** →「数据量较大，请使用过滤器缩小范围」（**契约无 `truncated` 字段，禁止新增/读取**）/ 错误「图谱加载失败」+ 重试 / 成功「N 节点 / M 关系」（动态）。
- **依赖**：U-000（硬阻塞）；**⇢ U-FE-05：契约依赖、非阻塞**（按 §11.4 Props 并行编写，QA gate 联调）；与 U-BE-04 契约并行。
- **验收标准**：需求 §6 F-005（力导向图、hover tooltip、点 Regulation 跳详情）；设计稿 §4 P-004（4 类图例含灰色 `source`、100 节点提示）；v1.2 §6（隔离库候选 184 > 100，**截断提示必触发**）。**需求 §6 的「3 个 Jurisdiction / 39 个 Topic」是旧共享库口径，按 v1.2 §6 的 100 上限验收，禁止照抄。**
- **自测方法**：`/graph` 渲染出节点与边；hover Regulation 出 Tooltip；点 Regulation → 详情页；选管辖区/主题 → 重请求并缩小；`nodes.length>=100` 时顶部出现提示；1024×768 图例折行、页面无横向滚动；二次切换过滤不崩溃（验证 U-FE-05 深拷贝生效）。

### 【U-FE-05】D3ForceGraph 组件（唯一可视化定制）
- **批次 / 角色**：Batch 1 · 前端。
- **独占写路径**：`frontend/src/components/D3ForceGraph.tsx`（**仅此一个文件，U-000 不创建此文件**）。
- **只读依赖**：`contract.ts`(`GraphNode`,`GraphLink`) / `@/components/ui/tooltip`（如需）；Props 冻结见 v1.1 §11.4；设计稿 §5 / §4 P-004 / §7。
- **功能描述**：导出 `D3ForceGraph({nodes, links, onNodeClick, onNodeHover?, maxNodes=100, className?})`。`ResizeObserver` 撑满容器（高 `calc(100vh - 260px)` / 最小 480px）；`d3.forceSimulation` + `forceLink().id(d=>d.id)` + `forceManyBody` + `forceCenter` + `forceCollide`；`d3.zoom` 缩放平移、`d3.drag` 拖节点；卸载 `simulation.stop()` 并移除监听。交互：hover Regulation → `onNodeHover`（Tooltip name+type）；点击 `type==='regulation'` → `onNodeClick`；点其余 3 类 → 组件内高亮一跳邻居（不跳页）；键盘 Enter/Space 等价点击，SVG `<g tabIndex={0} role="button" aria-label="{type}: {label}">`。图例 4 类：● Regulation(蓝) / ■ Jurisdiction(绿) / ◆ Topic(橙) / **● source(灰小圆)**，形状+色+文字三重编码。
- **★ 强制**：传入模拟前对 `nodes` 与 `links` **深拷贝**（`links.map(l => ({...l}))`），因 `d3.forceLink` 会把 `source/target` 从 id 字符串**原地改写为节点对象**，否则 React state 被污染、二次渲染崩溃（R14）。此处写**中文注释解释「为什么」**。
- **依赖**：U-000（硬阻塞）；**⇢ U-FE-04：契约依赖、非阻塞**。
- **验收标准**：需求 §6 F-005（hover tooltip、点 Regulation 跳详情）；设计稿 §7（键盘可达、`aria-label`、图例不依赖颜色单独表意）；v1.1 §11.4。
- **自测方法**：浏览器手工：连续 3 次切换过滤后图仍正常重渲染（**验证深拷贝，无 `source is not a string` 报错**）；滚轮缩放 / 拖拽平移 / 拖节点；hover 出 Tooltip；点蓝圆跳详情、点绿方/橙菱/灰圆只高亮邻居；Tab 聚焦节点后 Enter 触发点击；1024×768 画布随容器缩放。
- **禁止**：组件内嵌过滤状态 / 增加 `filters` prop；修改传入的 `nodes`/`links` 原对象；新增第 5 类节点枚举。

### 【U-FE-06】LLM 设置页（P-005 / F-006）
- **批次 / 角色**：Batch 1 · 前端。
- **独占写路径**：`frontend/src/pages/SettingsPage.tsx`（**仅此一个文件**）。
- **只读依赖**：`hooks/useLlmConfig.ts`（localStorage + Base64）/ `api.client.ts`(`api.llmTest`) / `useApi` 或直接 Promise / `contract.ts`(`LlmConfig`) / `@/components/ui/*`（Card/Input/Button/Switch/Sonner Toast）；设计稿 §4 P-005、§6、§7；需求 §6 F-006。
- **功能描述**：单张 Card（≤640px）三字段 `base_url`/`api_key`/`model` +「测试连接」「保存」+ 底部警示「请勿在生产环境使用（API Key 仅 Base64 编码，非加密）」。进入页读 localStorage 回填；`api_key` type=password + 显隐切换（Switch）；保存前 `new URL()` 校验 `^https?://`，非法行内提示「请输入有效的URL」；通过 → 写 localStorage + Toast「配置已保存」；「测试连接」调 `api.llmTest(config)`，in-flight 期间按钮 `disabled` 防重复提交，失败显示**非阻塞错误条**「LLM API调用失败：[错误详情]」，**不影响其他 5 个页面**。
- **状态**：回填前 Skeleton；无空态。
- **依赖**：U-000（硬阻塞）；与 U-BE-05 契约并行。
- **验收标准**：需求 §6 F-006（输入 `https://api.openai.com/v1` / `sk-xxx` / `gpt-4` → 保存到 localStorage +「配置已保存」）；需求 §5 异常（URL 格式错误提示、Key 错误/超时非阻塞）；设计稿 §7（1024 时 `min(640px,100%)` 单列）。
- **自测方法**：填 3 字段保存 → DevTools `localStorage["regulation-corpus:llm-config"]` 存在且 `api_key` 为 Base64、Toast 出现；刷新后回填；填 `ftp://x` 保存 → 行内「请输入有效的URL」且不写入；指向不可达 `base_url` 点测试 → 非阻塞错误条出现、切换到 `/regulations` 仍正常；连点测试按钮不产生重复请求。

### 【U-FE-07】前端 typecheck / build + 响应式 / a11y 收口
- **批次 / 角色**：Batch 2 · 前端 + QA（等 U-FE-01..06 全部完成）。
- **独占写路径**：`frontend/src/index.css`（**仅全局 `focus-visible` 焦点环 / 断点 token 允许微调**，U-000 已标注为 Batch 2 可交接）+ 新建 `deliverables/frontend_acceptance_report.md`（验收报告，不与任何卡冲突）。**禁止改任何 page / component / `App.tsx` / `api` / `hooks` 文件**；若发现缺陷，回报 team-lead 派回原卡 owner 修。
- **只读依赖**：全部前端源码、`contract.ts` ↔ `schemas.py` 双侧对照。
- **功能描述**：跑交付门槛并出报告：`npx tsc --noEmit` 零错误、`npm run build` 通过、`npm run lint`（可选）；按设计稿 §7 逐项手工验收全站键盘 Tab 顺序（导航→状态条→过滤控件→表格/画布→按钮）、统一 `focus-visible`、表格行 `tabIndex=0`+Enter、`aria-sort`、StatusBar `role="status" aria-live="polite"`、Toast `aria-live`、加载态 `aria-busy`、外链 `aria-label`「在新标签页打开」、图标按钮 `aria-label`；按 F-007 在 **1920×1080 → 1024×768** 逐页缩放，确认搜索框/表格/图谱**无页面级横向滚动**、过滤栏折行、图例折行。
- **依赖**：U-FE-01..06（验收依赖）；与 U-BE-06 并行。
- **自测方法**：上述 3 条命令全绿 + 报告内 5 个页面 × 2 分辨率逐项打勾；任何红项列明卡号并派回。
- **禁止**：为过 tsc 而改 `contract.ts` / `api/client.ts`（契约冻结，改动须走 §14 上报 team-lead）；引入前端单测框架（v1.1 §12.3 明确不做）。

---

## 4. 文件不相交矩阵（**并行写冲突证明**）

**规则**：矩阵只检查**同批次内并行卡**；U-000 → Batch 1 为串行交接（不同时写），Batch 2 同理。下表每张 Batch 1/2 卡的写路径**两两不相交**。

| 卡 | 独占写路径（唯一 owner） | 并行冲突 |
|---|---|---|
| U-000 | `pyproject.toml` `uv.lock` `.env.example` `backend/app/{main,config,schemas,errors,deps,cypher,mapping}.py` `backend/app/routers/__init__.py` + 5 个 router stub `frontend/*` 配置全套 `frontend/src/{main.tsx,App.tsx,index.css,lib/utils.ts,types/contract.ts,api/client.ts,hooks/*}` `components/{Shell,StatusBar,EmptyState,ErrorState}.tsx` `components/ui/*` 5 个 page stub | 串行交接，不与任何卡并行 |
| U-BE-01 | `backend/app/routers/meta.py` | 无 |
| U-BE-02 | `backend/app/routers/regulations.py` | 无 |
| U-BE-03 | `backend/app/routers/calendar.py` | 无 |
| U-BE-04 | `backend/app/routers/graph.py` | 无 |
| U-BE-05 | `backend/app/llm.py`、`backend/app/routers/llm.py` | 无 |
| U-BE-06 | `backend/tests/{conftest,test_mapping,test_cypher,test_api}.py` | 无（Batch 2，与 U-FE-07 并行） |
| U-FE-01 | `frontend/src/pages/RegulationsPage.tsx` | 无 |
| U-FE-02 | `frontend/src/pages/RegulationDetailPage.tsx` | 无 |
| U-FE-03 | `frontend/src/pages/CalendarPage.tsx` | 无 |
| U-FE-04 | `frontend/src/pages/GraphPage.tsx` | 无 |
| U-FE-05 | `frontend/src/components/D3ForceGraph.tsx` | 无 |
| U-FE-06 | `frontend/src/pages/SettingsPage.tsx` | 无 |
| U-FE-07 | `frontend/src/index.css`、`deliverables/frontend_acceptance_report.md` | 无（Batch 2，与 U-BE-06 并行） |

**只读共享清单（U-000 独占写，Batch 1/2 一律只 import，写即视为越界）**
`main.py`（`include_router` 已预挂 5 模块 + 全局异常/CORS/lifespan/`app.state.http`）、`App.tsx`（5 路由已写死）、`schemas.py`、`contract.ts`、`config.py`、`errors.py`、`deps.py`（含 `*_params` 校验入口）、`cypher.py`（**含 v1.2 新 C4**）、`mapping.py`（**含 `map_graph` 100 上限**）、`api/client.ts`（8 端点函数）、`useApi.ts`、`useLlmConfig.ts`、`Shell/StatusBar/EmptyState/ErrorState.tsx`、`components/ui/*`、`vite.config.ts`、`tailwind.config.ts`、`components.json`。

**已消除的 3 个潜在冲突（务必按此执行）**
1. **`map_graph` / 100 节点上限**：属 U-000 的 `mapping.py`（T0 #6），U-BE-04 **只调用**，不得改 `mapping.py` 或在 router 内重实现。
2. **v1.2 新 C4 `Q_CALENDAR`**：常量由 U-000 写入 `cypher.py`，U-BE-03 **只引用**，不得改 `cypher.py`。
3. **shadcn 基础件**：U-000 **一次性 add 全部 12 个**；Batch 1 页面卡**禁止再跑 `npx shadcn add`**（会写 `components/ui/*` 造成并行冲突）；缺组件 → 上报 team-lead 由 U-000 owner 补。

**未解决的文件冲突：0。** 仅有 1 处**接口依赖（非文件冲突）**：`U-FE-04 ⇢ U-FE-05` 依 v1.1 §11.4 冻结 Props 契约先行并行编码，QA gate 联调，不阻塞开工。另有 U-000 → Batch 1 的 10 处**串行交接文件**（5 router + 5 page），属设计内顺序交接，不构成并行写。

---

## 5. 并行排期建议

| 阶段 | 开发 | 认领单元 | 说明 |
|---|---|---|---|
| Batch 0 | **D0（1 人独占）** | **U-000** | **必须先做且门禁通过**；全量公共模块唯一负责人，杜绝各写各的模型/映射 |
| Batch 1（最大并发 **11**） | D1 | U-BE-01 + U-BE-02 | 后端 meta/regulations，同层相邻 |
| | D2 | U-BE-03 + U-BE-04 | 后端 calendar/graph |
| | D3 | U-BE-05 | 后端 LLM（含 httpx 客户端，独立面） |
| | D4 | U-FE-01 + U-FE-02 | 前端列表/详情（共用 P-001→P-002 跳转） |
| | D5 | U-FE-03 | 前端日历 |
| | D6 | U-FE-04 + U-FE-06 | 前端图谱页 + 设置页 |
| | D7 | U-FE-05 | D3ForceGraph（**高风险，建议专人**，与 D6 按 §11.4 Props 并行） |
| Batch 2（并发 2） | D3 | U-BE-06 | 等 U-BE-01..05 全部合入后转绿 |
| | D8 / QA | U-FE-07 | 等 U-FE-01..06 全部合入后跑门槛 |

- **最大有用并发 = 11**（Batch 1 全部 11 张卡可同时开工）。上表按人力压缩为 7 人；若人手充足，一卡一人即可，**不必等待同层其他卡**。
- **跨层零等待**：前端卡不等后端卡，靠 §0.2 冻结契约 + `api/client.ts` 类型化端点；真实联调统一放 QA gate。
- **唯一硬闸门**：U-000 冒烟 4 个 curl + `npm run dev` 全绿 → team-lead 显式解锁 Batch 1；**未通过不得开工**（v1.2 §8 步骤 9）。

### 每张卡必过的 QA Gate（三级，依次）

| 关卡 | 检查内容 |
|---|---|
| **fullstack-dev** | 落盘到独占路径；卡内「自测方法」逐条跑通；**未写任何非独占文件**；无 TODO 占位 |
| **code-reviewer** | ① 契约零偏离（字段/类型/枚举/端点/查询参数；`links[].type` 非 `kind`；无 `truncated`/`*_raw`）；② 无重复实现（模型/映射/Cypher/fetch/控件只用 U-000 的）；③ 中文注释只在关键处且解释「为什么」；④ 所有 `MATCH (r:Regulation)` 带 `WHERE r.instrument_id IS NOT NULL`（新 C4 例外）；⑤ 全链路 `async def` + `await`，无同步 `.run(` / 未 await 协程；⑥ 无硬编码计数（仅 `settings.total_count` 例外）；⑦ U-FE-05 深拷贝、U-BE-05 `llm.py` 不持 driver / 不生成 Cypher |
| **qa-verifier** | 需求 §6 对应 F-00x 逐条判定 + v1.2 §6 计数基线（30/1174、30 regs 含 EU AI Act、213 events、13/6/2/11 filters、graph ≤100 节点）+ `uv run pytest -q` 全绿 + `npx tsc --noEmit` / `npm run build` 通过 + 1024×768 无页面级横向滚动 + 断连/404/400/空结果异常分支 |

---

## 6. 风险提示 · Top 5（v1.1 §14 + v1.2 §9，写进每张卡的 Code Review）

| # | 陷阱 | 后果 | 强制应对 |
|---|---|---|---|
| **T1** | **Bolt 端口 7687 vs 7688 + 忘带 `--uri`**：loader 默认 `--uri bolt://localhost:7687` 指向**共享库** | 误写共享容器（违反「零写入」决策）/ 后端连不上 / 数据全空 | `config.py` 默认与 `.env` 一律 `bolt://localhost:7688`（v1.2 §2）；**任何重跑数据脚本必须显式 `--uri bolt://localhost:7688`**，执行前 `docker ps` 二次确认 `capco-app-neo4j` Up、共享 `capco-graph-neo4j` **保持 Exited**；`--reset` 后必须重跑 `load_calendar_events.py`（顺序 3→4 不可换） |
| **T2** | **硬编码计数**：把 30 / 213 / 13 / 6 / 2 / 11 / 100 / 184 / 148 / 61 写进业务或前端 | 数据一变即错；`61` 是旧共享库口径、`3/39` 是旧图库口径 | 仅 `total_count=1174` 允许固化为**后端** `settings` 常量；其余全部动态取接口；前端状态条/计数文案/截断判定一律动态；**需求 §6 F-005 的「3 Jurisdiction / 39 Topic」与 v1.1 §12.2 的「61 条」已由 v1.2 §6 取代，禁止照抄** |
| **T3** | **`links[].type` 误写成 `kind`**；或新增 `truncated` / `*_raw` 字段；或图谱混入 `InstrumentType` 第 5 枚举 | 前端拿不到关系类型 / 契约破坏 / d3 幽灵节点 | R4 已裁定保留 `type`（v1.2 §0）；`nodes[].type` 仅 4 值、`links[].type` 仅 3 值；截断用 `nodes.length >= 100` 判定；`InstrumentType` 与 `OF_TYPE` 不进 `/api/graph`（M4）；改字段一律 STOP 上报 team-lead |
| **T4** | **d3 `forceLink` 原地改写 `source/target`** 为节点对象 | React state 被污染、二次渲染崩溃 | U-FE-05 传入模拟前对 `nodes`/`links` **深拷贝**（`links.map(l=>({...l}))`），中文注释写「为什么」；U-FE-04 连续切过滤 3 次验证不崩；后端 `map_graph` 先定节点集再生成 link、丢弃悬空边（U-000 已实现） |
| **T5** | **`e.jur_filter` 是内部属性 / 用错 C4 版本**：误把 `jur_filter` 写进契约字段或 `FilterOptions` 第 5 个列表；或沿用 v1.1 §6 旧 C4（`HAS_MILESTONE` join） | 契约被污染（P-001 过滤器多出选项）/ 日历返回 0 或 110 条而非 213 | `cypher.py` 的 `Q_CALENDAR` **必须用 v1.2 §5 新版**（独立 `:CalendarEvent`、`e.jur_filter = $jurisdiction`、**7 个 RETURN 别名不变**、`map_calendar_event`/`apply_date_filter`/排序零改动）；`jur_filter` **仅存在于 Cypher 内部**，不出现在任何响应/契约/枚举字典；新版 C4 **不加** `WHERE r.instrument_id IS NOT NULL`；日历 59 种细粒度 jurisdiction 不新增字典 |

**另需固定盯防（非 Top5 但同样致命）**：所有 C2/C3/C5/C6 必带子图隔离 `WHERE r.instrument_id IS NOT NULL`（R1，`test_cypher.py` 加静态护栏）；`main.py` / `App.tsx` **U-000 之后冻结**；`q` 只 `strip()` 不转义（参数化是唯一防注入）；`/api/llm/*` 恒 HTTP 200 且 `llm.py` 不生成 Cypher；`/api/status` 断连仍 200；3 处 `regpass123` 已修复，**不得回退**。

---

**文档状态：** 已完成，交付 team-lead / 全体 fullstack-dev / code-reviewer / qa-verifier
**落盘：** `deliverables/feature_task_cards.md`　|　**卡总数：14**（U-000 ×1 + U-BE-01..06 ×6 + U-FE-01..07 ×7）
**批次：** Batch 0 = 1 卡（U-000，门禁）／Batch 1 = 11 卡（并行）／Batch 2 = 2 卡（验收，并行）
