# Capco Regulation Assistant

World Regulation Assistant — browse, search, and chat over a hybrid GraphRAG corpus of AI-related regulations (~1,174 instruments).

**Stack:** React (Vite) frontend · FastAPI backend · PostgreSQL + pgvector (content) · Neo4j (relationships)

---

## Architecture

```
┌─────────────────────┐     /api proxy      ┌─────────────────────┐
│  Frontend (Vite)    │ ──────────────────► │  Backend (FastAPI)  │
│  React + D3 + Tailwind                    │  uvicorn :8000      │
│  :5173              │                     └──────────┬──────────┘
└─────────────────────┘                                │
                          ┌────────────────────────────┼────────────────────────────┐
                          ▼                            ▼                            ▼
                 ┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
                 │ PostgreSQL 16   │        │ Neo4j 5.26      │        │ OpenAI-compat   │
                 │ + pgvector      │        │ (graph / RAG)   │        │ embeddings+LLM  │
                 │ :5433           │        │ Bolt :7688      │        │ (optional)      │
                 └─────────────────┘        └─────────────────┘        └─────────────────┘
```

| Layer | Role |
|-------|------|
| **Postgres + pgvector** | Source of truth for regulation content, milestones, sources, taxonomy aggregates, and vector embeddings for semantic chat retrieval |
| **Neo4j** | Relationship graph (jurisdiction, topics, sources) for knowledge-graph views and multi-hop GraphRAG context |
| **FastAPI** | REST API under `/api/*`; status probes Neo4j; list/detail/calendar/map/taxonomy primarily read Postgres |
| **Frontend** | Explore UI + context-aware chat copilot; LLM credentials can live in browser Settings (localStorage) |

Canonical local databases are started with **`docker-compose.app.yml`** (not the optional shared `docker-compose.yml`).

---

## Components

### Frontend (`frontend/`)

| Area | Path | Notes |
|------|------|-------|
| App shell / nav | `src/components/Shell.tsx` | Capco sidebar + page outlet + chat panel |
| Chat copilot | `src/components/ChatCopilot.tsx` | GraphRAG chat via `POST /api/chat` |
| Force graph | `src/components/D3ForceGraph.tsx` | Knowledge graph page |
| Globe map | `src/components/D3GlobeMap.tsx` | Global jurisdiction map |
| Pages | `src/pages/*` | Regulations, Tracker, Calendar, Graph, Map, Governance, Topics, Types, Lifecycle, Research, Breakdowns, Use Cases, Settings |
| API client | `src/api/client.ts` | Typed `/api` client |

### Backend (`backend/app/`)

| Module | Role |
|--------|------|
| `main.py` | FastAPI app, CORS, lifespan (Neo4j driver + Postgres pool) |
| `config.py` | Settings from `backend/.env` |
| `db_postgres.py` | asyncpg pool |
| `cypher.py` | Parameterized Neo4j queries (`Q_PING`, `Q_GRAPH`, `Q_REGULATIONS`) |
| `mapping.py` / `schemas.py` | API contract mapping |
| `routers/*` | REST endpoints (regulations, calendar, graph, map, taxonomy, chat, …) |

### Data & research (`research/`)

Ingest / enrichment scripts (CSV → Postgres, embeddings, Neo4j loaders). HTML dumps under `research/sources/` are regenerable and gitignored.

### Deliverables (`deliverables/`)

Product and architecture specs (requirements, GraphRAG replan, phase plans).

---

## Prerequisites

- **Docker** (Neo4j + Postgres)
- **Python 3.12+** and [uv](https://github.com/astral-sh/uv)
- **Node.js 20+** and npm
- Optional: OpenAI-compatible API key for embeddings / chat

---

## Install & run

### 1. Clone and configure

```bash
git clone https://github.com/alancapco/regulation-assists.git
cd regulation-assists

cp backend/.env.example backend/.env
# Edit backend/.env — set OPENAI_API_KEY if you need embeddings or server-side chat
```

### 2. One-command local stack

```bash
./start.sh
```

This will:

1. Start **Neo4j** (`capco-app-neo4j`, browser http://localhost:7475, Bolt `7688`) and **Postgres** (`capco-app-postgres`, `5433`) via `docker-compose.app.yml`
2. Sync Python deps with `uv` and run the API on http://localhost:8000
3. Start the Vite frontend on http://localhost:5173 (proxies `/api` → `:8000`)

Stop everything with:

```bash
./stop.sh
```

Proxy issues? `CLEAR_PROXY=1 ./start.sh`

### 3. Manual steps (optional)

```bash
# Databases only
docker compose -f docker-compose.app.yml up -d

# Backend
uv sync
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

### 4. Tests

```bash
uv run pytest
```

---

## Environment

App settings are loaded from **`backend/.env`** (see `backend/.env.example`).

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEO4J_URI` | `bolt://localhost:7688` | App Neo4j Bolt |
| `NEO4J_USER` / `NEO4J_PASSWORD` | `neo4j` / `capco-graph-change-me` | Neo4j auth |
| `POSTGRES_*` | host `localhost`, port `5433`, db `regulation_assistant` | Content store |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | empty / OpenAI | Embeddings + optional LLM |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Browser origins |
| `GRAPH_MAX_NODES` / `GRAPH_REG_LIMIT` | `500` / `200` | Graph API caps |

Compose passwords can be overridden with the same env vars when running `docker compose -f docker-compose.app.yml up -d`.

---

## API surface (high level)

| Method | Path | Store |
|--------|------|-------|
| GET | `/api/status` | Neo4j ping + Postgres count |
| GET | `/api/filters`, `/api/regulations`, `/api/regulations/{id}` | Postgres |
| GET | `/api/calendar` | Postgres milestones |
| GET | `/api/graph` | Neo4j |
| GET | `/api/map`, `/api/taxonomy/*`, `/api/governance`, … | Postgres (+ curated meta) |
| POST | `/api/chat` | Postgres vectors + Neo4j relationships + LLM |
| POST | `/api/llm/test` | LLM connectivity check |

---

## Docker notes

| File | Purpose |
|------|---------|
| **`docker-compose.app.yml`** | **Use this** — isolated Neo4j (`7475`/`7688`) + Postgres (`5433`) for this app |
| `docker-compose.yml` | Optional shared Neo4j only (`7474`/`7687`); not required for the assistant |

Data directories `neo4j-app/` and `neo4j/` are bind mounts and are **not** committed.

---

## Repository layout

```
regulation-assists/
├── backend/                 # FastAPI app + tests + migrations
├── frontend/                # Vite React UI
├── research/                # Ingest / scrape / embedding scripts
├── deliverables/            # Specs and plans
├── docker-compose.app.yml   # App Neo4j + Postgres
├── docker-compose.yml       # Optional shared Neo4j
├── start.sh / stop.sh
├── pyproject.toml           # Python deps (uv)
└── README.md
```

---

## Security notes

- Never commit `backend/.env` or root `.env` (gitignored).
- Rotate any keys that were previously committed to history.
- Default Neo4j/Postgres passwords are for local development only.

---

## License

Proprietary — Capco. All rights reserved unless otherwise stated.
