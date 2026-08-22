# -*- coding: utf-8 -*-
"""策略查询与内置策略入库同步。"""
from __future__ import annotations

from app.database import execute_query, execute_update
from app.schemas.common import serialize_row
from app.strategies import list_registered_strategies
from app.strategies.registry import get_strategy_meta


def _ensure_strategy_table():
    execute_update(
        """
        CREATE TABLE IF NOT EXISTS trade_strategy_info (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            strategy_name VARCHAR(100) NOT NULL,
            strategy_category VARCHAR(50) NOT NULL,
            strategy_code VARCHAR(64) NOT NULL,
            description TEXT,
            status TINYINT(1) NOT NULL DEFAULT 1,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_strategy_code (strategy_code)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )


def sync_builtin_strategies() -> None:
    """将内存注册表中的内置策略同步到 MySQL。"""
    _ensure_strategy_table()
    for meta in list_registered_strategies():
        execute_update(
            """
            INSERT INTO trade_strategy_info
                (strategy_name, strategy_category, strategy_code, description, status)
            VALUES (%s, %s, %s, %s, 1)
            ON DUPLICATE KEY UPDATE
                strategy_name = VALUES(strategy_name),
                strategy_category = VALUES(strategy_category),
                description = VALUES(description),
                status = 1
            """,
            (
                meta["strategy_name"],
                meta["strategy_category"],
                meta["strategy_code"],
                meta["description"],
            ),
        )


def list_strategies(page: int = 1, page_size: int = 50) -> dict:
    sync_builtin_strategies()
    page = max(1, page)
    page_size = min(max(1, page_size), 200)
    offset = (page - 1) * page_size

    total_rows = execute_query(
        "SELECT COUNT(1) AS cnt FROM trade_strategy_info WHERE status = 1"
    )
    total = int(total_rows[0]["cnt"]) if total_rows else 0

    rows = execute_query(
        """
        SELECT id, strategy_name, strategy_category, strategy_code, description,
               status, create_time, update_time
        FROM trade_strategy_info
        WHERE status = 1
        ORDER BY id ASC
        LIMIT %s OFFSET %s
        """,
        (page_size, offset),
    )

    items = []
    for row in rows:
        meta = get_strategy_meta(row["strategy_code"]) or {}
        items.append(
            {
                "strategy_id": row["id"],
                "strategy_key": row["strategy_code"],
                "strategy_name": row["strategy_name"],
                "strategy_desc": row["description"] or meta.get("description", ""),
                "strategy_category": row["strategy_category"],
                "is_built_in": bool(meta.get("is_built_in", True)),
                "create_time": serialize_row(row).get("create_time"),
            }
        )
    return {"items": items, "page": page, "page_size": page_size, "total": total}


def get_strategy_detail(strategy_key: str) -> dict:
    sync_builtin_strategies()
    meta = get_strategy_meta(strategy_key)
    if not meta:
        raise ValueError(f"未知策略: {strategy_key}")

    rows = execute_query(
        """
        SELECT id, strategy_name, strategy_code, description, create_time
        FROM trade_strategy_info
        WHERE strategy_code = %s AND status = 1
        LIMIT 1
        """,
        (strategy_key,),
    )
    if not rows:
        raise ValueError(f"策略未启用或不存在: {strategy_key}")

    row = rows[0]
    return {
        "strategy_id": row["id"],
        "strategy_key": row["strategy_code"],
        "strategy_name": row["strategy_name"],
        "strategy_desc": row["description"] or meta["description"],
        "is_built_in": True,
        "param_template": meta.get("param_template", []),
        "create_time": serialize_row(row).get("create_time"),
    }


def get_strategy_db_id(strategy_key: str) -> int:
    sync_builtin_strategies()
    rows = execute_query(
        "SELECT id FROM trade_strategy_info WHERE strategy_code = %s AND status = 1 LIMIT 1",
        (strategy_key,),
    )
    if not rows:
        raise ValueError(f"策略未启用或不存在: {strategy_key}")
    return int(rows[0]["id"])
