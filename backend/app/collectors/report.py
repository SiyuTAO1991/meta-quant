# -*- coding: utf-8 -*-
"""研报一致预期采集（同花顺）。"""
from __future__ import annotations

from datetime import datetime

import akshare as ak
from loguru import logger

from app.config import get_settings
from app.database import execute_update


def run_report_crawl(stock_codes: list[str] | None = None) -> dict:
    settings = get_settings()
    codes = stock_codes or settings.default_stocks
    saved = 0
    today = datetime.now().strftime("%Y-%m-%d")

    for code in codes:
        symbol = code.split(".")[0]
        try:
            df = ak.stock_profit_forecast_ths(symbol=symbol, indicator="预测年报每股收益")
        except Exception as e:
            logger.warning(f"report crawl {code}: {e}")
            continue
        if df is None or len(df) == 0:
            continue
        try:
            df.columns = ["year", "analyst_count", "min_val", "mean_val", "max_val", "industry_avg"]
        except Exception:
            pass
        eps_current = float(df.iloc[0]["mean_val"]) if "mean_val" in df.columns else None
        eps_next = float(df.iloc[1]["mean_val"]) if len(df) > 1 and "mean_val" in df.columns else None
        analyst_count = int(df.iloc[0].get("analyst_count", 0) or 0)
        execute_update(
            """
            INSERT INTO trade_report_consensus
            (stock_code, broker, report_date, eps_forecast_current, eps_forecast_next, source_file)
            VALUES (%s, %s, %s, %s, %s, 'ths_consensus')
            ON DUPLICATE KEY UPDATE
            eps_forecast_current=VALUES(eps_forecast_current),
            eps_forecast_next=VALUES(eps_forecast_next)
            """,
            (code, f"一致预期({analyst_count}家)", today, eps_current, eps_next),
        )
        saved += 1
    return {"rows": saved, "message": f"saved={saved}"}
