// Field-by-field TS mirror of schemas.py (single source of truth); contract is frozen — changes must sync both sides.

export interface OfficialSource {
  url: string
  domain: string
  rel_type: "SOURCED_FROM" | "HAS_OFFICIAL_TEXT" | "PUBLISHED_AT"
}

export interface Milestone {
  date: string | null
  title: string
  notes: string | null
}

export interface Regulation {
  instrument_id: string
  name: string
  jurisdiction: string
  type: string
  legal_force: string
  legislation_date: string | null
  description: string | null
  record_url: string
  official_sources: OfficialSource[]
  topics: string[]
  milestones: Milestone[]
  resume: string | null
  // Detailed sections from regulations.ai HTML
  plain_english?: string | null
  overview?: string | null
  definitions?: string | null
  governance_framework?: string | null
  key_focus_areas?: string | null
  implementation_framework?: string | null
  // Rich content fields
  summary?: string | null
  monitoring_evaluation?: string | null
  penalties_liability?: string | null
  relationship_to_other?: string | null
  international_alignment?: string | null
  implementation_timeline?: string | null
  requirements_must_do?: RequirementItem[]
  requirements_should_do?: RequirementItem[]
  requirements_must_not_do?: RequirementItem[]
  requirements_should_not_do?: RequirementItem[]
  obligations?: ObligationItem[]
}

export interface RequirementItem {
  requirement: string
  applies_to: string
  deadline: string
  full_text?: string
}

export interface ObligationItem {
  number?: string
  who: string
  requirement: string
  deadline?: string
  source?: string
  severity?: string
}

export interface CalendarEvent {
  id: string
  date: string
  title: string
  instrument_id: string
  regulation_name: string
  jurisdiction: string
  source_url: string | null
}

export interface GraphNode {
  id: string
  label: string
  type: "regulation" | "jurisdiction" | "topic" | "source"
}

export interface GraphLink {
  source: string
  target: string
  type: "IN_JURISDICTION" | "HAS_TOPIC" | "SOURCED_FROM"
}

export interface GraphData {
  nodes: GraphNode[]
  links: GraphLink[]
}

export interface AppStatus {
  connected: boolean
  regulation_count: number
  total_count: number
}

export interface LlmConfig {
  base_url: string
  api_key: string
  model: string
}

export interface LlmTestResponse {
  ok: boolean
  error: string | null
}

export interface FilterOptions {
  jurisdictions: string[]
  types: string[]
  legal_forces: string[]
  topics: string[]
}

export interface LlmAskRequest extends LlmConfig {
  question: string
  instrument_id?: string | null
}

export interface LlmAskResponse {
  ok: boolean
  answer: string | null
  error: string | null
}

export interface ErrorDetail {
  code: string
  message: string
  detail: string | null
}

export interface ErrorEnvelope {
  error: ErrorDetail
}

// Query params use a type alias rather than an interface: object types carry an implicit index signature,
// so they can be passed directly to qs(p: Record<string, string>).
export type RegulationQuery = {
  q: string
  jurisdiction: string
  type: string
  legal_force: string
  topic: string
  date_from: string
  date_to: string
}

export type CalendarQuery = {
  jurisdiction: string
  date_from: string
  date_to: string
}

export type GraphQuery = {
  jurisdiction: string
  topic: string
}

// Map page
export interface JurisdictionCount { jurisdiction: string; count: number; is_international: boolean }
export interface MapData { countries: JurisdictionCount[]; total_regulations: number }

// Governance page
export interface GovernanceArea { id: string; title: string; priority: "Critical" | "High" | "Medium"; roles: string[]; description: string; key_elements: string[]; regulation_count: number }
export interface GovernanceData { areas: GovernanceArea[]; total_areas: number }

// Taxonomy pages
export interface TopicItem { id: string; label: string; description: string; count: number }
export interface TypeItem { type: string; count: number; binding: boolean; description: string }
export interface StatusItem { status: string; count: number; phase: string; description: string }

// Research page
export interface ResearchItem { id: string; title: string; authors: string[]; institution: string; date: string; tags: string[]; summary: string; url: string; citations: number }

// Use-cases page
export interface Stake { title: string; description: string }
export interface UseCaseSummary { slug: string; title: string; target_audience: string[]; introduction: string }
export interface UseCaseDetail extends UseCaseSummary { stakes: Stake[]; dos: string[]; donts: string[]; regulation_ids: string[]; regulations: { instrument_id: string; name: string; type: string; jurisdiction: string }[] }

// Tracker params (type alias for qs() compatibility)
export type TrackerParams = { q?: string; jurisdiction?: string; type?: string; legal_force?: string; topic?: string; date_from?: string; date_to?: string }

// Breakdowns page
export interface ArticleBreakdown {
  article_number: string
  article_title: string
  chapter: string | null
  applies_from: string | null
  applies_to: string[]
  plain_english: string
  key_points: string[]
  action_items: string[]
  cross_jurisdiction: { jurisdiction: string; note: string }[]
}
export interface BreakdownSummary { slug: string; instrument_id: string; title: string; region: string; country: string; article_count: number }
export interface BreakdownDetail extends BreakdownSummary { articles: ArticleBreakdown[] }

// Chat endpoint (Phase B RAG)
export interface ChatRequest {
  query: string
  history?: Array<{ role: "user" | "assistant"; content: string }>
  page_context?: string
}

export interface Citation {
  instrument_id: string
  name: string
  snippet: string
  similarity: number | null
}

export interface ChatResponse {
  answer: string
  citations: Citation[]
  strategy: "vector" | "graph-first" | "hybrid"
}
