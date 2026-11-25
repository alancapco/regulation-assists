import re
from datetime import date
from typing import Annotated

from fastapi import Depends, Query, Request
from neo4j import AsyncDriver

from backend.app.errors import AppError
from backend.app.schemas import CalendarQuery, GraphQuery, RegulationQuery

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def get_driver(request: Request) -> AsyncDriver:
    # 单例 driver 由 main.py lifespan 创建并挂到 app.state；各 router 通过 Depends 复用连接池
    return request.app.state.driver


async def run(driver: AsyncDriver, cypher: str, **params) -> list[dict]:
    """标准读取范式（§1.2 全后端唯一写法）：共享连接池、隐式只读事务，
    不引入 execute_read 回调层。映射层只吃 list[dict]。"""
    async with driver.session() as session:
        result = await session.run(cypher, **params)
        return await result.data()


def _opt_date(v: str) -> str:
    # 空串 = 不过滤；非空须为合法 ISO 日期，除格式外还校验真实日历（如 2026-13-01 非法）
    if not v:
        return v
    if not ISO.match(v):
        raise AppError(400, "VALIDATION_ERROR", "日期格式须为 YYYY-MM-DD")
    try:
        date.fromisoformat(v)
    except ValueError:
        raise AppError(400, "VALIDATION_ERROR", "日期格式须为 YYYY-MM-DD")
    return v


def _dates(date_from: str, date_to: str) -> tuple[str, str]:
    date_from, date_to = _opt_date(date_from.strip()), _opt_date(date_to.strip())
    if date_from and date_to and date_from > date_to:
        raise AppError(400, "VALIDATION_ERROR", "date_from 不得晚于 date_to")
    return date_from, date_to


async def regulation_params(
    q: Annotated[str, Query(max_length=200)] = "",
    jurisdiction: str = "", type: str = "", legal_force: str = "", topic: str = "",
    date_from: str = "", date_to: str = "",
) -> RegulationQuery:
    date_from, date_to = _dates(date_from, date_to)
    return RegulationQuery(q=q.strip(), jurisdiction=jurisdiction, type=type,
                           legal_force=legal_force, topic=topic,
                           date_from=date_from, date_to=date_to)


async def calendar_params(
    jurisdiction: str = "", date_from: str = "", date_to: str = "",
) -> CalendarQuery:
    date_from, date_to = _dates(date_from, date_to)
    return CalendarQuery(jurisdiction=jurisdiction, date_from=date_from, date_to=date_to)


async def graph_params(jurisdiction: str = "", topic: str = "") -> GraphQuery:
    return GraphQuery(jurisdiction=jurisdiction, topic=topic)
