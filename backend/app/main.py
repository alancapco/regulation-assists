import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from neo4j import AsyncGraphDatabase
from neo4j.exceptions import AuthError, Neo4jError, ServiceUnavailable

from backend.app.config import settings
from backend.app.db_postgres import init_pool, close_pool
from backend.app.errors import AppError, envelope
from backend.app.routers import calendar, graph, llm, meta, regulations
from backend.app.routers import map as map_router, governance, taxonomy, research, usecases, breakdowns, chat

logger = logging.getLogger("backend.app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 不强制 verify_connectivity：允许 Neo4j 晚于后端启动，/api/status 每次实时探测（§9.2）
    app.state.driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
    app.state.http = httpx.AsyncClient()
    try:
        await init_pool()
    except Exception as e:
        logger.warning(f"Postgres pool init failed (continuing without): {e}")
    yield
    await app.state.driver.close()
    await app.state.http.aclose()
    await close_pool()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=exc.envelope().model_dump())

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # 为什么：FastAPI 默认 422，冻结契约统一成 400
        status, env = envelope("VALIDATION_ERROR", detail=str(exc))
        return JSONResponse(status_code=status, content=env.model_dump())

    @app.exception_handler(ServiceUnavailable)
    @app.exception_handler(AuthError)
    @app.exception_handler(Neo4jError)
    async def handle_neo4j_error(request: Request, exc: Exception) -> JSONResponse:
        # ServiceUnavailable 不是 Neo4jError 子类，故三者分别注册到同一处理器
        status, env = envelope("NEO4J_UNAVAILABLE", detail=str(exc))
        return JSONResponse(status_code=status, content=env.model_dump())

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("未处理异常")
        # 为什么：完整堆栈只进服务端日志，detail 不外泄给前端
        status, env = envelope("INTERNAL_ERROR")
        return JSONResponse(status_code=status, content=env.model_dump())

    # Batch 1: original 5 routers; Batch 2: 5 phase-2 routers registered with /api prefix
    for router in (meta.router, regulations.router, calendar.router, graph.router, llm.router):
        app.include_router(router)
    app.include_router(map_router.router, prefix="/api")
    app.include_router(governance.router, prefix="/api")
    app.include_router(taxonomy.router, prefix="/api")
    app.include_router(research.router, prefix="/api")
    app.include_router(usecases.router, prefix="/api")
    app.include_router(breakdowns.router, prefix="/api")
    app.include_router(chat.router)

    return app


app = create_app()
