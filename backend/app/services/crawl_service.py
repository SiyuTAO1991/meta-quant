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
        "need_stock": True,
    },
    {
        "task_id": "financial",
        "name": "财务数据采集",
        "cron": "0 20 * * 6",
        "description": "AkShare 财务指标采集",
        "need_stock": True,
    },
    {
        "task_id": "macro",
        "name": "宏观数据采集",
        "cron": "0 9 * * *",
        "description": "CPI/PPI/PMI/M2/LPR/国债收益率",
        "need_stock": False,
    },
    {
        "task_id": "news",
        "name": "新闻事件采集",
        "cron": "0 */2 * * *",
        "description": "东方财富个股新闻",
        "need_stock": False,
    },
    {
        "task_id": "report",
        "name": "研报一致预期采集",
        "cron": "30 21 * * *",
        "description": "同花顺盈利预测",
        "need_stock": True,
    },
    {
        "task_id": "calendar",
        "name": "财经日历采集",
        "cron": "0 8 * * *",
        "description": "百度财经日历",
        "need_stock": False,
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


def _list_stocks_from_db() -> list[str]:
    """库内已有日线的股票代码。"""
    try:
        rows = execute_query(
            "SELECT DISTINCT stock_code FROM trade_stock_daily ORDER BY stock_code"
        )
        return [r["stock_code"] for r in rows if r.get("stock_code")]
    except Exception as e:
        logger.warning(f"list stocks from db failed: {e}")
        return []


def _list_stocks_from_tushare() -> list[str]:
    """Tushare 当前上市 A 股全市场代码。"""
    try:
        from app.collectors.daily import _get_pro

        pro = _get_pro()
        df = pro.stock_basic(exchange="", list_status="L", fields="ts_code")
        if df is not None and len(df) > 0:
            return [str(c) for c in df["ts_code"].tolist()]
    except Exception as e:
        logger.warning(f"list stocks from tushare failed: {e}")
    return []


def _list_all_stocks(*, prefer_market: bool = False) -> list[str]:
    """
    解析“全部股票”列表。

    prefer_market=True: 优先 Tushare 全市场（日线/财务等留空股票代码时）
    prefer_market=False: 优先库内已有代码（新闻等增量场景）
    """
    if prefer_market:
        codes = _list_stocks_from_tushare()
        if codes:
            return codes
        codes = _list_stocks_from_db()
        if codes:
            return codes
    else:
        codes = _list_stocks_from_db()
        if codes:
            return codes
        codes = _list_stocks_from_tushare()
        if codes:
            return codes
    return get_settings().default_stocks


def _resolve_stocks(ts_codes: str, *, prefer_market: bool = False) -> list[str]:
    if ts_codes.strip():
        return [c.strip() for c in ts_codes.split(",") if c.strip()]
    return _list_all_stocks(prefer_market=prefer_market)


def _normalize_ymd(value: str, fallback: str = "") -> str:
    if not value:
        return fallback
    raw = value.strip().replace("-", "").replace("/", "")
    if len(raw) == 8 and raw.isdigit():
        return raw
    return fallback


def trigger_task(
    task_id: str,
    ts_codes: str = "",
    start_date: str = "",
    end_date: str = "",
) -> dict:
    task = next((t for t in TASK_DEFS if t["task_id"] == task_id), None)
    if not task:
        return {"ok": False, "message": f"未知任务: {task_id}"}

    start = _normalize_ymd(start_date)
    end = _normalize_ymd(end_date) or datetime.now().strftime("%Y%m%d")
    if not start:
        return {"ok": False, "message": "请选择采集日期"}

    from app.collectors import (
        run_calendar_crawl,
        run_daily_crawl,
        run_financial_crawl,
        run_macro_crawl,
        run_news_crawl,
        run_report_crawl,
    )

    need_stock = bool(task.get("need_stock", True))
    empty_codes = not ts_codes.strip()
    # 日线留空代码：后台按交易日全市场采集，不在请求线程解析五千多只股票
    daily_market = task_id == "daily_bar" and empty_codes

    # 清理同任务遗留的 running 日志，避免前端看到卡住记录
    _cleanup_stale_running_logs(task_id=task_id)

    log_id = _start_log(task_id, task["name"])

    def _run_in_background():
        try:
            if daily_market:
                stock_scope = "stocks=all(market_by_date)"
                result = run_daily_crawl(start_date=start, end_date=end, market=True)
            elif need_stock:
                # 日线指定代码 / 财务 / 研报：留空则 Tushare 全市场列表
                stocks = _resolve_stocks(ts_codes, prefer_market=True)
                stock_scope = (
                    f"stocks={len(stocks)}(market)"
                    if empty_codes
                    else f"stocks={','.join(stocks[:5])}{'...' if len(stocks) > 5 else ''}"
                )
                runners: dict[str, Callable] = {
                    "daily_bar": lambda: run_daily_crawl(stocks, start_date=start, end_date=end),
                    # 全市场：区间内已有数据的股票跳过；页面指定代码：不跳过，照常采集
                    "financial": lambda: run_financial_crawl(
                        stocks,
                        start_date=start,
                        end_date=end,
                        skip_existing_in_range=empty_codes,
                    ),
                    "report": lambda: run_report_crawl(stocks, start_date=start, end_date=end),
                }
                result = runners[task_id]()
            elif task_id == "news":
                stocks = _list_all_stocks(prefer_market=False)
                stock_scope = "scope=market"
                result = run_news_crawl(stocks, start_date=start, end_date=end)
            elif task_id == "macro":
                stock_scope = "scope=market"
                result = run_macro_crawl(start_date=start, end_date=end)
            elif task_id == "calendar":
                stock_scope = "scope=market"
                result = run_calendar_crawl(start_date=start, end_date=end)
            else:
                raise RuntimeError(f"未实现的任务: {task_id}")

            rows_affected = int(result.get("rows", 0))
            msg = f"{result.get('message', 'success')}; {stock_scope}"
            _finish_log(log_id, "success", msg, rows_affected)
            logger.info(f"task {task_id} log={log_id} done: {msg}")
        except Exception as e:
            logger.exception(f"task {task_id} failed")
            _finish_log(log_id, "failed", str(e), 0)

    import threading

    threading.Thread(target=_run_in_background, name=f"crawl-{task_id}-{log_id}", daemon=True).start()
    return {
        "ok": True,
        "log_id": log_id,
        "status": "running",
        "message": f"任务已提交后台执行 (log_id={log_id})",
    }


def _cleanup_stale_running_logs(task_id: str | None = None, max_minutes: int = 0):
    """清理遗留 running 日志。可按 task_id 限定；max_minutes<=0 表示不限制时间。"""
    try:
        conditions = ["status='running'"]
        params: list = [datetime.now()]
        if task_id:
            conditions.append("task_id=%s")
            params.append(task_id)
        if max_minutes and max_minutes > 0:
            conditions.append("started_at < DATE_SUB(NOW(), INTERVAL %s MINUTE)")
            params.append(max_minutes)
        where = " AND ".join(conditions)
        execute_update(
            f"""
            UPDATE trade_crawl_task_log
            SET status='failed',
                message=CONCAT(COALESCE(message, ''), ' | stale running cleaned'),
                finished_at=%s
            WHERE {where}
            """,
            tuple(params),
        )
    except Exception as e:
        logger.warning(f"cleanup stale logs failed: {e}")


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
