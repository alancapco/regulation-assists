# AI Regulation Corpus: Scraper, Ontology Graph and RAG — Research Findings & Plan

**Prepared for:** Alan (Capco)
**Date:** 10 November 2026 (architecture decision updated 11 November 2026)
**Scope:** `https://regulations.ai/` and `https://regulations.ai/resources`; upstream source links, regulation calendar, primary sources; **Graph = Neo4j on Docker**, **Postgres (full-text + data + vector) deferred to Phase 3+**
**Method:** direct inspection of the live site (HTML, RSC flight payload, JSON-LD, robots.txt, sitemap, MCP JSON-RPC), plus standards/stack research. All findings below were observed on 10 Nov 2026.

---

## 0. Executive verdict

**Do not build a conventional HTML scraper against regulations.ai.** It is both technically blocked and contractually prohibited. But you do not need one: the publisher exposes the *entire corpus* through machine-readable channels that are explicitly designed for AI agents. I verified and extracted them.

| Finding | Evidence |
|---|---|
| Generic crawlers are disallowed | `robots.txt`: `User-agent: * / Disallow: /`; the file notes `middleware.ts` hard-403s any UA containing "bot", "crawler" or "spider" unless allow-listed |
| Scraping is prohibited by contract | Terms of Use §9 (updated 1 Nov 2025): "You may not reproduce, republish, distribute, modify, **scrape**, or commercially exploit any material without prior written consent from Smitteck GmbH" |
| The publisher *wants* AI agents to read it | `llms.txt` ("the facts ... are public and free to read"), a public MCP server, and an **Open Knowledge Format (OKF) bulk corpus** |
| Bulk corpus is available without crawling 1,176 pages | `/okf/index.md` + 116 jurisdiction Markdown files; **1,174 instrument rows** parsed |
| Calendar is available as structured data | `/calendar` — **213 events**, full array in the RSC payload (JSON-LD is capped at 100) |
| Upstream official sources are enumerable | `/resources` — **140 unique official external URLs**, plus a `sourceUrl` on every calendar event and `official_source_url` on every instrument |
| Per-record structured metadata | Every `/regulations/<RAI-id>` page carries `schema.org/Legislation` JSON-LD |
| A sanctioned LLM path already exists | `https://regulations.ai/api/mcp/v1` — MCP over Streamable HTTP, no API key needed |

**Recommendation:** build an **ingester on the sanctioned channels**, not a scraper. Use the site as a *discovery and metadata layer*; use official government sources as the *authoritative text layer*. For anything beyond private research, obtain written consent from Smitteck GmbH first (see §10).

---

## 1. What regulations.ai actually is

- Operator: **Smitteck GmbH, Zurich, Switzerland** (footer, Terms §2, `llms.txt`). Founder visible on the homepage: Martin Smit.
- Stack: Next.js App Router (RSC / `self.__next_f` flight payload), Cloudflare, Firebase/Firestore referenced in CSP.
- Corpus claims (slightly inconsistent — see §10):

| Source | Instruments | Jurisdictions |
|---|---:|---:|
| Homepage | 1,176 ("668 in force, 399 in the pipeline") | 109 countries |
| `llms.txt` | 1,176 | 117 |
| `/okf/index.md` | 1,175 | 116 |
| MCP server description | 1,176 | "160+" |
| **This research (parsed OKF)** | **1,174 rows** | **116 profiles** |

- Other holdings: 4,683 defined terms (`/glossary`, 908 URLs in sitemap; "high-risk AI system" has 98 competing definitions), 291–297 enforcement/litigation actions (`/enforcement`), 581–289 research papers (`/research`), 71 news posts, 59 governance pages, 28 EU AI Act pages, 24 clause-level breakdowns, 26 use-case pages, 4 comparisons.
- Sitemap: **3,025 URLs**; 1,295 `/regulations/RAI-*` record pages; 111 distinct jurisdiction codes in IDs (US 302, GB 44, EU 37, CN 32, AR 30 …). Year suffixes run 2004–2026, with 279 records dated 2026.
- Controlled vocabularies are published and worth adopting directly:
  - **Statuses** (`/statuses`): Draft → Proposed → Under Review → Adopted → Awaiting Entry → In Force, plus Stalled / Withdrawn / Repealed / Superseded / In Force (Amended) / Blocked by court.
  - **Types** (`/types`): Act, Bill, Decree, Regulation (binding); Policy, Guideline, Standard (non-binding); Bill (proposal).
  - Topic keywords appear on each record's `Article` JSON-LD, e.g. `risk_management`, `governance_oversight`, `fundamental_rights`, `data_protection_privacy`, `liability_redress`, `enforcement_penalties`.

- Content gating: detail pages contain `.rai-gated` sections with `isAccessibleForFree: false`. Full analysis needs a free account. `llms.txt` says the full analysis "is served in full to crawlers and AI agents" — **do not** interpret that as permission to spoof an allow-listed UA; create a free account instead.

---

## 2. The constraint you must design around

`robots.txt` (verbatim highlights, last reviewed 2026-09-29):

```
# Policy: this is a free, public reference on AI regulation. Being cited by
# search engines and AI assistants IS the distribution model ...
User-agent: ChatGPT-User / OAI-SearchBot / GPTBot / ClaudeBot / PerplexityBot / ...
Allow: /   Disallow: /auth/
...
User-agent: *
Disallow: /
Sitemap: https://regulations.ai/sitemap.xml
```

The comment in that file states the middleware hard-403s unlisted bot-like UAs. Separately, Terms §9 prohibits scraping and redistribution without written consent.

**Therefore:**

1. No `python-requests`/Scrapy mass crawl with a generic UA, and **no UA spoofing** to impersonate Googlebot/ClaudeBot. That would be circumventing an access control and would breach the Terms.
2. Use the channels the publisher explicitly publishes for machines: `/okf/*`, `llms.txt`, `sitemap.xml`, JSON-LD, `/calendar`, and `/api/mcp/v1`.
3. Three deployment postures:
   - **A — private research prototype (lowest risk):** ingest the *facts* (identity, status, dates, official source URL), keep attribution, cite the record URL. This matches the site's own citation guidance in `llms.txt`.
   - **B — Capco client / commercial deliverable:** get **written consent** from Smitteck GmbH (via `/feedback` or the founder's LinkedIn) for bulk storage and redistribution, or licence the data. Do this before any client-facing build.
   - **C — primary-source-only (cleanest licence):** use regulations.ai only as a *seed/discovery index*, then fetch actual legal texts from government sources, which are mostly public domain / CC BY / Open Government Licence. This is the recommended route for a production compliance product.

---

## 3. Page-by-page ingestion map (what to pull, in what order)

| # | Endpoint | Volume | Format | What it gives you | Ingest method |
|---:|---|---:|---|---|---|
| 1 | `/robots.txt`, `/terms`, `/llms.txt` | 3 files | text | Policy, licence, site map, citation rules | Read once, store as governance metadata |
| 2 | `/sitemap.xml` | 3,025 URLs | XML with `lastmod` | URL discovery + **incremental refresh key** | Parse; diff `lastmod` per run |
| 3 | `/okf/index.md` | 116 jurisdictions | Markdown + YAML frontmatter | Jurisdiction list, instrument counts, trust/verification policy, `stale_after` | Parse bullet list |
| 4 | `/okf/jurisdictions/<slug>.md` | 1,174 rows | Markdown table | **Core bulk corpus**: title, RAI ID, type, status, status-checked date, official source URL; frontmatter lists all official sources for the jurisdiction | Parse table; this replaces ~1,176 page fetches |
| 5 | `/resources` | 140 unique external URLs | HTML | Curated official government/IGO source links per country | Parse `<h3>` group → `<h4>` jurisdiction → `<a>` |
| 6 | `/calendar` | **213 events** | RSC payload (primary), JSON-LD (capped) | Effective dates, deadlines, milestones, jurisdiction, instrument ID, **official source URL**, verified flag | Parse `{"events":[...]}` in `self.__next_f.push` |
| 7 | `/regulations/<RAI-id>` | 1,295 pages | `schema.org/Legislation` + `Article` + `BreadcrumbList` JSON-LD | Official name, identifier, type, jurisdiction, dates, legal force, `sameAs` / `isBasedOn` official URLs, topics, licence, `dateModified`, **Implementation Timeline milestones**, external source links | Page-by-page, rate-limited, only for records you need in depth |
| 8 | `/statuses`, `/types`, `/topics/*` | 2 + 11 pages | HTML | Controlled vocabularies for the ontology | Manual/one-off |
| 9 | `/glossary/<term>` | 908 pages | `DefinedTerm` JSON-LD | Competing definitions across laws — the highest-value graph nodes | Batch by term |
| 10 | `/enforcement/<id>` | 298 pages | `CollectionPage` JSON-LD | Regulator actions, fines, litigation, linked instruments | Phase 4 |
| 11 | `/research`, `/news`, `/breakdowns`, `/compare` | ~410 pages | HTML / JSON-LD | Secondary/analytical text for RAG chunks | Phase 4 |
| 12 | `/api/mcp/v1` | 8 tools | JSON-RPC 2.0 / Streamable HTTP | Query-time live access; `recent_changes` for change detection | Runtime integration, not bulk ingest |

**The "page by page" step is #7**, and it should be *selective*: OKF already gives you all 1,174 records' core facts. Fetch detail pages only for the subset where you need the official name, ELI/CELEX, milestones, topic tags or the full analysis. A full 1,295-page pass at 1 req/s is ~22 minutes — technically trivial, but unnecessary and less polite.

### Verified record schema (example: EU AI Act, `RAI-EU-NA-E2AIXXX-2024`)

```json
{
  "@type": "Legislation",
  "legislationIdentifier": "RAI-EU-NA-E2AIXXX-2024",
  "name": "Regulation (EU) 2024/1689 ... (Artificial Intelligence Act)",
  "legislationType": "Regulation",
  "legislationJurisdiction": "European Union",
  "legislationDate": "2024-08-01",
  "legislationLegalForce": "https://schema.org/PartiallyInForce",
  "sameAs": "https://op.europa.eu/... (official publication)",
  "isBasedOn": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689",
  "dateModified": "2026-10-21T06:25:19.027Z",
  "license": "https://regulations.ai/terms",
  "sdDatePublished": "2026-09-11"
}
```

The visible page additionally shows: `Effective: 1 Aug 2024`, `In Force (Amended)`, `Verified against eur-lex.europa.eu · 32024R1689 · 11 Sep 2026`, topic tags, and an **Implementation Timeline** table (2024-08-01, 2025-02-02, 2025-08-02, 2026-08-02, 2026-12-02, 2027-08-02, 2028-08-02). This is the pattern your `instrument.status_checked_at` + `regulatory_event` design must preserve.

---

## 4. Upstream links — "the list of links it is trying to get from"

### 4.1 The curated list on `/resources`

- **254** anchors total: **144** external link instances → **140 unique external URLs**, **110** internal links (89 of them `Regulations.AI Summary` pages).
- **109** country / jurisdiction / organisation entries across **10 groups**: International Organizations (9), North America (2), European Union (28), United Kingdom (1), Asia Pacific (19), Latin America (12), Middle East & North Africa (12), Europe non-EU (8), Africa (13), Eurasia (5).
- No pagination, no filters, no API, no CSV/JSON/RSS export. The only direct file link is the Russian national AI strategy PDF (`static.kremlin.ru`).
- 4 URLs are reused under two labels (Vietnam, Malaysia, Kenya, Egypt). One non-government source appears (Stanford HAI analysis for China).
- Sample of the domains: `un.org`, `oecd.ai`, `unesco.org`, `iso.org`, `itu.int`, `coe.int`, `digital-strategy.ec.europa.eu`, `europarl.europa.eu`, `whitehouse.gov`, `ai.gov`, `nist.gov`, `ncsl.org`, `parl.ca`, `gov.uk`, `aisi.gov.uk`, `pcpd.org.hk`, `hkma.gov.hk`, `moda.gov.tw`, `pdpc.gov.sg`, `sdaiA.gov.sa`, `kremlin.ru`, `gov.za` …
- **Complete 140-row inventory delivered as `research/data/resources_official_links.csv`** (columns: `region_group`, `jurisdiction_or_org`, `resource_label`, `official_url`, `domain`, `rai_summary_url`).

### 4.2 Where the *actual* regulation sources are (three layers)

These are more precise than `/resources`, which is a hand-curated portal list:

1. **Per instrument** (`/okf/jurisdictions/*.md` and `instruments.csv`): an `official_source_url` for nearly every one of the 1,174 instruments — e.g. `congress.gov`, `federalregister.gov`, `leginfo.legislature.ca.gov`, `legis.ga.gov`, `eur-lex.europa.eu`, `legislation.gov.uk`, `au.int`. One record (Argentina, `RAI-AR-NA-PJUAIXX-2024`) has **no source** (`—`), which is a data-quality flag.
2. **Per record JSON-LD**: `sameAs` (official publication) and `isBasedOn` (official legal text), plus all external links on the page. EU AI Act example: `CELEX:32024R1689`, the OJ text, an EP Legislative Observatory procedure link and a Commission press release.
3. **Per calendar event**: the RSC payload includes `sourceUrl` for all 213 events (e.g. `bills.parliament.uk/bills/4310`, `legislation.gov.uk/uksi/2026/425/...`, `legis.ga.gov/api/legislation/document/...`).
4. **OKF jurisdiction frontmatter**: a `sources:` block listing every official domain used for that jurisdiction (the US profile lists 25). Useful as an allowlist for your own fetcher.

### 4.3 Primary-source APIs and feeds (for the authoritative text layer)

| Jurisdiction | Source | Access | Notes |
|---|---|---|---|
| EU | **EUR-Lex / Publications Office CELLAR** | SPARQL `https://publications.europa.eu/webapi/rdf/sparql` + REST | CDM ontology, FRBR work/expression/manifestation; ELI `http://data.europa.eu/eli/reg/2024/1689/oj`; CELEX `32024R1689`. Reuse under Commission Decision 2011/833/EU; metadata CC0. Verified ELI resolves. |
| EU | Commission Digital Strategy "AI Act" page, AI Act Service Desk, Have Your Say | HTML / consultation calendar | Authoritative application timeline & consultation deadlines |
| EU | `artificialintelligenceact.eu/implementation-timeline` | HTML | Best structured article-mapped AI Act timeline (Article 111/112/113 dates) |
| US federal | **Federal Register API v1** | No-auth JSON REST | Verified live: `.../api/v1/documents.json?conditions[term]=artificial intelligence` → 1,623 hits. Public domain (17 U.S.C. 105). |
| US federal | GovInfo, eCFR, Congress.gov API, Regulations.gov v4 | Bulk/API, mostly `api.data.gov` key | Bills, CFR, dockets, public comments, rulemaking calendars |
| US states | NCSL AI Legislation Database, Open States API, LegiScan | HTML / REST (key) | The site's 300 US records are largely state bills; NCSL is the cleanest calendar-ish source |
| UK | legislation.gov.uk | Akoma Ntoso / CLML XML, RDF, Atom feeds; OGL | Bills at `bills.parliament.uk`; regulator guidance at `ico.org.uk`, `aisi.gov.uk` |
| Hong Kong, China | HKMA circulars/guidelines, PCPD, e-Legislation, SFC | HTML / PDF | Directly relevant to a Capco financial-services use case; no bulk API, so plan a targeted fetcher |
| China, mainland | CAC (`cac.gov.cn`), MIIT, TC260 | HTML / PDF, Chinese | Supplement with Stanford DigiChina translations; no official English API |
| International | OECD.AI Policy Observatory (900–1,000+ initiatives), UNESCO, ISO/IEC, ITU, NIST AI RMF, Council of Europe | Portals / PDFs / standards | Some standards are paywalled (ISO/IEC 42001) — store metadata + link, not the text |
| Litigation | CourtListener / RECAP | Public API | The site uses this for its enforcement tracker |

**Point of caution:** the official *text* is authoritative; the site's plain-English summaries are explicitly labelled "derived" and "not legal advice" (`llms.txt`: "where a summary and the linked official text disagree, the official text governs"). Your RAG must store both and rank/annotate them differently.

---

## 5. Where to get the regulation calendar

### 5.1 On regulations.ai

| Route | Detail |
|---|---|
| `/calendar` | "AI Compliance Calendar — 213 upcoming events across jurisdictions", default view "Next 12 months" shows 118; filters: date range, jurisdiction |
| **RSC flight payload** | `self.__next_f.push([1,"27:...{\"events\":[{...}]}"])` — the **complete 213 events** with `date`, `label`, `regId`, `title`, `jurisdiction`, `country`, `status`, `type`, `sourceUrl`, `verified`. **This is the one to parse.** |
| JSON-LD | `CollectionPage` → `ItemList` of `schema.org/Event`. Declares `numberOfItems: 213` but **only emits 100 `ListItem`s** — a publisher cap. Do not rely on it for completeness. |
| `.ics` export | "Download all (.ics)" is generated **client-side** as a Blob (`regulations-ai-compliance-calendar.ics`, `text/calendar`) from the same event array; there is no server-side `/api/calendar.ics` (verified 404). Per-event "+ Google Calendar" links are also present. |
| Per-record timeline | Each `/regulations/<id>` page has an "Implementation Timeline" milestone table (label, date, notes). |
| Change feed | MCP `recent_changes` returns status/date/milestone changes with previous and new values (90-day window free, 365-day with a free API key). |

**Delivered:** `research/data/calendar_events.csv` / `.jsonl` — all 213 events with official source URLs. Events run from 2026-11-27 to 2045-12-31 in the page payload; the majority are 2026–2027.

### 5.2 External authoritative calendars

- **European Commission, Digital Strategy — AI Act application timeline**: entry into force 1 Aug 2024; prohibitions + AI literacy 2 Feb 2025; GPAI/governance/penalties 2 Aug 2025; general application 2 Aug 2026; AI Omnibus moved high-risk Annex III rules to **2 Dec 2027** and Annex I product-embedded systems to **2 Aug 2028**. Note these changed in 2026 — a hard-coded calendar will go stale.
- **EU AI Act Article 113 / 111 / 112** milestone list (`artificialintelligenceact.eu/implementation-timeline`) — article-mapped dates, best source for `regulatory_event.event_kind`.
- **Federal Register / Regulations.gov** — publication dates and comment deadlines, machine-readable.
- **EU "Have Your Say"**, Commission work programme, OECD.AI / Stanford AI Index policy chapter, NCSL state legislation database — for forward-looking pipeline events.
- **CourtListener** docket termination dates — for litigation milestones.

**Design implication:** store calendar events with an `origin` field (`site_calendar` / `record_timeline` / `primary_feed`) and a `verified` flag. Reconcile duplicates across the three origins; flag conflicts rather than silently overwriting.

---

## 6. Ontology / knowledge-graph design

### 6.1 Standards to reuse (do not invent from scratch)

| Standard | Role in your model |
|---|---|
| **schema.org `Legislation`** | Already the site's record format — use as the base `instrument` schema |
| **ELI** (European Legislation Identifier) + CELEX | Stable, citable legal identifiers; FRBR work/expression/manifestation for amended and consolidated versions (CELLAR CDM) |
| **Akoma Ntoso / LegalDocML** | Clause-level structure for primary texts (`provision.ref = "Article 6(1)"`) |
| **SKOS** | Topic and terminology taxonomies; `skos:exactMatch` for cross-jurisdiction term alignment |
| **DPV** (W3C Data Privacy Vocabulary) + **AIRO** / **VAIR** | AI-Act-specific concepts: risk, roles, purposes, AI systems, FRIA, technical documentation. AIRO/VAIR are being integrated into DPV 2.1; DPV has dedicated GDPR and EU AI Act extensions |
| **PROV-O** | Provenance and verification — critical for "status verified against source X on date Y" |
| **LegalRuleML** | Deontic norms (obligation / prohibition / permission) — Phase 4, only if you want rule-level reasoning |
| **SHACL** | Validation constraints on the graph |
| **LegalRuleML / PrOnto / LKIF-core** | Reference models for legal roles and normative reasoning (research background) |

Reality check from the literature: ontology + graph methods model *structure* but not executable reasoning; turning provisions into logic still needs LLM-assisted extraction with expert review. Start with structure and provenance, not deontic logic.

### 6.2 Concrete node classes

`Jurisdiction` (country / subnational / supranational / international org / region — the site uses all five, including US states and "APEC"), `Authority` (regulator, ministry, legislature, court, standards body), `Instrument`, `Provision`, `SourceDocument`, `Obligation`, `RiskTier`, `DefinedTerm`, `Topic`, `RegulatoryEvent` / `Milestone`, `EnforcementAction`, `ResearchPaper`, `ActorRole` (provider / deployer / importer / distributor — from the EU AI Act), `ChangeEvent`.

### 6.3 Core predicates

| Predicate | From → To | Example |
|---|---|---|
| `APPLIES_IN` | Instrument → Jurisdiction | EU AI Act → European Union (and extraterritorial reach) |
| `ISSUED_BY` | Instrument → Authority | NIST AI RMF → NIST |
| `HAS_STATUS` | Instrument → Status **+ as_of + evidence** | "In Force (Amended), checked 11 Sep 2026 against eur-lex.europa.eu" |
| `AMENDS` / `SUPERSEDES` / `REPEALS` | Instrument → Instrument | Digital Omnibus on AI amends AI Act |
| `IMPLEMENTS` / `TRANSPOSES` | Instrument → Instrument | Member-state law transposes an EU Directive |
| `REFERENCES` / `CITES` | Instrument → Instrument / Standard / Paper | AI Act cites harmonised standards |
| `DEFINES` | Instrument → DefinedTerm | "high-risk AI system" (98 competing definitions) |
| `CLASSIFIES_AS` | Instrument → RiskTier / Topic | prohibited / high-risk / transparency risk |
| `IMPOSES` | Instrument → Obligation | conformity assessment, FRIA, logging |
| `APPLIES_TO_ROLE` | Obligation → ActorRole | provider vs deployer duties |
| `HAS_DEADLINE` | Instrument → RegulatoryEvent | 2 Dec 2027 high-risk obligations |
| `ENFORCED_BY` / `RESULTED_IN` | Authority → EnforcementAction ← Instrument | fine against X under Y |
| `DERIVED_FROM` | Chunk / Summary → SourceDocument | provenance for every RAG chunk |
| `SAME_AS` / `CONFLICTS_WITH` | cross-jurisdiction alignment | term or obligation comparison |

**Non-negotiable modelling rule:** a status is a *time-stamped assertion*, not a column. `llms.txt` says it plainly: "a lifecycle status without an 'as of' date is not a usable claim about a live legal instrument." Store `(status, status_checked_at, status_source_url)` together, and keep history in `ChangeEvent`.

---

## 7. Phase 2: RAG + Graph on Postgres

### 7.1 Stack decision

| Layer | Recommended | Alternatives / trade-off |
|---|---|---|
| Database | PostgreSQL 16/17 | PG 19 adds **SQL/PGQ** property-graph queries in core — promising but beta; extension lag is real |
| Vectors | **pgvector**, HNSW (`vector_cosine_ops`) | Sufficient well past 10M vectors; no separate vector DB |
| Keyword | `tsvector` + `pg_trgm` GIN | ParadeDB `pg_search` for true BM25 if recall needs it |
| Fusion | Reciprocal Rank Fusion (RRF) over vector + keyword, then a reranker | Simple, robust, no learned fusion needed |
| Graph store (now) | **Neo4j 5.26 + APOC** (Cypher, label-property graph) | Decided 11 Nov 2026 (see §0.1). Heavier than required at 1.2k instruments, but the container already exists and enables GDS-style algorithms later. SQL `edge` table kept in `schema.sql` if a single-DB deployment is later preferred. Apache AGE is therefore **not** needed |
| Cypher (query-time) | Parameterised **question templates** only | No free-form LLM Cypher (~77% correctness in production evals). Classify questions into ~20–30 templates; LLM fills parameters |
| Dedicated graph DB | Neo4j + GDS (now adopted) | Justified here by existing container + desired algorithms; true necessity threshold is ~1M entities for GDS graph algorithms |
| Full-text / data / vectors (later) | **Postgres**: `tsvector`+`pg_trgm`, structured data, `pgvector` HNSW | Deferred to Phase 3+; schema in `schema.sql` |
| Embeddings | `text-embedding-3-large` or `bge-m3`; rerank `bge-reranker-v2-m3` | `pgai` (Timescale) can generate embeddings in-DB if you want fewer moving parts |
| GraphRAG pattern | Hybrid vector + graph-neighbourhood expansion + template-based question patterns | Microsoft GraphRAG / LightRAG community summaries are expensive: LLM extraction + community summarisation is ~90% of build cost. Defer to Phase 4 |

**Honest recommendation (carried forward):** at ~1,200 instruments you are in "RAG-shaped, not graph-shaped" territory, so the graph is a *complement* to retrieval, not the primary store. We adopted Neo4j anyway (§0.1) because the container already runs and we want graph algorithms; keep the graph *small and derived* (one node per instrument, typed edges only) — **do not dump full document text into Neo4j**. Postgres still owns full-text, structured data and vectors later.

**Query reliability:** do **not** let the LLM write Cypher free-form (reported ~77% correctness in production evaluations). Classify questions into ~20–30 templates and let the LLM only fill parameters.

### 7.2 Retrieval flow for "talk to the source"

```
User question
  → parse filters (jurisdiction, date, status, role) from question + user profile
  → hybrid retrieval: pgvector ANN + tsvector keyword → RRF → reranker
  → graph expansion: 1–2 hop from hit instruments
        (amends / implements / defines / has_deadline / enforced_by)
  → temporal filter: status as-of date, effective_date <= question date
  → assemble context with three citations per chunk:
        regulations.ai record URL  |  official source URL  |  as-of date
  → LLM answer, with "derived summary vs official text" labelled
  → log to retrieval_log for evaluation
```

Every answer must be checkable. That is both good engineering and the site's explicit attribution requirement.

## 0.1 Architecture decision update — 11 November 2026

Alan confirmed the storage split:

- **The GRAPH is Neo4j on Docker.** Cypher + APOC, label-property graph.
- **Postgres is deferred** to Phase 3+ for full-text search (`tsvector`/`pg_trgm`), structured data storage, and `pgvector` embeddings. Its schema is kept in `research/poc/schema.sql` for that later phase.

This reverses the earlier "stay inside Postgres" lean **for the graph layer only** — the RAG/embedding layer was always going to be Postgres, and still is (just later). Two reasons drove the pivot: (1) a `neo4j:5.26-community` container with **APOC** already runs in this environment (`capco-graph-neo4j`, `bolt://localhost:7687`, `NEO4J_AUTH=neo4j/capco-graph-change-me`), and (2) we want real graph algorithms (community detection, impact / shortest-path) without Postgres `shared_preload_libraries` constraints. The earlier honest caveat (at ~1,200 instruments a dedicated graph DB is heavier than strictly required) still stands and is kept in §7 for the record.

What changed vs the original plan:

| Concern | Original lean (§7) | **Decided (11 Nov)** |
|---|---|---|
| Graph store | SQL `edge` table in Postgres; AGE optional | **Neo4j 5.26 + APOC** (Cypher) |
| Full-text / data / vectors | Postgres (pgvector, tsvector) | **Postgres — deferred to Phase 3+** |
| LLM-written Cypher | Forbidden (templates only) | **Forbidden — unchanged** |

Deliverables added: `research/poc/neo4j_schema.cypher`, `research/poc/neo4j_loader.py`, `docker-compose.yml`. First 30 records loaded into the running Neo4j on 11 Nov 2026 (see §7.4).

### 7.3 Two ways to "talk to the source" in an LLM — do both

1. **Now, zero build:** connect `https://regulations.ai/api/mcp/v1` to Claude Desktop / claude.ai / ChatGPT Developer mode / Cursor. Verified handshake (`initialize` → protocolVersion `2025-06-18`) and 8 tools: `search`, `fetch`, `search_regulations`, `get_regulation`, `recent_changes`, `get_glossary_term`, `list_jurisdictions`, `compare_regulations`. Free tier: 5 results/search, 90-day change window, short snippet; a **free API key** raises this to 50 results, 365 days and full summaries (`/dashboard/api-keys`). Use this to validate which questions your own system must answer better.
2. **Later, your own:** a query layer over **both** stores — Neo4j for graph/traversal questions (`compare_jurisdictions`, `trace_amendments`, impact / community queries) and Postgres (later) for full-text + vector retrieval. Expose as an MCP server with tools like `search_regulations`, `get_obligations`, `upcoming_deadlines`, `compare_jurisdictions`, `trace_amendments`. Your advantage is the ontology, temporal reasoning, primary-source text and client-specific scoping — not raw corpus size.

### 7.4 Neo4j implementation (built 11 Nov 2026)

- **Container:** `capco-graph-neo4j` (`neo4j:5.26-community`, **APOC enabled**), `bolt://localhost:7687`. Reproducible via `docker-compose.yml` (`NEO4J_AUTH=neo4j/capco-graph-change-me`).
- **Schema:** `research/poc/neo4j_schema.cypher` — uniqueness constraints on `Regulation.instrument_id`, `Jurisdiction.name`, `InstrumentType.name`, `Topic.name`, `Source.url`, `Milestone.uid`, plus lookup indexes.
- **Ontology (nodes / edges):**
  - `(Regulation)-[:IN_JURISDICTION]->(Jurisdiction)`
  - `(Regulation)-[:OF_TYPE]->(InstrumentType)`
  - `(Regulation)-[:HAS_TOPIC]->(Topic)` — SKOS-style controlled vocabulary from `topic_keywords`
  - `(Regulation)-[:SOURCED_FROM|HAS_OFFICIAL_TEXT|PUBLISHED_AT]->(Source)`
  - `(Regulation)-[:HAS_MILESTONE]->(Milestone)`
- **Loader:** `research/poc/neo4j_loader.py` reads `regulation_records.jsonl`, is idempotent, and **additive by default** (`--reset` wipes the whole graph first). It also cleans two known ingest artifacts: analytics/JS URLs (cloudflareinsights, googletagmanager) are dropped, and milestone `date` fields that captured HTML are trimmed.
- **First load (30 records):** 30 `Regulation` nodes, 3 `Jurisdiction`, 5 `InstrumentType`, 39 `Topic`, 107 `Source`, 61 `Milestone`, and 367 typed relationships (109 `SOURCED_FROM`, 77 `HAS_TOPIC`, 61 `HAS_MILESTONE`, 30 each of `IN_JURISDICTION` / `OF_TYPE` / `PUBLISHED_AT` / `HAS_OFFICIAL_TEXT`).
- **Coexistence caveat:** the running container already held a *prior* GraphRAG-style store (≈4,999 `__Entity__`, 1,137 `Chunk`, 255 `Document`, plus `Message` / `Session` / `User`). The loader is additive and uses distinct labels, so both subgraphs coexist. Decision needed: keep both, or `--reset` and rebuild clean (loses the prior store). See §10.

---

## 8. Phased plan

| Phase | Goal | Deliverables | Gate |
|---|---|---|---|
| **0 — Legal & scope** | Decide posture A/B/C; pick initial scope (recommend **EU + US + HK/UK** for a financial-services pilot) | Written consent request to Smitteck GmbH (if B); source-licence register; scope doc | **Do not ingest at scale before this gate** |
| **1 — Ingest** | Normalised corpus with provenance | `ingest.py` (done), `instruments.jsonl`, `calendar_events.jsonl`, `resources_official_links.csv`, `sitemap_index.csv`, `regulation_records.jsonl`; incremental refresh via `lastmod` + MCP `recent_changes` | Reconciliation report: OKF vs sitemap vs claimed totals |
| **2 — Ontology + graph** | Typed graph in **Neo4j** (Docker) | `neo4j_schema.cypher` + `neo4j_loader.py` (done), `docker-compose.yml`, controlled vocabularies loaded, entity resolution (ELI/CELEX/RAI ID), SHACL-style validation queries | Answer "which instruments amend the EU AI Act?" correctly |
| **3 — RAG** | Cited Q&A | `chunk` + embeddings, hybrid RRF retrieval, reranker, citation enforcement, 50–100 question eval set with gold official-source citations | ≥90% citation correctness; zero unattributed claims |
| **4 — GraphRAG** | Multi-hop + temporal reasoning | Question templates, 1–2 hop expansion, "what applies to a HK bank on 2 Dec 2027", obligation crosswalks (AI Act ↔ NIST AI RMF ↔ ISO 42001), optional community summaries | Beat Phase 3 on multi-hop / comparison questions |
| **5 — Ops** | Keep it live | Scheduled refresh, change detection, MCP bridge, freshness SLA, drift monitoring, cost dashboard, human review queue for unverified statuses | Weekly self-healing run with no manual intervention |

---

## 9. Data-quality findings you must handle

1. **Count drift:** 1,176 / 1,175 / 1,174 across homepage, `llms.txt`, OKF and our parse; jurisdictions quoted as 109 / 116 / 117 / "160+". Homepage instrument-type breakdown sums to 1,154, not 1,176. Enforcement 291 vs 297; research 581 vs 289 sitemap URLs; glossary 4,683 terms vs 908 URLs. **Treat all headline numbers as marketing; use parsed rows as truth.**
2. **Broken links:** footer link `/download-all-regulations` returns **404**. OKF index link `/okf/jurisdictions/c-te-d-ivoire.md` returns **404** (the record `RAI-CI-NA-CDNASXX-2025` does exist in the sitemap). Reconcile via sitemap, not the index alone.
3. **Missing sources:** at least one instrument has no official source URL (`—`). Never assume `official_source_url` is non-null.
4. **JSON-LD calendar cap:** `numberOfItems: 213` but only 100 `ListItem`s. Use the RSC payload.
5. **Unverified statuses:** the US OKF profile says 262 of 300 statuses were checked against an official source; 38 are unconfirmed. Propagate `status_checked_at IS NULL` into retrieval ranking.
6. **Machine-generated content:** pages state "Plain-English rewrite by Regulations.ai" with model + date (`Gemini 2.5 Flash · updated 21 Oct 2026 · reviewed 11 Sep 2026`). Label derived text in the graph.
7. **Legal volatility:** the AI Omnibus moved EU high-risk dates in 2026; a static calendar is wrong within months. Store `valid_from` / `valid_to` on events and edges.
8. **Jurisdiction ambiguity:** "European Union" vs its 27 member states; US federal vs 50 states; "Hong Kong", "Taiwan" listed alongside countries. Model `level` and `parent_id` explicitly, and keep the site's codes as-is without political reinterpretation.
9. **Entity resolution:** the same act appears as a Bill and later as an Act with different RAI IDs; "In Force (Amended)" and "Superseded" need successor links. This is the hardest part of the graph — budget for it.

---

## 10. Risks and open decisions

| Risk | Mitigation |
|---|---|
| **Terms of Use / robots violation** | No generic crawling, no UA spoofing; use sanctioned endpoints; get written consent for bulk storage/redistribution; keep attribution and record URLs |
| Primary-source licences | EUR-Lex reuse under Decision 2011/833/EU with acknowledgement; US federal works public domain but may embed third-party material; UK OGL; ISO standards are paywalled — store metadata only |
| Derived summaries treated as law | Rank official text above summaries; label `derived` vs `authoritative`; always expose source URL |
| Hallucinated legal claims | Citation enforcement, temporal filters, no free-form Cypher, eval set with gold citations |
| Graph over-engineering | Keep the Neo4j graph small/derived (one node per instrument); do not load full document text; Postgres owns text/vectors later |
| Cost of GraphRAG extraction | Run one representative indexing pass and extrapolate before committing; use small models for extraction |
| **Two graph stores in one DB** | The running Neo4j already holds a prior GraphRAG store (`__Entity__`/`Chunk`/`Document`). The new loader is additive; decide whether to `--reset` and rebuild clean (loses the prior store) or namespace/separate them |

**Decisions I need from you before Phase 1 hardens:**
1. Posture: **A** (private prototype), **B** (client deliverable + consent), or **C** (primary-source-only)?
2. Initial jurisdiction scope — EU + US + HK/UK, or all 116?
3. Do you need the **full legal text** (requires per-source fetchers, PDFs, translations), or is metadata + summaries + citations enough for v1?
4. Managed Postgres target (RDS / Cloud SQL / Supabase / Azure / self-hosted)? This decides whether AGE is even available (moot now that the graph is Neo4j; still relevant for the later Postgres full-text/vector layer).
5. Is the ontology meant to be Capco-client-facing (needs DPV/AIRO alignment and SHACL validation) or an internal research tool?
6. **Coexisting prior Neo4j store:** keep it alongside the new `Regulation` subgraph, or `--reset` the DB and load only the curated corpus?
7. **First-30 batch skew:** the initial 30 are 27 Argentina + 2 AU + 1 APEC (an artifact of inventory ordering). Re-pull a diverse 30 (EU/US/China/UK/HK…) for a better graph demo, or proceed?

---

## Appendix A — Exact endpoints verified on 10 Nov 2026

```
https://regulations.ai/robots.txt                     # generic UA disallowed
https://regulations.ai/terms                         # §9 scraping prohibition
https://regulations.ai/llms.txt                      # AI-agent site map (19.5 KB)
https://regulations.ai/sitemap.xml                   # 3,025 URLs with lastmod
https://regulations.ai/okf/index.md                  # OKF v0.2 bundle index
https://regulations.ai/okf/jurisdictions/index.md    # 116 jurisdiction profiles
https://regulations.ai/okf/jurisdictions/<slug>.md   # one file per jurisdiction
https://regulations.ai/resources                     # 140 unique official links
https://regulations.ai/calendar                      # 213 events (RSC payload)
https://regulations.ai/regulations/<RAI-id>          # Legislation JSON-LD
https://regulations.ai/statuses                      # lifecycle vocabulary
https://regulations.ai/types                         # instrument-type vocabulary
https://regulations.ai/mcp                           # MCP documentation
https://regulations.ai/api/mcp/v1                    # MCP JSON-RPC 2.0 (no auth)
https://regulations.ai/download-all-regulations      # 404 (broken footer link)
https://regulations.ai/api/calendar.ics              # 404 (ICS is client-generated)
```

MCP smoke test used:

```bash
curl -X POST https://regulations.ai/api/mcp/v1 \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

## Appendix B — Files delivered with this research

| File | Contents |
|---|---|
| `research/AI_Regulation_Corpus_Research_and_Plan.md` | This report |
| `research/data/resources_official_links.csv` | 140 upstream official source links with region, jurisdiction, label, domain, RAI summary URL |
| `research/data/calendar_events.csv` / `.jsonl` | All 213 calendar events with date, instrument ID, jurisdiction, status, type, official source URL, verified flag |
| `research/data/okf_jurisdictions.csv` | 116 jurisdiction profiles with instrument counts |
| `research/data/instruments.csv` / `.jsonl` | 1,174 normalised instruments (ID, title, jurisdiction, type, status, status-checked date, official source, record URL) |
| `research/data/sitemap_index.csv` | 3,025 URLs with section, record ID and `lastmod` for incremental refresh |
| `research/data/regulation_records.jsonl` | Page-by-page extraction (first **30** records) incl. Legislation JSON-LD, milestones and source links — loaded into Neo4j on 11 Nov 2026 |
| `research/poc/ingest.py` | Working stdlib-only ingester for the sanctioned endpoints (`--mode inventory\|records\|all`) |
| `research/poc/neo4j_schema.cypher` | Neo4j ontology: uniqueness constraints + lookup indexes for the graph |
| `research/poc/neo4j_loader.py` | Idempotent, additive loader: JSONL → Neo4j (nodes + typed edges), with ingest-artifact cleaning |
| `docker-compose.yml` | Neo4j 5.26-community + APOC, reproducible (`NEO4J_AUTH=neo4j/capco-graph-change-me`) |
| `research/poc/schema.sql` | Postgres schema (deferred to Phase 3+): pgvector + tsvector + edge-table, kept for later full-text / data / vector layer |

Reproduce:

```bash
# 1) ingest 30 records (uv project at repo root)
uv run python research/poc/ingest.py --mode records --out research/data --limit 30 --delay 0.5

# 2) start Neo4j (if not already running) — capco-graph-neo4j on 7474/7687
docker compose up -d

# 3) load the 30 records into the graph (additive by default)
uv run python research/poc/neo4j_loader.py \
    --in research/data/regulation_records.jsonl \
    --uri bolt://localhost:7687 --user neo4j --password capco-graph-change-me
```
