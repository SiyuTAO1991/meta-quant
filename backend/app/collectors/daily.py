# -*- coding: utf-8 -*-
"""日线行情采集（Tushare）。"""
from __future__ import annotations

from datetime import date

import pandas as pd
import tushare as ts
from loguru import logger

from app.config import get_settings
from app.database import execute_many, execute_query

INSERT_SQL = """
    INSERT INTO trade_stock_daily
    (stock_code, trade_date, open_price, high_price, low_price, close_price, volume, amount, turnover_rate)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
    open_price=VALUES(open_price), high_price=VALUES(high_price),
    low_price=VALUES(low_price), close_price=VALUES(close_price),
    volume=VALUES(volume), amount=VALUES(amount),
    turnover_rate=VALUES(turnover_rate)
"""


def _get_pro():
    token = get_settings().tushare_token
    if not token:
        raise RuntimeError("未配置 TUSHARE_TOKEN")
    ts.set_token(token.strip())
    return ts.pro_api()


def _is_etf(stock_code: str) -> bool:
    symbol = stock_code.split(".")[0]
    return symbol.startswith(("15", "16", "51", "56", "58"))


def _latest_dates() -> dict[str, str]:
    try:
        rows = execute_query(
            "SELECT stock_code, MAX(trade_date) AS max_date FROM trade_stock_daily GROUP BY stock_code"
        )
        result = {}
        for r in rows:
            if r["max_date"]:
                result[r["stock_code"]] = r["max_date"].strftime("%Y%m%d")
        return result
    except Exception as e:
        logger.warning(f"query latest dates failed: {e}")
        return {}


def _fetch_daily(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    if _is_etf(stock_code):
        df = _get_pro().fund_daily(ts_code=stock_code, start_date=start_date, end_date=end_date)
    else:
        df = ts.pro_bar(ts_code=stock_code, start_date=start_date, end_date=end_date, adj="qfq", freq="D")
    return df


def run_daily_crawl(
    stock_codes: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    settings = get_settings()
    codes = stock_codes or settings.default_stocks
    existing = _latest_dates()
    end = (end_date or date.today().strftime("%Y%m%d")).replace("-", "")
    total_rows = 0
    success = 0
    failed = []

    for code in codes:
        # 显式传入起始日时按区间采集；否则从库内最新日增量
        if start_date:
            start = start_date.replace("-", "")
        else:
            start = existing.get(code, "20250101")
        try:
            df = _fetch_daily(code, start, end)
            if df is None or len(df) == 0:
                success += 1
                continue
            df = df.rename(columns={"trade_date": "date", "vol": "volume"})
            df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
            rows = []
            for _, row in df.iterrows():
                rows.append(
                    (
                        code,
                        row["date"].strftime("%Y-%m-%d"),
                        float(row.get("open", 0) or 0),
                        float(row.get("high", 0) or 0),
                        float(row.get("low", 0) or 0),
                        float(row.get("close", 0) or 0),
                        int(row.get("volume", 0) or 0),
                        float(row.get("amount", 0) or 0),
                        None,
                    )
                )
            total_rows += execute_many(INSERT_SQL, rows)
            success += 1
        except Exception as e:
            logger.error(f"daily crawl {code} failed: {e}")
            failed.append(code)

    return {
        "rows": total_rows,
        "message": (
            f"range={start_date or 'auto'}~{end}, "
            f"success={success}, failed={len(failed)}, rows={total_rows}"
        ),
        "failed": failed,
    }
