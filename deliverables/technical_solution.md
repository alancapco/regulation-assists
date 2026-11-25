# 技术方案 · AI Regulation Corpus Explorer

**架构师：** 高见远 (solution-architect)　|　**版本：** v1.1　|　**日期：** 2026-11-11
**上游依据：** `deliverables/requirements_specification.md` v1.0、`deliverables/product_design_specification.md` **v1.1**（§8 冻结契约；v1.1 修订见其 §9）
**变更记录：** 见本文 §15「v1.1 修订记录」——仅澄清日历默认视图口径，**未变更任何字段名 / 类型 / 枚举 / 端点**。
**图谱依据：** `research/poc/neo4j_schema.cypher`、`research/poc/neo4j_loader.py`，并**已在活库 `capco-graph-neo4j` 上逐条验证本文 §6 全部 Cypher 模板**
**读者：** team-lead → feature-planner → 全体 fullstack-dev。**本文 §5 / §6 / §7 即冻结线，开发不得偏离。**

> **全局四原则（下游必须遵守，见 §13 落地方式）**
> ① **简洁为荣，冗余为耻** — 不重复实现、不过度抽象、复用既有能力；
> ② **注释只在关键处** — 仅在核心逻辑／算法／边界处理／易错点写中文注释，解释「为什么」，禁止逐行旁白；
> ③ **契约冻结** — 接口与数据模型冻结后变更必须走 §14 流程；
> ④ **交付必须落盘** — 本文已落盘 `deliverables/technical_solution.md`。

---

## 0. 摘要 · 开工前必读的 5 条

1. **本 Neo4j 实例是被共享的**。`MATCH (r:Regulation)` 实测返回 **638** 个节点，其中只有 **30** 个带 `instrument_id`（本项目数据）；其余 608 个是另一套 GraphRAG 数据集的 `:__Entity__:Regulation`。`:Topic` 共 39，其中只有 10 个属于本项目。**所有查询必须带 `WHERE r.instrument_id IS NOT NULL` 隔离本子图**，否则列表会返回 638 条垃圾数据、状态栏会显示 `638/1174`。这是本文最重要的实现约束（§6.0、R1）。
2. **图谱字段与冻结契约不一致，全部由映射层吸收，绝不改契约字段名**（§7）。
3. **`GraphData.links[]` 完整形状已定义**：`{ source, target, type }`，字段名 `type` 沿用设计师 §8 冻结契约，不引入 `kind`（§5.2、§5.4 API-006、R4）。
4. **只查 Neo4j，Postgres 延后**；本文不提供 SQL，改提供 **6 条可直接执行的参数化 Cypher 模板**（§6），全部 `$param` 参数化、无字符串拼接、无 LLM 生成 Cypher。
5. **两个数据现实与验收口径冲突，须 team-lead 拍板**（R2、R3）：日历实际只有 **61** 个 Milestone（设计/需求写 213），若按需求原文的「未来 12 个月」默认窗口仅命中 **1** 条、首屏近乎空白——故**默认不加日期过滤**（返回全量、按日期升序），「未来 12 个月」改为过滤栏快捷项（v1.1，见 §5.4 API-005）；图谱中**没有 EU AI Act (2024/1689)**，F-002 验收示例数据不存在。**后端不硬编码任何计数**（30/39/213/61 一律动态查询），仅 `total_count=1174` 是按主理人指令固化的常量。

---

## 1. 技术选型与版本

### 1.1 版本表（锁定基线）

| 层 | 组件 | 锁定版本 | 选型理由 |
|---|---|---|---|
| 运行时 | Python | 3.12.x（现有 `pyproject.toml` 为 `>=3.12`） | 沿用仓库约束；当前 `.venv` 为 3.14.3，若依赖解析异常回退 3.12 LTS |
| 后端框架 | FastAPI | 0.115.6 | 原生 async、Pydantic v2 深度集成、自动生成 OpenAPI（`/docs`）供前端对齐契约 |
| ASGI | uvicorn[standard] | 0.34.0 | 单进程异步即可满足「10 并发不降级」；`--reload` 用于开发 |
| 校验 | pydantic | 2.10.4 | v2：`Field(default_factory=list)` 保证数组恒为数组、`Literal` 冻结枚举 |
| 配置 | pydantic-settings | 2.7.0 | `.env` + 环境变量类型化，LLM 凭据**不入配置** |
| 图驱动 | **neo4j** | **6.4.1**（`uv.lock` 已锁） | 官方驱动自带一等 `AsyncGraphDatabase` / `AsyncDriver`，无需线程池包装 |
| HTTP 客户端 | httpx | 0.28.1 | OpenAI 兼容端点只用 1 种请求体，直发 `/chat/completions` 即可，避免引入 openai SDK 的重型抽象；便于对 Azure 做最小适配 |
| 测试 | pytest / pytest-asyncio | 8.3.4 / 0.25.0 | 映射层纯单测 + `ASGITransport` 接口测试 |
| 前端运行时 | Node.js | 20 LTS | 需求 §7.5 要求 20+ |
| 构建 | Vite | 6.0.5 | TS/React 官方模板，`/api` 代理开箱即用 |
| UI 框架 | React / react-dom | 18.3.1 | 选 18 而非 19：shadcn/Radix 生态在 18.3.1 上零 peer 依赖踩坑，19 对本项目无收益（能简单就不复杂） |
| 类型 | TypeScript | 5.7.2 | 契约 TS 镜像强类型，`tsc --noEmit` 作为交付门槛 |
| 路由 | react-router-dom | 6.28.1 | 设计稿用的 `<Outlet />` 布局路由 / `useSearchParams` 均为 v6 稳定 API |
| 样式 | tailwindcss / postcss / autoprefixer | 3.4.17 / 8.4.49 / 10.4.20 | shadcn 在 Tailwind v3 配置格式上稳定；v4 改了 config 协议，本期不用 |
| 组件 | shadcn/ui（CLI 生成，非 npm 版本包） | new-york 风格 | 设计稿 §5 明确「一律复用 shadcn，不造轮子」；依赖 Radix + CVA + clsx + tailwind-merge + lucide-react + sonner |
| 可视化 | d3 / @types/d3 | 7.9.0 / 7.4.3 | 用户指定；`forceSimulation` / `forceLink` / `d3.zoom` / `d3.drag` 全在 v7 核心包 |

> 以上为**已验证存在且互相兼容**的基线；`uv.lock` 与 `frontend/package-lock.json` 是最终权威版本来源。**禁止任何开发私自升级大版本**（尤其 Tailwind 3→4、React 18→19、Pydantic 1→2）。

### 1.2 异步 Neo4j 驱动决策：**用官方 async driver，不用 sync driver + 线程池**

**决策**：`from neo4j import AsyncGraphDatabase`，全链路 `async/await`；**单个 `AsyncDriver` 实例**在 FastAPI `lifespan` 中创建并挂到 `app.state`，所有请求共享其连接池，关闭时 `await driver.close()`。

**理由**：
1. FastAPI 全异步，若用同步 driver 必须 `await asyncio.to_thread(...)`，每个查询多一次线程切换 + 占用线程池；需求 §7.1 要求 10 并发不降级，异步 Bolt I/O 用单事件循环即可复用连接，线程池反而引入 10 个 OS 线程竞争。
2. `neo4j==6.4.1`（仓库已锁）原生提供 `AsyncDriver` / `AsyncSession` / `AsyncResult`。**已实测确认**：`AsyncGraphDatabase.driver` 存在、`AsyncSession.run` / `AsyncResult.data` / `AsyncDriver.verify_connectivity` 均为协程、`AsyncResult` 支持 `async for`。**没有任何理由再包一层线程池**。
3. 所有查询只读，直接用 `await session.run(cypher, **params)`（隐式只读事务），**不引入 `execute_read` 回调层**——只读场景多一层事务函数属于过度设计。

**标准读取范式（全后端唯一写法，禁止第二种）**：
```python
async with driver.session() as session:
    result = await session.run(CYPHER_TEMPLATE, **params)
    rows: list[dict] = await result.data()   # Record.data() → dict，映射层只吃 list[dict]
```

**强制约束**：`backend/app/` 内所有涉及 DB 的函数必须是 `async def` 并 `await`；Code Review 检查「是否出现同步 `.run(` 或未 await 的协程」。

---

## 2. 目录结构

### 2.1 uv 工程决策：**扩展根项目，不建独立 backend 项目**

**决策**：继续用仓库根的 `pyproject.toml` + `uv.lock`，`uv add` 追加依赖，**不创建 `backend/pyproject.toml`**。

| 理由 | 说明 |
|---|---|
| 复用既有环境 | `research/poc/neo4j_loader.py` 已在同一个 uv 环境里用 `neo4j` 驱动；另起项目会重复锁定驱动、分裂 lockfile、两套 `uv sync` |
| 共享凭据 | 后端与 loader 用同一组 `NEO4J_*`，一份 `.env` 足够 |
| 启动简单 | 根目录直接 `uv run uvicorn backend.app.main:app --reload --port 8000` |
| 文件更少 | 符合「简洁为荣」；`[tool.uv] package = false` 保持不变（无需打包） |

**重要边界**：复用的是**环境与图谱 DDL**，**不在运行时 import `research/poc/*`**。那些是带 `argparse`/`sys.exit` 的一次性 CLI 脚本，import 会引入脆弱耦合。后端自有 `cypher.py` / `mapping.py` 作为唯一定义处。loader 中的 `_domain()`（1 行 `urlparse`）在映射层用标准库同样实现，属于「1 行标准库调用」，不值得为此耦合 POC 脚本。

`pyproject.toml` 追加后形态：
```toml
[project]
name = "regulation-assists"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "neo4j>=5.20",              # 既有，uv.lock 已解析为 6.4.1
    "fastapi>=0.115,<1",
    "uvicorn[standard]>=0.34,<1",
    "pydantic>=2.10,<3",
    "pydantic-settings>=2.7,<3",
    "httpx>=0.28,<1",
]
[tool.uv]
package = false
[dependency-groups]
dev = ["pytest>=8.3", "pytest-asyncio>=0.25"]
```

### 2.2 目录树（精确路径）

```
regulation-assits/                         # 仓库根（已存在）
├─ research/                               # 【只读】既有数据 / POC 脚本 / 研究文档，本阶段不改
├─ deliverables/                           # 【既有】需求 / 设计 / 本文
├─ pyproject.toml  uv.lock                 # 【既有】按 §2.1 扩展
├─ docker-compose.yml                      # 【既有】需修 healthcheck 密码，见 R7
├─ .env.example                            # 【新增】后端环境变量样例
├─ backend/                                # 【新增】
│  ├─ __init__.py
│  ├─ app/
│  │  ├─ __init__.py
│  │  ├─ main.py            # app 工厂、lifespan、CORS、全局异常处理器、路由挂载
│  │  ├─ config.py          # Settings（pydantic-settings）+ TOTAL_COUNT 等常量
│  │  ├─ deps.py            # 单例 AsyncDriver 依赖注入
│  │  ├─ schemas.py         # ★ 冻结契约的全部 Pydantic 模型（唯一定义处）
│  │  ├─ errors.py          # 错误码枚举 / AppError / ErrorEnvelope
│  │  ├─ cypher.py          # ★ 6 条参数化 Cypher 模板常量（唯一定义处）
│  │  ├─ mapping.py         # ★ Neo4j record → 契约模型 的唯一映射层
│  │  ├─ llm.py             # httpx AsyncClient 封装（base_url 适配 / test / ask）
│  │  └─ routers/
│  │     ├─ __init__.py
│  │     ├─ meta.py         # GET /api/status, GET /api/filters
│  │     ├─ regulations.py  # GET /api/regulations, GET /api/regulations/{instrument_id}
│  │     ├─ calendar.py     # GET /api/calendar
│  │     ├─ graph.py        # GET /api/graph
│  │     └─ llm.py          # POST /api/llm/test, POST /api/llm/ask（可选）
│  └─ tests/
│     ├─ conftest.py        # fixture：mock AsyncDriver / ASGITransport client
│     ├─ test_mapping.py    # 纯函数单测（无 DB）
│     ├─ test_cypher.py     # 模板参数化 / 子图隔离断言 + 可选活库冒烟
│     └─ test_api.py        # 8 个端点的状态码 / 形状 / 异常分支
└─ frontend/                               # 【新增】
   ├─ components.json       # shadcn 配置（见 §11.5）
   ├─ package.json  package-lock.json
   ├─ vite.config.ts        # /api → http://localhost:8000 代理
   ├─ tsconfig.json  tsconfig.node.json
   ├─ tailwind.config.ts  postcss.config.js
   ├─ index.html
   └─ src/
      ├─ main.tsx  App.tsx  index.css
      ├─ lib/utils.ts                # cn()
      ├─ types/contract.ts           # ★ 冻结契约的 TS 镜像（唯一定义处）
      ├─ api/client.ts               # ★ fetch 封装 + 类型化端点函数 + 错误拦截
      ├─ hooks/useApi.ts             # ★ 全站唯一数据获取 hook
      ├─ hooks/useLlmConfig.ts       # localStorage + Base64
      ├─ components/
      │  ├─ ui/                      # shadcn CLI 生成，禁止手写
      │  ├─ Shell.tsx  StatusBar.tsx  EmptyState.tsx  ErrorState.tsx
      │  └─ D3ForceGraph.tsx        # ★ 唯一可视化定制
      └─ pages/
         ├─ RegulationsPage.tsx  RegulationDetailPage.tsx
         ├─ CalendarPage.tsx  GraphPage.tsx  SettingsPage.tsx
```

---

## 3. 配置

### 3.1 环境变量与 `.env.example`

```dotenv
# --- Neo4j（唯一数据源）---
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=capco-graph-change-me

# --- HTTP ---
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
LOG_LEVEL=INFO

# --- 展示 / 限流常量 ---
TOTAL_COUNT=1174          # OKF 全量清单条数，主理人指定常量，不从图库查询
GRAPH_MAX_NODES=100       # 图谱总节点上限
GRAPH_REG_LIMIT=40        # 法规锚点上限，为邻居节点预留 >=60 个名额
LLM_TIMEOUT_TEST=10       # 秒
LLM_TIMEOUT_ASK=30        # 秒
```

> **⚠️ 无 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` 环境变量**：LLM 凭据**只在前端 localStorage，绝不落服务端磁盘或进程内存**（见 §8.3）。

### 3.2 `backend/app/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "capco-graph-change-me"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    log_level: str = "INFO"
    total_count: int = 1174
    graph_max_nodes: int = 100
    graph_reg_limit: int = 40
    llm_timeout_test: float = 10.0
    llm_timeout_ask: float = 30.0

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

settings = Settings()
```

**约定**：`TOTAL_COUNT=1174` 是**唯一硬编码计数**，代表 OKF 清单全量规模（需求 §1.3 / 验收 F-008）。**其余任何数量（30 条法规、10 个主题、61 个事件、148 个候选节点）一律由查询动态得出，前端禁止写死**——图谱是共享库且 loader 为 MERGE 累积，硬编码必然失效。

### 3.3 LLM 凭据策略：**无状态，逐请求随 body 上送**

| 项 | 决策 |
|---|---|
| 存储 | 仅在浏览器 `localStorage`（`api_key` 按设计稿 Base64 编码，**非加密**，UI 显示警示） |
| 传输 | `POST /api/llm/*` 的 **JSON body** 携带 `LlmConfig`（见 §5.2）；后端不写 session、不写文件、不写日志 |
| 取舍 | 好处：零服务端状态、无认证/多租户隔离需求、重启不丢、符合 MVP 单用户；代价：key 经本机 HTTP 明文传输。**本地/内网部署可接受；若公网暴露必须改 HTTPS + 白名单**（R10）。另一方案（服务端加密存储 + session）在无鉴权前提下只会增加复杂度，明确不采用 |

---

## 4. 数据模型（图谱现状，替代 SQL）

> Postgres 延后到 Phase 3+，本期**没有建表 SQL**。图谱 DDL 已在 `research/poc/neo4j_schema.cypher` 且**已应用于活库**（5 个唯一性约束 + 4 个查询索引），开发**不得修改或重复执行**。本节只描述读取契约所依赖的结构。

### 4.1 实体关系（本项目子图）

```
(Jurisdiction {name}) ◀─[:IN_JURISDICTION]── (Regulation {instrument_id, ...})
(InstrumentType {name}) ◀─[:OF_TYPE]──────── (Regulation)
(Topic {name})         ◀─[:HAS_TOPIC]─────── (Regulation)
(Source {url, domain}) ◀─[:SOURCED_FROM | HAS_OFFICIAL_TEXT | PUBLISHED_AT]── (Regulation)
(Milestone {uid, name, date, notes}) ◀─[:HAS_MILESTONE]── (Regulation)
```

**所有关系方向均为 `Regulation → 邻居`**，这是 §5 列表/详情/图谱投影能用 pattern comprehension 一次取完、不产生 N+1 的结构基础。

### 4.2 节点属性（以 `neo4j_loader.py` 实际写入为准）

| 标签 | 属性 | 备注 |
|---|---|---|
| `Regulation` | `instrument_id`(PK), `name`, `legislation_type`, `legislation_date`, `legal_force`, `description`, `in_language`, `date_modified`, `official_publication_url`, `official_text_url`, `license`, `breadcrumb`, `full_analysis_free`, `record_url` | **没有** `jurisdiction` / `type` 属性！见 §7 M1。`legislation_date` 存为**字符串**，不是 Neo4j `Date` |
| `Jurisdiction` | `name` | 唯一约束 |
| `InstrumentType` | `name` | 唯一约束 |
| `Topic` | `name` | 唯一约束 |
| `Source` | `url`(唯一), `domain` | `domain` 由 loader 用 `urlparse().netloc` 写入 |
| `Milestone` | `uid`(唯一), `name`, `date`, `notes` | `date` 是**脏文本**（范围／`(Approx.)`／HTML 残留） |

### 4.3 活库实测（2026-11-11，本架构师启动容器后核验）

| 标签 | 全库节点数 | **本项目子图** | 说明 |
|---|---:|---:|---|
| `Regulation` | **638** | **30** | 608 个为 `:__Entity__:Regulation`（另一套 GraphRAG 数据，只有 `id`/`description`，无 `instrument_id`） |
| `Topic` | **39** | **10** | 29 个为 `:__Entity__:Topic` 外来节点 |
| `Jurisdiction` | 3 | 3 | 全部本项目 |
| `InstrumentType` | 5 | 5 | 全部本项目 |
| `Source` | 107 | 107 | 全部本项目 |
| `Milestone` | 61 | 61 | 全部本项目 |
| 其它外来标签 | `Document` 255 / `Chunk` 1137 / `__Entity__` 5039 / `User` 2 / `Session` 2 / `Message` 4 | — | 与本应用无关，但**共享同一数据库** |

> **由此产生 P0 铁律：本项目「法规」的判别式是 `r.instrument_id IS NOT NULL`。** 所有 `MATCH (r:Regulation)` 必须带此条件；`/api/filters` 的 `jurisdictions` / `topics` 必须从**本子图的关联节点**取值，不能 `MATCH (j:Jurisdiction) RETURN j.name` 或 `MATCH (t:Topic) RETURN t.name`（会混入 29 个外来 Topic）。详见 §6.0、R1。

### 4.4 本项目子图的数据质量实测（决定 §7 映射规则）

| 事实 | 实测值 | 对契约的影响 |
|---|---|---|
| `legal_force` 取值 | `InForce` / `PartiallyInForce` / `NotInForce`；**10 条为空** | 设计稿示例的 `Draft` / `Withdrawn` **不存在** → 必须走 `/api/filters` 动态字典（R5）；空值映射为 `""` |
| `legislation_type` 取值 | `Guideline` / `Decree` / `Bill` / `Policy` / `Regulation` | 5 值，动态字典 |
| 本项目 `Jurisdiction` | `Argentina` / `APEC` / `African Union` | 3 值，动态字典 |
| 本项目 `Topic` | 10 个 snake_case 值 | 动态字典 |
| `legislation_date` | 21 条 ISO，**9 条仅年份**（`2023`×4 / `2024`×4 / `2025`×1） | 归一为 `null`（不伪造月日），见 §7 |
| `Milestone.date` | **9 条非 ISO**（如 `2024-07-18 to 2024-07-19`、`2025-01-01 (Approx.)`、`2023-06-08 (introduced; Exp. 2504-D-2023)</td>…`） | 取首个 `YYYY-MM-DD`，见 §7 |
| 官方来源关系 | `HAS_OFFICIAL_TEXT` 30 / `PUBLISHED_AT` 30 / `SOURCED_FROM` 109；单条法规 **3~9 条** 源边 | **≤3 截断规则必须实现** |
| 重复 URL | **26/30** 条法规的 `official_text_url == official_publication_url` | **必须按 URL 去重**，否则详情出现两个同链接 |
| `Source.domain` | 本项目 107 个全非空 | 仍保留后端兜底计算（D2） |
| 无里程碑的法规 | 10 条 | `milestones: []`（数组恒为数组） |
| 图谱候选节点 | 30 regulation + 3 jurisdiction + 10 topic + 105 source = **148** | **超过 100 上限**，截断与悬空边处理必须实现 |
| `Milestone.uid` | 61 个全非空 | `CalendarEvent.id` 可直接用 |
| `name` / `description` / `record_url` | 全部非空 | 无需兜底，但仍 `coalesce` |

---

## 5. 冻结 API 契约 ⛔

> **字段名、类型、枚举一律沿用 `product_design_specification.md` §8。本节只做「补全」与「精确化」，未重命名任何字段。**

### 5.1 通用约定

| 项 | 约定 |
|---|---|
| Base path | `/api`（Vite dev 通过 proxy 转发到 `http://localhost:8000`） |
| 成功响应 | **裸对象 / 裸数组**，不包 `{data:...}` / `{code:0,...}`。如 `GET /api/regulations` → `Regulation[]` |
| 失败响应 | 统一 `ErrorEnvelope`（§9.1）+ 非 2xx HTTP 状态 |
| 鉴权 | **无**（MVP 单用户，A-001）；不传也不校验任何 token |
| 日期 | 一律 `YYYY-MM-DD` 字符串或 `null`；**不得**出现 `2023`、`2024-07-18 to ...`、`(Approx.)` |
| 数组 | `official_sources` / `topics` / `milestones` / `nodes` / `links` **恒为数组**，缺失返回 `[]`，永远不返回 `null` |
| 枚举大小写 | 与 Neo4j 一致（`InForce`、`HAS_TOPIC`，不转小写/驼峰） |
| 列表 / 详情 | **同一套字段名**；依主理人 D1，`GET /api/regulations` 返回**完整 `Regulation` 对象数组**（非精简摘要），30 条无性能问题，避免第二套命名 |
| `official_sources[].domain` | **后端计算**（D2）。优先 `Source.domain`，为空时用 `urlparse(url).netloc`；**前端永不解析 URL** |
| 参数化 | **所有**进入 Cypher 的用户输入均为 `$param`；`q` 中的 `' " ;` 不转义、不拼接，直接作为参数值（已实测注入串 `' OR 1=1 //` 返回 0 行，见 §12） |
| 幂等 / 并发 | 全部 GET 只读、天然幂等；每个请求开独立 `AsyncSession`，共享 driver 连接池，无共享可变状态；`POST /api/llm/*` 非幂等（外部调用可能计费），前端按钮在 in-flight 期间 `disabled` 防重复提交，后端不加幂等键（MVP 不需要） |

### 5.2 Pydantic 模型（`backend/app/schemas.py`，逐字落地）

```python
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from urllib.parse import urlparse

# ---------- 冻结契约（与 product_design_specification.md §8 一一对应）----------
class OfficialSource(BaseModel):
    url: str
    domain: str
    rel_type: Literal["SOURCED_FROM", "HAS_OFFICIAL_TEXT", "PUBLISHED_AT"]

class Milestone(BaseModel):
    date: str | None
    title: str

class Regulation(BaseModel):
    instrument_id: str
    name: str
    jurisdiction: str
    type: str
    legal_force: str
    legislation_date: str | None
    description: str | None
    record_url: str
    official_sources: list[OfficialSource] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    milestones: list[Milestone] = Field(default_factory=list)

class CalendarEvent(BaseModel):
    id: str
    date: str
    title: str
    instrument_id: str
    regulation_name: str
    jurisdiction: str
    source_url: str | None

class GraphNode(BaseModel):
    id: str
    label: str
    type: Literal["regulation", "jurisdiction", "topic", "source"]   # 仅 4 值

class GraphLink(BaseModel):
    source: str
    target: str
    type: Literal["IN_JURISDICTION", "HAS_TOPIC", "SOURCED_FROM"]     # 仅 3 值

class GraphData(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    links: list[GraphLink] = Field(default_factory=list)

class AppStatus(BaseModel):
    connected: bool
    regulation_count: int
    total_count: int

class LlmConfig(BaseModel):                 # 前端 localStorage 镜像；也作为 POST body
    base_url: str
    api_key: str = ""
    model: str = ""

class LlmTestResponse(BaseModel):           # 冻结：POST /api/llm/test
    ok: bool
    error: str | None

# ---------- 本方案新增（架构师定义，同样冻结）----------
class FilterOptions(BaseModel):             # GET /api/filters
    jurisdictions: list[str] = Field(default_factory=list)
    types: list[str] = Field(default_factory=list)
    legal_forces: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)

class LlmAskRequest(LlmConfig):             # POST /api/llm/ask（可选功能 A-004）
    question: str = Field(min_length=1, max_length=2000)
    instrument_id: str | None = None

class LlmAskResponse(BaseModel):
    ok: bool
    answer: str | None
    error: str | None

class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: str | None = None

class ErrorEnvelope(BaseModel):
    error: ErrorDetail

class RegulationQuery(BaseModel):           # GET /api/regulations 的 7 个冻结查询参数
    q: str = ""
    jurisdiction: str = ""
    type: str = ""
    legal_force: str = ""
    topic: str = ""
    date_from: str = ""
    date_to: str = ""

class CalendarQuery(BaseModel):             # GET /api/calendar
    jurisdiction: str = ""
    date_from: str = ""
    date_to: str = ""

class GraphQuery(BaseModel):                # GET /api/graph
    jurisdiction: str = ""
    topic: str = ""
```

**查询参数依赖（唯一校验入口，`backend/app/routers/*.py` 通过 `Depends` 复用）**：
```python
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def _opt_date(v: str) -> str:
    # 空串 = 不过滤；非空必须是合法 ISO 日期，交由后端参数化 / 映射层比较
    if v and not ISO.match(v):
        raise AppError(400, "VALIDATION_ERROR", "日期格式须为 YYYY-MM-DD")
    return v

async def regulation_params(
    q: Annotated[str, Query(max_length=200)] = "",
    jurisdiction: str = "", type: str = "", legal_force: str = "", topic: str = "",
    date_from: str = "", date_to: str = "",
) -> RegulationQuery:
    date_from, date_to = _opt_date(date_from.strip()), _opt_date(date_to.strip())
    if date_from and date_to and date_from > date_to:
        raise AppError(400, "VALIDATION_ERROR", "date_from 不得晚于 date_to")
    return RegulationQuery(q=q.strip(), jurisdiction=jurisdiction, type=type,
                           legal_force=legal_force, topic=topic,
                           date_from=date_from, date_to=date_to)
```
> `q` 只做 `strip()` + 长度限制，**不做任何字符转义**：参数化是唯一防注入手段，转义反而会改变搜索语义。

### 5.3 接口清单

| API-ID | 功能ID | Method | Path | 说明 | 鉴权 | 成功 | Cypher |
|---|---|---|---|---|---|---|---|
| API-001 | F-008 | GET | `/api/status` | 连接状态 + 计数 | 无 | `200 AppStatus` | C1 + C2 |
| API-002 | F-001/003/004/005 | GET | `/api/filters` | 4 类 facet 动态字典 | 无 | `200 FilterOptions` | C6 |
| API-003 | F-001 | GET | `/api/regulations` | 列表 + 搜索 + 过滤（**完整对象数组** D1） | 无 | `200 Regulation[]` | C3 |
| API-004 | F-002/F-003 | GET | `/api/regulations/{instrument_id}` | 详情 | 无 | `200 Regulation` | C3 |
| API-005 | F-004 | GET | `/api/calendar` | 日历事件 | 无 | `200 CalendarEvent[]` | C4 |
| API-006 | F-005 | GET | `/api/graph` | 力导向图数据 | 无 | `200 GraphData` | C5 |
| API-007 | F-006 | POST | `/api/llm/test` | 测试 OpenAI 兼容端点连通性 | 无 | `200 LlmTestResponse` | 无 |
| API-008 | A-004 | POST | `/api/llm/ask` | 可选问答（**非核心路径**） | 无 | `200 LlmAskResponse` | 复用 C3 取上下文 |

> **为什么新增 `GET /api/filters`（API-002）**：设计稿 P-001/P-003/P-004 的 4 个 Select 需要枚举字典，但**实际值与设计稿示例不一致**（真实 `legal_force` 是 `InForce/PartiallyInForce/NotInForce`，设计稿写的 `Draft/Withdrawn` 不存在；真实 jurisdiction 只有 3 个且不是 EU/US/CN）。若前端硬编码选项，过滤器必然失效。故加一个只读 facet 端点，值全部由本子图动态聚合。**这是「不加抽象、只补必要信息」的最小增量**，不引入任何新表/缓存。

### 5.4 接口详情

#### API-001 `GET /api/status` → `AppStatus`
- 参数：无。
- 行为：`await session.run(Q_PING)` → 成功则 `connected=True`，再 `Q_STATUS` 取 `regulation_count`；`total_count = settings.total_count`（1174 常量）。
- **Neo4j 断连时仍返回 HTTP 200**：`{"connected": false, "regulation_count": 0, "total_count": 1174}`，让状态条能渲染红灯而不抛错（§9.3）。
- 响应示例：`{"connected": true, "regulation_count": 30, "total_count": 1174}`
- 错误码：**无**（该端点不返回 4xx/5xx）。
- 幂等：只读、幂等；前端 `Shell` 挂载时与 `window.focus` 时各取一次，**不轮询**（避免过度设计）。

#### API-002 `GET /api/filters` → `FilterOptions`
- 参数：无。Cypher C6，从**本子图关联节点**聚合（隔离外来节点）。
- 响应示例（活库实测）：
```json
{
  "jurisdictions": ["APEC", "African Union", "Argentina"],
  "types": ["Bill", "Decree", "Guideline", "Policy", "Regulation"],
  "legal_forces": ["InForce", "NotInForce", "PartiallyInForce"],
  "topics": ["accountability_documentation", "conformity_assessment_registration", "..."]
}
```
- 映射层对 4 个列表统一 `sorted(v for v in xs if v)`；空库返回 4 个 `[]`。
- 错误码：`503 NEO4J_UNAVAILABLE` / `500 INTERNAL_ERROR`。幂等：只读。

#### API-003 `GET /api/regulations` → `Regulation[]`
- 查询参数（冻结 7 个）：`q, jurisdiction, type, legal_force, topic, date_from, date_to`，全部可选，空串 = 不过滤。
- Cypher C3（`$instrument_id=""`）；**日期过滤在映射层执行**（§7.4）。
- 响应：完整 `Regulation` 对象数组（D1），按 `name` 升序。
- 响应示例（节选，活库真实数据）：
```json
[{
  "instrument_id": "RAI-X5-GO-INITIAT-2025",
  "name": "APEC Artificial Intelligence (AI) Initiative (2026-2030)",
  "jurisdiction": "APEC", "type": "Policy", "legal_force": "",
  "legislation_date": "2026-01-01",
  "description": "The APEC AI Initiative (2026-2030) guides ...",
  "record_url": "https://regulations.ai/regulations/RAI-X5-GO-INITIAT-2025",
  "official_sources": [
    {"url":"https://www.apec.org/...","domain":"www.apec.org","rel_type":"SOURCED_FROM"},
    {"url":"https://www.apec.org/...","domain":"www.apec.org","rel_type":"HAS_OFFICIAL_TEXT"}
  ],
  "topics": ["governance_oversight", "international_alignment"],
  "milestones": [{"date":"2026-01-01","title":"APEC AI Initiative endorsed"}]
}]
```
- 错误码：`400 VALIDATION_ERROR`（日期非法 / 区间倒置）、`503 NEO4J_UNAVAILABLE`、`500 INTERNAL_ERROR`。**0 结果是 `200 []`，不是错误**（前端显示空态）。
- 幂等：只读、幂等；30 条一次返回，无分页（A-003）。

#### API-004 `GET /api/regulations/{instrument_id}` → `Regulation`
- 路径参数：`instrument_id: str`（如 `RAI-AR-NA-AD2DAXX-2018`）。
- 复用 C3（`$instrument_id` 置为路径值，其余参数全空）——**列表与详情共用同一 Cypher 与同一 `map_regulation`，杜绝两套命名/两套实现**。
- 响应：单个 `Regulation`（**不是数组**）。
- 错误码：`404 NOT_FOUND`（ID 不存在，文案「未找到该法规」）、`503 NEO4J_UNAVAILABLE`、`500 INTERNAL_ERROR`。
- 幂等：只读、幂等；`instrument_id` 上有唯一性约束，索引查找。

#### API-005 `GET /api/calendar` → `CalendarEvent[]`
- 查询参数：`jurisdiction, date_from, date_to`（后两者为 ISO，**全部可选，空串 = 不过滤**）。
- **默认视图（v1.1 与设计师 §4 P-003 对齐）**：**前端默认不传 `date_from` / `date_to`**，即返回本子图全量事件并按归一后日期升序（活库 61 条）；「未来 12 个月」作为过滤栏**快捷按钮**由前端拼好 ISO 参数后下发。理由：需求原文的「未来 12 个月」默认窗口实测只命中 1 条，首屏近乎空白。此调整**不改契约**（`CalendarQuery` 默认 `""` 天然支持，后端 `apply_date_filter` 在两参数为空时不裁剪），也不新增任何字段 / 端点。计数文案恒为动态「共 N 个事件」，不写死 213。最终口径仍以 team-lead 对 R2 的拍板为准（接受 61 或补导 213 条数据）。
- Cypher C4 返回全部本子图 Milestone；**归一 + 日期过滤 + 排序全在映射层**（`m.date` 是脏文本，见 §7.4）。
- 响应示例（活库真实数据）：
```json
[{
  "id": "RAI-AR-NA-AD2DAXX-2018|Decree 996/2018 signed|2018-11-02",
  "date": "2018-11-02", "title": "Decree 996/2018 signed",
  "instrument_id": "RAI-AR-NA-AD2DAXX-2018",
  "regulation_name": "Agenda Digital 2030 (Digital Agenda 2030)",
  "jurisdiction": "Argentina",
  "source_url": "https://www.argentina.gob.ar/normativa/nacional/decreto-996-2018-316036"
}]
```
- `source_url` 按 `HAS_OFFICIAL_TEXT > PUBLISHED_AT > SOURCED_FROM` 优先级取首个，全无则 `null`。
- 错误码：`400 VALIDATION_ERROR`、`503 NEO4J_UNAVAILABLE`、`500 INTERNAL_ERROR`；0 结果 `200 []`。
- **⚠️ 数量口径（R2）**：本子图只有 **61** 个 Milestone，`date_from=2026-11-11 ~ 2027-11-11` 实测仅 **1** 条，`2026-2045` 仅 **6** 条，远非需求/设计的 213。**后端绝不硬编码 213**；请 team-lead 确认验收口径或安排导入 `research/data/calendar_events.jsonl`。

#### API-006 `GET /api/graph` → `GraphData`　★ `links[]` 完整定义
- 查询参数：`jurisdiction, topic`（与 P-004 过滤栏一致）。
- **`GraphData.links[]` 形状（本方案补全，字段名冻结）**：
```jsonc
{
  "source": "string",   // 起点节点 id，恒等于某个 nodes[].id；本图谱中恒为 Regulation 的 instrument_id
  "target": "string",   // 终点节点 id，恒等于某个 nodes[].id
  "type":   "IN_JURISDICTION" | "HAS_TOPIC" | "SOURCED_FROM"   // 仅 3 值
}
```
  - **字段名用 `type`，不用 `kind`**：设计师 §8 冻结契约已把该字段命名为 `type`（`links: [{source, target, type}]`）；主理人消息中的「source/target/kind」按**关系语义描述**理解。依「不重命名字段」铁律保留 `type`。若确需改名属契约变更，走 §14（R4）。
  - 方向：一律 `Regulation → 邻居`，与图谱关系方向一致；`d3.forceLink().id(d => d.id)` 会把 `source`/`target` 字符串**原地替换成节点对象**，故前端必须传深拷贝（§11.4）。
  - `source`/`target` 引用的节点**保证存在于 `nodes` 中**（§7.5 丢弃悬空边）。
  - 不投影 `OF_TYPE` / `HAS_OFFICIAL_TEXT` / `PUBLISHED_AT` / `HAS_MILESTONE` / `OCCURS_IN`：它们不在冻结的 3 值枚举内；这些关系仍可在**详情端点**的 `official_sources[].rel_type` / `milestones` 中读到，图谱不丢信息、只是不画。
- **节点 id 规则（保证全局唯一，避免 d3 合并节点）**：
  | type | `id` | `label` |
  |---|---|---|
  | `regulation` | `r.instrument_id`（**不加前缀**，前端点击直接用它拼 `/regulations/:id`） | `r.name` |
  | `jurisdiction` | `"jur:" + j.name` | `j.name` |
  | `topic` | `"topic:" + t.name` | `t.name` |
  | `source` | `"src:" + s.url` | `s.domain` |
  - **`InstrumentType` 节点一律不出现在 `/api/graph`**：`nodes[].type` 冻结为 4 值，主理人已裁定不新增第 5 个枚举值；`OF_TYPE` 关系同样不投影。`type` 字段（法规类型）已作为 `Regulation.type` 在列表/详情中提供，图谱无需重复表达（M4）。
  - 设计稿图例只画了 ●Regulation ■Jurisdiction ◆Topic，**漏了 `source`**；`D3ForceGraph` 补第四类「灰色小圆 + 文字」，形状/色/文字三重编码保持不变（R11）。
- 100 节点上限：`GRAPH_MAX_NODES=100` 总节点上限、`GRAPH_REG_LIMIT=40` 法规锚点上限；**优先级 regulation > jurisdiction > topic > source**，超出即丢弃，并**同步丢弃端点被裁掉的 link**。前端以 `nodes.length >= 100` 判定截断并展示「数据量较大，请使用过滤器缩小范围」（契约无 `truncated` 字段，禁止新增）。活库候选 148 节点，必然触发截断。
- 响应示例：
```json
{
  "nodes": [
    {"id":"RAI-X5-GO-INITIAT-2025","label":"APEC AI Initiative (2026-2030)","type":"regulation"},
    {"id":"jur:APEC","label":"APEC","type":"jurisdiction"},
    {"id":"topic:governance_oversight","label":"governance_oversight","type":"topic"},
    {"id":"src:https://www.apec.org/...","label":"www.apec.org","type":"source"}
  ],
  "links": [
    {"source":"RAI-X5-GO-INITIAT-2025","target":"jur:APEC","type":"IN_JURISDICTION"},
    {"source":"RAI-X5-GO-INITIAT-2025","target":"topic:governance_oversight","type":"HAS_TOPIC"},
    {"source":"RAI-X5-GO-INITIAT-2025","target":"src:https://www.apec.org/...","type":"SOURCED_FROM"}
  ]
}
```
- 错误码：`503 NEO4J_UNAVAILABLE`、`500 INTERNAL_ERROR`；0 结果 `200 {"nodes":[],"links":[]}`。幂等：只读。

#### API-007 `POST /api/llm/test` → `LlmTestResponse`
- Body：`LlmConfig`（**平铺**，即 `{base_url, api_key, model}`，不加 `config` 包装）。
- `base_url` 校验：`urlparse` 后 `scheme ∈ {http, https}` 且 `netloc` 非空，否则 `400 VALIDATION_ERROR`（文案「请输入有效的URL」）。
- 行为：`POST {base_url}/chat/completions`，`messages=[{"role":"user","content":"ping"}]`，`max_tokens=1`，`timeout=LLM_TIMEOUT_TEST`。
- 响应：`{"ok": true, "error": null}` / `{"ok": false, "error": "LLM API调用失败：[错误详情]"}`。
- **该端点恒返回 HTTP 200**：上游超时/401/404/网络错误一律转成 `ok=false`，绝不把可选功能失败升级成全局 5xx（F-006「不阻塞其他功能」）。
- 幂等：非幂等（外部调用可能计费）；前端「测试连接」按钮 in-flight 时禁用。

#### API-008 `POST /api/llm/ask` → `LlmAskResponse`（**可选**，A-004）
- Body：`LlmAskRequest = LlmConfig + {question, instrument_id?}`（继承冻结 `LlmConfig`，无额外包装）。
- 行为：若带 `instrument_id`，复用 **C3** 取该 `Regulation`，由后端拼装纯文本上下文（name / description / type / legal_force / legislation_date / topics / milestones / official_sources），与 `question` 组成 messages；无 `instrument_id` 则只发 `question`。**模型输出只作为答案文本返回，绝不解析、绝不执行、绝不生成 Cypher**（§8.4）。
- 响应：`{"ok": true, "answer": "...", "error": null}` / `{"ok": false, "answer": null, "error": "..."}`，恒 HTTP 200。
- 若 feature-planner 判定本期不做问答，可直接裁剪本端点，**F-006 只需 API-007**；裁剪不改动任何冻结字段。

---

## 6. Cypher 模板库（`backend/app/cypher.py`）

> **共 6 条，覆盖 7 个数据端点**（`/api/status` 用 C1+C2，`/api/llm/*` 零 Cypher，`/api/llm/ask` 复用 C3）。需求 §7.3 提到「20-30 个模板」是上限描述；按「简洁为荣、只写需要的」，**6 条即完整集，不凑数**。
> 全部模板已在本项目活库上逐条执行验证（含空过滤、各单过滤、组合过滤、注入串、按 ID 查询），结果见 §12。
> **禁止**任何形式的 Cypher 字符串拼接（含 f-string 拼接用户输入）；所有变量一律 `$param`。**不使用 APOC**，保持纯 Cypher 5 语法。

### 6.0 所有模板的共同前置：子图隔离 ⛔

```cypher
MATCH (r:Regulation)
WHERE r.instrument_id IS NOT NULL     -- ★ 共享库隔离：不带这一行会混进 608 个外来节点
```

`instrument_id` 是本子图的天然判别式（外来 `:__Entity__:Regulation` 只有 `id`/`description`）。**C2/C3/C4/C5/C6 全部必须包含此条件**；`C6` 的 `jurisdictions`/`topics` 还必须从「本子图 Regulation 的关联节点」取值，而不是全标签扫描。这是 P0 级实现约束，Code Review 逐条核对。

### C1 `Q_PING` — 连通性
```cypher
RETURN 1 AS ok
```

### C2 `Q_STATUS` — 法规计数（供 F-008 状态条）
```cypher
MATCH (r:Regulation)
WHERE r.instrument_id IS NOT NULL
RETURN count(r) AS regulation_count
```

### C3 `Q_REGULATIONS` — 列表 + 详情共用（★ 唯一 Regulation 投影）

**参数**：`$instrument_id, $q, $jurisdiction, $type, $legal_force, $topic`（全部 `str`，空串 = 不过滤）。**注意：日期参数不进 Cypher**，见 §7.4。

```cypher
MATCH (r:Regulation)
WHERE r.instrument_id IS NOT NULL
  AND ($instrument_id = '' OR r.instrument_id = $instrument_id)
  AND ($q = '' OR toLower(coalesce(r.name, '')) CONTAINS toLower($q)
               OR toLower(coalesce(r.description, '')) CONTAINS toLower($q))
  AND ($jurisdiction = '' OR EXISTS { MATCH (r)-[:IN_JURISDICTION]->(j:Jurisdiction) WHERE j.name = $jurisdiction })
  AND ($type = '' OR r.legislation_type = $type)
  AND ($legal_force = '' OR r.legal_force = $legal_force)
  AND ($topic = '' OR EXISTS { MATCH (r)-[:HAS_TOPIC]->(tp:Topic) WHERE tp.name = $topic })
RETURN
  r.instrument_id AS instrument_id,
  r.name AS name,
  coalesce(head([ (r)-[:IN_JURISDICTION]->(j:Jurisdiction) | j.name ]), '') AS jurisdiction,
  coalesce(r.legislation_type, '') AS type,
  coalesce(r.legal_force, '') AS legal_force,
  r.legislation_date AS legislation_date,
  r.description AS description,
  coalesce(r.record_url, '') AS record_url,
  [ (r)-[rel:SOURCED_FROM|HAS_OFFICIAL_TEXT|PUBLISHED_AT]->(s:Source)
    | { url: s.url, domain: coalesce(s.domain, ''), rel_type: type(rel) } ] AS official_sources_raw,
  [ (r)-[:HAS_TOPIC]->(t:Topic) | t.name ] AS topics,
  [ (r)-[:HAS_MILESTONE]->(m:Milestone) | { date: m.date, title: m.name } ] AS milestones_raw
ORDER BY coalesce(r.name, '')
```

**设计要点（关键处注释）**：
- 用 **pattern comprehension** 而非多条 `OPTIONAL MATCH`：`r` 与三类邻居是多对多，链接式 `OPTIONAL MATCH` 会产生笛卡尔积（`j × topic × source` 行），而 comprehension 保证**一条法规一行**、且无匹配时自然返回 `[]`（直接满足「数组恒为数组」）。
- `jurisdiction` 用 `head([...])` 而非 `OPTIONAL MATCH`，同样避免行膨胀；`coalesce(..., '')` 保证契约中 `jurisdiction: string` 永不为 `null`。
- `type` 取 `r.legislation_type` 属性而非 `InstrumentType.name`（见 §7 M1）；`$type` 过滤也用属性，走索引、少一跳。
- `EXISTS { MATCH ... }` 相关子查询用于 `jurisdiction` / `topic` 过滤，避免过滤条件把主查询变成多值行。
- 列表端点传 `$instrument_id=''`，详情端点传具体 ID，**一条模板两用**，禁止复制粘贴出第二份投影。
- **≤3 官方来源、domain 后端兜底、milestone 日期归一/排序**全部留给 §7 映射层（Cypher 只负责如实取回原始值）。

### C4 `Q_CALENDAR` — 日历事件

**参数**：`$jurisdiction`（空串 = 不过滤）。`date_from/date_to` 在映射层执行。

```cypher
MATCH (r:Regulation)-[:HAS_MILESTONE]->(m:Milestone)
WHERE r.instrument_id IS NOT NULL
  AND ($jurisdiction = '' OR EXISTS { MATCH (r)-[:IN_JURISDICTION]->(j:Jurisdiction) WHERE j.name = $jurisdiction })
RETURN
  m.uid AS id,
  m.date AS date_raw,
  coalesce(m.name, '') AS title,
  r.instrument_id AS instrument_id,
  coalesce(r.name, '') AS regulation_name,
  coalesce(head([ (r)-[:IN_JURISDICTION]->(j:Jurisdiction) | j.name ]), '') AS jurisdiction,
  coalesce(
    head([ (r)-[:HAS_OFFICIAL_TEXT]->(s:Source) | s.url ]),
    head([ (r)-[:PUBLISHED_AT]->(s:Source) | s.url ]),
    head([ (r)-[:SOURCED_FROM]->(s:Source) | s.url ])
  ) AS source_url
ORDER BY m.date
```
- `id ← m.uid`、`title ← m.name`（§7 M2）。
- `source_url` 用 `coalesce(head(...), head(...), head(...))` 做**确定性优先级**，无匹配自然为 `null`。
- `ORDER BY m.date` 只是粗排；**权威排序在映射层按归一后 ISO 日期**（脏文本直接字符串排序不可靠）。
- 日期异常事件由映射层归一，无法解析则跳过（F-004「日期为空/格式错误跳过」；需求 §7.4「范围取起始日期」优先，见 §7 M5）。

### C5 `Q_GRAPH` — 图谱原始行（nodes/links 由映射层组装）

**参数**：`$jurisdiction, $topic, $reg_limit`（`reg_limit = settings.graph_reg_limit`，默认 40）。

```cypher
MATCH (r:Regulation)
WHERE r.instrument_id IS NOT NULL
  AND ($jurisdiction = '' OR EXISTS { MATCH (r)-[:IN_JURISDICTION]->(j:Jurisdiction) WHERE j.name = $jurisdiction })
  AND ($topic = '' OR EXISTS { MATCH (r)-[:HAS_TOPIC]->(tp:Topic) WHERE tp.name = $topic })
WITH r ORDER BY coalesce(r.name, '') LIMIT $reg_limit
RETURN
  r.instrument_id AS rid,
  coalesce(r.name, r.instrument_id) AS rname,
  [ (r)-[:IN_JURISDICTION]->(j:Jurisdiction) | { id: 'jur:' + j.name,   label: j.name } ] AS jurs,
  [ (r)-[:HAS_TOPIC]->(t:Topic)             | { id: 'topic:' + t.name, label: t.name } ] AS topics,
  [ (r)-[:SOURCED_FROM]->(s:Source)         | { id: 'src:' + s.url,     label: coalesce(s.domain, '') } ] AS sources
```
- **仅投影 3 类冻结关系**；`OF_TYPE` / `HAS_OFFICIAL_TEXT` / `PUBLISHED_AT` / `HAS_MILESTONE` 不进图谱（M4、§5.4 API-006）。
- `source` 节点仅通过 `SOURCED_FROM` 进入，避免违反 `links.type` 三值枚举。
- **100 节点总上限不在 Cypher 里做**：因为一旦在 Cypher 截断节点，链接会指向不存在的节点（d3 会生成幽灵节点）。故 Cypher 只限法规锚点，总上限与「丢弃悬空边」在映射层一次性完成（§7.5）。
- `reg_limit=40 < max_nodes=100` 是**刻意预留**：保证即使将来法规数增长，也至少有 60 个名额给邻居节点，不会退化成「100 个孤立法规 + 0 条边」。

### C6 `Q_FILTERS` — facet 动态字典

**参数**：无。

```cypher
MATCH (r:Regulation)
WHERE r.instrument_id IS NOT NULL
WITH collect(DISTINCT r.legislation_type) AS types,
     collect(DISTINCT r.legal_force) AS legal_forces
OPTIONAL MATCH (rj:Regulation)-[:IN_JURISDICTION]->(j:Jurisdiction)
WHERE rj.instrument_id IS NOT NULL
WITH types, legal_forces, collect(DISTINCT j.name) AS jurisdictions
OPTIONAL MATCH (rt:Regulation)-[:HAS_TOPIC]->(t:Topic)
WHERE rt.instrument_id IS NOT NULL
RETURN jurisdictions, types, legal_forces, collect(DISTINCT t.name) AS topics
```
- `collect(DISTINCT ...)` 忽略 `null`，因此 10 条 `legal_force` 为空的法规**不会**产生空选项；`OPTIONAL MATCH` 保证空子图也返回一行（4 个 `[]`），不会「查无此行」。
- **jurisdictions / topics 从关联边取值**，而非 `MATCH (t:Topic)` 全标签扫描——后者会混入 29 个外来 `:__Entity__:Topic`（§4.3）。
- `types` / `legal_forces` 从 `r.legislation_type` / `r.legal_force` 取，与 C3 的 `type` 投影同源，保证「筛选项一定筛得出结果」。
- 排序在映射层统一 `sorted()`，Cypher 不做 `ORDER BY`（collect 结果无序）。

### 6.7 模板 → 端点 / 契约字段映射总表

| 契约字段 | 图属性 / 表达式 | 模板 |
|---|---|---|
| `Regulation.instrument_id / name / description / record_url` | `r.instrument_id / r.name / r.description / r.record_url` | C3 |
| `Regulation.jurisdiction` | `head([(r)-[:IN_JURISDICTION]->(j) \| j.name])` | C3 |
| `Regulation.type` | `r.legislation_type` | C3 |
| `Regulation.legal_force` | `r.legal_force`（空 → `""`） | C3 |
| `Regulation.legislation_date` | `r.legislation_date` → 映射层归一 | C3 |
| `official_sources[].url / domain` | `s.url / s.domain`（domain 后端兜底） | C3 |
| `official_sources[].rel_type` | `type(rel)`（`SOURCED_FROM\|HAS_OFFICIAL_TEXT\|PUBLISHED_AT`） | C3 |
| `topics[]` | `[(r)-[:HAS_TOPIC]->(t) \| t.name]` | C3 |
| `milestones[].date / title` | `m.date`（归一）/ `m.name` | C3 |
| `CalendarEvent.id` | `m.uid` | C4 |
| `CalendarEvent.title / regulation_name / jurisdiction / source_url` | `m.name / r.name / j.name / s.url` | C4 |
| `GraphData.nodes[]` | `r` + `IN_JURISDICTION` / `HAS_TOPIC` / `SOURCED_FROM` 邻居 | C5 + 映射层 |
| `GraphData.links[].type` | 上述 3 类关系（常量，非查询） | 映射层 |
| `AppStatus.regulation_count` | `count(r)`（带子图隔离） | C2 |
| `AppStatus.total_count` | `settings.total_count = 1174` | 非查询 |

---

## 7. 数据映射层（`backend/app/mapping.py`）

> **唯一职责**：把 `list[dict]`（Cypher 行）变成 §5.2 的 Pydantic 模型。**所有契约↔图谱错位必须且只能在此吸收**，router 不得自行拼字段。

### 7.1 四处错位决议（主理人指定 M1–M4 + 本方案补充 M5）

| 编号 | 错位 | **决议（不得改契约字段名）** |
|---|---|---|
| **M1** | 契约 `Regulation.jurisdiction` / `.type` 是扁平字符串，图中是关联节点（`Jurisdiction.name` / `InstrumentType.name`），且 `Regulation` 另有 `legislation_type` 属性 | **`jurisdiction` ← `Jurisdiction.name`**（图中无 `r.jurisdiction` 属性，只能走 `IN_JURISDICTION`，C3 用 `head([...])` 投影）。**`type` ← `r.legislation_type` 属性为准**（与 `InstrumentType.name` 同源同值——loader 用同一个 `legislation_type` 字段同时写属性与 `OF_TYPE`；取属性省一次关系跳跃、可走索引、且与 `$type` 过滤同源）。`OF_TYPE` / `InstrumentType` 仅作图谱辅助，**不作为 `type` 数据源** |
| **M2** | 契约 `milestones[].title` ← 图 `Milestone.name`；契约 `CalendarEvent.id` ← `Milestone.uid` | C3/C4 已把 `m.name AS title`、`m.uid AS id` 投影好，映射层直接取；**C3 的 `milestones_raw` 不含 uid**（详情不需要），C4 的 `id` 用 `uid` |
| **M3** | 契约 `official_sources[].rel_type` 需真实关系类型；`domain` 需在 `Source.domain` | C3 用 `[rel:A\|B\|C]` 绑定关系变量并 `type(rel)` 输出真实 `rel_type`；`domain` 优先 `s.domain`，为空时后端 `urlparse(url).netloc` 兜底（**D2：前端永不解析 URL**） |
| **M4** | 契约 `nodes[].type` 枚举仅 4 值，图中还有 `InstrumentType` 节点 | **`/api/graph` 完全排除 `InstrumentType` 节点与 `OF_TYPE` 关系**，C5 只投影 `IN_JURISDICTION` / `HAS_TOPIC` / `SOURCED_FROM`；**不新增第 5 个枚举值**。理由：法规类型已由 `Regulation.type` 表达，图谱重复表达无信息增益；且契约冻结优先于图完整性 |
| **M5**（本方案补充） | 需求 §7.4 要求「范围日期取起始日期」，设计稿 P-003 却说「date 非 ISO 时跳过」 | **先归一、后过滤**：`normalize_date()` 用首个 `YYYY-MM-DD` 正则提取（范围取起始、`(Approx.)`/HTML 清洗），**只有完全无法提取才跳过**。实测 9 条非 ISO Milestone 全部可救回 → 日历保住 61 条。这样同时满足需求 §7.4 与设计稿「异常不返回」的意图，且不伪造日期 |

### 7.2 函数签名（唯一映射入口）

```python
ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
REL_PRIORITY = {"HAS_OFFICIAL_TEXT": 0, "PUBLISHED_AT": 1, "SOURCED_FROM": 2}

def normalize_date(raw: object) -> str | None: ...
def normalize_domain(raw: str | None, url: str) -> str: ...
def map_official_sources(raw: list[dict]) -> list[OfficialSource]: ...
def map_milestones(raw: list[dict]) -> list[Milestone]: ...
def map_regulation(rec: dict) -> Regulation: ...
def map_calendar_event(rec: dict) -> CalendarEvent | None: ...
def apply_date_filter(items: list, date_from: str, date_to: str,
                      key: str) -> list: ...            # 列表/日历共用
def map_graph(rows: list[dict], max_nodes: int = 100) -> GraphData: ...
def map_filters(rec: dict) -> FilterOptions: ...
```

### 7.3 逐函数规则

```python
def normalize_date(raw: object) -> str | None:
    """为什么：图谱的 Milestone.date 含范围/'(Approx.)'/HTML 残留，legislation_date 还有
    仅年份('2023')；契约只允许 YYYY-MM-DD 或 null。取首个 ISO 起始日期（需求 §7.4），
    仅年份/无法解析返回 None——不伪造 01-01，避免给合规研究虚假精确日期。"""
    if not raw:
        return None
    m = ISO_RE.search(str(raw))
    return m.group(0) if m else None
```
- `"2024-07-19"` → `"2024-07-19"`；`"2024-07-18 to 2024-07-19"` → `"2024-07-18"`；`"2025-01-01 (Approx.)"` → `"2025-01-01"`；`"2023-06-08 (introduced; ...)</td>…"` → `"2023-06-08"`；`"2023"` → `None`；`""` → `None`。

```python
def normalize_domain(raw: str | None, url: str) -> str:
    # D2：domain 一律后端算，Source.domain 缺失时从 url 兜底
    return raw or (urlparse(url).netloc if url else "")
```

```python
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
```
- 优先级 `HAS_OFFICIAL_TEXT`（法律正文）> `PUBLISHED_AT`（官方公报）> `SOURCED_FROM`（一般引用）；同优先级按 URL 字典序保证**结果稳定可测**。
- 单条法规实测 3~9 条源边 → 截断到 3 是硬规则；无来源 → `[]`（详情显示「官方来源：未提供」，F-003）。

```python
def map_milestones(raw: list[dict]) -> list[Milestone]:
    # title ← m.name（M2）；归一后按 date 升序，null 排末尾（契约要求升序）
    out = [Milestone(date=normalize_date(x.get("date")), title=x.get("title") or "")
           for x in (raw or [])]
    return sorted(out, key=lambda m: (m.date is None, m.date or ""))
```
> 注：契约 `milestones[]` 只有 `{date, title}`，**没有存放原始日期文本的字段**，故无法解析时 `date=null`（前端显示「—」）。设计稿「显示原始文本」无法在不改契约的前提下实现，作为已知限制记录（R6）；本期 9 条异常日期均可救回，实际不触发。

```python
def map_regulation(rec: dict) -> Regulation:
    """列表/详情共用（D1），唯一 Regulation 构造入口。"""
    return Regulation(
        instrument_id = rec["instrument_id"],
        name          = rec.get("name") or "",
        jurisdiction  = rec.get("jurisdiction") or "",   # M1: Jurisdiction.name
        type          = rec.get("type") or "",           # M1: r.legislation_type
        legal_force   = rec.get("legal_force") or "",    # 10 条空 → ""
        legislation_date = normalize_date(rec.get("legislation_date")),
        description   = rec.get("description"),
        record_url    = rec.get("record_url") or "",
        official_sources = map_official_sources(rec.get("official_sources_raw")),
        topics        = sorted({t for t in (rec.get("topics") or []) if t}),
        milestones    = map_milestones(rec.get("milestones_raw")),
    )
```

```python
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
```

```python
def apply_date_filter(items, date_from: str, date_to: str, key: str):
    """为什么放在映射层而不是 Cypher：legislation_date / Milestone.date 都是脏文本，
    必须'先归一再比较'；Cypher 里对 '2023'、'2024-07-18 to ...' 做字符串 >= 会出错。
    30/61 行数据量下无性能代价，且日期值根本不进入 Cypher，注入面为零。
    API-003 用 key='legislation_date'，API-005 用 key='date'，两处共用同一实现。"""
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
```
> **决策记录**：`date_from` / `date_to` 仍是冻结的查询参数、由 `Depends` 做 ISO 校验，但**不进 Cypher**。列表与日历各调用一次 `apply_date_filter`，最终按归一日期排序。C3/C4 因此少两个参数，且所有进 Cypher 的值仍全是 `$param`。

```python
def map_filters(rec: dict) -> FilterOptions:
    def clean(xs): return sorted(v for v in (xs or []) if v)
    return FilterOptions(jurisdictions=clean(rec.get("jurisdictions")),
                         types=clean(rec.get("types")),
                         legal_forces=clean(rec.get("legal_forces")),
                         topics=clean(rec.get("topics")))
```

### 7.4 `map_graph` —— 100 节点上限与悬空边（★ 易错点）

```python
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
```
- 活库实测候选 148 节点 → 截断为 100（30 法规 + 3 管辖区 + 10 主题 + 57 source），`links` 中指向被裁 source 的边自动丢弃。
- `type` 三值全部是**常量**，不来自查询结果，天然满足冻结枚举。
- 前端以 `nodes.length >= max_nodes` 显示「数据量较大，请使用过滤器缩小范围」（契约无 `truncated` 字段，**禁止新增**）。

---

## 8. LLM 集成设计（`backend/app/llm.py`）

### 8.1 客户端选型：**httpx，不用 openai SDK**

| 理由 | 说明 |
|---|---|
| 面积极小 | 只有 2 个端点、1 种请求体（`POST /chat/completions`），SDK 的流式/工具/重试抽象全用不上 |
| URL 完全可控 | `base_url` 由用户逐请求下发，需支持 OpenAI `https://api.openai.com/v1`、vLLM `http://host:8000/v1`、Ollama `http://localhost:11434/v1`、Azure 的部署路径；直发 HTTP 最容易做最小适配 |
| 依赖更少 | 不引入 SDK 版本漂移；`httpx` 已是测试依赖（`ASGITransport`） |

`main.py` 的 lifespan 里创建一个**共享 `httpx.AsyncClient()`**（不设 `base_url`，每次传绝对 URL，复用连接池），关闭时 `await client.aclose()`。

### 8.2 请求构造（兼容 4 类端点）

```python
def build_request(cfg: LlmConfig, messages: list[dict], max_tokens: int) -> tuple[str, dict, dict]:
    base = cfg.base_url.rstrip("/")
    if "openai.azure.com" in base:
        # 为什么：Azure OpenAI 不用 /v1/chat/completions，而是部署路径 + api-key 头，
        # 且 model 字段即部署名；单独分支才能覆盖主理人点名的 Azure。
        url = f"{base}/openai/deployments/{cfg.model}/chat/completions?api-version=2024-10-21"
        headers = {"api-key": cfg.api_key} if cfg.api_key else {}
    else:
        url = f"{base}/chat/completions"
        headers = {"Authorization": f"Bearer {cfg.api_key}"} if cfg.api_key else {}
        # 为什么允许空 api_key：Ollama / 本地 vLLM 通常不需要鉴权
    body = {"model": cfg.model, "messages": messages, "max_tokens": max_tokens,
            "temperature": 0.2, "stream": False}
    return url, headers, body
```
- `base_url` 必须 `^https?://` 且 `urlparse().netloc` 非空（Pydantic `field_validator`），非法 → `400 VALIDATION_ERROR`「请输入有效的URL」。
- `timeout`：`test` 用 `settings.llm_timeout_test`(10s)、`ask` 用 `llm_timeout_ask`(30s)，逐请求 `timeout=` 覆盖。
- 成功取 `resp.json()["choices"][0]["message"]["content"]`；任何 `httpx.HTTPError` / 非 2xx / JSON 结构异常 → 统一转成 `ok=false, error=str(exc)`。

### 8.3 配置流与无状态

```
SettingsPage(前端)
  └─ useLlmConfig: localStorage["regulation-corpus:llm-config"]
       {base_url, api_key(Base64), model}
  └─ POST /api/llm/test | /api/llm/ask 的 JSON body  ← 每次请求都带
  └─ 后端 build_request() → httpx 直发用户指定端点
  └─ 后端不持久化、不缓存、不写日志、不写 env
```
- **失败非阻塞**：`/api/llm/*` 恒 HTTP 200；前端错误条「LLM API调用失败：[错误详情]」；其它 5 个页面完全不受影响（F-006 验收）。
- **安全**：key 只在前端内存 + 本机 HTTP body；Base64 非加密，UI 明示警示（设计稿 §4 P-005 / 需求 §7.2）。公网部署需 HTTPS（R10）。

### 8.4 为什么**绝不**用 LLM 生成 Cypher

- 需求 §4.2 明令「LLM生成Cypher查询：研究文档明确禁止（准确率77%），只用模板」，永久不做。
- **架构层的硬保证**：`cypher.py` 是不可变常量模块，`llm.py` **不 import** `cypher.py`、不持有 driver、不接触 `session`；`/api/llm/ask` 的模型输出只作为 `answer` 字符串返回（可选上下文来自 C3 已查好的 `Regulation`），后端**不解析、不 eval、不执行**任何模型输出。Code Review 检查这两条依赖边界。

---

## 9. 错误处理、CORS 与断连行为

### 9.1 统一错误信封（`backend/app/errors.py`）

```python
class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, detail: str | None = None): ...

# 错误码（冻结）
# VALIDATION_ERROR    400  参数校验失败
# NOT_FOUND           404  instrument_id 不存在
# NEO4J_UNAVAILABLE   503  Neo4j 连接失败 / 认证失败 / 查询超时
# INTERNAL_ERROR      500  其它未预期异常
```
**失败响应体（所有端点一致）**：
```json
{ "error": { "code": "NEO4J_UNAVAILABLE",
             "message": "无法连接到图数据库，请检查 Neo4j 服务状态",
             "detail": "Couldn't connect to localhost:7687" } }
```
全局处理器（`main.py`）：
| 捕获 | 映射 |
|---|---|
| `AppError` | 按自带 status / code 输出 `ErrorEnvelope` |
| `RequestValidationError` | `400 VALIDATION_ERROR`（**把 FastAPI 默认 422 统一成 400**） |
| `neo4j.exceptions.ServiceUnavailable` / `AuthError` / `Neo4jError` | `503 NEO4J_UNAVAILABLE` |
| `Exception` | `500 INTERNAL_ERROR`，服务端 `logger.exception` 记录完整堆栈，`detail` 不外泄 |

> 前端 `api/client.ts` 拦截 `!response.ok` → 解析 `error.message` 展示；网络错误统一「服务器错误，请稍后重试」+ `console.error` 详细日志（设计稿 §6）。

### 9.2 Neo4j 断连行为（分级，避免"可选功能失败拖垮全站"）

| 场景 | 行为 |
|---|---|
| `GET /api/status` | **恒 HTTP 200**，`connected=false, regulation_count=0, total_count=1174` → 状态条红灯（F-008） |
| 其余 6 个数据端点 | `503 NEO4J_UNAVAILABLE` → 列表红色 Alert、搜索按钮禁用；日历/图谱/详情统一 `ErrorState` + 重试 |
| `POST /api/llm/*` | **不受影响**，照常 200（LLM 不依赖 Neo4j） |
| `GET /api/filters` | 随库断连 503；前端 facet 降级为「全部」单选项，不阻塞搜索 |

**启动行为**：`lifespan` 里 `AsyncGraphDatabase.driver(...)` **不强制 `verify_connectivity()` 成功才启动**——允许 Neo4j 后于后端启动；`Q_PING` 每次 `/api/status` 实时探测。避免容器顺序导致后端起不来。

### 9.3 CORS

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,        # 默认 localhost:5173 / 127.0.0.1:5173
    allow_credentials=False,               # 无 cookie / 无鉴权
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
```
开发期 Vite 配 `server.proxy = { "/api": "http://localhost:8000" }`（同源，CORS 不生效）；CORS 保留是为了直接 `http://localhost:5173` 打 `http://localhost:8000` 的调试场景。**不部署独立前端服务器**，本期不做 SPA 静态托管（避免过度设计）。

---

## 10. 公共模块清单与落地时序（★ 并行开发的前置条件）

| # | 模块 | 精确路径 | 用途 | 引用方 | 落地时机 |
|---|---|---|---|---|---|
| 1 | 契约模型 | `backend/app/schemas.py` | 全部 Pydantic 模型 + 枚举 | 所有 router / mapping / llm / tests | **T0** |
| 2 | 配置 | `backend/app/config.py` | `Settings` + 常量 | main / deps / meta / graph / llm | **T0** |
| 3 | 错误码与信封 | `backend/app/errors.py` | `AppError` / `ErrorEnvelope` / 码表 | main + 所有 router | **T0** |
| 4 | 驱动依赖 | `backend/app/deps.py` | 单例 `AsyncDriver` + 标准读取范式 | 所有数据 router | **T0** |
| 5 | Cypher 模板库 | `backend/app/cypher.py` | 6 条参数化常量 | 4 个数据 router | **T0** |
| 6 | 映射层 | `backend/app/mapping.py` | record → 契约（吸收 M1–M5） | 4 个数据 router | **T0** |
| 7 | LLM 客户端 | `backend/app/llm.py` | httpx 封装 / Azure 适配 | llm router | T1 |
| 8 | 契约 TS 镜像 | `frontend/src/types/contract.ts` | 与 `schemas.py` 一一对应 | 全部 page / component / api | **T0（前端）** |
| 9 | API client | `frontend/src/api/client.ts` | fetch + 错误拦截 + 类型化端点 | 全部 page | **T0（前端）** |
| 10 | `useApi` | `frontend/src/hooks/useApi.ts` | 全站唯一 loading/error/data hook | 5 个 page | **T0（前端）** |
| 11 | `useLlmConfig` | `frontend/src/hooks/useLlmConfig.ts` | localStorage + Base64 | SettingsPage / llm api | **T0（前端）** |
| 12 | shadcn 基础件 | `frontend/src/components/ui/` | CLI 生成，禁止手写 | 全部页面 | **T0（前端）** |
| 13 | Shell 四件套 | `Shell / StatusBar / EmptyState / ErrorState` | 布局 + 状态 | 全部页面 | **T0（前端）** |
| 14 | `D3ForceGraph` | `frontend/src/components/D3ForceGraph.tsx` | 唯一可视化定制 | GraphPage | T1 |

**落地时序（team-lead 排期时必须遵守）**：
> **T0 = 并行开发启动前**。由**一名**开发先一次性落地 #1–#6 + #8–#13，并跑通 `GET /api/status` 与 `GET /api/regulations` 的最小闭环；**T0 未合入前，其余开发不得开始写各自的端点/页面**，否则必然各写各的映射、各造一套模型（违反原则①）。
> T1 起再按 F-001~F-008 并行分工：`routers/*` 每个文件一个人、`pages/*` 每个页面一个人，`D3ForceGraph` 单独一人。

**明确不做（避免过度设计）**：不设「统一响应包装层」（契约是裸对象）、不设 Repository/Service 抽象层（router 直接调 `cypher.py` + `mapping.py`）、不设 Redis 缓存（30 条数据）、不设 Redux/Pinia（见 §11.3）。

---

## 11. 前端架构

### 11.1 路由（`react-router-dom` v6，`src/App.tsx`）

```tsx
<BrowserRouter>
  <Routes>
    <Route element={<Shell />}>                         {/* 布局路由，含 <Outlet/> + StatusBar */}
      <Route path="/regulations" element={<RegulationsPage />} />
      <Route path="/regulations/:instrument_id" element={<RegulationDetailPage />} />
      <Route path="/calendar" element={<CalendarPage />} />
      <Route path="/graph" element={<GraphPage />} />
      <Route path="/settings" element={<SettingsPage />} />
    </Route>
    <Route path="/" element={<Navigate to="/regulations" replace />} />
    <Route path="*" element={<Navigate to="/regulations" replace />} />
  </Routes>
</BrowserRouter>
```
- 详情页返回用 `navigate(-1)` 保留来源（日历/图谱点法规名跳详情后能回原处）；面包屑「法规列表 / <name>」回 P-001。
- P-001 的 7 个过滤条件用 `useSearchParams` 写 URL query（可分享、可后退）。
- 无独立 404 页；详情 ID 不存在 → 页内 `ErrorState` +「返回列表」。

### 11.2 契约镜像与 API client

`src/types/contract.ts` 是 `schemas.py` 的**逐字 TS 镜像**（含 `type` 联合字面量），只此一处定义；任何契约变更必须**两侧同改**（§14）。

```ts
// src/api/client.ts —— 全站唯一 fetch 出口
const BASE = "/api";
export class ApiError extends Error { constructor(public code: string, msg: string) { super(msg); } }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" }, ...init,
  });
  if (!res.ok) {
    const env = await res.json().catch(() => null) as ErrorEnvelope | null;
    throw new ApiError(env?.error?.code ?? "INTERNAL_ERROR",
                       env?.error?.message ?? "服务器错误，请稍后重试");
  }
  return res.json() as Promise<T>;
}
const qs = (p: Record<string, string>) => {
  const u = new URLSearchParams();
  Object.entries(p).forEach(([k, v]) => { if (v) u.set(k, v); });  // 空串不发送
  const s = u.toString(); return s ? "?" + s : "";
};
export const api = {
  status:      ()                      => request<AppStatus>("/status"),
  filters:     ()                      => request<FilterOptions>("/filters"),
  regulations: (p: RegulationQuery)   => request<Regulation[]>("/regulations" + qs(p)),
  regulation:  (id: string)           => request<Regulation>(`/regulations/${encodeURIComponent(id)}`),
  calendar:    (p: CalendarQuery)     => request<CalendarEvent[]>("/calendar" + qs(p)),
  graph:       (p: GraphQuery)        => request<GraphData>("/graph" + qs(p)),
  llmTest:     (c: LlmConfig)         => request<LlmTestResponse>("/llm/test",
                                          { method: "POST", body: JSON.stringify(c) }),
  llmAsk:      (r: LlmAskRequest)     => request<LlmAskResponse>("/llm/ask",
                                          { method: "POST", body: JSON.stringify(r) }),
};
```
> `qs` 里空串不发送 → 后端 `Depends` 默认 `""` → C3/C4/C5 的「空串=不过滤」语义成立。

### 11.3 状态管理：**不用 Redux / 不用 TanStack Query**

```ts
// src/hooks/useApi.ts —— 全站唯一数据 hook（约 25 行）
export function useApi<T>(fetcher: () => Promise<T>, deps: unknown[]) {
  const [state, setState] = useState<{data?: T; loading: boolean; error?: string}>(
    { loading: true });
  const reload = useCallback(() => {
    let alive = true;
    setState({ loading: true });
    fetcher()
      .then(d => alive && setState({ data: d, loading: false }))
      .catch(e => alive && setState({ loading: false, error: e.message }));
    return () => { alive = false; };
  }, deps);
  useEffect(() => reload(), [reload]);
  return { ...state, refetch: reload };
}
```
- 5 个页面共用一个 hook，`StatusBar` 在 `Shell` 挂载 / `window.focus` 时调 `api.status()`（不轮询）。
- 无跨页共享的全局业务状态（30 条数据、页面间只靠路由参数/URL query 传递），**引入状态库纯属过度设计**。
- `alive` 标志防止快速切过滤时旧响应覆盖新结果（易错点，中文注释「为什么」）。

### 11.4 `D3ForceGraph` 组件 Props（唯一可视化定制）

```ts
interface D3ForceGraphProps {
  nodes: GraphNode[];
  links: GraphLink[];
  onNodeClick: (node: GraphNode) => void;      // 仅 type==='regulation' 由页面跳 P-002
  onNodeHover?: (node: GraphNode | null) => void; // Tooltip：name + type
  maxNodes?: number;                            // 默认 100，供图例/提示用
  className?: string;
}
```
- **去掉设计稿草案里的 `filters` prop**：过滤由页面重新请求后传入新的 `nodes/links`，组件只负责渲染，避免组件内嵌过滤状态造成双向同步（原则①）。
- 内部：`ResizeObserver` 撑满容器（高 `calc(100vh - 260px)` / 最小 480px）；`d3.forceSimulation` + `forceLink().id(d => d.id)` + `forceManyBody` + `forceCenter` + `forceCollide`；`d3.zoom` 缩放平移、`d3.drag` 拖节点；卸载时 `simulation.stop()` 并移除监听。
- **★ 易错点（必须中文注释）**：`d3.forceLink` 会把 `link.source/target` 从 id 字符串**原地改写为节点对象**。因此传入模拟前必须 `links.map(l => ({ ...l }))` 深拷贝，且 `nodes` 同样拷贝，否则 React state 被 d3 污染、二次渲染即崩。
- 交互：hover Regulation → Tooltip（name + type）；点击 `type==='regulation'` → `onNodeClick` → `/regulations/${node.id}`（**id 未加前缀正是为此**）；点击其它类型 → 组件内高亮一跳邻居（不跳页）；键盘 `Enter/Space` 等价点击，SVG `<g tabIndex={0} role="button" aria-label="...">`。
- 图例：● Regulation（蓝）/ ■ Jurisdiction（绿）/ ◆ Topic（橙）/ **● source（灰，设计稿遗漏，本方案补齐）**，形状 + 色 + 文字三重编码。

### 11.5 shadcn 初始化

`npx shadcn@latest init -d`，`components.json`：
```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york", "rsc": false, "tsx": true,
  "tailwind": { "config": "tailwind.config.ts", "css": "src/index.css",
                "baseColor": "slate", "cssVariables": true },
  "aliases": { "components": "@/components", "utils": "@/lib/utils",
               "ui": "@/components/ui", "lib": "@/lib", "hooks": "@/hooks" }
}
```
`npx shadcn@latest add table card badge button input select tabs tooltip skeleton separator switch sonner`。**`Dialog` 不装**（设计稿标注「MVP 可不用」，符合原则①）。所有基础控件一律从 `@/components/ui` 引用，禁止页面内自写按钮/表格/输入框。

### 11.6 LLM 配置存储

`useLlmConfig`：`localStorage["regulation-corpus:llm-config"]`，`api_key` 用 `btoa`/`atob` Base64（**非加密**，UI 底部警示「请勿在生产环境使用」）；进入页回填、保存前 `new URL()` 校验 `^https?://`。`api.llmTest(config)` / `api.llmAsk({...config, question})` 逐请求携带。

### 11.7 响应式

Tailwind 断点：`lg:`(1024) / `xl:`(1280)；P-001 过滤栏 ≥1280 单行 6 列、1024–1279 折 2 行、Select 最小宽 160px、`name` 列 `truncate`；表格自身 `overflow-x-auto`，**页面级无横向滚动**（F-007 验收 1024×768）。

---

## 12. 测试策略

### 12.1 后端 pytest（必须可离线跑）

| 文件 | 内容 | 依赖 |
|---|---|---|
| `test_mapping.py` | `normalize_date`（ISO / 范围 / `(Approx.)` / HTML / 仅年份→None）；`map_official_sources`（≤3、URL 去重、优先级、`rel_type` 真实值、domain 兜底）；`map_milestones`（升序、null 末尾）；`map_regulation`（M1 扁平化、数组恒数组）；`map_calendar_event`（M2 uid、异常跳过）；**`map_graph`（100 上限、无悬空边、无第 5 枚举值、节点 id 前缀规则）**；`apply_date_filter` | 纯 dict，无 DB |
| `test_cypher.py` | 断言 6 条模板中**不含**任何用户输入插值（静态字符串常量）；断言每条 `MATCH (r:Regulation)` 后含 `r.instrument_id IS NOT NULL`（R1 回归护栏）；可选 `NEO4J_TEST_URI` 活库冒烟（未设置则 skip） | 静态 + 可选活库 |
| `test_api.py` | `httpx.AsyncClient(transport=ASGITransport(app=app))` + `AsyncMock` 驱动返回预置行：8 个端点 200 形状、空结果 `[]`、404、`400` 日期非法、`503` 模拟 `ServiceUnavailable`、`/api/status` 断连仍 200 且 `connected=false`、`/api/llm/test` 上游失败仍 200 且 `ok=false` | mock，无真 LLM |

**活库冒烟清单（人工，开发启动后执行）**：`docker start capco-graph-neo4j` → `curl` 8 个端点，核对 `regulation_count=30`、`filters` 返回 3/5/3/10 个选项、`regulations` 长度 30 且每条 `instrument_id` 非空、`graph.nodes ≤ 100` 且所有 `links.source/target ∈ nodes[].id`。

### 12.2 已完成的活库验证（本架构师执行，2026-11-11）

启动 `capco-graph-neo4j` 后逐条跑完 §6 全部模板，结果：

| 验证项 | 结果 |
|---|---|
| C1 `Q_PING` | OK，`ok=1` |
| C2 `Q_STATUS` | OK，`regulation_count=30`（未加隔离前会得 638） |
| C6 `Q_FILTERS` | OK，返回 3 jurisdictions / 5 types / 3 legal_forces / 10 topics，无外来节点 |
| C3 空过滤 | OK，**30 行**，全部 `instrument_id` 非空 |
| C3 各单过滤 | `q=AI` 29、`jurisdiction=Argentina` 27、`type=Decree` 3、`legal_force=PartiallyInForce` 1、`topic=safety_testing_evaluation` 2 |
| C3 注入串 `q="' OR 1=1 //"` | **0 行**（参数化生效，无注入、无语法错误） |
| C3 按 `instrument_id` | 1 行（详情复用同一模板验证通过） |
| C4 日历 / 按管辖区 | 61 行 / `Argentina` 54 行 |
| C5 图谱 / 按管辖区 | 30 锚点行（候选 148 节点）/ `APEC` 1 行 |

### 12.3 前端

- `npx tsc --noEmit`（**交付门槛**，契约镜像与 `api/client.ts` 类型必须零错误）；
- `npm run build`（Vite 生产构建通过）；
- `npm run lint`（ESLint，可选）。
- **不引入前端单测框架**：唯一有逻辑的 `D3ForceGraph` 属 DOM/可视化，MVP 用浏览器手工验收（hover tooltip、点 Regulation 跳详情、100 节点提示、1024×768 无横向滚动）即可，符合「不做投机性架构」。

---

## 13. 全局四原则的落地方式

| 原则 | 本文中的具体约束 |
|---|---|
| ① 简洁为荣，冗余为耻 | 6 条 Cypher 覆盖全部数据端点；**C3 一条模板同时服务列表与详情**；`apply_date_filter` 一处实现供列表/日历共用；映射层唯一；不设 Repository/Service/统一包装层/缓存/Redux；不装用不到的 shadcn `Dialog`；不 import `research/poc/*` |
| ② 注释只在关键处 | 中文注释只允许出现在：§6.0 子图隔离、C3 pattern comprehension 选型、§7.3 `normalize_date` / `apply_date_filter`「为什么归一在映射层」、§7.4 悬空边、§8.2 Azure 分支、§11.3 `alive` 标志、§11.4 d3 变更 source/target。禁止逐行旁白、禁止英文 narration |
| ③ 契约冻结 | §5 / §6 / §7 冻结；`schemas.py` 与 `contract.ts` 两侧一一对应；任何字段名/类型/枚举变更走 §14 |
| ④ 交付必须落盘 | 本文 `deliverables/technical_solution.md` 已落盘；下游代码须落在 §2.2 指定路径 |

---

## 14. 风险与难点

| ID | 风险 / 难点 | 影响 | 应对（**加 ⚠️ 者需 team-lead 拍板**） |
|---|---|---|---|
| **R1** ⛔ | **共享 Neo4j 实例**：`:Regulation` 638 节点（30 本项目）、`:Topic` 39（10 本项目），另有 `__Entity__/Document/Chunk` 等外来数据 | 不加 `WHERE r.instrument_id IS NOT NULL` → 列表返回 638 条垃圾、状态栏 638/1174、图谱全是空节点 | 所有 C2–C6 强制子图隔离；`test_cypher.py` 加静态断言护栏；`/api/filters` 只从关联边取 facet。**已在本方案全部模板内建并活库验证** |
| **R2** ⚠️ | **日历数量口径**：需求/设计写 213 事件，图库实为 **61** 个 Milestone；「未来 12 个月」窗口只命中 **1** 条，2026–2045 仅 6 条 | F-004 验收「显示 213 个事件」无法达成；若沿用「未来 12 个月」默认窗口首屏近乎空白 | 后端**绝不硬编码 213**，`/api/calendar` 返回图库实际数量。**v1.1 已与设计师 §4 P-003 对齐「默认不加日期过滤（全量 61 条、按日期升序），未来 12 个月改为前端快捷按钮」**——不改契约、不改接口，仅前端默认呈现（见 §5.4 API-005）。请 team-lead 确认：① 接受 61 作为 MVP 口径，或 ② 由数据侧扩展 loader 导入 `research/data/calendar_events.jsonl`（213 条）后再验收。**这是数据问题，不是接口问题** |
| **R3** ⚠️ | **数据覆盖与验收示例不符**：本子图 jurisdiction 仅 `APEC / African Union / Argentina`，**不含 EU AI Act (2024/1689)**，也不含 `eur-lex.europa.eu` | F-002 验收示例「EU AI Act + eur-lex 域名标签」在当前图库上失败 | `diverse_30.json`（含 EU/US/CN…）**并未加载进图库**。请 team-lead 确认是否需重跑 loader 换数据集；后端与契约均不依赖具体法规，**接口实现不受影响，仅验收用例需换成本子图真实 ID**（如 `RAI-AR-NA-AD2DAXX-2018`） |
| **R4** ⚠️ | **`GraphData.links` 字段名歧义**：设计师 §8 用 `type`，主理人消息写「source/target/kind」 | 前端若按 `kind` 读会拿不到关系类型 | **本方案裁定保留 `type`**（冻结契约优先 + 不重命名字段铁律）。请 team-lead 确认；若确需 `kind` 属契约变更，须走 §14 并同步双方 |
| **R5** | **枚举值与设计稿示例不一致**：真实 `legal_force = InForce/PartiallyInForce/NotInForce`（无 `Draft/Withdrawn`），10 条为空；jurisdiction 只有 3 个 | 前端硬编码选项 → 过滤失效 / 空结果 | 新增 `GET /api/filters`（API-002），4 个 Select 全部动态填充，**前端禁止硬编码任何枚举**；空 `legal_force` 映射 `""` |
| **R6** | `milestones[].date` 契约无「原始日期文本」字段；9/30 `legislation_date` 仅年份 | 无法解析的日期只能显示 `—`；9 条法规生效日期为空 | `normalize_date`：范围/近似/HTML 取首个 ISO（实测 9 条 Milestone 全部可救回）；仅年份 → `null`，**不伪造 01-01**（合规场景避免虚假精确）。若需展示年份属契约变更（加 `*_raw` 字段） |
| **R7** ⛔ | **Neo4j 容器当前是停止状态**；`docker-compose.yml:36` healthcheck 密码仍是 `regpass123`（应为 `capco-graph-change-me`）；`neo4j_loader.py:28,192` 默认密码同为 `regpass123` | 后端起不来 / 容器被标 unhealthy / 重跑 loader 认证失败 | 开发第一件事：修 3 处密码 → `docker compose up -d`（或 `docker start capco-graph-neo4j`，本架构师已用后者启动并验证）→ 再跑 `uv run uvicorn ...`。**架构师不修改既有文件，交由 dev 修复** |
| **R8** | 26/30 法规的 official_text_url 与 publication_url 相同；单条法规 3~9 条源边 | 详情页重复链接 / 超出「最多 3 条」 | `map_official_sources`：按 URL 去重 + 优先级 + 截断 3 条（§7.3） |
| **R9** | 图谱候选 148 节点 > 100 上限 | 截断后产生悬空边，d3 造幽灵节点 | `map_graph` 先定节点集再生成 link，丢弃端点被裁的边；前端 `nodes.length>=100` 显示提示（契约无 `truncated` 字段） |
| **R10** | LLM `base_url` 用户可控 → SSRF；key 经本机 HTTP 明文 | 本地/内网单用户可接受；公网暴露有风险 | 本期内网部署（A-002）接受；公网化需 `base_url` 白名单 + HTTPS。绝不持久化 key |
| **R11** | 设计稿图例漏了 `source` 节点类型（但契约有 4 值） | 图谱出现无图例节点 | `D3ForceGraph` 补「灰色小圆 + source」图例，保持形状/色/文字三重编码 |
| **R12** | Python 3.14.3 当前 `.venv` 与部分依赖兼容性未全验证 | 依赖解析 / 安装异常 | 建议 CI 固定 3.12 LTS；`uv lock` 为权威 |
| **R13** | LLM 外部端点不可控（超时/401/模型不存在） | 可选功能失败 | 端点恒 200 + `ok=false` + 超时 10/30s；**不影响其它 5 个页面** |
| **R14** | `d3.forceLink` 原地改写 `source/target` | React state 被污染、二次渲染崩溃 | 传入深拷贝（§11.4），中文注释标注 |

---

## 15. 方案冻结声明

- **冻结范围（本文件签署即生效，开发不得偏离）**
  1. `deliverables/technical_solution.md` **§5 冻结 API 契约**（8 个端点 / 全部 Pydantic 模型 / 字段名 / 类型 / 枚举 / 错误码）；
  2. **§6 Cypher 模板库**（6 条，含 §6.0 子图隔离铁律）；
  3. **§7 数据映射层**（M1–M5 决议、≤3 来源、日期归一、100 节点上限、悬空边丢弃）；
  4. `backend/app/schemas.py` 与 `frontend/src/types/contract.ts` 必须**逐字段一一对应**；
  5. 主理人两项决策 **D1**（列表返回完整 `Regulation` 数组）、**D2**（domain 后端算）已写入本文，同样冻结。
- **变更流程（任何字段名 / 类型 / 枚举 / 端点变更）**
  1. 由我（高见远）更新本文件并升版本号（如 v1.1 → v1.2），写明变更前后对照；
  2. 同步 **team-lead → feature-planner → 全部受影响的 fullstack-dev**，确认排期影响；
  3. **同时**更新 `backend/app/schemas.py` 与 `frontend/src/types/contract.ts` 两侧，并补 `test_mapping.py` / `test_api.py` 回归；
  4. **禁止口头约定、禁止只在代码里改而不改文档**。

### v1.1 修订记录（2026-11-11，与 `product_design_specification.md` v1.1 同步）

> **性质：仅澄清「日历默认视图」的前端呈现口径，不是契约变更。** 字段名 / 类型 / 枚举 / 端点 / Pydantic 模型 / Cypher 模板 / 映射规则 **全部未动**；`CalendarQuery` 的 `date_from` / `date_to` 默认值仍是 `""`（空串 = 不过滤），后端 `apply_date_filter` 行为不变，`schemas.py` 与 `contract.ts` 无需改动，无需补测试。

| # | 位置 | v1.0 → v1.1 | 依据 |
|---|---|---|---|
| 1 | §5.4 API-005 查询参数 | 「默认由前端给『未来 12 个月』」→「**默认不传 `date_from`/`date_to`（返回全量、按日期升序）；『未来 12 个月』改为过滤栏快捷按钮**；计数动态、不写死 213」 | 实库 R2：该窗口仅命中 1 条，首屏近乎空白；产品设计师 v1.1 §4 P-003 建议 |
| 2 | §0 摘要第 5 条 / §14 R2 | 补明上述默认视图调整及其「不改契约」性质 | 同上 |
| 3 | 文档头 | 版本 v1.0 → v1.1；上游设计稿标为 v1.1 | 走 §15 变更流程 |

- **同步范围**：已直接回复 product-designer 并抄送 team-lead；feature-planner 拆分 F-004 时须按「默认全量 + 快捷按钮」实现，不得按需求原文的「默认未来 12 个月」。
- **仍待 team-lead 拍板**：R2 的最终验收口径（接受 61 条 / 补导 `calendar_events.jsonl` 的 213 条）。无论哪种，**接口与上述默认呈现均不受影响**。

- **已识别但不阻塞开工的待决项**：R2（日历 61 vs 213 验收口径）、R3（图库数据覆盖与 EU AI Act 示例）、R4（`links.type` 命名确认）。**这三项只影响验收用例与数据准备，不影响接口实现**——feature-planner 可据本文立即拆分任务，但必须在验收用例中避开硬编码 213 / EU AI Act。
- **下游须知**：① 先完成 §10 的 T0 公共模块，再并行；② 所有 `MATCH (r:Regulation)` 必须带子图隔离；③ 注释只在关键处、用中文写「为什么」；④ 修 R7 三处密码后再启动。

---

**文档状态：** 已完成并冻结，交付 team-lead / feature-planner / 全体 fullstack-dev
**落盘路径：** `deliverables/technical_solution.md`
**附：** §6 全部 Cypher 模板已在活库 `capco-graph-neo4j` 上逐条执行验证（结果见 §12.2）。
