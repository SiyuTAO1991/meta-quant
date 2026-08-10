# -*- coding: utf-8 -*-
"""数据采集模块入口。逻辑参考 quant_trading_test/CASE-数据采集。"""
from app.collectors.daily import run_daily_crawl
from app.collectors.financial import run_financial_crawl
from app.collectors.macro import run_macro_crawl
from app.collectors.news import run_news_crawl
from app.collectors.report import run_report_crawl
from app.collectors.calendar import run_calendar_crawl

__all__ = [
    "run_daily_crawl",
    "run_financial_crawl",
    "run_macro_crawl",
    "run_news_crawl",
    "run_report_crawl",
    "run_calendar_crawl",
]
