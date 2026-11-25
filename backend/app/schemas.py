from typing import Literal
from pydantic import BaseModel, Field

# ---------- 冻结契约（与 product_design_specification.md §8 一一对应）----------
class OfficialSource(BaseModel):
    url: str
    domain: str
    rel_type: Literal["SOURCED_FROM", "HAS_OFFICIAL_TEXT", "PUBLISHED_AT"]

class Milestone(BaseModel):
    date: str | None
    title: str
    notes: str | None = None

class Regulation(BaseModel):
    instrument_id: str
    name: str
    jurisdiction: str
    type: str
    legal_force: str
    legislation_date: str | None
    description: str | None
    record_url: str
    official_sources: list[OfficialSource] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    milestones: list[Milestone] = Field(default_factory=list)
    last_modified: str | None = None
    resume: str | None = None
    official_text_url: str | None = None
    publication_url: str | None = None
    # Detailed sections from regulations.ai HTML
    plain_english: str | None = None
    overview: str | None = None
    definitions: str | None = None
    governance_framework: str | None = None
    key_focus_areas: str | None = None
    implementation_framework: str | None = None
    # Rich content fields
    summary: str | None = None
    monitoring_evaluation: str | None = None
    penalties_liability: str | None = None
    relationship_to_other: str | None = None
    international_alignment: str | None = None
    implementation_timeline: str | None = None
    requirements_must_do: list[dict] = Field(default_factory=list)
    requirements_should_do: list[dict] = Field(default_factory=list)
    requirements_must_not_do: list[dict] = Field(default_factory=list)
    requirements_should_not_do: list[dict] = Field(default_factory=list)
    obligations: list[dict] = Field(default_factory=list)

class CalendarEvent(BaseModel):
    id: str
    date: str
    title: str
    instrument_id: str
    regulation_name: str
    jurisdiction: str
    source_url: str | None

class GraphNode(BaseModel):
    id: str
    label: str
    type: Literal["regulation", "jurisdiction", "topic", "source"]   # 仅 4 值

class GraphLink(BaseModel):
    source: str
    target: str
    type: Literal["IN_JURISDICTION", "HAS_TOPIC", "SOURCED_FROM"]     # 仅 3 值

class GraphData(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    links: list[GraphLink] = Field(default_factory=list)

class AppStatus(BaseModel):
    connected: bool
    regulation_count: int
    total_count: int

class LlmConfig(BaseModel):                 # 前端 localStorage 镜像；也作为 POST body
    base_url: str
    api_key: str = ""
    model: str = ""

class LlmTestResponse(BaseModel):           # 冻结：POST /api/llm/test
    ok: bool
    error: str | None

# ---------- 本方案新增（架构师定义，同样冻结）----------
class FilterOptions(BaseModel):             # GET /api/filters
    jurisdictions: list[str] = Field(default_factory=list)
    types: list[str] = Field(default_factory=list)
    legal_forces: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)

class LlmAskRequest(LlmConfig):             # POST /api/llm/ask（可选功能 A-004）
    question: str = Field(min_length=1, max_length=2000)
    instrument_id: str | None = None

class LlmAskResponse(BaseModel):
    ok: bool
    answer: str | None
    error: str | None

class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: str | None = None

class ErrorEnvelope(BaseModel):
    error: ErrorDetail

class RegulationQuery(BaseModel):           # GET /api/regulations 的 7 个冻结查询参数
    q: str = ""
    jurisdiction: str = ""
    type: str = ""
    legal_force: str = ""
    topic: str = ""
    date_from: str = ""
    date_to: str = ""

class CalendarQuery(BaseModel):             # GET /api/calendar
    jurisdiction: str = ""
    date_from: str = ""
    date_to: str = ""

class GraphQuery(BaseModel):                # GET /api/graph
    jurisdiction: str = ""
    topic: str = ""
