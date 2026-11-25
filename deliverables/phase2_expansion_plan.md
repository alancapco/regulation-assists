# Phase 2 Feature Expansion Plan
**Capco Regulation Assistant - Feature Roadmap**

Date: 2026-11-11  
Status: Draft for Review

---

## Executive Summary

This document outlines a phased approach to add 11 new features plus a chat copilot to the Capco Regulation Assistant, based on regulations.ai's feature set.

**Current State**: MVP with 30 regulations covering:
- Regulations list with filters
- Regulation detail pages
- Calendar view (213 milestones)
- Knowledge graph (d3 force-directed)
- Settings (LLM config)

**Target State**: Full-featured regulation research platform matching regulations.ai capabilities

---

## Research Findings Summary

### Successfully Analyzed Pages

#### 1. Topics (/topics)
- **Structure**: 13 core topic categories + 10 cross-country queries
- **Core Topics**: Governance, Transparency, Risk Management, Data Protection, Security, Fairness, Human Rights, Liability, Innovation, Sector-Specific, International Alignment, Environmental, Public Sector
- **URL Pattern**: 
  - Core: `/regulations/tracker?topic=governance_oversight`
  - Queries: `/topics/ai-law-status`
- **Data Model**: Each topic has name, description, "Typically Includes" list, examples, regulation count
- **UI**: Vertical list, non-card layout, high info density

#### 2. Statuses (/statuses)
- **12 Status Types**: Draft, Proposed, Under Review, Stalled, Withdrawn, Adopted, Awaiting Entry, In Force, In Force (Amended), Repealed, Superseded, Blocked by Court
- **Lifecycle Flow**: Draft → Proposed → Under Review → Adopted → Awaiting Entry → In Force
- **Exit States**: Stalled, Withdrawn (bills), Repealed (acts), Superseded (policies)
- **URL Pattern**: `/regulations/tracker?status=In%20Force`
- **Data Model**: Status name, phase (Pre-Legislative/Legislative/Post-Legislative/Active/Final), description, examples

#### 3. Types (/types)
- **7 Legal Instrument Types**:
  - Binding: Act, Decree, Regulation
  - Non-Binding: Policy, Guideline, Standard
  - Proposal: Bill
- **URL Pattern**: `/regulations/tracker?type=Act`
- **Data Model**: Type name, bindingness, characteristics, examples, regulation count
- **UI**: Card-based layout with descriptions

#### 4. Governance (/governance)
- **12 Governance Areas**: Board Oversight, Risk Management, Documentation, Human Oversight, Transparency, Data Governance, Testing, Incident Management, Supply Chain, AI Literacy, Compliance Monitoring, Enforcement
- **Role-Based Filtering**: Board, Legal/Compliance, Engineering/DevOps, HR
- **Priority Levels**: Critical, High Priority, Medium Priority
- **URL Pattern**: `/governance/board-oversight` (detail pages per area)
- **Data Model**: Area name, priority, relevant roles, key elements (4+ per area), linked regulations

### Failed to Analyze (Concurrency Limits)
- Map (/map) - geographic visualization
- Tracker (/regulations/tracker) - enhanced list view
- Research (/research) - articles/papers
- Breakdowns (/breakdowns) - regulation summaries
- Finance use-case (/use-cases/finance) - vertical-specific view
- EU AI Act detail enhancement

---

## Implementation Phases

### Phase 2.1: Taxonomy Pages (2-3 days)
**Goal**: Add Topics, Types, Statuses as browse/filter pages

#### Backend Work
1. **Data Model**:
   ```python
   # backend/app/models.py additions
   class Topic(BaseModel):
       id: str
       name: str
       description: str
       typically_includes: List[str]
       examples: List[str]
       regulation_count: int
   
   class RegulationType(BaseModel):
       id: str
       name: str
       binding: bool
       description: str
       characteristics: List[str]
       examples: List[str]
       regulation_count: int
   
   class Status(BaseModel):
       id: str
       name: str
       phase: str  # Pre-Legislative, etc.
       description: str
       examples: List[str]
       is_final: bool
       regulation_count: int
   ```

2. **Neo4j Queries**:
   - Extract topics from existing `:HAS_TOPIC` relationships
   - Count regulations per topic/type/status
   - Compute lifecycle phase from status field

3. **API Endpoints**:
   ```
   GET /api/topics - list all topics with counts
   GET /api/types - list all types with counts
   GET /api/statuses - list all statuses with counts
   ```

4. **Update existing endpoints**:
   - `/api/regulations` already supports `?topic=`, `?type=`, `?status=` filters
   - Add regulation counts to filter options response

#### Frontend Work
1. **New Routes**:
   - `/topics` - TopicsPage.tsx
   - `/types` - TypesPage.tsx
   - `/statuses` - StatusesPage.tsx

2. **Add to Shell navigation**:
   ```tsx
   { to: "/topics", label: "Topics", icon: Tag }
   { to: "/types", label: "Types", icon: FileText }
   { to: "/statuses", label: "Statuses", icon: Activity }
   ```

3. **UI Components**:
   - TopicCard (shows topic + count, links to filtered regs)
   - TypeCard (with binding/non-binding badges)
   - StatusCard (with lifecycle phase badges)

4. **Styling**: Match Capco monochrome + uppercase micro-labels

**Effort**: 2-3 developer-days

---

### Phase 2.2: Governance Framework (3-4 days)
**Goal**: Add the 12-area governance guide with role-based filtering

#### Backend Work
1. **Static Content Model**:
   ```python
   class GovernanceArea(BaseModel):
       id: str
       name: str
       priority: str  # Critical, High, Medium
       description: str
       relevant_roles: List[str]
       key_elements: List[str]
       related_regulations: List[str]  # regulation IDs
   ```

2. **Data Source**:
   - Create `backend/app/data/governance_areas.json` with the 12 areas
   - Map each area to relevant regulations via topic/requirement keywords

3. **API Endpoints**:
   ```
   GET /api/governance - list all 12 areas with counts
   GET /api/governance/{area_id} - detail for one area
   ```

#### Frontend Work
1. **New Routes**:
   - `/governance` - GovernancePage.tsx (list of 12 areas)
   - `/governance/:area_id` - GovernanceAreaDetailPage.tsx

2. **Role Filter**:
   - Dropdown: All Roles | Board | Legal/Compliance | Engineering/DevOps | HR
   - Client-side filtering of areas by `relevant_roles`

3. **UI Components**:
   - GovernanceAreaCard (priority badge, role chips, key elements preview)
   - Detail page: full description + key elements + linked regulations

4. **Add to nav**: "Governance" link in Shell

**Effort**: 3-4 developer-days

---

### Phase 2.3: Map Visualization (4-5 days)
**Goal**: Geographic map showing regulation counts per jurisdiction

#### Research Needed
- Scrape regulations.ai/map to determine:
  - Map library (Leaflet/Mapbox/D3 geo)
  - Choropleth or markers?
  - Jurisdiction → lat/lon/geojson mapping

#### Backend Work
1. **Aggregate Query**:
   ```
   GET /api/jurisdictions/stats
   Returns: [{ name, iso_code, regulation_count, coordinates }]
   ```

2. **GeoJSON**:
   - Use Natural Earth or open dataset for country/region boundaries
   - Map jurisdiction strings to ISO codes

#### Frontend Work
1. **Dependencies**:
   - Add `react-leaflet` or `mapbox-gl` (TBD after research)
   - Add GeoJSON boundaries

2. **MapPage.tsx**:
   - Interactive map with clickable regions
   - Tooltip on hover (jurisdiction + count)
   - Click → navigate to filtered regulations list
   - Legend showing count range

3. **Responsive**:
   - Mobile: smaller map + list below
   - Desktop: full-width map

**Effort**: 4-5 developer-days (includes map library integration)

---

### Phase 2.4: Enhanced Tracker (2 days)
**Goal**: Improve regulations list with tracker-specific features

#### Research Needed
- Scrape regulations.ai/regulations/tracker to determine:
  - What columns differ from main list?
  - Sortable fields?
  - Timeline view vs table view?
  - Progress indicators?

#### Likely Additions
1. **Table Enhancements**:
   - Add "Last Updated" column
   - Add "Days Since Update" indicator
   - Status change timeline (if milestone data allows)

2. **View Toggle**:
   - Table view (current)
   - Timeline view (Gantt-style, showing lifecycle progression)

3. **Advanced Filters**:
   - Date ranges for "updated since"
   - Multi-select for topics/types/statuses

**Effort**: 2 developer-days (assuming no major data model changes)

---

### Phase 2.5: Research & Breakdowns (3-4 days)
**Goal**: Add research articles and regulation breakdowns

#### Research Page
1. **Data Model**:
   ```python
   class ResearchArticle(BaseModel):
       id: str
       title: str
       date: date
       author: Optional[str]
       summary: str
       url: str
       topics: List[str]
       related_regulations: List[str]
   ```

2. **Data Source**:
   - Start with manual JSON file (5-10 seed articles)
   - API: `GET /api/research`

3. **UI**:
   - Card-based list (date, title, summary, topics)
   - Filter by topic
   - Click → open external URL or internal view

#### Breakdowns Page
1. **Determine Structure**:
   - Scrape regulations.ai/breakdowns to understand
   - Likely: AI-generated summaries per regulation?

2. **Implementation**:
   - If summaries: add `summary` field to Regulation model
   - Generate via LLM from description + official sources
   - UI: Grid of regulation cards with summaries

**Effort**: 3-4 developer-days

---

### Phase 2.6: Use-Cases (Finance Vertical) (2 days)
**Goal**: Industry-specific views

#### Backend Work
1. **Data Model**:
   ```python
   class UseCase(BaseModel):
       id: str
       industry: str  # finance, healthcare, etc.
       name: str
       description: str
       relevant_regulations: List[str]
   ```

2. **Mapping Logic**:
   - Tag regulations with industry relevance
   - Create curated use-case pages (finance → GDPR, AI Act financial services provisions, etc.)

#### Frontend Work
1. **Routes**:
   - `/use-cases` - list of verticals
   - `/use-cases/finance` - finance-specific page

2. **UI**:
   - Hero: "AI Regulations for Finance"
   - Section 1: Key regulations
   - Section 2: Common requirements
   - Section 3: Compliance checklist

**Effort**: 2 developer-days (1 vertical as template, others can scale)

---

### Phase 2.7: Enhanced Regulation Detail (2-3 days)
**Goal**: Match regulations.ai detail page richness

#### Research Needed
- Scrape regulations.ai/regulations/RAI-EU-NA-E2AIXXX-2024 to identify:
  - Article breakdown (structured sections)
  - PDF viewer integration
  - Related regulations section
  - Impact analysis

#### Enhancements
1. **Article Breakdown**:
   - If regulation has structured articles (EU AI Act, GDPR), show TOC
   - Click article → scroll to section

2. **Related Regulations**:
   - Query Neo4j for regulations sharing topics/jurisdiction
   - Display as "Related" section

3. **PDF Viewer** (if feasible):
   - Embed official PDF if URL available
   - Use `react-pdf` or iframe

4. **Timeline Enhancement**:
   - Show lifecycle progression (Draft → In Force)
   - Visual timeline with milestones

**Effort**: 2-3 developer-days

---

### Phase 2.8: Chat Copilot (5-7 days)
**Goal**: LLM-powered Q&A assistant

#### Backend Work
1. **New Endpoint**:
   ```
   POST /api/chat
   Body: { message: str, context: List[str] }
   Returns: { response: str, sources: List[str] }
   ```

2. **RAG Pipeline**:
   - Embed regulation descriptions using OpenAI embeddings
   - Store in vector DB (add `pgvector` extension to Postgres)
   - On query: retrieve top-k relevant regulations
   - Pass to LLM with prompt: "Answer using these regulations..."

3. **LLM Integration**:
   - Reuse existing OpenAI config from Settings
   - Add streaming support (SSE or WebSocket)

#### Frontend Work
1. **Chat UI**:
   - Fixed bottom-right button (like Intercom/Zendesk)
   - Slide-in panel (400px width)
   - Message list + input box
   - Typing indicator

2. **Features**:
   - Ask questions about regulations
   - Get summaries
   - Compare regulations
   - Find relevant regulations by topic

3. **Context Awareness**:
   - If on detail page, include that regulation in context
   - If on filtered list, mention active filters

**Effort**: 5-7 developer-days (includes vector DB setup + RAG pipeline)

---

## Data Requirements

### Existing Neo4j (30 regulations)
- Regulation nodes with properties: name, jurisdiction, type, status, description, dates
- Topic relationships: `(:Regulation)-[:HAS_TOPIC]->(:Topic)`
- Jurisdiction relationships: `(:Regulation)-[:IN_JURISDICTION]->(:Jurisdiction)`
- Source relationships: `(:Regulation)-[:HAS_OFFICIAL_TEXT]->(:Source)`
- Timeline: milestones array on Regulation node

### New Data Needed

#### Phase 2.1 (Taxonomy)
- **None** - compute from existing data

#### Phase 2.2 (Governance)
- Static JSON with 12 governance areas
- Mapping: governance area → relevant topics

#### Phase 2.3 (Map)
- GeoJSON file for country boundaries
- Jurisdiction → ISO code mapping

#### Phase 2.5 (Research)
- Research articles JSON (5-10 seed)

#### Phase 2.6 (Use-Cases)
- Use-case definitions JSON
- Regulation → industry tagging

#### Phase 2.8 (Chat)
- Vector embeddings (computed from descriptions)
- Postgres `pgvector` extension

---

## Technology Additions

| Phase | New Dependencies | Rationale |
|-------|------------------|-----------|
| 2.3 | `react-leaflet` or `mapbox-gl` | Map visualization |
| 2.3 | GeoJSON dataset | Country boundaries |
| 2.7 | `react-pdf` (optional) | PDF viewer |
| 2.8 | `pgvector` Postgres extension | Vector similarity search |
| 2.8 | OpenAI embeddings API | Semantic search |

---

## Effort Estimate

| Phase | Feature | Days |
|-------|---------|------|
| 2.1 | Topics, Types, Statuses pages | 2-3 |
| 2.2 | Governance framework | 3-4 |
| 2.3 | Map visualization | 4-5 |
| 2.4 | Enhanced tracker | 2 |
| 2.5 | Research & Breakdowns | 3-4 |
| 2.6 | Use-cases (Finance) | 2 |
| 2.7 | Enhanced detail page | 2-3 |
| 2.8 | Chat copilot | 5-7 |
| **Total** | | **23-32 days** |

**Note**: This assumes:
- 1 full-time developer working sequentially
- OR 2-3 developers working in parallel on independent phases
- Current 30 regulations remain the dataset until user signals to pull full corpus

---

## Recommended Execution Order

### Sprint 1 (Week 1): Foundation
- Phase 2.1: Taxonomy pages (Topics, Types, Statuses)
- Phase 2.2: Governance framework

**Rationale**: These are browse/discovery features that don't require new data sources or complex integrations.

### Sprint 2 (Week 2): Visualization & Enhancement
- Phase 2.3: Map visualization
- Phase 2.4: Enhanced tracker
- Phase 2.7: Enhanced detail page

**Rationale**: Build on existing data, improve UX.

### Sprint 3 (Week 3): Content & Intelligence
- Phase 2.5: Research & Breakdowns
- Phase 2.6: Use-cases
- Phase 2.8: Chat copilot

**Rationale**: These require content curation and LLM integration, natural final phase.

---

## Open Questions for User

1. **Priority**: Which phase should we start with?
2. **Map**: Do you have a preference for map library (Leaflet vs Mapbox)?
3. **Chat**: Should chat persist history, or be session-only?
4. **Data Scale**: When do you want to pull the full regulations.ai corpus (1000+ regulations)?
5. **Auth**: Will this app need user accounts eventually (for saved searches, watchlists, etc.)?

---

## Next Steps

1. **User reviews this plan** and confirms phases + priority
2. **Complete missing research** (Map, Tracker, Breakdowns) via manual WebFetch or retry agents
3. **Start Phase 2.1** with detailed task cards for parallel implementation

---

**Document Version**: 1.0 Draft  
**Last Updated**: 2026-11-11 22:16
