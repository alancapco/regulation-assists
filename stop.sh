#!/usr/bin/env bash
# 停止 AI Regulation Corpus 全栈：前端(vite :5173) + 后端(uvicorn :8000) + 隔离 Neo4j(capco-app-neo4j)
# 用法：./stop.sh   （在仓库根目录执行，或任意目录均可，脚本会定位自身）
# 重要：只动本项目专属容器 capco-app-neo4j，绝不碰共享库 capco-graph-neo4j。
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> Stopping AI Regulation Corpus stack..."

# 1) 前端 Vite dev（占 :5173）
if lsof -ti tcp:5173 >/dev/null 2>&1; then
  echo "    stopping frontend (vite :5173)..."
  lsof -ti tcp:5173 | xargs -r kill 2>/dev/null
  # 等最多 10 秒确认端口释放
  for _ in $(seq 1 10); do
    lsof -ti tcp:5173 >/dev/null 2>&1 || break
    sleep 1
  done
  if lsof -ti tcp:5173 >/dev/null 2>&1; then
    echo "    [warn] frontend still up after SIGTERM, sending SIGKILL..."
    lsof -ti tcp:5173 | xargs -r kill -9 2>/dev/null
  fi
  echo "    frontend stopped."
else
  echo "    frontend not running on :5173, skipping."
fi

# 2) 后端 FastAPI（uvicorn 占 :8000）
if lsof -ti tcp:8000 >/dev/null 2>&1; then
  echo "    stopping backend (uvicorn :8000)..."
  lsof -ti tcp:8000 | xargs -r kill 2>/dev/null
  for _ in $(seq 1 10); do
    lsof -ti tcp:8000 >/dev/null 2>&1 || break
    sleep 1
  done
  if lsof -ti tcp:8000 >/dev/null 2>&1; then
    echo "    [warn] backend still up after SIGTERM, sending SIGKILL..."
    lsof -ti tcp:8000 | xargs -r kill -9 2>/dev/null
  fi
  echo "    backend stopped."
else
  echo "    backend not running on :8000, skipping."
fi

# 3) 隔离 Neo4j（只停 capco-app-neo4j，绝不碰共享库 capco-graph-neo4j）
if command -v docker >/dev/null 2>&1; then
  if docker ps -a --format '{{.Names}}' | grep -qx capco-app-neo4j; then
    echo "    stopping isolated Neo4j (capco-app-neo4j)..."
    docker compose -f docker-compose.app.yml down 2>&1 | tail -3
    echo "    isolated Neo4j stopped (data preserved in ./neo4j-app)."
  else
    echo "    isolated Neo4j container not present, skipping."
  fi
else
  echo "    [warn] docker not found — skipping Neo4j stop."
fi

# 4) 仅作提示：共享库容器状态（如存在），明确声明未触碰
if command -v docker >/dev/null 2>&1; then
  if docker ps -a --format '{{.Names}}' | grep -qx capco-graph-neo4j; then
    st="$(docker inspect -f '{{.State.Status}}' capco-graph-neo4j 2>/dev/null || echo unknown)"
    echo "    [info] shared Neo4j capco-graph-neo4j left untouched (status=$st)."
  fi
fi

echo
echo "==> Stopped. Use ./start.sh to bring the stack back up."
