# Database dumps

Portable snapshots for replicating the Regulation Assistant data store on another machine.

| File | Contents | Size (approx.) |
|------|----------|----------------|
| `postgres_regulation_assistant.dump` | Postgres custom-format (`pg_dump -Fc`) | ~14 MB |
| `postgres_regulation_assistant.sql.gz` | Same DB as gzipped SQL | ~14 MB |
| `neo4j.dump` | Neo4j `neo4j` database (`neo4j-admin database dump`) | ~6 MB |

Counts at dump time: **1,174** regulations (Postgres + Neo4j).

## Prerequisites

```bash
cp .env.example .env   # set passwords if you changed defaults
docker compose -f docker-compose.app.yml --env-file .env up -d
```

Wait until `capco-app-postgres` and `capco-app-neo4j` are healthy.

## Restore Postgres

```bash
# From repo root — empty/replace the app database
docker exec -i capco-app-postgres \
  pg_restore -U capco -d regulation_assistant --clean --if-exists --no-owner --no-acl \
  < data/dumps/postgres_regulation_assistant.dump
```

Or from the SQL gzip:

```bash
gunzip -c data/dumps/postgres_regulation_assistant.sql.gz \
  | docker exec -i capco-app-postgres \
    psql -U capco -d regulation_assistant
```

## Restore Neo4j

`neo4j-admin load` needs the DB offline:

```bash
docker stop capco-app-neo4j

docker run --rm \
  -v "$(pwd)/neo4j-app/data:/data" \
  -v "$(pwd)/data/dumps:/dumps" \
  neo4j:5.26-community \
  neo4j-admin database load neo4j --from-path=/dumps --overwrite-destination=true

docker start capco-app-neo4j
```

Browser: http://localhost:7475 · Bolt: `bolt://localhost:7688` (password from `.env`).

## Re-dump (maintainers)

```bash
# Postgres
docker exec capco-app-postgres pg_dump -U capco -d regulation_assistant --no-owner --no-acl -Fc \
  > data/dumps/postgres_regulation_assistant.dump

# Neo4j
docker stop capco-app-neo4j
docker run --rm \
  -v "$(pwd)/neo4j-app/data:/data" \
  -v "$(pwd)/data/dumps:/dumps" \
  neo4j:5.26-community \
  neo4j-admin database dump neo4j --to-path=/dumps --overwrite-destination=true
docker start capco-app-neo4j
```
