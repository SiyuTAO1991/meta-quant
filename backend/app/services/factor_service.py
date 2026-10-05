# -*- coding: utf-8 -*-
"""因子库服务：股票校验、数据补采、因子评价与历史落库。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from loguru import logger

from app.database import execute_query, execute_update, get_connection
from app.factors.evaluate import evaluate_factors
from app.factors.registry import list_categories, list_factor_meta
from app.schemas.common import serialize_row
from app.services.stock_service import (
    ensure_daily_data,
    get_daily_coverage,
    parse_stock_codes,
    verify_stock_exists,
)
from app.utils import normalize_date

LOOKBACK_BUFFER_DAYS = 180
MIN_BARS_PER_STOCK = 80
MIN_STOCKS_FOR_EVAL = 20
MAX_STOCKS_ALL_UNIVERSE = 3000


def get_factor_meta() -> dict[str, Any]:
    return {
        "factors": list_factor_meta(),
        "categories": ["全部"] + list_categories(),
        "holding_periods": [
            {"label": "5日", "value": 5},
            {"label": "10日", "value": 10},
            {"label": "20日", "value": 20},
            {"label": "60日", "value": 60},
        ],
        "universe_options": [
            {"label": "全A股", "value": "all"},
            {"label": "部分A股", "value": "custom"},
        ],
        "sort_options": [
            {"label": "|IR| (稳定性)", "value": "abs_ir"},
            {"label": "|IC| (强度)", "value": "abs_ic"},
            {"label": "IC均值", "value": "ic_mean"},
            {"label": "Q5-Q1", "value": "q5_q1"},
            {"label": "单调性", "value": "monotonicity"},
        ],
    }


def validate_stocks(stock_text: str) -> dict[str, Any]:
    """校验用户录入的股票代码是否存在。"""
    codes = parse_stock_codes(stock_text)
    valid: list[dict] = []
    invalid: list[dict] = []
    for code in codes:
        try:
            info = verify_stock_exists(code)
            valid.append(
                {
                    "ts_code": info.get("ts_code") or code,
                    "name": info.get("name") or "",
                }
            )
        except ValueError as e:
            invalid.append({"ts_code": code, "reason": str(e)})
    return {
        "ok": len(invalid) == 0,
        "valid": valid,
        "invalid": invalid,
        "count": len(valid),
    }


def _ensure_eval_tables() -> None:
    execute_update(
        """
        CREATE TABLE IF NOT EXISTS trade_factor_eval_job (
            id INT AUTO_INCREMENT PRIMARY KEY,
            universe VARCHAR(20) NOT NULL COMMENT 'all/custom',
            stock_codes TEXT COMMENT '部分A股代码，逗号分隔',
            stock_count INT DEFAULT 0 COMMENT '实际参评股票数',
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            holding_days INT NOT NULL DEFAULT 20,
            category VARCHAR(50) DEFAULT '全部',
            sort_by VARCHAR(50) DEFAULT 'abs_ir',
            keyword VARCHAR(100) DEFAULT '',
            factor_count INT DEFAULT 0,
            data_end DATE NULL COMMENT '当时日线数据截止日',
            crawl_triggered TINYINT DEFAULT 0,
            crawl_message VARCHAR(500) DEFAULT '',
            status VARCHAR(20) NOT NULL DEFAULT 'success',
            message VARCHAR(1000) DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            KEY idx_factor_eval_job_created (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='因子评价任务(条件)'
        """
    )
    execute_update(
        """
        CREATE TABLE IF NOT EXISTS trade_factor_eval_result (
            id INT AUTO_INCREMENT PRIMARY KEY,
            job_id INT NOT NULL,
            factor_code VARCHAR(50) NOT NULL,
            factor_name VARCHAR(100) NOT NULL,
            category VARCHAR(50) DEFAULT '',
            ic_mean DECIMAL(16,8) NULL,
            ir DECIMAL(16,8) NULL,
            ic_win_rate DECIMAL(10,6) NULL,
            q1_excess DECIMAL(16,8) NULL,
            q5_excess DECIMAL(16,8) NULL,
            q5_q1 DECIMAL(16,8) NULL,
            q5_turnover DECIMAL(10,6) NULL,
            monotonicity DECIMAL(10,6) NULL,
            sample_stocks INT DEFAULT 0,
            sample_periods INT DEFAULT 0,
            ok TINYINT DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            KEY idx_factor_eval_result_job (job_id),
            KEY idx_factor_eval_result_code (factor_code),
            KEY idx_factor_eval_result_created (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='因子评价结果'
        """
    )


def _list_universe_codes(universe: str, stock_codes: str | list[str] | None) -> list[str]:
    if universe == "custom":
        if not stock_codes:
            raise ValueError("部分A股模式下请录入股票代码")
        codes = parse_stock_codes(stock_codes)
        for code in codes:
            verify_stock_exists(code)
        return codes

    rows = execute_query(
        """
        SELECT stock_code, COUNT(*) AS cnt
        FROM trade_stock_daily
        GROUP BY stock_code
        HAVING COUNT(*) >= %s
        ORDER BY cnt DESC, stock_code
        LIMIT %s
        """,
        (MIN_BARS_PER_STOCK, MAX_STOCKS_ALL_UNIVERSE),
    )
    return [r["stock_code"] for r in rows if r.get("stock_code")]


def _ensure_data_ready(
    codes: list[str],
    start_date: str,
    end_date: str,
    *,
    universe: str,
) -> dict[str, Any]:
    """检查评价区间数据；不足时自动触发日线采集。"""
    start = normalize_date(start_date, as_dash=True)
    end = normalize_date(end_date, as_dash=True)
    lookback_start = (
        datetime.strptime(start, "%Y-%m-%d") - timedelta(days=LOOKBACK_BUFFER_DAYS)
    ).strftime("%Y-%m-%d")

    crawl_info: dict[str, Any] = {"triggered": False, "mode": None, "message": ""}

    if universe == "all":
        rows = execute_query(
            """
            SELECT COUNT(DISTINCT stock_code) AS n_stocks,
                   COUNT(DISTINCT trade_date) AS n_days
            FROM trade_stock_daily
            WHERE trade_date BETWEEN %s AND %s
            """,
            (lookback_start, end),
        )
        n_stocks = int((rows[0]["n_stocks"] if rows else 0) or 0)
        n_days = int((rows[0]["n_days"] if rows else 0) or 0)
        need_market = n_stocks < MIN_STOCKS_FOR_EVAL or n_days < 40
        if need_market:
            from app.collectors.daily import run_daily_crawl

            logger.info(
                f"factor auto market crawl: stocks={n_stocks} days={n_days} "
                f"range={lookback_start}~{end}"
            )
            result = run_daily_crawl(
                [],
                start_date=lookback_start.replace("-", ""),
                end_date=end.replace("-", ""),
                market=True,
            )
            crawl_info = {
                "triggered": True,
                "mode": "market",
                "message": result.get("message", ""),
                "rows": result.get("rows", 0),
            }
            codes = _list_universe_codes("all", None)
    else:
        need: list[str] = []
        for code in codes:
            cov = get_daily_coverage(code, lookback_start, end)
            if int(cov.get("count") or 0) < MIN_BARS_PER_STOCK:
                need.append(code)
        if need:
            logger.info(f"factor auto crawl {len(need)} stocks, range={lookback_start}~{end}")
            ensure_daily_data(need, lookback_start, end, min_bars=MIN_BARS_PER_STOCK)
            crawl_info = {
                "triggered": True,
                "mode": "by_stock",
                "message": f"补采 {len(need)} 只股票日线",
                "stocks": need,
            }

    return {
        "codes": codes,
        "load_start": lookback_start,
        "load_end": end,
        "eval_start": start,
        "crawl": crawl_info,
    }


def _load_price_map(codes: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    if not codes:
        return {}
    batch_size = 400
    frames: dict[str, list[dict]] = {}
    for i in range(0, len(codes), batch_size):
        batch = codes[i : i + batch_size]
        placeholders = ",".join(["%s"] * len(batch))
        rows = execute_query(
            f"""
            SELECT stock_code, trade_date, open_price, high_price, low_price,
                   close_price, volume
            FROM trade_stock_daily
            WHERE stock_code IN ({placeholders})
              AND trade_date BETWEEN %s AND %s
            ORDER BY stock_code, trade_date
            """,
            (*batch, start, end),
        )
        for r in rows:
            frames.setdefault(r["stock_code"], []).append(r)

    price_map: dict[str, pd.DataFrame] = {}
    for code, items in frames.items():
        if len(items) < MIN_BARS_PER_STOCK:
            continue
        df = pd.DataFrame(items)
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df = df.set_index("trade_date").sort_index()
        df = df.rename(
            columns={
                "open_price": "open",
                "high_price": "high",
                "low_price": "low",
                "close_price": "close",
                "volume": "volume",
            }
        )
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        price_map[code] = df[["open", "high", "low", "close", "volume"]]
    return price_map


def _sort_rows(rows: list[dict], sort_by: str) -> list[dict]:
    key = sort_by or "abs_ir"

    def score(r: dict) -> float:
        if key == "abs_ic":
            return abs(r.get("ic_mean") or 0)
        if key == "ic_mean":
            return float(r.get("ic_mean") or -999)
        if key == "q5_q1":
            return abs(r.get("q5_q1") or 0)
        if key == "monotonicity":
            return float(r.get("monotonicity") or 0)
        return abs(r.get("ir") or 0)

    return sorted(rows, key=score, reverse=True)


def _save_evaluation(
    *,
    universe: str,
    stock_codes_text: str,
    stock_count: int,
    start_date: str,
    end_date: str,
    holding_days: int,
    category: str,
    sort_by: str,
    keyword: str,
    rows: list[dict],
    data_end: str | None,
    crawl: dict[str, Any],
) -> int:
    """写入评价任务 + 因子结果，返回 job_id。"""
    _ensure_eval_tables()
    crawl_triggered = 1 if crawl.get("triggered") else 0
    crawl_message = str(crawl.get("message") or "")[:500]
    data_end_val = (data_end or "")[:10] or None

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO trade_factor_eval_job (
                    universe, stock_codes, stock_count, start_date, end_date,
                    holding_days, category, sort_by, keyword, factor_count,
                    data_end, crawl_triggered, crawl_message, status, message
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'success','')
                """,
                (
                    universe,
                    stock_codes_text or "",
                    stock_count,
                    start_date,
                    end_date,
                    holding_days,
                    category or "全部",
                    sort_by or "abs_ir",
                    keyword or "",
                    len(rows),
                    data_end_val,
                    crawl_triggered,
                    crawl_message,
                ),
            )
            job_id = int(cursor.lastrowid)

            result_rows = [
                (
                    job_id,
                    str(r.get("code") or ""),
                    str(r.get("name") or ""),
                    str(r.get("category") or ""),
                    r.get("ic_mean"),
                    r.get("ir"),
                    r.get("ic_win_rate"),
                    r.get("q1_excess"),
                    r.get("q5_excess"),
                    r.get("q5_q1"),
                    r.get("q5_turnover"),
                    r.get("monotonicity"),
                    int(r.get("sample_stocks") or 0),
                    int(r.get("sample_periods") or 0),
                    1 if r.get("ok") else 0,
                )
                for r in rows
            ]
            if result_rows:
                cursor.executemany(
                    """
                    INSERT INTO trade_factor_eval_result (
                        job_id, factor_code, factor_name, category,
                        ic_mean, ir, ic_win_rate, q1_excess, q5_excess,
                        q5_q1, q5_turnover, monotonicity,
                        sample_stocks, sample_periods, ok
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    result_rows,
                )
            conn.commit()
            return job_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_factor_results(page: int = 1, size: int = 10) -> dict[str, Any]:
    """平铺查询因子评价结果行（关联任务条件），按评价时间倒序，默认每页 10 条。"""
    _ensure_eval_tables()
    page = max(int(page or 1), 1)
    size = min(max(int(size or 10), 1), 100)
    offset = (page - 1) * size

    count_rows = execute_query("SELECT COUNT(*) AS cnt FROM trade_factor_eval_result")
    total = int(count_rows[0]["cnt"]) if count_rows else 0

    rows = execute_query(
        """
        SELECT
            r.id,
            r.job_id,
            r.factor_code AS code,
            r.factor_name AS name,
            r.category,
            r.ic_mean,
            r.ir,
            r.ic_win_rate,
            r.q1_excess,
            r.q5_excess,
            r.q5_q1,
            r.q5_turnover,
            r.monotonicity,
            r.sample_stocks,
            r.sample_periods,
            r.ok,
            j.universe,
            j.stock_codes,
            j.stock_count,
            j.start_date,
            j.end_date,
            j.holding_days,
            j.category AS job_category,
            j.sort_by,
            j.keyword AS job_keyword,
            j.data_end,
            j.crawl_triggered,
            j.created_at AS eval_time
        FROM trade_factor_eval_result r
        INNER JOIN trade_factor_eval_job j ON j.id = r.job_id
        ORDER BY j.created_at DESC, r.id DESC
        LIMIT %s OFFSET %s
        """,
        (size, offset),
    )

    items = []
    for row in rows:
        item = serialize_row(row)
        item["ok"] = bool(item.get("ok"))
        item["crawl_triggered"] = bool(item.get("crawl_triggered"))
        items.append(item)

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "thresholds": {
            "strong_ic": 0.03,
            "stable_ir": 0.5,
            "mono": 0.5,
        },
    }


def run_factor_evaluation(
    *,
    universe: str = "all",
    stock_codes: str | list[str] | None = None,
    start_date: str,
    end_date: str,
    holding_days: int = 20,
    category: str = "全部",
    sort_by: str = "abs_ir",
    keyword: str = "",
) -> dict[str, Any]:
    """执行因子评价并落库。"""
    if holding_days not in (5, 10, 20, 60):
        raise ValueError("调仓周期仅支持 5/10/20/60 日")
    if not start_date or not end_date:
        raise ValueError("请选择评价起止日期")

    start = normalize_date(start_date, as_dash=True)
    end = normalize_date(end_date, as_dash=True)
    if start > end:
        raise ValueError("开始日期不能晚于结束日期")

    universe = (universe or "all").strip().lower()
    if universe not in ("all", "custom"):
        raise ValueError("股票池仅支持 all / custom")

    codes = _list_universe_codes(universe, stock_codes)
    ready = _ensure_data_ready(codes, start, end, universe=universe)
    codes = ready["codes"] if universe == "all" else codes

    if universe == "all" and len(codes) < MIN_STOCKS_FOR_EVAL:
        raise ValueError(
            f"全A股可用股票不足（当前 {len(codes)} 只），请先采集日线或缩小区间后重试"
        )

    price_map = _load_price_map(codes, ready["load_start"], ready["load_end"])
    if len(price_map) < 10:
        raise ValueError(f"有效K线股票过少（{len(price_map)}），无法评价")

    logger.info(
        f"factor eval start: universe={universe} stocks={len(price_map)} "
        f"holding={holding_days} range={start}~{end}"
    )
    rows = evaluate_factors(price_map, holding_days=holding_days)

    if category and category != "全部":
        rows = [r for r in rows if r.get("category") == category]
    kw = (keyword or "").strip().lower()
    if kw:
        rows = [
            r
            for r in rows
            if kw in str(r.get("code", "")).lower()
            or kw in str(r.get("name", "")).lower()
        ]

    rows = _sort_rows(rows, sort_by)

    data_end = None
    max_rows = execute_query("SELECT MAX(trade_date) AS mx FROM trade_stock_daily")
    if max_rows and max_rows[0].get("mx"):
        mx = max_rows[0]["mx"]
        data_end = mx.isoformat() if hasattr(mx, "isoformat") else str(mx)

    if isinstance(stock_codes, list):
        stock_codes_text = ",".join(stock_codes)
    else:
        stock_codes_text = (stock_codes or "").strip()

    crawl = ready.get("crawl") or {}
    job_id = _save_evaluation(
        universe=universe,
        stock_codes_text=stock_codes_text,
        stock_count=len(price_map),
        start_date=start,
        end_date=end,
        holding_days=holding_days,
        category=category,
        sort_by=sort_by,
        keyword=keyword,
        rows=rows,
        data_end=data_end,
        crawl=crawl,
    )
    logger.info(f"factor eval saved job_id={job_id} factors={len(rows)}")

    return {
        "job_id": job_id,
        "items": rows,
        "total": len(rows),
        "universe": universe,
        "stock_count": len(price_map),
        "holding_days": holding_days,
        "start_date": start,
        "end_date": end,
        "data_end": data_end,
        "crawl": crawl,
        "thresholds": {
            "strong_ic": 0.03,
            "stable_ir": 0.5,
            "mono": 0.5,
        },
    }
