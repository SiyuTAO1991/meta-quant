# -*- coding: utf-8 -*-
"""行情查询服务。"""
from __future__ import annotations

import re
from typing import Iterable

from loguru import logger

from app.database import execute_query
from app.schemas.common import serialize_row
from app.utils import normalize_date

_TS_CODE_RE = re.compile(r"^\d{6}\.(SH|SZ|BJ)$")
_MIN_BACKTEST_BARS = 20


def normalize_ts_code(code: str) -> str:
    """校验并规范化股票代码，如 600519.SH。"""
    text = (code or "").strip().upper()
    if not _TS_CODE_RE.match(text):
        raise ValueError(f"股票代码格式错误: {code}，请使用如 600519.SH")
    return text


def parse_stock_codes(stock_list: Iterable[str] | str) -> list[str]:
    """解析股票代码列表，支持逗号/空格/中文逗号分隔。"""
    if isinstance(stock_list, str):
        raw_parts = re.split(r"[,，\s]+", stock_list.strip())
    else:
        raw_parts = []
        for item in stock_list:
            if not item:
                continue
            if isinstance(item, str) and re.search(r"[,，\s]", item):
                raw_parts.extend(re.split(r"[,，\s]+", item.strip()))
            else:
                raw_parts.append(str(item))

    codes: list[str] = []
    seen: set[str] = set()
    for part in raw_parts:
        part = part.strip()
        if not part:
            continue
        code = normalize_ts_code(part)
        if code not in seen:
            seen.add(code)
            codes.append(code)
    if not codes:
        raise ValueError("请填写至少一个股票代码")
    return codes


def verify_stock_exists(ts_code: str) -> dict:
    """通过 Tushare 校验股票是否存在且处于上市状态。"""
    try:
        from app.collectors.daily import _get_pro

        pro = _get_pro()
        df = pro.stock_basic(ts_code=ts_code, fields="ts_code,name,list_status")
        if df is None or len(df) == 0:
            raise ValueError(f"股票代码不存在: {ts_code}")
        row = df.iloc[0]
        if str(row.get("list_status") or "") != "L":
            raise ValueError(f"股票 {ts_code} 当前非上市状态，无法回测")
        return {"ts_code": ts_code, "name": str(row.get("name") or "")}
    except ValueError:
        raise
    except Exception as e:
        logger.warning(f"verify stock via tushare failed {ts_code}: {e}")
        rows = execute_query(
            "SELECT COUNT(1) AS cnt FROM trade_stock_daily WHERE stock_code = %s LIMIT 1",
            (ts_code,),
        )
        if rows and int(rows[0]["cnt"]) > 0:
            return {"ts_code": ts_code, "name": ""}
        raise ValueError(f"无法校验股票 {ts_code}，请检查 TUSHARE_TOKEN 配置或先采集数据") from e


def get_daily_coverage(ts_code: str, start_date: str, end_date: str) -> dict:
    """查询指定区间内日线覆盖情况。"""
    start = normalize_date(start_date, as_dash=True)
    end = normalize_date(end_date, as_dash=True)
    rows = execute_query(
        """
        SELECT COUNT(1) AS cnt, MIN(trade_date) AS min_date, MAX(trade_date) AS max_date
        FROM trade_stock_daily
        WHERE stock_code = %s AND trade_date BETWEEN %s AND %s
        """,
        (ts_code, start, end),
    )
    row = rows[0] if rows else {}
    count = int(row.get("cnt") or 0)
    min_date = row.get("min_date")
    max_date = row.get("max_date")
    return {
        "ts_code": ts_code,
        "count": count,
        "min_date": min_date.isoformat() if min_date else None,
        "max_date": max_date.isoformat() if max_date else None,
        "sufficient": count >= _MIN_BACKTEST_BARS,
    }


def ensure_daily_data(
    stock_list: Iterable[str] | str,
    start_date: str,
    end_date: str,
    min_bars: int = _MIN_BACKTEST_BARS,
) -> list[str]:
    """
    回测前数据保障：
    1. 校验股票代码格式与是否存在
    2. 检查库内日线是否满足回测区间
    3. 不足时同步调用日线采集补齐后再继续
    """
    codes = parse_stock_codes(stock_list)
    start = normalize_date(start_date, as_dash=True)
    end = normalize_date(end_date, as_dash=True)

    for code in codes:
        verify_stock_exists(code)

    need_crawl: list[str] = []
    for code in codes:
        coverage = get_daily_coverage(code, start, end)
        if coverage["count"] < min_bars:
            need_crawl.append(code)
            logger.info(
                f"backtest data insufficient {code}: count={coverage['count']} "
                f"range={coverage['min_date']}~{coverage['max_date']}"
            )

    if need_crawl:
        from app.collectors.daily import run_daily_crawl

        logger.info(f"backtest auto crawl daily_bar for {need_crawl}, range={start}~{end}")
        result = run_daily_crawl(
            need_crawl,
            start_date=start.replace("-", ""),
            end_date=end.replace("-", ""),
        )
        failed = result.get("failed") or []
        if failed:
            raise ValueError(f"自动采集失败: {', '.join(failed)}")

        still_bad: list[str] = []
        for code in need_crawl:
            coverage = get_daily_coverage(code, start, end)
            if coverage["count"] < min_bars:
                still_bad.append(f"{code}(仅{coverage['count']}条)")
        if still_bad:
            raise ValueError(
                f"采集后数据仍不足以回测: {', '.join(still_bad)}，请检查 TUSHARE_TOKEN 或调整回测区间"
            )

    return codes


def query_stock_daily(ts_code: str, start_date: str, end_date: str) -> list[dict]:
    start = normalize_date(start_date, as_dash=True)
    end = normalize_date(end_date, as_dash=True)
    sql = """
        SELECT stock_code, trade_date, open_price, high_price, low_price,
               close_price, volume, amount, turnover_rate
        FROM trade_stock_daily
        WHERE stock_code = %s AND trade_date BETWEEN %s AND %s
        ORDER BY trade_date ASC
    """
    rows = execute_query(sql, (ts_code, start, end))
    return [serialize_row(r) for r in rows]


def query_index_daily(index_code: str, start_date: str, end_date: str) -> list[dict]:
    """指数日线：优先查库；库中无数据时返回空列表（可由采集补齐）。"""
    return query_stock_daily(index_code, start_date, end_date)


def query_stock_concepts(ts_code: str) -> list[dict]:
    """概念板块：尝试 AkShare，失败则返回空。"""
    try:
        import akshare as ak

        symbol = ts_code.split(".")[0]
        df = ak.stock_board_concept_name_em()
        # 简化：返回热门概念列表（个股所属概念接口不稳定时的兜底）
        if df is None or len(df) == 0:
            return []
        items = []
        for _, row in df.head(30).iterrows():
            items.append(
                {
                    "ts_code": ts_code,
                    "concept_name": str(row.get("板块名称") or row.iloc[1]),
                    "symbol": symbol,
                }
            )
        return items
    except Exception as e:
        logger.warning(f"concept query failed: {e}")
        return []


def list_available_stocks(limit: int = 50) -> list[str]:
    rows = execute_query(
        "SELECT DISTINCT stock_code FROM trade_stock_daily ORDER BY stock_code LIMIT %s",
        (limit,),
    )
    return [r["stock_code"] for r in rows]
