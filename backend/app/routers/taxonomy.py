from fastapi import APIRouter

from backend.app.db_postgres import get_pool

router = APIRouter()

TOPIC_META = {
    "governance_oversight": {"label": "Governance and Oversight", "description": "Board structures, accountability chains, and oversight mechanisms"},
    "transparency_disclosure": {"label": "Transparency and Accountability", "description": "Disclosure obligations, explainability, and public registries"},
    "risk_management": {"label": "Risk Management", "description": "Risk classification, impact assessment, and mitigation frameworks"},
    "data_protection_privacy": {"label": "Data and Privacy", "description": "Training data quality, GDPR alignment, and data subject rights"},
    "cybersecurity_model_security": {"label": "Security and Robustness", "description": "Adversarial robustness, model security, and incident response"},
    "fairness_non_discrimination": {"label": "Fairness and Non-Discrimination", "description": "Bias detection, protected characteristics, and equitable outcomes"},
    "human_rights_ethics": {"label": "Human Rights and Ethics", "description": "Fundamental rights, ethical review, and human dignity"},
    "liability_redress": {"label": "Liability and Enforcement", "description": "Legal accountability, penalty structures, and redress mechanisms"},
    "innovation_competitiveness": {"label": "Innovation and Competitiveness", "description": "Regulatory sandboxes, SME exemptions, and innovation support"},
    "sector_specific": {"label": "Sector-Specific Applications", "description": "Healthcare, finance, HR, and other high-impact domains"},
    "international_alignment": {"label": "International Alignment", "description": "Cross-border cooperation, mutual recognition, and global standards"},
    "environmental_sustainability": {"label": "Environmental and Sustainability Impact", "description": "Energy consumption, carbon footprint, and sustainability reporting"},
    "accountability_documentation": {"label": "Documentation and Accountability", "description": "Technical documentation, audit trails, and record-keeping"},
    "enforcement_penalties": {"label": "Enforcement and Penalties", "description": "Penalty structures, enforcement actions, and compliance obligations"},
    "safety_testing": {"label": "Safety and Testing", "description": "Pre-deployment testing, conformity assessment, and monitoring"},
    "fundamental_rights": {"label": "Fundamental Rights", "description": "Human dignity, non-discrimination, and rights protection"},
}

TYPE_META = {
    "Act": {"binding": True, "description": "Legislation passed by a legislature. Highest level of legal authority."},
    "Bill": {"binding": False, "description": "Draft legislation introduced but not yet enacted. Indicates legislative intent."},
    "Decree": {"binding": True, "description": "Law issued by the Executive with the force of law, often bypassing parliament."},
    "Regulation": {"binding": True, "description": "Binding rules issued by regulatory agencies or supranational bodies."},
    "Policy": {"binding": False, "description": "High-level government strategy. Not legally enforceable but guides future law."},
    "Guideline": {"binding": False, "description": "Non-binding recommendations and best practices from authorities."},
    "Standard": {"binding": False, "description": "Technical specifications from standards bodies (ISO, IEEE, NIST)."},
}

STATUS_META = {
    # DB values are camelCase without spaces — mapped to human-readable phase/description
    "InForce":          {"phase": "Active",              "description": "Currently effective, binding and applicable."},
    "PartiallyInForce": {"phase": "Active",              "description": "Effective and binding, with significant amendments since enactment."},
    "Draft":            {"phase": "Pre-Legislative",     "description": "Under internal development or consultation, not yet formally submitted."},
    "Proposed":         {"phase": "Legislative Process", "description": "Formally submitted or registered with a legislative body."},
    "UnderReview":      {"phase": "Legislative Process", "description": "Being debated, amended, or in committee."},
    "Adopted":          {"phase": "Post-Legislative",    "description": "Approved by legislature, awaiting signing or publication."},
    "AwaitingEntry":    {"phase": "Post-Legislative",    "description": "Signed and published but effective date is in the future."},
    "Stalled":          {"phase": "Legislative Process", "description": "No legislative progress for an extended period."},
    "Withdrawn":        {"phase": "Final",               "description": "Proposal failed — voted down, vetoed, or withdrawn by its authors."},
    "Repealed":         {"phase": "Final",               "description": "No longer in effect — explicitly removed by new legislation."},
    "Superseded":       {"phase": "Final",               "description": "Policy or guideline replaced by a subsequent instrument."},
}

@router.get("/taxonomy/topics")
async def get_topics() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT unnested_topic AS id, count(*) AS count "
            "FROM regulations, LATERAL unnest(topics) AS unnested_topic "
            "GROUP BY id ORDER BY count DESC"
        )
    result = []
    for row in rows:
        tid = row["id"] or ""
        meta = TOPIC_META.get(tid, {"label": tid, "description": ""})
        result.append({"id": tid, "label": meta["label"], "description": meta["description"], "count": row["count"]})
    return result


@router.get("/taxonomy/types")
async def get_types() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT type, count(*) AS count FROM regulations "
            "WHERE type != '' GROUP BY type ORDER BY count DESC"
        )
    result = []
    for row in rows:
        t = row["type"] or ""
        meta = TYPE_META.get(t, {"binding": False, "description": ""})
        result.append({"type": t, "count": row["count"], "binding": meta["binding"], "description": meta["description"]})
    return result


@router.get("/taxonomy/statuses")
async def get_statuses() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT legal_force AS status, count(*) AS count FROM regulations "
            "WHERE legal_force != '' GROUP BY status ORDER BY count DESC"
        )
    result = []
    for row in rows:
        s = row["status"] or ""
        meta = STATUS_META.get(s, {"phase": "Unknown", "description": ""})
        result.append({"status": s, "count": row["count"], "phase": meta["phase"], "description": meta["description"]})
    return result
