# -*- coding: utf-8 -*-
"""财务数据采集（AkShare）。"""
from __future__ import annotations

import akshare as ak
from loguru import logger

from app.config import get_settings
from app.database import execute_many

INSERT_SQL = """
    INSERT INTO trade_stock_financial
    (stock_code, report_date, revenue, net_profit, eps, roe, roa,
     gross_margin, net_margin, debt_ratio, current_ratio,
     operating_cashflow, total_assets, total_equity, data_source)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
    revenue=VALUES(revenue), net_profit=VALUES(net_profit), eps=VALUES(eps),
    roe=VALUES(roe), roa=VALUES(roa), gross_margin=VALUES(gross_margin),
    net_margin=VALUES(net_margin), debt_ratio=VALUES(debt_ratio),
    current_ratio=VALUES(current_ratio), operating_cashflow=VALUES(operating_cashflow),
    total_assets=VALUES(total_assets), total_equity=VALUES(total_equity)
"""


def _safe_float(val):
    if val is None:
        return None
    try:
        if str(val).strip() in ("", "--", "None", "nan"):
            return None
        v = float(val)
        return v if v == v else None
    except (ValueError, TypeError):
        return None


def _to_symbol(ts_code: str) -> str:
    return ts_code.split(".")[0]


def _crawl_one(stock_code: str) -> int:
    symbol = _to_symbol(stock_code)
    try:
        df = ak.stock_financial_analysis_indicator(symbol=symbol)
    except Exception as e:
        logger.warning(f"finance indicator {stock_code} failed: {e}")
        return 0
    if df is None or len(df) == 0:
        return 0

    rows = []
    for _, row in df.head(20).iterrows():
        report_date = str(row.get("日期") or row.iloc[0])[:10]
        rows.append(
            (
                stock_code,
                report_date,
                _safe_float(row.get("营业收入") or row.get("主营业务收入")),
                _safe_float(row.get("净利润")),
                _safe_float(row.get("摊薄每股收益") or row.get("每股收益")),
                _safe_float(row.get("净资产收益率") or row.get("加权净资产收益率")),
                _safe_float(row.get("总资产报酬率") or row.get("总资产净利率")),
                _safe_float(row.get("销售毛利率") or row.get("毛利率")),
                _safe_float(row.get("销售净利率") or row.get("净利率")),
                _safe_float(row.get("资产负债率")),
                _safe_float(row.get("流动比率")),
                _safe_float(row.get("经营活动产生的现金流量净额")),
                _safe_float(row.get("资产总计") or row.get("总资产")),
                _safe_float(row.get("股东权益合计") or row.get("净资产")),
                "akshare",
            )
        )
    return execute_many(INSERT_SQL, rows)


def run_financial_crawl(stock_codes: list[str] | None = None) -> dict:
    settings = get_settings()
    codes = stock_codes or settings.default_stocks
    total = 0
    failed = []
    for code in codes:
        try:
            total += _crawl_one(code)
        except Exception as e:
            logger.error(f"financial crawl {code}: {e}")
            failed.append(code)
    return {"rows": total, "message": f"rows={total}, failed={len(failed)}", "failed": failed}
