# -*- coding: utf-8 -*-
"""财务数据查询服务。"""
from __future__ import annotations

from app.database import execute_query
from app.schemas.common import serialize_row


def _code_candidates(ts_code: str) -> list[str]:
    """兼容 600519 / 600519.SH / sh600519 等写法。"""
    code = (ts_code or "").strip().upper()
    if not code:
        return []
    candidates = [ts_code.strip(), code]
    if "." not in code and code.isdigit():
        if code.startswith(("5", "6", "9")):
            candidates.append(f"{code}.SH")
        elif code.startswith(("0", "1", "2", "3")):
            candidates.append(f"{code}.SZ")
    symbol = code.split(".")[0]
    candidates.extend([symbol, f"sh{symbol}", f"sz{symbol}", f"SH{symbol}", f"SZ{symbol}"])
    # 去重保序
    seen = set()
    out = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def query_finance_indicator(ts_code: str, start_year: int, end_year: int) -> list[dict]:
    codes = _code_candidates(ts_code)
    if not codes:
        return []
    placeholders = ",".join(["%s"] * len(codes))
    sql = f"""
        SELECT *
        FROM trade_stock_financial
        WHERE stock_code IN ({placeholders})
          AND YEAR(report_date) BETWEEN %s AND %s
        ORDER BY report_date DESC
    """
    rows = execute_query(sql, (*codes, start_year, end_year))
    # 年份区间无数据时，回退返回该股票全部财务记录，避免前端误判“无数据”
    if not rows:
        rows = execute_query(
            f"""
            SELECT *
            FROM trade_stock_financial
            WHERE stock_code IN ({placeholders})
            ORDER BY report_date DESC
            """,
            tuple(codes),
        )
    return [serialize_row(r) for r in rows]


def query_finance_by_period(ts_code: str, period: str) -> dict | None:
    period_dash = f"{period[:4]}-{period[4:6]}-{period[6:8]}" if len(period) == 8 else period
    codes = _code_candidates(ts_code)
    if not codes:
        return None
    placeholders = ",".join(["%s"] * len(codes))
    rows = execute_query(
        f"""
        SELECT * FROM trade_stock_financial
        WHERE stock_code IN ({placeholders}) AND report_date = %s
        LIMIT 1
        """,
        (*codes, period_dash),
    )
    return serialize_row(rows[0]) if rows else None


def compare_finance(ts_codes: list[str], year: int) -> list[dict]:
    if not ts_codes:
        return []
    codes: list[str] = []
    for c in ts_codes:
        codes.extend(_code_candidates(c))
    codes = list(dict.fromkeys(codes))
    placeholders = ",".join(["%s"] * len(codes))
    sql = f"""
        SELECT *
        FROM trade_stock_financial
        WHERE stock_code IN ({placeholders})
          AND YEAR(report_date) = %s
        ORDER BY stock_code, report_date DESC
    """
    rows = execute_query(sql, (*codes, year))
    return [serialize_row(r) for r in rows]
