# -*- coding: utf-8 -*-
"""新闻查询服务。"""
from __future__ import annotations

from app.database import execute_query
from app.schemas.common import serialize_row
from app.utils import normalize_date


def query_stock_news(
    ts_code: str,
    keyword: str = "",
    start_date: str = "",
    page: int = 1,
    size: int = 20,
) -> dict:
    conditions = ["stock_code = %s"]
    params: list = [ts_code]
    if keyword:
        conditions.append("(title LIKE %s OR content LIKE %s)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    if start_date:
        conditions.append("published_at >= %s")
        params.append(normalize_date(start_date, True))

    where = " AND ".join(conditions)
    count_rows = execute_query(f"SELECT COUNT(*) AS cnt FROM trade_stock_news WHERE {where}", params)
    total = int(count_rows[0]["cnt"]) if count_rows else 0
    offset = max(page - 1, 0) * size
    rows = execute_query(
        f"""
        SELECT * FROM trade_stock_news
        WHERE {where}
        ORDER BY published_at DESC, id DESC
        LIMIT %s OFFSET %s
        """,
        (*params, size, offset),
    )
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [serialize_row(r) for r in rows],
    }


def query_hot_news(page: int = 1, size: int = 20) -> dict:
    offset = max(page - 1, 0) * size
    count_rows = execute_query("SELECT COUNT(*) AS cnt FROM trade_stock_news WHERE is_important = 1")
    total = int(count_rows[0]["cnt"]) if count_rows else 0
    if total == 0:
        count_rows = execute_query("SELECT COUNT(*) AS cnt FROM trade_stock_news")
        total = int(count_rows[0]["cnt"]) if count_rows else 0
        rows = execute_query(
            """
            SELECT * FROM trade_stock_news
            ORDER BY published_at DESC, id DESC
            LIMIT %s OFFSET %s
            """,
            (size, offset),
        )
    else:
        rows = execute_query(
            """
            SELECT * FROM trade_stock_news
            WHERE is_important = 1
            ORDER BY published_at DESC, id DESC
            LIMIT %s OFFSET %s
            """,
            (size, offset),
        )
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [serialize_row(r) for r in rows],
    }


def query_news_detail(news_id: int) -> dict | None:
    rows = execute_query("SELECT * FROM trade_stock_news WHERE id = %s LIMIT 1", (news_id,))
    return serialize_row(rows[0]) if rows else None
