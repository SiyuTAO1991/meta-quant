# -*- coding: utf-8 -*-
"""FastAPI 入口。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.router import api_router
from app.config import get_settings
from app.database import ping_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    logger.info(f"starting {settings.app_name} v{settings.app_version}")
    ok = ping_db()
    logger.info(f"mysql connected={ok} db={settings.db_name}@{settings.db_host}")
    try:
        from app.services.crawl_service import _cleanup_stale_running_logs

        _cleanup_stale_running_logs()
        logger.info("cleaned stale crawl running logs")
    except Exception as e:
        logger.warning(f"cleanup crawl logs skipped: {e}")
    try:
        from app.services.strategy_service import sync_builtin_strategies

        sync_builtin_strategies()
        logger.info("synced builtin strategies")
    except Exception as e:
        logger.warning(f"sync strategies skipped: {e}")
    yield
    logger.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/health")
    def health():
        return {"status": "up", "mysql": ping_db()}

    return app


app = create_app()
