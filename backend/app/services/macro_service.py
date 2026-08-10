# -*- coding: utf-8 -*-
"""宏观指标查询服务。"""
from __future__ import annotations

from app.database import execute_query
from app.schemas.common import serialize_row
from app.utils import normalize_date

MACRO_CATALOG = [
    {"indicator_code": "CPI", "name": "CPI同比", "unit": "%", "type": "inflation", "field": "cpi_yoy"},
    {"indicator_code": "PPI", "name": "PPI同比", "unit": "%", "type": "inflation", "field": "ppi_yoy"},
    {"indicator_code": "PMI", "name": "制造业PMI", "unit": "", "type": "activity", "field": "pmi"},
    {"indicator_code": "M2", "name": "M2同比", "unit": "%", "type": "liquidity", "field": "m2_yoy"},
    {"indicator_code": "SHRZGM", "name": "社融规模增量", "unit": "亿元", "type": "liquidity", "field": "shrzgm"},
    {"indicator_code": "LPR_1Y", "name": "LPR一年期", "unit": "%", "type": "rate", "field": "lpr_1y"},
    {"indicator_code": "LPR_5Y", "name": "LPR五年期", "unit": "%", "type": "rate", "field": "lpr_5y"},
    {"indicator_code": "CN_BOND_10Y", "name": "中国10年国债收益率", "unit": "%", "type": "rate", "field": "cn_bond_10y", "table": "rate"},
    {"indicator_code": "US_BOND_10Y", "name": "美国10年国债收益率", "unit": "%", "type": "rate", "field": "us_bond_10y", "table": "rate"},
]


def list_macro_indicators(indicator_type: str = "", page: int = 1, size: int = 20) -> dict:
    items = MACRO_CATALOG
    if indicator_type:
        items = [i for i in items if i["type"] == indicator_type]
    total = len(items)
    start = max(page - 1, 0) * size
    page_items = items[start : start + size]
    return {"total": total, "page": page, "size": size, "items": page_items}


def query_macro_trend(indicator_code: str, start_date: str, end_date: str) -> list[dict]:
    start = normalize_date(start_date, True)
    end = normalize_date(end_date, True)
    meta = next((i for i in MACRO_CATALOG if i["indicator_code"] == indicator_code.upper()), None)
    if not meta:
        return []

    field = meta["field"]
    if meta.get("table") == "rate":
        sql = f"""
            SELECT rate_date AS date, {field} AS value
            FROM trade_rate_daily
            WHERE rate_date BETWEEN %s AND %s
            ORDER BY rate_date ASC
        """
    else:
        sql = f"""
            SELECT indicator_date AS date, {field} AS value
            FROM trade_macro_indicator
            WHERE indicator_date BETWEEN %s AND %s
            ORDER BY indicator_date ASC
        """
    rows = execute_query(sql, (start, end))
    result = []
    for r in rows:
        item = serialize_row(r)
        if item.get("value") is not None:
            result.append(item)
    return result
