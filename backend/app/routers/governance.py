from fastapi import APIRouter, Depends
from neo4j import AsyncDriver
from pydantic import BaseModel

from backend.app.deps import get_driver, run

router = APIRouter()

GOVERNANCE_AREAS = [
    {"id": "board-oversight", "title": "Board Oversight & Accountability", "priority": "Critical", "roles": ["Board", "Legal/Compliance"], "description": "Executive-level governance structures and board responsibilities for AI systems", "key_elements": ["AI Governance Committee establishment", "Board-level AI expertise requirements", "Executive accountability assignments", "Chief AI Officer roles", "Board reporting cadence"]},
    {"id": "risk-management", "title": "Risk Management Framework", "priority": "Critical", "roles": ["Board", "Legal/Compliance", "Engineering/DevOps"], "description": "Systematic identification, assessment, and mitigation of AI-related risks", "key_elements": ["Risk classification methodology", "Impact assessment procedures", "Risk registers and documentation", "Residual risk acceptance criteria", "Risk appetite statements"]},
    {"id": "documentation", "title": "Documentation & Records", "priority": "High", "roles": ["Legal/Compliance", "Engineering/DevOps"], "description": "Technical documentation, audit trails, and record-keeping requirements", "key_elements": ["Technical documentation standards", "Data provenance records", "Model cards and system specifications", "Audit trail requirements", "Retention periods"]},
    {"id": "human-oversight", "title": "Human Oversight & Ethical Safeguards", "priority": "Critical", "roles": ["Board", "Legal/Compliance", "Engineering/DevOps", "HR"], "description": "Human-in-the-loop requirements and ethical guardrails for AI systems", "key_elements": ["Human-in-the-loop protocols", "Override and intervention capabilities", "Ethical review processes", "Meaningful human control", "Appeals mechanisms"]},
    {"id": "transparency", "title": "Transparency & Disclosure Requirements", "priority": "High", "roles": ["Legal/Compliance", "Engineering/DevOps", "HR"], "description": "AI system disclosure obligations and user notification requirements", "key_elements": ["AI system disclosure statements", "User notification requirements", "Public AI registries", "Explainability standards", "Algorithmic impact assessments"]},
    {"id": "data-governance", "title": "Data Governance", "priority": "Critical", "roles": ["Engineering/DevOps", "Legal/Compliance"], "description": "Training data quality, provenance tracking, and data protection for AI", "key_elements": ["Training data quality standards", "Data provenance and lineage tracking", "Bias detection in datasets", "Data minimisation principles", "Cross-border data transfer rules"]},
    {"id": "testing-validation", "title": "Testing & Validation", "priority": "High", "roles": ["Engineering/DevOps"], "description": "Pre-deployment testing, conformity assessment, and ongoing monitoring", "key_elements": ["Pre-deployment testing protocols", "Conformity assessment procedures", "Performance benchmarking", "Red-teaming requirements", "Post-deployment monitoring"]},
    {"id": "incident-management", "title": "Incident Management", "priority": "High", "roles": ["Engineering/DevOps", "Legal/Compliance"], "description": "AI incident response, mandatory reporting, and remediation procedures", "key_elements": ["Incident classification criteria", "Detection and monitoring systems", "Response and escalation procedures", "72-hour reporting requirements", "Remediation tracking"]},
    {"id": "supply-chain", "title": "AI Supply Chain Governance", "priority": "Critical", "roles": ["Legal/Compliance", "Engineering/DevOps"], "description": "Third-party AI vendor management, Shadow AI controls, and procurement", "key_elements": ["AI vendor due diligence", "Shadow AI detection and control", "Contractual AI requirements", "Open-source model risk", "AI procurement standards"]},
    {"id": "ai-literacy", "title": "AI Literacy & Culture", "priority": "High", "roles": ["HR", "Board"], "description": "Staff AI training, organisational competency, and cultural awareness", "key_elements": ["AI literacy training programs", "Role-specific competency requirements", "AI champions and designated experts", "Cultural change management", "EU AI Act Article 4 obligations"]},
    {"id": "compliance-monitoring", "title": "Compliance Monitoring", "priority": "High", "roles": ["Legal/Compliance", "Board"], "description": "Internal audits, external assessments, and continuous compliance assurance", "key_elements": ["Internal audit programs", "External assessment coordination", "Compliance dashboards and metrics", "Regulatory change monitoring", "Certification management"]},
    {"id": "enforcement-penalties", "title": "Enforcement & Penalties", "priority": "Medium", "roles": ["Legal/Compliance", "Board"], "description": "Understanding enforcement trends, penalty structures, and legal exposure", "key_elements": ["Penalty structure understanding", "Enforcement trend analysis", "Regulatory interaction protocols", "Appeal rights and procedures", "Indemnification strategies"]},
]

# Area id → topic names used for regulation count lookup
_AREA_TOPICS: dict[str, list[str]] = {
    "board-oversight":       ["governance_oversight"],
    "risk-management":       ["risk_management"],
    "documentation":         ["accountability_documentation"],
    "human-oversight":       ["human_rights_ethics"],
    "transparency":          ["transparency_disclosure"],
    "data-governance":       ["data_protection_privacy"],
    "testing-validation":    ["risk_management", "safety_testing"],
    "incident-management":   ["enforcement_penalties"],
    "supply-chain":          ["risk_management"],
    "ai-literacy":           ["governance_oversight"],
    "compliance-monitoring": ["governance_oversight", "enforcement_penalties"],
    "enforcement-penalties": ["enforcement_penalties", "liability_redress"],
}

_Q_TOPIC_COUNT = """
MATCH (r:Regulation)-[:HAS_TOPIC]->(t:Topic)
WHERE r.instrument_id IS NOT NULL AND t.name IN $topics
RETURN count(DISTINCT r) AS count
"""


class GovernanceArea(BaseModel):
    id: str
    title: str
    priority: str
    roles: list[str]
    description: str
    key_elements: list[str]
    regulation_count: int


class GovernanceData(BaseModel):
    areas: list[GovernanceArea]
    total_areas: int


@router.get("/governance")
async def get_governance(driver: AsyncDriver = Depends(get_driver)) -> GovernanceData:
    areas: list[GovernanceArea] = []
    for area in GOVERNANCE_AREAS:
        topics = _AREA_TOPICS.get(area["id"], [])
        rows = await run(driver, _Q_TOPIC_COUNT, topics=topics)
        count = rows[0]["count"] if rows else 0
        areas.append(GovernanceArea(**{k: area[k] for k in area}, regulation_count=count))
    return GovernanceData(areas=areas, total_areas=len(areas))
