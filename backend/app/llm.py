"""LLM 纯 HTTP 调用层（U-BE-05 / 技术方案 §8）。

硬性边界（§8.4）：本模块不 import cypher.py、不持有 driver、不接触 session，
也绝不解析/执行模型输出——模型文本只作为 answer 字符串原样返回。
共享 httpx.AsyncClient 由 main.py lifespan 创建并挂在 app.state.http，
router 负责把 client 注入本模块函数。
"""
import json
import re
from urllib.parse import urlparse

import httpx
from backend.app.schemas import LlmConfig

# 仅放行 http/https：避免把 api_key 发往非预期协议（如 ftp://）
_SCHEME_RE = re.compile(r"^https?://", re.IGNORECASE)

# Azure OpenAI 的部署 API 版本（主理人点名的兼容分支）
_AZURE_API_VERSION = "2024-10-21"


def validate_base_url(cfg: LlmConfig) -> None:
    # 为什么放在这里而非 schemas.LlmConfig：该模型冻结（U-BE-05 仅 import，不可改），
    # 且契约要求非法 URL 返回 400「请输入有效的URL」而非 Pydantic 默认的 422，故在此集中校验。
    parsed = urlparse(cfg.base_url)
    if not _SCHEME_RE.match(cfg.base_url) or not parsed.netloc:
        raise ValueError("请输入有效的URL")


def build_request(cfg: LlmConfig, messages: list[dict], max_tokens: int) -> tuple[str, dict, dict]:
    """构造 chat/completions 请求三元组 (url, headers, body)。
    兼容 4 类端点：Azure 走部署路径 + api-key 头；其余用 Bearer；允许空 api_key（Ollama/vLLM）。"""
    validate_base_url(cfg)
    base = cfg.base_url.rstrip("/")
    hostname = urlparse(cfg.base_url).hostname or ""
    if hostname.endswith("openai.azure.com"):
        # Azure 不用 /v1/chat/completions，model 字段即部署名，必须单独分支
        url = f"{base}/openai/deployments/{cfg.model}/chat/completions?api-version={_AZURE_API_VERSION}"
        headers = {"api-key": cfg.api_key} if cfg.api_key else {}
    else:
        url = f"{base}/chat/completions"
        # 允许空 api_key：本地 Ollama / vLLM 通常无需鉴权
        headers = {"Authorization": f"Bearer {cfg.api_key}"} if cfg.api_key else {}
    body = {
        "model": cfg.model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "stream": False,
    }
    return url, headers, body


async def call_llm(client: httpx.AsyncClient, cfg: LlmConfig, messages: list[dict],
                   max_tokens: int, timeout: float) -> dict:
    """纯 HTTP 调用；任何上游错误（连接/超时/非 2xx/JSON 结构异常）统一降级成
    {ok:false, answer:None, error}，绝不抛出 5xx（F-006 不阻塞其他页面）。
    base_url 已被 router 预校验，故此处不再抛 ValueError。"""
    try:
        url, headers, body = build_request(cfg, messages, max_tokens)
        resp = await client.post(url, headers=headers, json=body, timeout=timeout)
        resp.raise_for_status()
        # JSON 结构异常（缺 choices[0].message.content 等）一并降级
        content = resp.json()["choices"][0]["message"]["content"]
        return {"ok": True, "answer": content, "error": None}
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        return {"ok": False, "answer": None, "error": str(exc)}
