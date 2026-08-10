# -*- coding: utf-8 -*-
"""行情查询服务。"""
from __future__ import annotations

from loguru import logger

from app.database import execute_query
from app.schemas.common import serialize_row
from app.utils import normalize_date


def query_stock_daily(ts_code: str, start_date: str, end_date: str) -> list[dict]:
    start = normalize_date(start_date, as_dash=True)
    end = normalize_date(end_date, as_dash=True)
    sql = """
        SELECT stock_code, trade_date, open_price, high_price, low_price,
               close_price, volume, amount, turnover_rate
        FROM trade_stock_daily
        WHERE stock_code = %s AND trade_date BETWEEN %s AND %s
        ORDER BY trade_date ASC
    """
    rows = execute_query(sql, (ts_code, start, end))
    return [serialize_row(r) for r in rows]


def query_index_daily(index_code: str, start_date: str, end_date: str) -> list[dict]:
    """指数日线：优先查库；库中无数据时返回空列表（可由采集补齐）。"""
    return query_stock_daily(index_code, start_date, end_date)


def query_stock_concepts(ts_code: str) -> list[dict]:
    """概念板块：尝试 AkShare，失败则返回空。"""
    try:
        import akshare as ak

        symbol = ts_code.split(".")[0]
        df = ak.stock_board_concept_name_em()
        # 简化：返回热门概念列表（个股所属概念接口不稳定时的兜底）
        if df is None or len(df) == 0:
            return []
        items = []
        for _, row in df.head(30).iterrows():
            items.append(
                {
                    "ts_code": ts_code,
                    "concept_name": str(row.get("板块名称") or row.iloc[1]),
                    "symbol": symbol,
                }
            )
        return items
    except Exception as e:
        logger.warning(f"concept query failed: {e}")
        return []


def list_available_stocks(limit: int = 50) -> list[str]:
    rows = execute_query(
        "SELECT DISTINCT stock_code FROM trade_stock_daily ORDER BY stock_code LIMIT %s",
        (limit,),
    )
    return [r["stock_code"] for r in rows]
