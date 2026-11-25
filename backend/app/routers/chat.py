"""
Phase B: RAG endpoint with hybrid retrieval (vector + graph).
POST /api/chat — query router, vector search, graph traversal, context assembly, LLM generation.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from neo4j import AsyncDriver
import logging
import re

from backend.app.config import settings
from backend.app.db_postgres import get_pool
from backend.app.deps import get_driver, run
from backend.app.errors import AppError

router = APIRouter()
logger = logging.getLogger("backend.app.routers.chat")


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list)
    page_context: str | None = None


class Citation(BaseModel):
    instrument_id: str
    name: str
    snippet: str
    similarity: float | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    strategy: str  # "vector", "graph-first", "hybrid"


def route_query(question: str) -> str:
    """Classify query to determine retrieval strategy."""
    q = question.lower()

    # Multi-hop indicators → hybrid (graph + vector)
    multi_hop_keywords = [
        "related to", "affected by", "impact", "compared to", "across", "between",
        "which countries", "who must", "governance", "compliance", "difference"
    ]
    if any(kw in q for kw in multi_hop_keywords):
        return "hybrid"

    # Entity-specific → graph-first
    if any(kw in q for kw in ["eu ai act", "gdpr", "article", "regulation"]):
        return "graph-first"

    # Default: vector-only (semantic search)
    return "vector"


async def vector_search(pool, query: str, top_k: int = 10, threshold: float = 0.7) -> list[dict]:
    """
    Semantic search using pgvector cosine similarity.
    Returns list of {instrument_id, name, resume, similarity}.
    """
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        resp = client.embeddings.create(model="text-embedding-3-small", input=[query])
        query_embedding_list = resp.data[0].embedding
        query_embedding_str = "[" + ",".join(str(v) for v in query_embedding_list) + "]"
    except Exception as exc:
        logger.warning(f"Embedding generation failed: {exc}")
        return []

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT instrument_id, name, resume,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM regulations
            WHERE embedding IS NOT NULL
              AND 1 - (embedding <=> $1::vector) > $2
            ORDER BY embedding <=> $1::vector
            LIMIT $3
            """,
            query_embedding_str, threshold, top_k,
        )
    return [dict(r) for r in rows]


async def graph_traversal(driver: AsyncDriver, query: str) -> list[str]:
    """
    Extract entities from query, find seed nodes in Neo4j, expand 2-hop, return instrument_ids.
    Simplified: match jurisdiction/topic keywords, then expand.
    """
    # Simple entity extraction (keyword match)
    jurisdictions = ["australia", "brazil", "canada", "china", "european union", "eu",
                     "hong kong", "india", "japan", "singapore", "south korea", "united kingdom", "uk", "united states", "us"]
    topics = ["governance", "transparency", "risk", "data protection", "privacy",
              "cybersecurity", "fairness", "liability", "innovation", "safety",
              "artificial intelligence", "ai", "machine learning", "automation"]
    # Common regulation names/acronyms
    regulations = ["gdpr", "ccpa", "hipaa", "eu ai act", "dsa", "dma", "aia", "regulation"]

    q_lower = query.lower()
    matched_jur = [j for j in jurisdictions if j in q_lower]
    matched_topic = [t for t in topics if t in q_lower]
    matched_reg = [r for r in regulations if r in q_lower]

    if not matched_jur and not matched_topic and not matched_reg:
        return []

    # Build Cypher: match regulations connected to these entities, or by name match
    cypher = """
    MATCH (r:Regulation)
    WHERE r.instrument_id IS NOT NULL
      AND (
        EXISTS { MATCH (r)-[:IN_JURISDICTION]->(j:Jurisdiction) WHERE toLower(j.name) IN $jurisdictions }
        OR EXISTS { MATCH (r)-[:HAS_TOPIC]->(t:Topic) WHERE toLower(t.name) IN $topics }
        OR ANY(keyword IN $regulations WHERE toLower(r.name) CONTAINS keyword)
      )
    RETURN DISTINCT r.instrument_id AS instrument_id
    LIMIT 20
    """
    try:
        rows = await run(driver, cypher, jurisdictions=matched_jur, topics=matched_topic, regulations=matched_reg)
        return [r["instrument_id"] for r in rows]
    except Exception as exc:
        logger.warning(f"Graph traversal failed: {exc}")
        return []


async def fetch_content_by_ids(pool, instrument_ids: list[str]) -> list[dict]:
    """Fetch full regulation content from Postgres by instrument_ids."""
    if not instrument_ids:
        return []
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT instrument_id, name, resume, description FROM regulations WHERE instrument_id = ANY($1)",
            instrument_ids,
        )
    return [dict(r) for r in rows]


def assemble_context(vector_results: list[dict], graph_ids: list[str], content_map: dict) -> list[dict]:
    """
    Merge vector + graph results, deduplicate, rank by hybrid score.
    Returns list of {instrument_id, name, content, score}.
    """
    seen = set()
    merged = []

    # Add vector results with similarity scores
    for vr in vector_results:
        iid = vr["instrument_id"]
        if iid in seen:
            continue
        seen.add(iid)
        content = content_map.get(iid, {})
        merged.append({
            "instrument_id": iid,
            "name": vr.get("name", content.get("name", "")),
            "content": content.get("resume") or content.get("description") or "",
            "vector_score": vr.get("similarity", 0.0),
            "graph_score": 1.0 if iid in graph_ids else 0.0,
        })

    # Add graph-only results (not in vector top-k)
    for gid in graph_ids:
        if gid in seen:
            continue
        seen.add(gid)
        content = content_map.get(gid, {})
        merged.append({
            "instrument_id": gid,
            "name": content.get("name", ""),
            "content": content.get("resume") or content.get("description") or "",
            "vector_score": 0.0,
            "graph_score": 1.0,
        })

    # Hybrid ranking: graph_proximity * 0.6 + vector_similarity * 0.4
    for item in merged:
        item["hybrid_score"] = item["graph_score"] * 0.6 + item["vector_score"] * 0.4

    merged.sort(key=lambda x: x["hybrid_score"], reverse=True)
    return merged[:10]  # top 10 for LLM context


async def fetch_graph_metadata(driver: AsyncDriver, instrument_ids: list[str]) -> dict[str, dict]:
    """
    Fetch graph metadata (jurisdictions, topics, related regulations) for given instrument_ids.
    Returns dict mapping instrument_id to metadata.
    """
    if not instrument_ids:
        return {}
    
    cypher = """
    UNWIND $ids AS iid
    MATCH (r:Regulation {instrument_id: iid})
    OPTIONAL MATCH (r)-[:IN_JURISDICTION]->(j:Jurisdiction)
    OPTIONAL MATCH (r)-[:HAS_TOPIC]->(t:Topic)
    OPTIONAL MATCH (r)-[:REFERENCES]->(related:Regulation)
    WITH r, 
         collect(DISTINCT j.name) AS jurisdictions,
         collect(DISTINCT t.name) AS topics,
         collect(DISTINCT {id: related.instrument_id, name: related.name}) AS references
    RETURN r.instrument_id AS instrument_id,
           r.type AS type,
           r.legal_force AS status,
           jurisdictions,
           topics,
           references
    """
    
    try:
        rows = await run(driver, cypher, ids=instrument_ids)
        result = {}
        for row in rows:
            iid = row["instrument_id"]
            result[iid] = {
                "jurisdictions": [j for j in row["jurisdictions"] if j],
                "topics": [t for t in row["topics"] if t],
                "references": [ref for ref in row["references"] if ref.get("id")],
                "type": row.get("type", ""),
                "status": row.get("status", ""),
            }
        return result
    except Exception as exc:
        logger.warning(f"Failed to fetch graph metadata: {exc}")
        return {}


async def generate_answer(context: list[dict], query: str, page_context: str | None = None, driver: AsyncDriver | None = None) -> str:
    """Call OpenAI LLM to generate answer with citations."""
    if not context:
        return "I couldn't find relevant regulations to answer your question."

    # Fetch graph metadata if driver is provided
    graph_metadata = {}
    if driver:
        instrument_ids = [item["instrument_id"] for item in context]
        graph_metadata = await fetch_graph_metadata(driver, instrument_ids)

    # Build enriched context string with graph relationships
    context_parts = []
    for i, item in enumerate(context):
        iid = item["instrument_id"]
        meta = graph_metadata.get(iid, {})
        
        # Build structured regulation entry
        entry = f"[{i+1}] {item['name']}\n"
        entry += f"ID: {iid}\n"
        
        if meta.get("jurisdictions"):
            entry += f"Jurisdiction: {', '.join(meta['jurisdictions'])}\n"
        
        if meta.get("topics"):
            entry += f"Topics: {', '.join(meta['topics'])}\n"
        
        if meta.get("type"):
            entry += f"Type: {meta['type']}\n"
        
        if meta.get("status"):
            entry += f"Status: {meta['status']}\n"
        
        if meta.get("references"):
            ref_names = [ref.get("name", ref.get("id", "")) for ref in meta["references"][:3]]
            if ref_names:
                entry += f"Related regulations: {', '.join(ref_names)}\n"
        
        entry += f"\nSummary: {item['content'][:600]}"
        context_parts.append(entry)
    
    context_text = "\n\n" + "="*80 + "\n\n".join(context_parts)

    page_context_text = ""
    if page_context:
        page_context_text = f"\n\nPage Context:\n{page_context}\n"

    system_prompt = f"""You are an AI regulation assistant. Answer the user's question based solely on the provided regulation excerpts. Cite sources using [1], [2], etc.

When answering, consider the jurisdictions, topics, and relationships between regulations to provide comprehensive context.{page_context_text}

Regulations:
{context_text}
"""

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",  # Fixed: was "gpt-6-luna" which doesn't exist
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        return resp.choices[0].message.content
    except Exception as exc:
        logger.error(f"LLM generation failed: {exc}")
        return f"Error generating answer: {str(exc)}"


@router.post("/api/chat")
async def chat(
    request: ChatRequest,
    driver: AsyncDriver = Depends(get_driver),
) -> ChatResponse:
    """
    Hybrid RAG endpoint: route query → vector search + graph traversal → context assembly → LLM generation.
    """
    query = request.query
    strategy = route_query(query)

    pool = await get_pool()
    vector_results = []
    graph_ids = []

    # Execute retrieval based on strategy
    if strategy == "vector":
        vector_results = await vector_search(pool, query, top_k=10, threshold=0.35)  # Lower threshold for better recall
    elif strategy == "graph-first":
        graph_ids = await graph_traversal(driver, query)
        # Fallback to vector if graph returns nothing
        if not graph_ids:
            vector_results = await vector_search(pool, query, top_k=5, threshold=0.35)
    elif strategy == "hybrid":
        vector_results = await vector_search(pool, query, top_k=10, threshold=0.35)
        graph_ids = await graph_traversal(driver, query)

    # Fetch full content from Postgres
    all_ids = list(set([vr["instrument_id"] for vr in vector_results] + graph_ids))
    content_rows = await fetch_content_by_ids(pool, all_ids)
    content_map = {r["instrument_id"]: r for r in content_rows}

    # Assemble context and rank
    context = assemble_context(vector_results, graph_ids, content_map)

    # Fallback if context is empty: retry with lower threshold
    if not context:
        logger.info("Empty context, retrying with lower threshold (0.2)")
        vector_results = await vector_search(pool, query, top_k=10, threshold=0.2)
        all_ids = [vr["instrument_id"] for vr in vector_results]
        content_rows = await fetch_content_by_ids(pool, all_ids)
        content_map = {r["instrument_id"]: r for r in content_rows}
        context = assemble_context(vector_results, [], content_map)
    
    # Final fallback: return 3 most recent regulations
    if not context:
        logger.info("Still empty, fetching 3 most recent regulations as fallback")
        async with pool.acquire() as conn:
            fallback_rows = await conn.fetch(
                """
                SELECT instrument_id, name, resume, description
                FROM regulations
                WHERE resume IS NOT NULL OR description IS NOT NULL
                ORDER BY last_modified DESC NULLS LAST
                LIMIT 3
                """
            )
        for row in fallback_rows:
            context.append({
                "instrument_id": row["instrument_id"],
                "name": row["name"],
                "content": row["resume"] or row["description"] or "",
                "vector_score": 0.0,
                "graph_score": 0.0,
                "hybrid_score": 0.0,
            })

    # Generate answer with LLM (pass driver for graph metadata)
    answer = await generate_answer(context, query, request.page_context, driver)

    # Build citations
    citations = [
        Citation(
            instrument_id=item["instrument_id"],
            name=item["name"],
            snippet=item["content"][:200] + "..." if len(item["content"]) > 200 else item["content"],
            similarity=item["vector_score"] if item["vector_score"] > 0 else None,
        )
        for item in context
    ]

    return ChatResponse(answer=answer, citations=citations, strategy=strategy)
