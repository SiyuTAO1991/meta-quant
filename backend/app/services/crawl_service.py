# -*- coding: utf-8 -*-
"""采集任务管理服务。"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from loguru import logger

from app.config import get_settings
from app.database import execute_query, execute_update
from app.schemas.common import serialize_row

TASK_DEFS = [
    {
        "task_id": "daily_bar",
        "name": "日线行情采集",
        "cron": "0 18 * * 1-5",
        "description": "Tushare 增量采集 A 股日线",
    },
    {
        "task_id": "financial",
        "name": "财务数据采集",
        "cron": "0 20 * * 6",
        "description": "AkShare 财务指标采集",
    },
    {
        "task_id": "macro",
        "name": "宏观数据采集",
        "cron": "0 9 * * *",
        "description": "CPI/PPI/PMI/M2/LPR/国债收益率",
    },
    {
        "task_id": "news",
        "name": "新闻事件采集",
        "cron": "0 */2 * * *",
        "description": "东方财富个股新闻",
    },
    {
        "task_id": "report",
        "name": "研报一致预期采集",
        "cron": "30 21 * * *",
        "description": "同花顺盈利预测",
    },
    {
        "task_id": "calendar",
        "name": "财经日历采集",
        "cron": "0 8 * * *",
        "description": "百度财经日历",
    },
]


def list_tasks() -> list[dict]:
    return TASK_DEFS


def _ensure_log_table():
    execute_update(
        """
        CREATE TABLE IF NOT EXISTS trade_crawl_task_log (
            id INT AUTO_INCREMENT PRIMARY KEY,
            task_id VARCHAR(50) NOT NULL,
            task_name VARCHAR(100),
            status VARCHAR(20) NOT NULL DEFAULT 'running',
            message TEXT,
            rows_affected INT DEFAULT 0,
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            finished_at DATETIME NULL,
            KEY idx_crawl_task_id (task_id),
            KEY idx_crawl_started (started_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )


def _start_log(task_id: str, task_name: str) -> int:
    _ensure_log_table()
    # 必须在同一连接内取 LAST_INSERT_ID，否则新连接会得到 0
    from app.database import get_connection

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO trade_crawl_task_log (task_id, task_name, status, message)
                VALUES (%s, %s, 'running', 'started')
                """,
                (task_id, task_name),
            )
            log_id = int(cursor.lastrowid)
            conn.commit()
            return log_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _finish_log(log_id: int, status: str, message: str, rows_affected: int = 0):
    execute_update(
        """
        UPDATE trade_crawl_task_log
        SET status=%s, message=%s, rows_affected=%s, finished_at=%s
        WHERE id=%s
        """,
        (status, message[:2000], rows_affected, datetime.now(), log_id),
    )


def _resolve_stocks(ts_codes: str) -> list[str]:
    settings = get_settings()
    if ts_codes.strip():
        return [c.strip() for c in ts_codes.split(",") if c.strip()]
    return settings.default_stocks


def trigger_task(task_id: str, ts_codes: str = "") -> dict:
    task = next((t for t in TASK_DEFS if t["task_id"] == task_id), None)
    if not task:
        return {"ok": False, "message": f"未知任务: {task_id}"}

    from app.collectors import (
        run_calendar_crawl,
        run_daily_crawl,
        run_financial_crawl,
        run_macro_crawl,
        run_news_crawl,
        run_report_crawl,
    )

    runners: dict[str, Callable] = {
        "daily_bar": lambda: run_daily_crawl(_resolve_stocks(ts_codes)),
        "financial": lambda: run_financial_crawl(_resolve_stocks(ts_codes)),
        "macro": run_macro_crawl,
        "news": lambda: run_news_crawl(_resolve_stocks(ts_codes)),
        "report": lambda: run_report_crawl(_resolve_stocks(ts_codes)),
        "calendar": run_calendar_crawl,
    }

    log_id = _start_log(task_id, task["name"])
    try:
        result = runners[task_id]()
        rows_affected = int(result.get("rows", 0))
        msg = result.get("message", "success")
        _finish_log(log_id, "success", msg, rows_affected)
        return {"ok": True, "log_id": log_id, "rows": rows_affected, "message": msg}
    except Exception as e:
        logger.exception(f"task {task_id} failed")
        _finish_log(log_id, "failed", str(e), 0)
        return {"ok": False, "log_id": log_id, "message": str(e)}


def query_task_logs(task_id: str = "", start_date: str = "", page: int = 1, size: int = 30) -> dict:
    _ensure_log_table()
    conditions = ["1=1"]
    params: list = []
    if task_id:
        conditions.append("task_id = %s")
        params.append(task_id)
    if start_date:
        conditions.append("DATE(started_at) >= %s")
        params.append(start_date if "-" in start_date else f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}")

    where = " AND ".join(conditions)
    count_rows = execute_query(
        f"SELECT COUNT(*) AS cnt FROM trade_crawl_task_log WHERE {where}", params
    )
    total = int(count_rows[0]["cnt"]) if count_rows else 0
    offset = max(page - 1, 0) * size
    rows = execute_query(
        f"""
        SELECT * FROM trade_crawl_task_log
        WHERE {where}
        ORDER BY id DESC
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


def retry_task(log_id: int) -> dict:
    rows = execute_query(
        "SELECT task_id FROM trade_crawl_task_log WHERE id = %s LIMIT 1", (log_id,)
    )
    if not rows:
        return {"ok": False, "message": f"日志不存在: {log_id}"}
    return trigger_task(rows[0]["task_id"])
