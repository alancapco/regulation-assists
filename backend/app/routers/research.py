from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()

RESEARCH_ITEMS = [
    {"id": "1", "title": "Harmonizing AI Safety Thresholds Across Jurisdictions", "authors": ["Centre for the Governance of AI"], "institution": "Centre for the Governance of AI", "date": "2026-07-15", "tags": ["Governance", "Safety & Testing", "Standards"], "summary": "Examines whether global convergence on AI capability thresholds is feasible, analysing the EU AI Act, UK AISI frameworks, and US EO approaches.", "url": "https://governance.ai", "citations": 0},
    {"id": "2", "title": "Post-Deployment Accountability Gaps in the EU AI Act", "authors": ["Ada Lovelace Institute"], "institution": "Ada Lovelace Institute", "date": "2026-06-10", "tags": ["EU AI Act", "Accountability", "Governance"], "summary": "Analysis showing 77.1% of AI incidents in financial services lack demonstrable EU AI Act compliance evidence, pointing to systemic post-deployment monitoring gaps.", "url": "https://www.adalovelaceinstitute.org", "citations": 3},
    {"id": "3", "title": "Hardware-Level Governance of AI Compute", "authors": ["Brundage, M.", "Hadfield-Menell, D."], "institution": "arXiv", "date": "2026-05-22", "tags": ["Compute", "Governance", "Frontier Risk"], "summary": "Proposes technical mechanisms for governing AI through hardware controls, including chip-level reporting and export control frameworks.", "url": "https://arxiv.org", "citations": 12},
    {"id": "4", "title": "AI Index 2026 Annual Report", "authors": ["Stanford HAI"], "institution": "Stanford University HAI", "date": "2026-04-01", "tags": ["Governance", "Risk Management", "Standards"], "summary": "Comprehensive annual measurement of AI progress, adoption, and governance developments across 50+ countries, with dedicated financial services chapter.", "url": "https://hai.stanford.edu/ai-index", "citations": 45},
    {"id": "5", "title": "Improving Frontier AI Incident Reporting Regimes", "authors": ["UK AI Safety Institute"], "institution": "UK Government DSIT", "date": "2026-03-18", "tags": ["Incidents", "Safety & Testing", "Governance"], "summary": "Proposes a standardised incident taxonomy and mandatory reporting framework aligned with the EU AI Act and UK AI regulatory roadmap.", "url": "https://www.gov.uk/government/organisations/ai-safety-institute", "citations": 8},
    {"id": "6", "title": "Tort Law at the Frontier of AI", "authors": ["Oxford Internet Institute"], "institution": "University of Oxford", "date": "2026-02-28", "tags": ["Governance", "Accountability", "Risk Management"], "summary": "Examines how existing tort doctrine applies to AI harms and what regulatory gaps remain unaddressed by current liability frameworks in the EU and US.", "url": "https://www.oii.ox.ac.uk", "citations": 6},
    {"id": "7", "title": "Delays to Frontier AI in EU and UK", "authors": ["Future of Life Institute"], "institution": "Future of Life Institute", "date": "2026-01-15", "tags": ["EU AI Act", "Frontier Risk", "Governance"], "summary": "Empirical study measuring actual delays in frontier AI model releases in the EU and UK attributable to compliance preparation under new regulatory frameworks.", "url": "https://futureoflife.org", "citations": 19},
    {"id": "8", "title": "Loss of Oversight: Erosion of AI Monitoring Mechanisms", "authors": ["Centre for Human-Compatible AI"], "institution": "UC Berkeley CHAI", "date": "2025-11-30", "tags": ["Human Oversight", "Governance", "Agents"], "summary": "Documents how existing human oversight mechanisms are being eroded by AI capability improvements, with policy recommendations for maintaining meaningful control.", "url": "https://humancompatible.ai", "citations": 31},
]


class ResearchItem(BaseModel):
    id: str
    title: str
    authors: list[str]
    institution: str
    date: str
    tags: list[str]
    summary: str
    url: str
    citations: int


@router.get("/research")
async def get_research(tag: str = Query(default="")) -> list[ResearchItem]:
    if not tag:
        return [ResearchItem(**item) for item in RESEARCH_ITEMS]
    tag_lower = tag.lower()
    return [ResearchItem(**item) for item in RESEARCH_ITEMS
            if any(tag_lower in t.lower() for t in item["tags"])]
