// ============================================================================
// AI-Regulation Knowledge Graph — Neo4j schema
// ----------------------------------------------------------------------------
// Layer split (per architecture decision):
//   * Neo4j  = the GRAPH (entities + relationships, traversal, GraphRAG)
//   * Postgres (later) = full-text search, structured data, and pgvector
//
// Node labels
//   Regulation      one AI-policy/legal instrument (source: regulations.ai RAI-id)
//   Jurisdiction    a country / bloc / org that issues instruments
//   InstrumentType  controlled vocabulary: Bill, Regulation, Policy, Guideline, Decree…
//   Topic           controlled vocabulary (SKOS-style) from topic_keywords
//   Source          an external official URL the instrument is sourced from / based on
//   Milestone       a dated event on the instrument's implementation timeline
//
// Relationships
//   (Regulation)-[:IN_JURISDICTION]->(Jurisdiction)
//   (Regulation)-[:OF_TYPE]->(InstrumentType)
//   (Regulation)-[:HAS_TOPIC]->(Topic)
//   (Regulation)-[:SOURCED_FROM]->(Source)        generic external references
//   (Regulation)-[:HAS_OFFICIAL_TEXT]->(Source)   isBasedOn (primary legal text)
//   (Regulation)-[:PUBLISHED_AT]->(Source)        sameAs (official publication)
//   (Regulation)-[:HAS_MILESTONE]->(Milestone)
//   (Milestone)-[:OCCURS_IN]->(Jurisdiction)      optional enrichment later
//
// Every relationship is derived from the source record; no free-form LLM
// Cypher is executed at query time (question templates only). Provenance is
// preserved on Source.url and Regulation.official_*.
// ============================================================================

// --- Uniqueness constraints / indexes (idempotent) -------------------------
CREATE CONSTRAINT regulation_id IF NOT EXISTS
  FOR (r:Regulation) REQUIRE r.instrument_id IS UNIQUE;

CREATE CONSTRAINT jurisdiction_name IF NOT EXISTS
  FOR (j:Jurisdiction) REQUIRE j.name IS UNIQUE;

CREATE CONSTRAINT instrtype_name IF NOT EXISTS
  FOR (t:InstrumentType) REQUIRE t.name IS UNIQUE;

CREATE CONSTRAINT topic_name IF NOT EXISTS
  FOR (t:Topic) REQUIRE t.name IS UNIQUE;

CREATE CONSTRAINT source_url IF NOT EXISTS
  FOR (s:Source) REQUIRE s.url IS UNIQUE;

CREATE CONSTRAINT milestone_uid IF NOT EXISTS
  FOR (m:Milestone) REQUIRE m.uid IS UNIQUE;

// --- Lookup indexes for traversal / filtering performance -------------------
CREATE INDEX regulation_name IF NOT EXISTS FOR (r:Regulation) ON (r.name);
CREATE INDEX regulation_legal_force IF NOT EXISTS FOR (r:Regulation) ON (r.legal_force);
CREATE INDEX source_domain IF NOT EXISTS FOR (s:Source) ON (s.domain);
CREATE INDEX milestone_date IF NOT EXISTS FOR (m:Milestone) ON (m.date);
