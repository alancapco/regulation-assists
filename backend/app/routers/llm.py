"""U-BE-05：POST /api/llm/test 与 /api/llm/ask（API-007 / API-008，恒 HTTP 200）。

两个端点均把上游失败降级成 ok:false 而非 5xx（F-006 不阻塞其他 5 个页面）；
仅在 base_url 格式非法时返回 400 VALIDATION_ERROR（输入校验，非运行时故障）。
"""
from fastapi import APIRouter, Depends, Request
from neo4j import AsyncDriver

from backend.app import cypher
from backend.app.config import settings
from backend.app.deps import get_driver, run
from backend.app.errors import AppError
from backend.app.llm import call_llm, validate_base_url
from backend.app.mapping import map_regulation
from backend.app.schemas import (
    LlmAskRequest, LlmAskResponse, LlmConfig, LlmTestResponse, Regulation,
)

router = APIRouter()

# test 用最小探测消息；ask 答案上限（契约未指定，取合理值）
_PING_MESSAGES = [{"role": "user", "content": "ping"}]
_ASK_MAX_TOKENS = 512


def _format_regulation(reg: Regulation) -> str:
    """把 Regulation 拼成纯文本上下文（不含任何 Cypher/可执行片段）。"""
    lines = [f"法规名称：{reg.name}"]
    if reg.type:
        lines.append(f"类型：{reg.type}")
    if reg.legal_force:
        lines.append(f"法律效力：{reg.legal_force}")
    if reg.legislation_date:
        lines.append(f"立法日期：{reg.legislation_date}")
    if reg.description:
        lines.append(f"描述：{reg.description}")
    if reg.topics:
        lines.append("主题标签：" + "、".join(reg.topics))
    if reg.milestones:
        ms = [f"{m.date}: {m.title}" for m in reg.milestones if m.date]
        if ms:
            lines.append("时间线：" + "；".join(ms))
    if reg.official_sources:
        lines.append("官方来源：" + "；".join(s.url for s in reg.official_sources))
    return "\n".join(lines)


async def build_context(driver: AsyncDriver, instrument_id: str | None) -> str:
    """取 Regulation 拼纯文本上下文；在 router 层完成（llm.py 不碰 DB，§8.4）。
    Neo4j 断连/查询异常时降级为空上下文，保证 /api/llm/ask 恒 200 且不受 Neo4j 影响（§9.2）。"""
    if not instrument_id:
        return ""
    try:
        rows = await run(driver, cypher.Q_REGULATIONS, instrument_id=instrument_id,
                        q="", jurisdiction="", type="", legal_force="", topic="")
    except Exception:
        return ""
    if not rows:
        return ""
    return _format_regulation(map_regulation(rows[0]))


def build_messages(context: str, question: str) -> list[dict]:
    if context:
        return [
            {"role": "system",
             "content": "以下是与问题相关的法规上下文，请仅依据上下文作答：\n" + context},
            {"role": "user", "content": question},
        ]
    return [{"role": "user", "content": question}]


def _require_valid_url(cfg: LlmConfig) -> None:
    # 非法 URL 属输入校验 → 400；其余上游故障一律降级 200，不在此处处理
    try:
        validate_base_url(cfg)
    except ValueError:
        raise AppError(400, "VALIDATION_ERROR", "请输入有效的URL")


@router.post("/api/llm/test", response_model=LlmTestResponse)
async def test_llm(body: LlmConfig, request: Request) -> LlmTestResponse:
    _require_valid_url(body)
    res = await call_llm(request.app.state.http, body, _PING_MESSAGES, 1, settings.llm_timeout_test)
    return LlmTestResponse(ok=res["ok"], error=res["error"])


@router.post("/api/llm/ask", response_model=LlmAskResponse)
async def ask_llm(body: LlmAskRequest, request: Request,
                  driver: AsyncDriver = Depends(get_driver)) -> LlmAskResponse:
    _require_valid_url(body)
    context = await build_context(driver, body.instrument_id)
    messages = build_messages(context, body.question)
    res = await call_llm(request.app.state.http, body, messages, _ASK_MAX_TOKENS, settings.llm_timeout_ask)
    return LlmAskResponse(ok=res["ok"], answer=res["answer"], error=res["error"])
