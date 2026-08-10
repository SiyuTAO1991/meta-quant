# -*- coding: utf-8 -*-
"""财务数据查询服务。"""
from __future__ import annotations

from app.database import execute_query
from app.schemas.common import serialize_row


def query_finance_indicator(ts_code: str, start_year: int, end_year: int) -> list[dict]:
    sql = """
        SELECT *
        FROM trade_stock_financial
        WHERE stock_code = %s
          AND YEAR(report_date) BETWEEN %s AND %s
        ORDER BY report_date DESC
    """
    rows = execute_query(sql, (ts_code, start_year, end_year))
    return [serialize_row(r) for r in rows]


def query_finance_by_period(ts_code: str, period: str) -> dict | None:
    period_dash = f"{period[:4]}-{period[4:6]}-{period[6:8]}" if len(period) == 8 else period
    rows = execute_query(
        """
        SELECT * FROM trade_stock_financial
        WHERE stock_code = %s AND report_date = %s
        LIMIT 1
        """,
        (ts_code, period_dash),
    )
    return serialize_row(rows[0]) if rows else None


def compare_finance(ts_codes: list[str], year: int) -> list[dict]:
    if not ts_codes:
        return []
    placeholders = ",".join(["%s"] * len(ts_codes))
    sql = f"""
        SELECT *
        FROM trade_stock_financial
        WHERE stock_code IN ({placeholders})
          AND YEAR(report_date) = %s
        ORDER BY stock_code, report_date DESC
    """
    rows = execute_query(sql, (*ts_codes, year))
    return [serialize_row(r) for r in rows]
