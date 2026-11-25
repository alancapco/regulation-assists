"""
Breakdowns router — article-by-article structural analysis of key regulations.
Content is curated/static for the 30-regulation corpus; each breakdown maps to
one regulation by instrument_id. The 7-field article template mirrors regulations.ai.
"""
from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncDriver
from pydantic import BaseModel

from backend.app.deps import get_driver, run

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ArticleBreakdown(BaseModel):
    article_number: str
    article_title: str
    chapter: str | None
    applies_from: str | None
    applies_to: list[str]
    plain_english: str
    key_points: list[str]
    action_items: list[str]
    cross_jurisdiction: list[dict]  # [{jurisdiction, note}]

class BreakdownSummary(BaseModel):
    slug: str
    instrument_id: str
    title: str
    region: str
    country: str
    article_count: int

class BreakdownDetail(BreakdownSummary):
    articles: list[ArticleBreakdown]

# ---------------------------------------------------------------------------
# Static breakdown data for key regulations in the 30-regulation corpus
# ---------------------------------------------------------------------------

_BREAKDOWNS: list[dict] = [
    {
        "slug": "eu-ai-act",
        "instrument_id": "RAI-EU-NA-E2AIXXX-2024",
        "title": "EU AI Act",
        "region": "Europe",
        "country": "European Union",
        "articles": [
            {
                "article_number": "Article 1",
                "article_title": "Subject Matter",
                "chapter": "Chapter I — General Provisions",
                "applies_from": "2024-08-01",
                "applies_to": ["All providers and deployers of AI systems in the EU market"],
                "plain_english": "The EU AI Act lays down harmonised rules for placing AI systems on the EU market. It applies to any provider—regardless of location—whose AI output is used in the EU, and to deployers established in the EU.",
                "key_points": ["Applies extraterritorially to non-EU providers", "Creates risk-based compliance tiers", "Applies to both commercial and non-commercial deployments"],
                "action_items": ["Determine whether your AI system falls within scope", "Identify your role: provider, deployer, importer, or distributor", "Map your AI systems to risk tiers"],
                "cross_jurisdiction": [{"jurisdiction": "UK AI Act (proposed)", "note": "Similar extraterritorial scope"}, {"jurisdiction": "Canada AIDA", "note": "Comparable risk-classification approach"}],
            },
            {
                "article_number": "Article 6",
                "article_title": "Classification Rules for High-Risk AI Systems",
                "chapter": "Chapter III — High-Risk AI Systems",
                "applies_from": "2026-08-02",
                "applies_to": ["Providers of AI systems listed in Annex III", "Deployers in critical infrastructure, HR, education, law enforcement, finance, essential services"],
                "plain_english": "An AI system is high-risk if it is used as a safety component in products covered by EU harmonisation law, or if it falls into one of the eight categories in Annex III — covering critical infrastructure, employment decisions, credit scoring, law enforcement, border management, administration of justice, and democratic processes.",
                "key_points": ["Credit scoring and insurance risk are explicitly high-risk (Annex III §5b)", "Mandatory conformity assessment before deployment", "High-risk systems must be registered in the EU database before market placement", "€35M or 7% global turnover penalties for prohibited AI"],
                "action_items": ["Cross-check your AI use-cases against all 8 Annex III categories", "Commission a conformity assessment from a notified body if required", "Register the system in the EU AI database before go-live", "Appoint an EU-based representative if you are a non-EU provider"],
                "cross_jurisdiction": [{"jurisdiction": "Colorado AI Act", "note": "Similar high-risk categorisation for consequential decisions"}, {"jurisdiction": "China Generative AI Measures", "note": "Separate high-risk category for AIGC"}],
            },
            {
                "article_number": "Article 9",
                "article_title": "Risk Management System",
                "chapter": "Chapter III — High-Risk AI Systems",
                "applies_from": "2026-08-02",
                "applies_to": ["Providers of high-risk AI systems"],
                "plain_english": "High-risk AI providers must establish and maintain a documented risk management system that runs throughout the entire AI system lifecycle — from design through decommissioning. The system must identify and analyse known and foreseeable risks, estimate and evaluate risks, and adopt measures to eliminate or mitigate them.",
                "key_points": ["Risk management must be continuous, not a one-off exercise", "Residual risks must be communicated to deployers", "Post-market monitoring must feed back into the risk management cycle", "Requires documented risk register and mitigation measures"],
                "action_items": ["Establish a formal AI risk register covering each high-risk system", "Define acceptable risk thresholds and document residual risks", "Integrate risk review into your model change management process", "Assign a named risk owner for each high-risk AI system"],
                "cross_jurisdiction": [{"jurisdiction": "NIST AI RMF", "note": "Voluntary US counterpart covering similar lifecycle risk management"}, {"jurisdiction": "ISO/IEC 42001", "note": "International standard for AI management systems"}],
            },
        ],
    },
    {
        "slug": "uk-online-safety-ai",
        "instrument_id": "RAI-GB-NA-PRACTIC-2024",
        "title": "UK FCA/PRA AI Good Practice",
        "region": "Europe",
        "country": "United Kingdom",
        "articles": [
            {
                "article_number": "Section 1",
                "article_title": "Governance and Accountability",
                "chapter": "Part I — Governance",
                "applies_from": "2024-01-01",
                "applies_to": ["FCA/PRA authorised firms using AI in regulated activities"],
                "plain_english": "UK financial regulators expect firms to maintain clear senior management accountability for AI, with the Senior Managers and Certification Regime (SM&CR) applying directly to AI-related decisions. The board and executive committee should have sufficient AI literacy to provide meaningful challenge.",
                "key_points": ["SM&CR accountability maps directly onto AI governance", "Board must approve AI risk appetite", "Firms should designate a senior manager accountable for AI", "Minutes and evidence of board-level AI challenge required"],
                "action_items": ["Map AI decisions to SM&CR statements of responsibilities", "Brief board on AI risk appetite at least annually", "Designate a Chief AI Officer or equivalent SMF holder", "Document board-level AI challenge in committee minutes"],
                "cross_jurisdiction": [{"jurisdiction": "EU AI Act Art. 26", "note": "Comparable deployer obligations for financial high-risk AI"}],
            },
            {
                "article_number": "Section 3",
                "article_title": "Model Risk Management",
                "chapter": "Part II — Model Risk",
                "applies_from": "2024-01-01",
                "applies_to": ["Banks, insurers, asset managers using predictive or generative AI models"],
                "plain_english": "The FCA and PRA expect AI models to be subject to the same model risk management discipline as traditional quantitative models — including independent validation, documentation, and periodic review. Firms relying on vendor models remain responsible for understanding and validating them.",
                "key_points": ["Independent model validation is expected regardless of model source", "Firms cannot outsource accountability to AI vendors", "Explainability requirements for retail credit decisions", "Stress-testing AI models under adverse conditions is expected"],
                "action_items": ["Include AI/ML models in your model inventory", "Commission independent validation of high-impact models annually", "Document model assumptions, limitations, and known failure modes", "Define explainability standards for customer-facing AI decisions"],
                "cross_jurisdiction": [{"jurisdiction": "US Fed SR 11-7", "note": "US model risk management guidance with broad AI applicability"}, {"jurisdiction": "MAS FEAT Principles", "note": "Singapore equivalent for financial AI governance"}],
            },
        ],
    },
    {
        "slug": "singapore-ai-governance",
        "instrument_id": "RAI-SG-NA-AVAGTXX-2022",
        "title": "Singapore Model AI Governance Framework",
        "region": "Asia",
        "country": "Singapore",
        "articles": [
            {
                "article_number": "Principle 1",
                "article_title": "Internal Governance Structures and Measures",
                "chapter": "Part A — Governance",
                "applies_from": "2020-01-01",
                "applies_to": ["Organisations deploying AI in Singapore, particularly in financial services"],
                "plain_english": "Organisations should designate clear senior management accountability for AI decisions. The framework recommends appointing a named AI decision-maker at board or executive level, establishing an AI ethics committee, and documenting how AI decisions align with organisational values.",
                "key_points": ["Voluntary but widely adopted by MAS-regulated firms", "Board-level sponsorship required for high-impact AI", "Ethics committee or equivalent governance body recommended", "Regular reporting to senior management on AI risks"],
                "action_items": ["Establish AI governance charter approved at board level", "Define AI risk appetite aligned with business strategy", "Create an AI ethics review panel for new use-cases", "Report AI incidents and near-misses to senior management quarterly"],
                "cross_jurisdiction": [{"jurisdiction": "EU AI Act", "note": "Broadly aligned governance requirements, with EU rules being binding"}, {"jurisdiction": "NIST AI RMF", "note": "Similar voluntary governance framework for US organisations"}],
            },
        ],
    },
]

# Build lookup indexes
_BY_SLUG = {b["slug"]: b for b in _BREAKDOWNS}
_BY_INSTRUMENT = {b["instrument_id"]: b for b in _BREAKDOWNS}

_Q_REG_NAME = """
MATCH (r:Regulation)
WHERE r.instrument_id IS NOT NULL AND r.instrument_id = $instrument_id
RETURN r.name AS name LIMIT 1
"""

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/breakdowns", response_model=list[BreakdownSummary])
async def list_breakdowns():
    return [
        BreakdownSummary(
            slug=b["slug"],
            instrument_id=b["instrument_id"],
            title=b["title"],
            region=b["region"],
            country=b["country"],
            article_count=len(b["articles"]),
        )
        for b in _BREAKDOWNS
    ]


@router.get("/breakdowns/{slug}", response_model=BreakdownDetail)
async def get_breakdown(slug: str):
    b = _BY_SLUG.get(slug)
    if not b:
        raise HTTPException(status_code=404, detail="Breakdown not found")
    return BreakdownDetail(
        slug=b["slug"],
        instrument_id=b["instrument_id"],
        title=b["title"],
        region=b["region"],
        country=b["country"],
        article_count=len(b["articles"]),
        articles=[ArticleBreakdown(**a) for a in b["articles"]],
    )
