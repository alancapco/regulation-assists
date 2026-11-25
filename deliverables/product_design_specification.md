# 产品设计说明 · AI Regulation Corpus Explorer

**设计师：** 简宜用 (product-designer)　|　**版本：** v1.1（定稿）· 已适配 v1.2 数据面　|　**日期：** 2026-11-11
**上游依据：** `deliverables/requirements_specification.md` v1.0（F-001 ~ F-008）
**对齐依据（权威顺序）：** `deliverables/technical_solution_v12_addendum.md` **v1.2**（数据面 / 隔离库计数，**最权威**）＞ `deliverables/technical_solution.md` **v1.1**（§5 冻结契约 / §7 映射层 / §11 前端架构 / §14 风险表 / §15 修订记录）
**定位：** 单用户只读研究工具，全站无登录页。本文 §8 字段规格即**冻结 API 契约**，未经 team-lead / 架构师批准不得改字段名或类型。

> **全局四原则**：① 简洁为荣、冗余为耻（一律复用 shadcn，不造轮子）；② 注释只在关键处（中文，解释「为什么」）；③ 契约冻结；④ 交付必须落盘。
>
> **v1.1 说明**：依据架构师活库核验结果修订施工细节并补全契约，**未新增需求、未重命名任何字段**。§1~§8 编号保持不变（技术方案多处引用），变更清单见 §9。
> **定稿补记（2026-11-11）**：§4 P-003 默认视图获架构师确认并定稿；快捷按钮写入 URL query；文档头「对齐依据」订正为 v1.1 并补引 §15。§8 契约零改动、版本号不升 v1.2。
> **v1.2 数据面适配补记（2026-11-11）**：架构师 v1.2 附录已加载 `diverse_30`（含 EU AI Act / eur-lex）与 **213 条全 ISO 日历事件**，**R2 / R3 / R4 全部关闭**（§0 / §7 治理收口）。本稿据此更新页面示例、枚举实库值、计数口径，并撤销「定位到今天」按钮；**§8 冻结契约逐字未改、契约版本仍为 v1.1**（与架构师「v1.2 仅为数据面附录、不升契约版本」一致），故本稿版本号仍为 v1.1（定稿）。详见 §9 第 10 条。

---

## 1. 信息架构

**Shell（全站唯一布局，所有页面共享）**
- 顶部导航栏：Logo + 「AI Regulation Corpus」+ 4 个 NavLink（法规列表 / 法规日历 / 知识图谱 / 设置），当前项高亮。
- 状态条 F-008：导航下方通栏，`Neo4j: 🟢 已连接 | 已加载 {regulation_count}/{total_count} 条法规`。**两个数字由 `GET /api/status` 动态填入，前端禁止写死**（v1.2 隔离库实测 30/1174）；`connected=false` 时 🔴 + 错误文案（见 §6）。
- 内容区：`<Outlet />`，`max-w-[1600px] mx-auto p-6`。

**页面树**
```
/                                   → 重定向 /regulations
└─ Shell
   ├─ /regulations                    P-001 法规列表（首页，F-001/F-007/F-008）
   │    └─ /regulations/:instrument_id        P-002 法规详情（F-002/F-003）
   ├─ /calendar                       P-003 法规日历（F-004）
   ├─ /graph                          P-004 知识图谱（F-005）
   └─ /settings                       P-005 LLM 设置（F-006）
```
- 详情页为列表页子路由，面包屑「法规列表 / <法规名>」可返回；从日历/图谱点法规名同样跳 P-002，返回用 `navigate(-1)` 保留来源。
- 无独立 404/错误页：未知路由重定向 `/regulations`；详情 ID 不存在 → 页内错误态 + 「返回列表」。

## 2. 用户流程（页面级，含异常分支）

| 流程 | 主路径 | 异常分支 |
|---|---|---|
| 1 检索 F-001 | P-001 → 输入/筛选 → 表格刷新（<2s） | Neo4j 断连 → 状态条红灯 + 搜索/重置按钮禁用；0 结果 → 空态 +「清除筛选」；`/api/filters` 503 → 4 个 Select 降级为仅「全部」，不阻塞搜索 |
| 2 详情溯源 F-002/003 | P-001 点「查看详情」→ P-002 → 外链新标签页 | ID 不存在 → 错误态；来源缺失 →「官方来源：未提供」；日期无法归一 → `date:null` 显示「—」（契约无原始文本字段，见 §9 R6） |
| 3 日历 F-004 | 导航 → P-003 → 时间轴/列表切换 → 过滤 | 日期无法归一的事件后端跳过；过滤后 0 条 → 空态 |
| 4 图谱 F-005 | 导航 → P-004 → hover tooltip / 点 Regulation → P-002 | 返回节点数达 100 上限（v1.2 隔离库候选 **184** 必触发）→ 提示缩小范围；渲染失败 → 错误态 +「重试」 |
| 5 配置 F-006 | 导航 → P-005 → 填表 → 保存 → Toast | URL 非法 → 行内校验；测试连接失败 → 非阻塞错误条，不影响其他页 |

## 3. 页面清单

| 页面ID | 页面名 | 路由 | 功能ID | 入口 | 跳转目标 |
|---|---|---|---|---|---|
| P-001 | 法规列表 | `/regulations` | F-001/007/008 | 默认首页、导航栏、面包屑 | P-002 |
| P-002 | 法规详情 | `/regulations/:instrument_id` | F-002/003 | P-001/P-003/P-004 | 外链（新标签）、P-001（topic 标签） |
| P-003 | 法规日历 | `/calendar` | F-004 | 导航栏 | P-002、外链 |
| P-004 | 知识图谱 | `/graph` | F-005 | 导航栏 | P-002 |
| P-005 | LLM 设置 | `/settings` | F-006 | 导航栏 | 无（原地保存） |

## 4. 页面详情（逐页）

### P-001 法规列表 `/regulations`
- **布局**：SearchFilterBar（Card：搜索框 + 4 个 Select + 日期区间 +「搜索」「重置」）→ 结果计数行 → Table → **无分页**（30 条一次性返回，A-003）。
- **字段规格**（查询/展示参数）

| 字段 | 类型 | 必填 | 校验 / 取值 | 默认值 | 来源(Neo4j) |
|---|---|---|---|---|---|
| `q` | string | 否 | trim，≤200 字符；`' " ;` 不前端转义，由后端参数化防注入 | `""` | `r.name` / `r.description` 模糊匹配 |
| `jurisdiction` | enum(string) | 否 | **选项来自 `FilterOptions.jurisdictions[]`** 或 `All` | `All` | `Jurisdiction.name`（映射为扁平串） |
| `type` | enum(string) | 否 | **选项来自 `FilterOptions.types[]`** 或 `All` | `All` | `r.legislation_type` |
| `legal_force` | enum(string) | 否 | **选项来自 `FilterOptions.legal_forces[]`** 或 `All` | `All` | `r.legal_force`（空 → `""`） |
| `topic` | enum(string) | 否 | **选项来自 `FilterOptions.topics[]`** 或 `All` | `All` | `HAS_TOPIC` |
| `date_from` / `date_to` | string(ISO `YYYY-MM-DD`) | 否 | 合法日期；`date_from ≤ date_to`，否则禁用「搜索」并提示 | 空 | `r.legislation_date`（归一后比较） |

- **⚠️ 枚举硬编码禁令**：4 个 Select 的选项一律由 `GET /api/filters` 动态填充（Shell 挂载时取一次，全站共用），**前端禁止硬编码任何枚举值**。v1.1 依据旧共享库写的 `APEC / African Union / Argentina`、`Draft/Withdrawn` 等**已被 v1.2 数据面取代，一律失效**（附录 §0）。v1.2 隔离库实测字典：jurisdictions **13**（含 EU / US / China…）、types **6**（Act/Bill/Decree/Guideline/Policy/Regulation）、legal_forces **2**（InForce/PartiallyInForce）、topics **11**；这些数字仅供验收核对，**仍不得写进代码**。
- **空值呈现**：`legal_force`、`jurisdiction` 可能为 `""`，表格 Badge 显示「—」，不渲染空 Badge；`legislation_date` 为 `null` 显示「—」（v1.2 隔离库 9/30 条仅年份，归一为 `null`，不伪造 01-01）。
- **表格列（冻结）**：`name` | `jurisdiction` | `type` | `legislation_date` | `legal_force`(Badge) | 操作(「查看详情」Button)。表头点击按 `name` / `legislation_date` 升降序（前端排序，30 条）。
- **交互**：输入防抖 300ms 自动触发（保证 <2s 体感）或点「搜索」立即触发；「重置」恢复默认并重新查询；行 hover 高亮、行单击等价于点「查看详情」；过滤条件写入 URL query（可分享、可后退）。
- **状态**：加载中 → 5 行 `Skeleton`；空 → `EmptyState`「未找到匹配的法规，请尝试其他关键词或过滤条件」+「清除筛选」；错误 → 红色 Alert「无法连接到图数据库，请检查 Neo4j 服务状态」+「重试」；成功 → 「共 N 条法规」（N 动态）。
- **响应式**：≥1280 过滤器单行 6 列；1024–1279 折 2 行、Select 最小宽 160px、`name` 列 `truncate`、隐藏描述列；表格自身 `overflow-x-auto`，**页面级无横向滚动**。

**线框（要点，示例取自 v1.2 隔离库）**
```
┌ Nav: 法规列表* | 日历 | 图谱 | 设置 ────────────────┐
├ Status: Neo4j: 🟢 已连接 | 已加载 30/1174 条法规 ──┤
├ [搜索 q______] [管辖区▾][类型▾][状态▾][主题▾]    ──┤
│ [日期起___][日期止___] [搜索][重置]      共 30 条  │
├ 名称        |管辖区|类型  |生效日期|状态    |操作    ┤
│ EU AI Act…  | EU   |Reg… |2024-08|InForce |[详情]  │
└ …30 行，无分页 ──────────────────────────────────┘
```

### P-002 法规详情 `/regulations/:instrument_id`
- **布局**：面包屑 → H1 + 状态 Badge → `Tabs`（概览 / 时间线）→ 三张 Card：基本信息、官方来源、主题标签；桌面右侧元信息卡。
- **字段规格**（响应对象 `Regulation`，见 §8）

| 字段 | 类型 | 必显 | 校验 / 呈现 | 来源 |
|---|---|---|---|---|
| `instrument_id` | string | 是 | 路由参数，格式 `RAI-XX-...`；空 → 错误态 | `r.instrument_id` |
| `name` | string | 是 | H1，过长换行不截断 | `r.name` |
| `description` | string\|null | 否 | 空显示「暂无描述」 | `r.description` |
| `jurisdiction`/`type`/`legal_force` | string | 是 | Badge；`""` 显示「—」 | 同上 |
| `legislation_date` | string(ISO)\|null | 否 | `null` 显示「—」（v1.2 隔离库 9/30 条仅年份，归一为 `null`，不伪造 01-01） | `r.legislation_date` |
| `record_url` | string(URL) | 是 | `<a target="_blank" rel="noopener noreferrer">`，文案「在 regulations.ai 查看记录」 | `r.record_url` |
| `official_sources[]` | array | 否 | **最多 3 条**；每项 `{url, domain, rel_type}`，按域名标签展示；空数组 →「官方来源：未提供」。**后端已完成按 URL 去重 + 优先级 + ≤3 截断、`domain` 已算好，前端直接渲染，勿再截断、勿自行解析 URL** | SOURCED_FROM / HAS_OFFICIAL_TEXT / PUBLISHED_AT |
| `milestones[]` | array | 否 | `{date, title}`，按 `date` 升序、`null` 排末尾并显示「—」；**契约无原始日期文本字段，不显示原始文本**（R6 已知限制） | `HAS_MILESTONE` |
| `topics[]` | string[] | 否 | 可点击 Badge → 跳 P-001 并预置 `topic` 筛选 | `HAS_TOPIC` |

- **交互**：外链一律新标签页；topic Badge 带 `?topic=xxx` 回列表；时间线条目无操作。
- **状态**：加载中 → 标题 + 三卡 Skeleton；空（ID 不存在，404）→「未找到该法规」+「返回列表」；错误 → 通用错误 + 重试；成功 → 正常渲染。
- **响应式**：≥1280 两栏（主 2/3 + 元信息 1/3）；1024–1279 单栏堆叠，Tabs 保留。
- **✅ 验收用例数据（v1.2 R3 已恢复）**：隔离库 `diverse_30` 含 `RAI-EU-NA-E2AIXXX-2024`（Regulation (EU) 2024/1689）与 `eur-lex.europa.eu`，**F-002 / F-003 验收恢复需求 §6 原文**：名称/描述/类型/生效日期、≥1 官方来源带 `eur-lex.europa.eu` 域名标签、record_url、≥1 实施时间线条目；点击官方链接新标签打开 eur-lex；另用一条无官方来源的真实 ID（由 dev 在隔离库中选取）验证「官方来源：未提供」且 record_url 仍可点。**v1.1 中「改用 `RAI-AR-NA-AD2DAXX-2018`」的替代 ID 警告已作废**。
- **线框（要点）**：面包屑 / H1+Badge / Tabs / 三卡（基本信息｜官方来源含 ≤3 域名标签 + record_url｜主题 Badge）/ 时间线竖向列表。

### P-003 法规日历 `/calendar`
- **布局**：过滤栏（日期起止 + 管辖区 Select + `Tabs` 时间轴/列表）→ 事件计数 → 按年月分组的竖向时间轴（圆点 + 竖线 + Card），或紧凑 Table 列表。
- **字段规格**：过滤 `date_from`/`date_to`(ISO)、`jurisdiction`(同 P-001 动态字典)；事件 `CalendarEvent = {id, date, title, instrument_id, regulation_name, jurisdiction, source_url}`，`source_url` 为 `null` 时不渲染外链按钮。后端**先归一、后过滤**：脏日期取首个 `YYYY-MM-DD`（范围取起始、`(Approx.)`/HTML 清洗），完全无法解析才跳过；返回事件按归一后 `date` 升序。（v1.2 隔离库 213 条全部为合法 ISO，归一逻辑仍保留但对当前数据不触发。）
- **✅ 默认视图（已定稿，v1.2 数据面下继续成立）**：**默认不传 `date_from`/`date_to` → 返回全量、按归一后 `date` 升序**；「未来 12 个月」为过滤栏快捷按钮；计数文案始终动态「共 N 个事件」，**禁止写死 213（也禁止写死 61）**。v1.2 隔离库实测 **213 条、2026-11-27 → 2045-12-31、全部 ISO**（R2 已关闭）；旧共享库的「61 条 / 9 条脏日期 / 2018 年历史事件」描述**一律失效**。接口侧依据（`CalendarQuery` 默认 `""` → `qs()` 不发送该参数 → `apply_date_filter` 双空不裁剪 → 新版 C4 不加日期条件）不变，本项仍为**纯前端默认呈现调整**，§8 契约零改动。
- **交互**：Tabs 切换只换呈现、不重新请求；`regulation_name` 点击 → P-002；「查看原文」→ 外链新标签；改过滤 → 重新请求；**「未来 12 个月」快捷按钮把算好的 ISO `date_from`/`date_to` 一并写入 URL query**（与 P-001「过滤条件写入 URL」一致，可分享、可后退、刷新可复现），「重置日期」清除这两个参数。
- **「定位到今天」按钮 → v1.2 数据面复核后撤销**：该按钮的前提是「默认全量含历史事件、纯升序首屏落在 2018 年」（旧共享库 61 条口径）。v1.2 隔离库 213 条事件**全部为 2026-11-27 → 2045-12-31 的未来事件**，按日期升序首屏天然就是最近将生效的义务，滚动到首个 `date >= 今天` 的分组等于滚回页面顶部，**零收益**。按「简洁为荣、冗余为耻」原则**从 MVP 移除**：不新增字段/接口/组件，§8 契约零改动；若未来补入历史事件再评估。已同步 feature-planner 从 U-FE-03 功能描述与自测项中删除该按钮（保留亦不致功能错误，仅冗余）。
- **状态**：加载中 → Skeleton 卡 ×6；空 →「该范围内暂无里程碑事件」+「重置日期」；错误 → 通用错误 + 重试；成功 →「共 N 个事件」（N 动态）。
- **数据范围（v1.2 隔离库）**：`2026-11-27 → 2045-12-31`、全部 ISO；具体条目以 `GET /api/calendar` 实时返回为准，**页面禁止内置任何示例事件常量**。
- **响应式**：1024 时过滤栏 2 行，时间轴 Card 内字段折行，无横向滚动。

### P-004 知识图谱 `/graph`
- **布局**：过滤栏（管辖区 / 主题 Select +「重置视图」+ 节点计数）→ 自定义 `D3ForceGraph` 画布（`ResizeObserver` 撑满容器，高 `calc(100vh - 260px)`、最小 480px）→ 图例 **4 类**：● Regulation（蓝）/ ■ Jurisdiction（绿）/ ◆ Topic（橙）/ **● source（灰、小圆）**，形状 + 色 + 文字三重编码。
- **字段规格**：`GraphData = {nodes:[{id,label,type}], links:[{source,target,type}]}`；`nodes[].type ∈ regulation|jurisdiction|topic|source`（**4 值，含 source**）；`links[].type ∈ IN_JURISDICTION|HAS_TOPIC|SOURCED_FROM`（**3 值；字段名冻结为 `type`，不引入 `kind`**）；`source`/`target` 恒为 `nodes[].id`、方向恒为 Regulation→邻居；节点上限 100。
- **交互**：滚轮缩放 / 拖拽平移 / 拖拽节点；hover Regulation → Tooltip（name + type）；点击 **Regulation 节点** → P-002（其 `id` 即 `instrument_id`，无前缀，直接拼路由）；点击其余 3 类节点 → 高亮其一跳邻居（不跳页）；过滤 → 重新请求子集并重渲染；「重置视图」恢复默认筛选与缩放。**前端须对 `nodes`/`links` 深拷贝后再交给 d3**（`forceLink` 会原地改写 `source/target` 为节点对象，否则 React state 被污染、二次渲染崩溃）。
- **状态**：加载中 → 画布中央 Spinner「正在渲染图谱…」；空 →「没有符合筛选条件的节点」；**返回 `nodes.length >= 100` 即视为截断**（v1.2 隔离库候选约 30+13+11+130 = **184** 节点必触发；契约无 `truncated` 字段，禁止新增）→ 顶部提示「数据量较大，请使用过滤器缩小范围」；错误 →「图谱加载失败」+「重试」；成功 →「N 节点 / M 关系」。需求 §6 的「3 个 Jurisdiction / 39 个 Topic」是旧共享库口径，**按 100 上限验收，禁止照抄**。
- **响应式**：画布随容器缩放；1024 时图例折行、过滤栏 2 行；页面无横向滚动。
- **线框（要点，计数为示意）**
```
┌ 过滤: 管辖区▾ 主题▾ [重置视图]  100 节点 / M 关系 ┐
┌──────────────── d3 canvas ───────────────────┐
│   ◆──●──■    ●      (缩放/平移/拖拽)         │
│      ╲  │   ╱       hover → Tooltip          │
│       ●─●──◆        click ● → 详情页         │
└─────────────────────────────────────────────┘
图例: ●Regulation ■Jurisdiction ◆Topic ●source(灰)
```

### P-005 LLM 设置 `/settings`
- **布局**：单张 Card（≤640px），三字段 +「测试连接」「保存」+ 底部警示文案「请勿在生产环境使用（API Key 仅 Base64 编码，非加密）」。
- **字段规格**

| 字段 | 类型 | 必填 | 校验 | 默认值 | 存储 |
|---|---|---|---|---|---|
| `base_url` | string(URL) | 保存时必填 | `^https?://` 开头且 `new URL()` 可解析，否则行内提示「请输入有效的URL」 | `""` | localStorage |
| `api_key` | string(password) | 否 | 输入框 type=password + 显隐切换；Base64 编码后存储（非加密） | `""` | localStorage |
| `model` | string | 否 | trim，≤100 字符，placeholder `gpt-4` | `""` | localStorage |

- **交互**：进入页读 localStorage 回填；「保存」校验通过 → 写入 + Toast「配置已保存」；「测试连接」调 `POST /api/llm/test`（in-flight 期间按钮 `disabled` 防重复提交），失败显示非阻塞错误条「LLM API调用失败：[错误详情]」，**不阻塞其他功能**。
- **状态**：加载中 → 回填前 Skeleton；错误 → 行内校验 / 错误条；成功 → Toast；无空态。
- **响应式**：1024 时 Card 宽 `min(640px, 100%)`，字段单列。

## 5. 公共组件清单（一律复用，禁止各页自写）

| 组件 | 来源 | 用途 | 复用页面 | 关键 Props |
|---|---|---|---|---|
| `Table`/`TableRow` | shadcn | 列表、日历列表模式 | P-001/P-003 | `columns`, `data`, `onRowClick`, `sort` |
| `Card` | shadcn | 过滤栏、详情卡、设置卡 | 全部 | `className` |
| `Badge` | shadcn | 状态、类型、topic 标签 | P-001/002/003 | `variant`, `onClick?` |
| `Button` | shadcn | 搜索/重置/详情/保存 | 全部 | `variant`, `disabled`, `loading` |
| `Input` | shadcn | 关键词、日期、URL、Key | P-001/003/005 | `value`, `maxLength`, `type` |
| `Select` | shadcn | 4 类过滤器 | P-001/003/004 | `options`, `value`, `placeholder="全部"` |
| `Tabs` | shadcn | 详情概览/时间线、日历切换 | P-002/003 | `value`, `onValueChange` |
| `Tooltip` | shadcn | 图谱 hover、过滤器说明 | P-004 | `content`, `side` |
| `Skeleton` | shadcn | 全部加载态 | 全部 | `className` |
| `Toast`(sonner) | shadcn | 保存成功、非阻塞错误 | P-005/全局 | `message`, `variant` |
| `Separator`/`Switch` | shadcn | 卡片分隔、Key 显隐 | P-002/005 | — |
| `Dialog` | — | **不安装**（MVP 无确认类弹窗，技术方案 §11.5 已裁定） | — | — |
| `StatusBar` | 自定义 | F-008 状态条 | Shell | `{connected, regulation_count, total_count}` |
| `EmptyState` | 自定义 | 统一空态（图标+文案+行动按钮） | P-001/003/004 | `message`, `actionLabel`, `onAction` |
| `ErrorState` | 自定义 | 统一错误态 | 全部 | `message`, `onRetry` |
| `D3ForceGraph` | **自定义（唯一可视化定制）** | d3 力导向图 | P-004 | `nodes`, `links`, `onNodeClick`, `onNodeHover?`, `maxNodes=100`, `className?` |

- **Props 对齐说明**：v1.0 草案的 `filters` prop **已移除**（对齐技术方案 §11.4）——过滤由页面重新请求后传入新的 `nodes/links`，组件只负责渲染，避免组件内嵌过滤状态造成双向同步。
- **`Select` 数据源**：所有 4 类过滤器的 `options` 一律来自 `GET /api/filters` 的 `FilterOptions`，由 Shell 取一次后全局共用；禁止任一页面自行拼选项。v1.2 字典为 13/6/2/11（仅供验收核对）。

## 6. 交互模式与文案规范

- **筛选**：`q` 防抖 300ms 或点「搜索」→ 组装 `SearchQuery` 一次性请求；Select 变更即时触发；条件写入 URL query；「重置」清空回默认集。
- **图谱节点**：仅 `type=regulation` 可点跳详情；其余节点点击=高亮邻居；hover 出 Tooltip；键盘 Enter/Space 等价点击。
- **日历切换**：Tabs 为纯前端视图状态，切模式不重发请求；「未来 12 个月」快捷按钮写入 URL query，不改变排序、不新增数据、不改契约。**v1.2 数据面下「定位到今天」按钮已撤销**（见 §4 P-003）。
- **设置保存**：客户端校验 → localStorage → Toast；测试连接独立于保存。
- **全局错误**：`api/client.ts` 拦截非 2xx → 解析统一错误信封 `error.message` 展示；网络错误 →「服务器错误，请稍后重试」+ 控制台详细日志。

| 场景 | 文案 |
|---|---|
| 状态条正常 | `Neo4j: 🟢 已连接 \| 已加载 {regulation_count}/{total_count} 条法规`（动态，v1.2 实测 30/1174） |
| Neo4j 断连 | 状态条 `Neo4j: 🔴 未连接`，列表 Alert「无法连接到图数据库，请检查 Neo4j 服务状态」，搜索按钮禁用 |
| 搜索 0 结果 | 「未找到匹配的法规，请尝试其他关键词或过滤条件」 |
| 官方来源缺失 | 「官方来源：未提供」（record_url 仍显示） |
| 图谱节点达上限 | 「数据量较大，请使用过滤器缩小范围」（触发条件 `nodes.length >= 100`） |
| 日历空 | 「该范围内暂无里程碑事件」 |
| 空值 / 日期无法归一 | `—` |
| LLM 失败 | 「LLM API调用失败：[错误详情]」 |
| URL 非法 | 「请输入有效的URL」 |
| 保存成功 | 「配置已保存」 |
| 服务器错误 | 「服务器错误，请稍后重试」 |
| 未找到该法规 | 「未找到该法规」（404） |

## 7. 无障碍

- 全站键盘可达：Tab 顺序 = 导航 → 状态条 → 过滤控件 → 表格/画布 → 操作按钮；统一 `focus-visible` 焦点环。
- 表格行 `tabIndex=0` + `onKeyDown(Enter)` 打开详情；表头 `aria-sort`。
- 图谱节点 SVG `<g tabIndex={0} role="button" aria-label="{type}: {label}">`，Enter/Space 触发 `onNodeClick`；Tooltip 用 `aria-describedby` 关联；图例含文字（含 `source`），不依赖颜色单独表意。
- StatusBar `role="status" aria-live="polite"`；Toast `aria-live`；加载态 `aria-busy="true"`。
- 外链 `aria-label` 说明「在新标签页打开」；所有图标按钮必须有 `aria-label`。

## 8. API 数据形状（冻结契约 ⛔ 未经架构师批准不得变更字段名/类型）

> 与 `technical_solution.md` v1.1 §5.2 的 Pydantic 模型逐字段一致；`frontend/src/types/contract.ts` 为其 TS 镜像。**v1.2 附录 §7 已确认：字段名/类型/枚举/端点/查询参数零变更，本节逐字未改。**

```jsonc
// GET /api/regulations?q=&jurisdiction=&type=&legal_force=&topic=&date_from=&date_to=
// GET /api/regulations/:instrument_id
// D1 已确认：列表返回【完整】Regulation 对象数组，详情返回单个对象；同一套字段名
Regulation {
  "instrument_id":    "string",           // PK，路由参数
  "name":             "string",
  "jurisdiction":     "string",           // 可为空串 ""
  "type":             "string",           // 可为空串 ""
  "legal_force":      "string",           // 可为空串 ""；值来自 /api/filters，非固定枚举
  "legislation_date": "string|null",      // ISO YYYY-MM-DD 或 null
  "description":      "string|null",
  "record_url":       "string",           // regulations.ai 记录页
  "official_sources": [ { "url":"string", "domain":"string", "rel_type":"string" } ], // ≤3，缺失为 []
  "topics":           [ "string" ],
  "milestones":       [ { "date":"string|null", "title":"string" } ]  // 按 date 升序，null 末尾
}

// GET /api/calendar?jurisdiction=&date_from=&date_to= → CalendarEvent[]
CalendarEvent { "id":"string", "date":"string", "title":"string",
  "instrument_id":"string", "regulation_name":"string",
  "jurisdiction":"string", "source_url":"string|null" }

// GET /api/graph?jurisdiction=&topic= → GraphData
GraphData {
  "nodes": [ { "id":"string", "label":"string",
               "type":"regulation|jurisdiction|topic|source" } ],   // 仅 4 值
  "links": [ { "source":"string", "target":"string",
               "type":"IN_JURISDICTION|HAS_TOPIC|SOURCED_FROM" } ]   // 仅 3 值，字段名 type
}

// GET /api/status → AppStatus（断连时仍 HTTP 200，connected=false）
AppStatus { "connected":"boolean", "regulation_count":"number", "total_count":"number" }

// GET /api/filters → FilterOptions（架构师新增 API-002，同样冻结）
FilterOptions { "jurisdictions":["string"], "types":["string"],
                "legal_forces":["string"], "topics":["string"] }     // 4 个列表恒为数组、已排序、已去空

// 所有非 2xx 统一错误信封
ErrorEnvelope { "error": { "code":"string", "message":"string", "detail":"string|null" } }
// code ∈ VALIDATION_ERROR(400) | NOT_FOUND(404) | NEO4J_UNAVAILABLE(503) | INTERNAL_ERROR(500)

// 前端本地 localStorage（非后端接口）；亦作为 POST /api/llm/* 的平铺 body
LlmConfig { "base_url":"string", "api_key":"string", "model":"string" }
// POST /api/llm/test → LlmTestResponse { "ok":"boolean", "error":"string|null" }（恒 HTTP 200）
```

**查询参数（冻结）**：`q`, `jurisdiction`, `type`, `legal_force`, `topic`, `date_from`, `date_to`（空串 = 不过滤）。
**约束**
1. 列表/详情共用 `Regulation` 同一字段名；`official_sources`/`topics`/`milestones`/`nodes`/`links` 及 `FilterOptions` 的 4 个字典列表**恒为数组**（缺失返回 `[]`，不返回 `null`）。
2. 所有日期统一 `YYYY-MM-DD` 或 `null`；**不伪造 01-01**（仅年份归一为 `null`）；枚举大小写与 Neo4j 一致。
3. `official_sources[].domain` **由后端计算**（D2），前端永不解析 URL；`official_sources` 已由后端按 URL 去重 + 优先级 + ≤3 截断，前端不得再次截断。
4. `links[].type` 字段名冻结为 `type`，**不引入 `kind`**；`source`/`target` 恒引用 `nodes[].id`，前端须深拷贝后交给 d3。
5. **契约无 `truncated` / `*_raw` 字段，禁止新增**（R6/R9）：图谱截断用 `nodes.length >= 100` 判定；无法解析的日期用 `date:null` + 显示「—」表达。
6. **所有数量动态取自接口**，前端禁止写死 30 / 39 / 213 / 61 / 100；仅 `total_count=1174` 为后端固化常量。
7. `legal_force` 等字段值以 `/api/filters` 动态字典为准，本文不再列固定枚举。

## 9. 修订记录

### 9.1 v1.0 → v1.1（对齐技术方案，未新增需求）

| # | 位置 | v1.0 → v1.1 | 依据 |
|---|---|---|---|
| 1 | §4 P-001 字段表 + 新增禁令 | 4 个枚举改为 `GET /api/filters` 动态字典，删除占位示例；补空串 `""` 显示「—」 | 架构师 R5 / API-002 |
| 2 | §8 契约 | 新增 `FilterOptions`、`ErrorEnvelope`；补 D1/D2 决议、`links.type` 不引入 `kind`、4 值/3 值枚举、禁止新增 `truncated`/`*_raw`、数量动态化 | 技术方案 §5.2 / §9.1 / §14 |
| 3 | §4 P-004 + §2 流程4 | 图例补第 4 类 `source`（灰小圆）；截断判定改为 `nodes.length >= 100`；补 d3 深拷贝提示 | R11 / R9 / R14 |
| 4 | §4 P-002 / P-003 + §2 流程2、3 | 删除「显示原始日期文本」（契约无该字段，改为 `date:null` 显示「—」）；日历改为「先归一后过滤」 | R6 / M5 / 需求 §7.4 |
| 5 | §4 P-003 | 新增「默认视图」设计：默认全量 + 「未来 12 个月」快捷项，计数动态、不写死 213（**定稿补记已转为「已定稿」**） | R2（61 vs 213） |
| 6 | §1 / §6 文案 | 状态条 `30/1174` 改为 `{regulation_count}/{total_count}` 动态模板 | 技术方案 §3.2 |
| 7 | §4 P-002 | 补「后端已完成 URL 去重 + ≤3 截断 + domain 计算，前端直接渲染」；**验收示例改用替代 ID（v1.2 已作废，见 9.2）** | R8 / R3 / D2 |
| 8 | §5 组件清单 | `D3ForceGraph` 移除 `filters` prop；`Dialog` 标注不安装；补 `Select` 数据源约束 | §11.4 / §11.5 |
| 9（定稿补记） | §4 P-003 / §6 / 文档头 | 默认视图转「已定稿」；快捷按钮写入 URL query；新增「定位到今天」按钮（**v1.2 已撤销，见 9.2**）；版本号不升 v1.2 | 架构师 v1.1 §5.4 / §15 |

### 9.2 v1.2 数据面适配（第 10 条，契约零改动）

依据 `technical_solution_v12_addendum.md` v1.2 §0 / §6 / §7（隔离库 7688 实测）。**架构师 v1.1 §4.3 / §4.4 / §12.2 的旧共享库计数与枚举一律失效，本稿同步失效。**

| # | 位置 | 旧（v1.1，旧共享库） | 新（v1.2 隔离库） |
|---|---|---|---|
| 10a | §4 P-002 验收用例 | 图库不含 EU AI Act，改用 `RAI-AR-NA-AD2DAXX-2018` | **恢复需求 §6 原文**：`RAI-EU-NA-E2AIXXX-2024`（2024/1689）+ `eur-lex.europa.eu` 域名标签 + 来源缺失用例；替代 ID 警告作废 |
| 10b | §4 P-001 枚举与线框 | `APEC/African Union/Argentina`、3/5/3/10 字典、线框示例 APEC | **13/6/2/11**（含 EU/US/China）、线框示例改回 EU AI Act；仍禁止硬编码 |
| 10c | §4 P-003 数量口径 | 61 条、9 条脏日期、首屏落在 2018 年、R2 待拍板 | **213 条、2026-11-27→2045-12-31 全 ISO**；R2 关闭；默认全量定稿不变 |
| 10d | §4 P-003「定位到今天」 | 保留按钮（因含历史事件） | **撤销**：213 条全为未来事件，升序首屏即最近将生效义务，滚动到「今天」等于回顶部、零收益；按简洁原则移除 |
| 10e | §2 流程4 / §4 P-004 截断 | 候选 148 节点 | **候选约 184 节点**（30+13+11+130），`nodes.length >= 100` 提示必触发；需求 §6 旧口径禁止照抄 |
| 10f | 文档头 / 文末待拍板 | 对齐依据仅 `technical_solution.md` v1.1；待拍板 2 项 | 补 v1.2 附录为**数据面最权威**；**R2 / R3 / R4 全部关闭，设计侧无未决问题** |

**待拍板项：全部关闭**（v1.2 附录 §0 / §7 治理收口）——R2（真实 213 条已加载）、R3（diverse_30 含 EU AI Act / eur-lex，验收恢复需求 §6 原文）、R4（team-lead 确认 `links[].type` 保留 `type`）。契约与接口实现不受影响，可进入开发。

---

**文档状态：** v1.1 定稿 · 已适配 v1.2 数据面，交付 team-lead / 架构师 / feature-planner / 前端开发
**下游须知：** ① 复用 §5 组件清单，勿自造控件、勿硬编码枚举与计数；② 关键逻辑注释用中文写「为什么」；③ §8 为冻结契约（版本 v1.1），改动需架构师批准并两侧同步（§14）；④ 数据面事实一律以 v1.2 附录 §6 为准；⑤ 本文件已落盘 `deliverables/product_design_specification.md`。
