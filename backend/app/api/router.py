# -*- coding: utf-8 -*-
from fastapi import APIRouter

from app.api.routes import backtest, calendar, catalyst, chan, crawl, finance, macro, news, report, stock

api_router = APIRouter()

# 直接合并子路由，避免多层 include 在部分 Starlette 版本下不展开
for module in (stock, finance, macro, news, report, calendar, catalyst, crawl, backtest, chan):
    for route in module.router.routes:
        api_router.routes.append(route)
