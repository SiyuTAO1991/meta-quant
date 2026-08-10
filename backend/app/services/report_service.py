# -*- coding: utf-8 -*-
"""研报一致性预期查询。"""
from __future__ import annotations

from app.database import execute_query
from app.schemas.common import serialize_row


def query_report_list(
    ts_code: str,
    org: str = "",
    rating: str = "",
    page: int = 1,
    size: int = 20,
) -> dict:
    conditions = ["stock_code = %s"]
    params: list = [ts_code]
    if org:
        conditions.append("broker LIKE %s")
        params.append(f"%{org}%")
    if rating:
        conditions.append("rating = %s")
        params.append(rating)

    where = " AND ".join(conditions)
    count_rows = execute_query(
        f"SELECT COUNT(*) AS cnt FROM trade_report_consensus WHERE {where}", params
    )
    total = int(count_rows[0]["cnt"]) if count_rows else 0
    offset = max(page - 1, 0) * size
    rows = execute_query(
        f"""
        SELECT * FROM trade_report_consensus
        WHERE {where}
        ORDER BY report_date DESC, id DESC
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


def query_report_detail(report_id: int) -> dict | None:
    rows = execute_query(
        "SELECT * FROM trade_report_consensus WHERE id = %s LIMIT 1", (report_id,)
    )
    return serialize_row(rows[0]) if rows else None
