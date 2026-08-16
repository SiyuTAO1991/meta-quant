# -*- coding: utf-8 -*-
"""财经日历与催化剂事件查询。"""
from __future__ import annotations

from datetime import date

from app.database import execute_query
from app.schemas.common import serialize_row
from app.utils import level_to_importance, normalize_date


def _importance_filter(level: str) -> tuple[str, list]:
    imp = level_to_importance(level)
    if imp is None:
        return "", []
    return " AND importance >= %s", [imp]


def query_calendar(
    start_date: str,
    end_date: str,
    level: str = "",
    page: int = 1,
    size: int = 20,
) -> dict:
    start = normalize_date(start_date, True)
    end = normalize_date(end_date, True)
    extra, params = _importance_filter(level)
    where_sql = f"event_date BETWEEN %s AND %s{extra}"
    query_params = (start, end, *params)

    count_rows = execute_query(
        f"SELECT COUNT(*) AS cnt FROM trade_calendar_event WHERE {where_sql}",
        query_params,
    )
    total = int(count_rows[0]["cnt"]) if count_rows else 0
    page = max(int(page or 1), 1)
    size = max(min(int(size or 20), 100), 1)
    offset = (page - 1) * size

    rows = execute_query(
        f"""
        SELECT * FROM trade_calendar_event
        WHERE {where_sql}
        ORDER BY event_date ASC, importance DESC, id ASC
        LIMIT %s OFFSET %s
        """,
        (*query_params, size, offset),
    )
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [serialize_row(r) for r in rows],
    }


def query_calendar_today(level: str = "", page: int = 1, size: int = 20) -> dict:
    today = date.today().isoformat()
    return query_calendar(today, today, level, page=page, size=size)


def query_catalyst_events(
    ts_code: str = "",
    event_type: str = "",
    start_date: str = "",
    end_date: str = "",
    level: str = "high",
) -> list[dict]:
    conditions = ["1=1"]
    params: list = []

    # 催化剂：重要日历 + 重要新闻
    extra, imp_params = _importance_filter(level)
    if imp_params:
        conditions.append("importance >= %s")
        params.extend(imp_params)

    if event_type:
        conditions.append("(category LIKE %s OR title LIKE %s)")
        params.extend([f"%{event_type}%", f"%{event_type}%"])
    if start_date:
        conditions.append("event_date >= %s")
        params.append(normalize_date(start_date, True))
    if end_date:
        conditions.append("event_date <= %s")
        params.append(normalize_date(end_date, True))

    where = " AND ".join(conditions)
    rows = execute_query(
        f"""
        SELECT * FROM trade_calendar_event
        WHERE {where}
        ORDER BY event_date DESC, importance DESC
        LIMIT 200
        """,
        params,
    )
    events = [serialize_row(r) for r in rows]

    if ts_code:
        news_rows = execute_query(
            """
            SELECT id, stock_code, title, content, published_at, sentiment, is_important, source
            FROM trade_stock_news
            WHERE stock_code = %s AND is_important = 1
            ORDER BY published_at DESC
            LIMIT 50
            """,
            (ts_code,),
        )
        for n in news_rows:
            item = serialize_row(n)
            events.append(
                {
                    "id": f"news-{item['id']}",
                    "event_date": (item.get("published_at") or "")[:10],
                    "title": item.get("title"),
                    "category": "stock_news",
                    "importance": 3 if item.get("is_important") else 2,
                    "stock_code": item.get("stock_code"),
                    "source": item.get("source"),
                    "sentiment": item.get("sentiment"),
                }
            )
    return events


def query_catalyst_today(level: str = "high") -> list[dict]:
    today = date.today().isoformat()
    return query_catalyst_events(start_date=today, end_date=today, level=level)
