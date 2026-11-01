# -*- coding: utf-8 -*-
from fastapi import APIRouter

from app.api.routes import (
    backtest,
    calendar,
    catalyst,
    chan,
    crawl,
    factor,
    feature_engineering,
    finance,
    lightgbm_api,
    macro,
    multi_factor,
    news,
    rag_api,
    report,
    stock,
    xgboost_api,
)

api_router = APIRouter()

# 直接合并子路由，避免多层 include 在部分 Starlette 版本下不展开
for module in (
    stock,
    finance,
    macro,
    news,
    report,
    calendar,
    catalyst,
    crawl,
    backtest,
    chan,
    factor,
    feature_engineering,
    multi_factor,
    xgboost_api,
    lightgbm_api,
    rag_api,
):
    for route in module.router.routes:
        api_router.routes.append(route)
