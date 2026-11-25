#!/usr/bin/env bash
# Start the AI Regulation Corpus stack:
#   isolated Neo4j + Postgres (docker-compose.app.yml)
#   backend (uvicorn :8000) + frontend (vite :5173)
# Usage: ./start.sh   (from repo root, or any cwd — script locates itself)
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Optional: clear proxy env that can break local Docker / npm / uv calls
if [ "${CLEAR_PROXY:-0}" = "1" ]; then
  unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY no_proxy NO_PROXY || true
fi

port_in_use() { lsof -ti tcp:"$1" >/dev/null 2>&1; }

echo "==> Starting AI Regulation Corpus stack..."

# Single env file at repo root
if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  echo "    created .env from .env.example — set OPENAI_API_KEY if you need embeddings/chat."
fi
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

# 1) App Neo4j + Postgres (idempotent). Never touches shared capco-graph-neo4j.
if command -v docker >/dev/null 2>&1; then
  docker compose -f docker-compose.app.yml --env-file .env up -d 2>&1 | tail -5
  echo "    waiting for Neo4j + Postgres to become healthy..."
  for _ in $(seq 1 45); do
    neo="$(docker inspect -f '{{.State.Health.Status}}' capco-app-neo4j 2>/dev/null || echo unknown)"
    pg="$(docker inspect -f '{{.State.Health.Status}}' capco-app-postgres 2>/dev/null || echo unknown)"
    if [ "$neo" = "healthy" ] && [ "$pg" = "healthy" ]; then
      echo "    Neo4j + Postgres healthy."
      break
    fi
    sleep 2
  done
else
  echo "    [warn] docker not found — skipping DB start; API will fail if DBs are down."
fi

mkdir -p .run

# 2) Backend FastAPI on :8000 (Vite proxies /api → localhost:8000)
if port_in_use 8000; then
  echo "    backend already running on :8000, skipping."
else
  echo "    starting backend on http://localhost:8000 ..."
  uv sync >/dev/null 2>&1
  nohup uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 > .run/backend.log 2>&1 &
  echo "    backend pid=$!"
fi

# 3) Frontend Vite on :5173
if port_in_use 5173; then
  echo "    frontend already running on :5173, skipping."
else
  echo "    starting frontend on http://localhost:5173 ..."
  if [ ! -d frontend/node_modules ]; then
    (cd frontend && npm install) || true
  fi
  (cd frontend && nohup npm run dev -- --port 5173 > ../.run/frontend.log 2>&1 &)
  echo "    frontend started."
fi

echo
echo "==> Started."
echo "    Frontend : http://localhost:5173"
echo "    Backend  : http://localhost:8000   (API via http://localhost:5173/api)"
echo "    Neo4j UI : http://localhost:7475   (Bolt :7688)"
echo "    Postgres : localhost:5433"
echo "    Logs     : .run/backend.log   .run/frontend.log"
echo "    Stop with: ./stop.sh"
