from fastapi import APIRouter, Depends
from neo4j import AsyncDriver
from pydantic import BaseModel

from backend.app.deps import get_driver, run
from backend.app.errors import AppError

router = APIRouter()

_Q_REG_BY_ID = """
MATCH (r:Regulation)
WHERE r.instrument_id IS NOT NULL AND r.instrument_id = $instrument_id
RETURN
  r.instrument_id AS instrument_id,
  r.name AS name,
  coalesce(r.legislation_type, '') AS type,
  coalesce(head([(r)-[:IN_JURISDICTION]->(j:Jurisdiction) | j.name ]), '') AS jurisdiction
LIMIT 1
"""


class Stake(BaseModel):
    title: str
    description: str


class UseCase(BaseModel):
    slug: str
    title: str
    target_audience: list[str]
    introduction: str
    stakes: list[Stake]
    dos: list[str]
    donts: list[str]
    regulation_ids: list[str]


class UseCaseDetail(UseCase):
    regulations: list[dict]


_USE_CASES: dict[str, dict] = {
    "finance": {
        "slug": "finance",
        "title": "AI in Finance & Banking",
        "target_audience": ["Banks", "Insurers", "Asset managers", "Fintech founders", "Compliance officers", "Model risk officers"],
        "introduction": "Financial services face the most detailed AI regulatory obligations globally. The EU AI Act classifies credit scoring and insurance risk assessment as high-risk AI, while US banking regulators (Fed SR 11-7, OCC, FDIC) have required model risk management for algorithmic systems since 2011. The UK FCA and PRA have issued joint guidance on AI governance for regulated firms.",
        "stakes": [
            {"title": "Credit and insurance are high-risk under the EU AI Act", "description": "AI systems used for creditworthiness assessment and life/health insurance risk profiling are explicitly listed as high-risk in Annex III of the EU AI Act, requiring conformity assessments, human oversight, and ongoing monitoring."},
            {"title": "US model risk management applies broadly", "description": "Federal Reserve SR 11-7 and OCC guidance require banks to validate, document, and independently review all algorithmic decision models — a standard that now explicitly extends to AI/ML systems."},
            {"title": "FCA expects explainability for retail decisions", "description": "The FCA's Consumer Duty (2023) requires firms to demonstrate that AI-driven retail financial decisions are fair, explainable, and do not cause foreseeable harm."},
            {"title": "Third-party AI vendor risk", "description": "Regulators globally expect firms to perform due diligence on AI vendors and maintain accountability for outsourced algorithmic decisions."},
        ],
        "dos": [
            "Document AI model purpose, training data, and validation results",
            "Establish a model risk management framework covering AI/ML systems",
            "Implement human review for high-stakes credit and insurance decisions",
            "Conduct bias testing across protected demographic groups",
            "Register high-risk AI systems with EU authorities before deployment",
        ],
        "donts": [
            "Deploy credit scoring AI without conformity assessment in the EU",
            "Rely on AI decisions without maintaining override capabilities",
            "Use AI for insurance underwriting without bias audits",
            "Skip vendor due diligence for third-party AI models",
            "Treat legacy statistical models as exempt from AI governance obligations",
        ],
        "regulation_ids": ["RAI-EU-NA-E2AIXXX-2024"],
    },
    "healthcare": {
        "slug": "healthcare",
        "title": "AI in Healthcare & Life Sciences",
        "target_audience": [],
        "introduction": "",
        "stakes": [],
        "dos": [],
        "donts": [],
        "regulation_ids": [],
    },
    "hr": {
        "slug": "hr",
        "title": "AI in HR & Employment",
        "target_audience": [],
        "introduction": "",
        "stakes": [],
        "dos": [],
        "donts": [],
        "regulation_ids": [],
    },
}


@router.get("/use-cases")
async def list_use_cases() -> list[dict]:
    return [
        {"slug": uc["slug"], "title": uc["title"],
         "target_audience": uc["target_audience"], "introduction": uc["introduction"]}
        for uc in _USE_CASES.values()
    ]


@router.get("/use-cases/{slug}")
async def get_use_case(slug: str, driver: AsyncDriver = Depends(get_driver)) -> UseCaseDetail:
    uc = _USE_CASES.get(slug)
    if not uc:
        raise AppError(404, "NOT_FOUND", "未找到该用例")
    regulations = []
    for rid in uc["regulation_ids"]:
        rows = await run(driver, _Q_REG_BY_ID, instrument_id=rid)
        if rows:
            regulations.append(rows[0])
    return UseCaseDetail(**uc, regulations=regulations)
