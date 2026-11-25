# Capco Regulation Assistant — GraphRAG Architecture Replan
**Senior Product Architecture — 2026-11-11**

## Problem Statement

The current architecture stores ALL data in Neo4j — rich content, relationships, metadata, milestones, source links. This is wrong for GraphRAG:

- Neo4j is a **relationship engine**, not a document store. Storing full text, milestone notes, and source link lists in graph node properties makes the graph bloated and queries slow.
- The article.md files contain rich data (milestone notes, 5-9 source links, résumé text, last_modified) that Neo4j can't efficiently serve.
- There's no vector search layer for semantic retrieval — the chat copilot can only do keyword matching.
- The detail page is "almost empty" because Neo4j has thin data while Postgres (which doesn't exist yet) should hold the full rich content.

## Target Architecture: Hybrid GraphRAG

Based on industry best practices (Microsoft GraphRAG, Neo4j GraphRAG Python, LlamaIndex PropertyGraphIndex, ZooZ Engineering hybrid case study):

### Three-Layer Storage

```
┌─────────────────────────────────────────────────────┐
│                    Query Router                       │
│  Classifies: simple lookup → vector / multi-hop → graph│
└────────┬──────────────────┬──────────────────────────┘
         │                  │
    ┌────▼────┐      ┌─────▼──────┐
    │ Vector  │      │   Graph     │
    │ Search  │      │  Traversal  │
    │(pgvector)│     │  (Neo4j)    │
    └────┬────┘      └─────┬──────┘
         │                  │
    ┌────▼────┐      ┌─────▼──────┐
    │Postgres │      │   Neo4j     │
    │ + pgvec │      │  (relations │
    │ (content)│      │  + ontology)│
    └─────────┘      └────────────┘
```

### Layer 1: PostgreSQL (Source of Truth — Rich Content)

Postgres holds ALL document/content data. This is the primary data store:

```sql
-- Core regulation table (full rich content)
CREATE TABLE regulations (
    instrument_id    TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    jurisdiction     TEXT NOT NULL,
    type             TEXT NOT NULL,
    legal_force      TEXT,
    legislation_date TEXT,
    description      TEXT,          -- short description
    resume           TEXT,           -- longer résumé from article.md
    last_modified    TIMESTAMP,
    official_text_url TEXT,
    publication_url  TEXT,
    record_url       TEXT,
    -- Vector embedding of resume+description for semantic search
    embedding        vector(1536)
);

-- Milestones with full notes
CREATE TABLE milestones (
    id           SERIAL PRIMARY KEY,
    instrument_id TEXT REFERENCES regulations(instrument_id),
    title         TEXT NOT NULL,
    date          TEXT,
    notes         TEXT,
    sort_order    INT DEFAULT 0
);

-- Source links (all of them, not just 3)
CREATE TABLE source_links (
    id           SERIAL PRIMARY KEY,
    instrument_id TEXT REFERENCES regulations(instrument_id),
    url           TEXT NOT NULL,
    domain        TEXT,
    rel_type      TEXT,  -- SOURCED_FROM, HAS_OFFICIAL_TEXT, PUBLISHED_AT
    sort_order    INT DEFAULT 0
);

-- Research articles
CREATE TABLE research_items (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    authors     TEXT[],
    institution TEXT,
    date        DATE,
    tags        TEXT[],
    summary     TEXT,
    url         TEXT,
    citations   INT DEFAULT 0,
    embedding   vector(1536)
);

-- Chat history (session-based, not persisted in localStorage)
CREATE TABLE chat_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at  TIMESTAMP DEFAULT now()
);

CREATE TABLE chat_messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID REFERENCES chat_sessions(id),
    role        TEXT NOT NULL,  -- 'user' | 'assistant' | 'system'
    content     TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT now()
);
```

### Layer 2: Neo4j (Relationship Graph + Ontology)

Neo4j holds ONLY the relationship/ontology layer. No content text:

```cypher
// Nodes (thin — just IDs and labels)
(:Regulation {instrument_id: "RAI-EU-NA-E2AIXXX-2024", name: "EU AI Act"})
(:Jurisdiction {name: "European Union"})
(:Topic {name: "risk_management", label: "Risk Management"})
(:Source {url: "https://eur-lex...", domain: "eur-lex.europa.eu"})
(:GovernanceArea {id: "board-oversight", title: "Board Oversight & Accountability"})
(:RegulationType {name: "Regulation", binding: true})
(:Status {name: "InForce", phase: "Active"})

// Relationships (the actual graph value)
(:Regulation)-[:IN_JURISDICTION]->(:Jurisdiction)
(:Regulation)-[:HAS_TOPIC]->(:Topic)
(:Regulation)-[:SOURCED_FROM]->(:Source)
(:Regulation)-[:HAS_OFFICIAL_TEXT]->(:Source)
(:Regulation)-[:PUBLISHED_AT]->(:Source)
(:Regulation)-[:HAS_GOVERNANCE_AREA]->(:GovernanceArea)
(:Regulation)-[:HAS_TYPE]->(:RegulationType)
(:Regulation)-[:HAS_STATUS]->(:Status)
(:GovernanceArea)-[:RELEVANT_TO]->(:Topic)
```

### Layer 3: Vector Search (pgvector)

PostgreSQL `pgvector` extension provides semantic similarity search:

```sql
-- Embedding generation at ingestion time
-- Uses OpenAI text-embedding-3-small (1536 dims) or local model
-- Stored alongside content in Postgres

-- Semantic search query
SELECT instrument_id, name, resume,
       1 - (embedding <=> $query_embedding) AS similarity
FROM regulations
WHERE 1 - (embedding <=> $query_embedding) > 0.7
ORDER BY embedding <=> $query_embedding
LIMIT 10;
```

### Retrieval Pipeline (Hybrid GraphRAG)

```
User Question
    │
    ▼
┌──────────────────┐
│  Query Router     │  Classifies query complexity:
│  (rule-based)     │  - "simple": single-fact lookup → vector only
│  - keyword match  │  - "relational": multi-hop → graph + vector
│  - entity count   │  - "global": synthesis → community summaries
└───────┬──────────┘
        │
   ┌────┴────┐
   ▼         ▼
┌──▼──┐  ┌──▼──────────────┐
│Vec  │  │Graph Traversal  │
│Search│  │ 1. Extract entities from query
│top-k│  │ 2. Find seed nodes in Neo4j
│rows │  │ 3. K-hop expansion (2-3 hops)
│     │  │ 4. Collect related regulation IDs
└──┬──┘  └──────┬──────────┘
   │            │
   └─────┬──────┘
         ▼
┌──────────────────┐
│ Context Assembly  │  Merge vector + graph results
│ - Fetch full content from Postgres by instrument_id
│ - Deduplicate by instrument_id
│ - Rank by: graph_proximity * 0.6 + vector_similarity * 0.4
│ - Format as LLM context with citations
└─────────┬────────┘
          ▼
┌──────────────────┐
│  LLM Generation   │  Synthesize answer with evidence paths
│  - System prompt: "Answer using these regulations..."
│  - Include source citations
│  - Include relationship paths from graph
└──────────────────┘
```

### Query Router Logic (Rule-Based, No ML Needed)

```python
def route_query(question: str) -> str:
    """Classify query to determine retrieval strategy."""
    q = question.lower()

    # Multi-hop indicators → graph traversal + vector
    multi_hop_keywords = ["related to", "affected by", "impact", "compared to",
                          "across", "between", "which countries", "who must",
                          "governance", "compliance", "difference"]
    if any(kw in q for kw in multi_hop_keywords):
        return "hybrid"

    # Entity-specific → graph lookup + fetch from postgres
    if any(kw in q for kw in ["eu ai act", "gdpr", "article"]):
        return "graph-first"

    # Default: semantic search (vector only)
    return "vector"
```

### Data Flow

```
Ingestion (article.md → Postgres + Neo4j)
    │
    ├── Parse markdown → extract all fields
    ├── Insert/Update Postgres tables (regulations, milestones, source_links)
    ├── Generate embedding from resume + description → store in regulations.embedding
    └── Upsert Neo4j graph (thin nodes + relationships only)

Query (user question → answer)
    │
    ├── Route query (simple / hybrid / global)
    ├── Vector search: pgvector semantic similarity
    ├── Graph traversal: Neo4j entity lookup + k-hop expansion
    ├── Context assembly: fetch full content from Postgres by IDs
    └── LLM generation with cited evidence
```

## Implementation Plan

### Phase A: Postgres Setup + Data Migration (3-4 days)

1. **Set up Postgres** with pgvector extension
   - Docker container alongside Neo4j
   - Add to docker-compose.app.yml
   - Create schema (tables above)

2. **Build ingestion pipeline** (`research/ingest_to_postgres.py`)
   - Parse all 30 article.md files
   - Insert into Postgres tables
   - Generate embeddings via OpenAI API (or local model)
   - Store embeddings in pgvector

3. **Slim down Neo4j** — remove content properties from Regulation nodes
   - Keep only: instrument_id, name (for display in graph)
   - Keep all relationships (IN_JURISDICTION, HAS_TOPIC, SOURCED_FROM, etc.)
   - Add new relationships: HAS_GOVERNANCE_AREA, HAS_TYPE, HAS_STATUS

### Phase B: Backend API Rewrite (3-4 days)

1. **New Postgres connection** in backend (asyncpg)
   - `backend/app/db_postgres.py` — connection pool, query helpers
   - Keep existing Neo4j connection for graph queries

2. **Update endpoints to read from Postgres**:
   - `/api/regulations` — SELECT from Postgres (with filters)
   - `/api/regulations/{id}` — SELECT from Postgres (full detail with milestones + sources)
   - `/api/calendar` — SELECT milestones from Postgres
   - `/api/filters` — SELECT DISTINCT from Postgres
   - `/api/map` — SELECT jurisdiction + count from Postgres
   - `/api/taxonomy/*` — SELECT from Postgres
   - `/api/research` — SELECT from Postgres
   - `/api/use-cases` — keep static JSON for now

3. **Keep Neo4j for graph-only endpoints**:
   - `/api/graph` — Neo4j graph traversal (unchanged)
   - `/api/governance` — Neo4j relationship counts

4. **New RAG endpoint**:
   - `POST /api/chat` — hybrid retrieval
   - Route query → vector search (Postgres) + graph traversal (Neo4j)
   - Fetch full content from Postgres
   - Call LLM with assembled context
   - Return answer + source citations

### Phase C: Frontend Updates (2-3 days)

1. **Detail page** — will now show full rich data (résumé, milestone notes, all sources)
   because the API returns Postgres content, not thin Neo4j properties

2. **Chat copilot** — connect to new `/api/chat` endpoint
   - Show source citations in responses
   - Show relationship paths when graph traversal was used

3. **Search** — add semantic search bar
   - Uses vector similarity, not just keyword matching
   - Shows relevance scores

### Phase D: Vector Search Integration (2-3 days)

1. **Embedding generation** — at ingestion time
   - OpenAI text-embedding-3-small (1536 dims, $0.02/1M tokens)
   - Or local model (all-MiniLM-L6-v2, 384 dims, free)

2. **Semantic search UI** — search bar in header
   - Typing → debounced vector search
   - Results ranked by similarity score
   - Click → navigate to regulation detail

3. **Chat copilot RAG** — hybrid retrieval
   - Vector search for semantic relevance
   - Graph traversal for relationship context
   - Context assembly with deduplication and ranking

## Technology Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Content store | PostgreSQL 16 | Source of truth for all document content |
| Vector search | pgvector extension | Same DB, no separate vector DB needed |
| Relationship graph | Neo4j 5.26 | Ontology, relationships, graph traversal |
| Embeddings | OpenAI text-embedding-3-small | 1536 dims, cheap, high quality |
| RAG orchestration | Custom Python (async) | No LangChain/LlamaIndex overhead |
| Query routing | Rule-based | Simple, no ML model needed for 30 regs |

## docker-compose.app.yml Addition

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: capco-app-postgres
    ports:
      - "5433:5432"   # Avoid conflict if local postgres is on 5432
    environment:
      POSTGRES_USER: capco
      POSTGRES_PASSWORD: capco-regulation-change-me
      POSTGRES_DB: regulation_assistant
    volumes:
      - ./neo4j-app/pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U capco"]
      interval: 5s
      timeout: 3s
      retries: 10
    restart: unless-stopped
```

## Key Design Decisions

1. **Postgres is the content source of truth** — Neo4j never stores full text, only IDs and labels for graph display
2. **Neo4j is the relationship engine** — all ontology, taxonomy, and relationship queries go through Cypher
3. **pgvector for semantic search** — no separate vector database; Postgres handles both content and vectors
4. **Rule-based query router** — for 30 regulations, ML-based routing is overkill; simple keyword rules suffice
5. **Embeddings at ingestion time** — not at query time; one-time cost per regulation
6. **Idempotent ingestion** — MERGE in Neo4j, UPSERT in Postgres; safe to re-run

## What This Fixes

- ✅ Detail page shows full rich content (from Postgres, not thin Neo4j properties)
- ✅ Milestone notes display (stored in Postgres milestones table)
- ✅ All source links show (not truncated to 3)
- ✅ Semantic search works (pgvector)
- ✅ Chat copilot does proper RAG (vector + graph retrieval)
- ✅ Neo4j stays fast (only holds graph, not content)
- ✅ Scalable to 1000+ regulations (Postgres handles content, Neo4j handles relationships)
