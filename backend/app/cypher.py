# Parameterized Cypher templates (single definition site). All $param — no string concat.
# Every Regulation query includes r.instrument_id IS NOT NULL to isolate this corpus
# from other GraphRAG :__Entity__:Regulation nodes that may share the DB.

Q_PING = "RETURN 1 AS ok"

Q_REGULATIONS = """
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
  [ (r)-[:HAS_MILESTONE]->(m:Milestone) | { date: m.date, title: m.name, notes: m.notes } ] AS milestones_raw,
  r.last_modified AS last_modified,
  r.resume AS resume,
  r.official_text_url AS official_text_url,
  r.publication_url AS publication_url
ORDER BY coalesce(r.name, '')
"""

Q_GRAPH = """
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
"""
