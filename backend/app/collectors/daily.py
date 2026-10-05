# -*- coding: utf-8 -*-
"""日线行情采集（Tushare）。"""
from __future__ import annotations

from datetime import date

import pandas as pd
import tushare as ts
from loguru import logger

from app.config import get_settings
from app.database import execute_many, execute_query

INSERT_SQL = """
    INSERT INTO trade_stock_daily
    (stock_code, trade_date, open_price, high_price, low_price, close_price, volume, amount, turnover_rate)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
    open_price=VALUES(open_price), high_price=VALUES(high_price),
    low_price=VALUES(low_price), close_price=VALUES(close_price),
    volume=VALUES(volume), amount=VALUES(amount),
    turnover_rate=VALUES(turnover_rate)
"""

# 超过该数量时走按交易日全市场接口，避免逐票 pro_bar 过慢
_MARKET_MODE_THRESHOLD = 100


def _get_pro():
    token = get_settings().tushare_token
    if not token:
        raise RuntimeError("未配置 TUSHARE_TOKEN")
    ts.set_token(token.strip())
    return ts.pro_api()


def _is_etf(stock_code: str) -> bool:
    symbol = stock_code.split(".")[0]
    return symbol.startswith(("15", "16", "51", "56", "58"))


def _latest_dates() -> dict[str, str]:
    try:
        rows = execute_query(
            "SELECT stock_code, MAX(trade_date) AS max_date FROM trade_stock_daily GROUP BY stock_code"
        )
        result = {}
        for r in rows:
            if r["max_date"]:
                result[r["stock_code"]] = r["max_date"].strftime("%Y%m%d")
        return result
    except Exception as e:
        logger.warning(f"query latest dates failed: {e}")
        return {}


def _fetch_daily(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    if _is_etf(stock_code):
        df = _get_pro().fund_daily(ts_code=stock_code, start_date=start_date, end_date=end_date)
    else:
        df = ts.pro_bar(ts_code=stock_code, start_date=start_date, end_date=end_date, adj="qfq", freq="D")
    return df


def _df_to_rows(df: pd.DataFrame, code_col: str = "ts_code") -> list[tuple]:
    if df is None or len(df) == 0:
        return []
    work = df.rename(columns={"trade_date": "date", "vol": "volume"})
    work["date"] = pd.to_datetime(work["date"], format="%Y%m%d")
    rows: list[tuple] = []
    for _, row in work.iterrows():
        code = str(row.get(code_col) or row.get("stock_code") or "")
        if not code:
            continue
        rows.append(
            (
                code,
                row["date"].strftime("%Y-%m-%d"),
                float(row.get("open", 0) or 0),
                float(row.get("high", 0) or 0),
                float(row.get("low", 0) or 0),
                float(row.get("close", 0) or 0),
                int(row.get("volume", 0) or 0),
                float(row.get("amount", 0) or 0),
                None,
            )
        )
    return rows


def _open_trade_dates(start: str, end: str) -> list[str]:
    pro = _get_pro()
    cal = pro.trade_cal(exchange="SSE", start_date=start, end_date=end, is_open="1")
    if cal is None or len(cal) == 0:
        return []
    return [str(d) for d in cal["cal_date"].tolist()]


def _latest_adj_map(as_of: str) -> dict[str, float]:
    """取 as_of 当日（或往前找最近交易日）的复权因子，用于前复权。"""
    pro = _get_pro()
    for _ in range(10):
        adj = pro.adj_factor(trade_date=as_of)
        if adj is not None and len(adj) > 0:
            return {
                str(r.ts_code): float(r.adj_factor)
                for r in adj.itertuples(index=False)
                if r.adj_factor is not None and float(r.adj_factor) != 0
            }
        # 非交易日往前一天
        dt = pd.to_datetime(as_of)
        as_of = (dt - pd.Timedelta(days=1)).strftime("%Y%m%d")
    return {}


def _apply_qfq(daily: pd.DataFrame, day_adj: pd.DataFrame, latest_adj: dict[str, float]) -> pd.DataFrame:
    if daily is None or len(daily) == 0:
        return daily
    merged = daily.merge(day_adj[["ts_code", "adj_factor"]], on="ts_code", how="left")
    merged["latest_adj"] = merged["ts_code"].map(latest_adj)
    # 无复权因子时保留原价
    ratio = merged["adj_factor"] / merged["latest_adj"]
    ratio = ratio.fillna(1.0)
    for col in ("open", "high", "low", "close"):
        if col in merged.columns:
            merged[col] = merged[col] * ratio
    return merged


def _run_daily_market(start: str, end: str) -> dict:
    """按交易日全市场采集（适合留空股票代码）。"""
    dates = _open_trade_dates(start, end)
    if not dates:
        return {
            "rows": 0,
            "message": f"range={start}~{end}, success=0, failed=0, fetched=0, affected=0（区间无交易日）",
            "failed": [],
        }

    latest_adj = _latest_adj_map(end)
    logger.info(f"daily market crawl: {len(dates)} trade days, {start}~{end}, adj_map={len(latest_adj)}")

    pro = _get_pro()
    total_fetched = 0
    total_affected = 0
    success_days = 0
    failed_days: list[str] = []

    for i, d in enumerate(dates, 1):
        try:
            daily = pro.daily(trade_date=d)
            if daily is None or len(daily) == 0:
                success_days += 1
                continue
            day_adj = pro.adj_factor(trade_date=d)
            if day_adj is None or len(day_adj) == 0:
                day_adj = pd.DataFrame(columns=["ts_code", "adj_factor"])
            qfq = _apply_qfq(daily, day_adj, latest_adj)
            rows = _df_to_rows(qfq, code_col="ts_code")
            total_fetched += len(rows)
            total_affected += execute_many(INSERT_SQL, rows)
            success_days += 1
            if i % 5 == 0 or i == len(dates):
                logger.info(
                    f"daily market progress {i}/{len(dates)} date={d} "
                    f"fetched={total_fetched} affected={total_affected}"
                )
        except Exception as e:
            logger.error(f"daily market crawl {d} failed: {e}")
            failed_days.append(d)

    note = ""
    if total_fetched > 0 and total_affected == 0:
        note = "（区间数据已存在，无新增/变更）"
    elif total_fetched == 0 and success_days > 0:
        note = "（接口无返回或区间无交易日）"

    return {
        "rows": total_affected,
        "message": (
            f"range={start}~{end}, success={success_days}, failed={len(failed_days)}, "
            f"fetched={total_fetched}, affected={total_affected}{note}; mode=market_by_date"
        ),
        "failed": failed_days,
    }


def _run_daily_by_stock(codes: list[str], start_date: str | None, end: str) -> dict:
    existing = _latest_dates()
    total_fetched = 0
    total_affected = 0
    success = 0
    failed: list[str] = []

    logger.info(f"daily stock crawl: {len(codes)} stocks, start={start_date or 'auto'}, end={end}")

    for code in codes:
        if start_date:
            start = start_date.replace("-", "")
        else:
            start = existing.get(code, "20250101")
        try:
            df = _fetch_daily(code, start, end)
            if df is None or len(df) == 0:
                success += 1
                continue
            # pro_bar 结果通常已是单票，补 ts_code 便于统一落库
            if "ts_code" not in df.columns:
                df = df.copy()
                df["ts_code"] = code
            rows = _df_to_rows(df, code_col="ts_code")
            # 若接口未带 ts_code，强制使用入参 code
            rows = [
                (code, r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8])
                for r in rows
            ]
            total_fetched += len(rows)
            total_affected += execute_many(INSERT_SQL, rows)
            success += 1
        except Exception as e:
            logger.error(f"daily crawl {code} failed: {e}")
            failed.append(code)

    note = ""
    if total_fetched > 0 and total_affected == 0:
        note = "（区间数据已存在，无新增/变更）"
    elif total_fetched == 0 and success > 0:
        note = "（接口无返回或区间无交易日）"

    return {
        "rows": total_affected,
        "message": (
            f"range={start_date or 'auto'}~{end}, "
            f"success={success}, failed={len(failed)}, "
            f"fetched={total_fetched}, affected={total_affected}{note}"
        ),
        "failed": failed,
    }


def run_daily_crawl(
    stock_codes: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    *,
    market: bool = False,
) -> dict:
    settings = get_settings()
    codes = stock_codes if stock_codes is not None else settings.default_stocks
    end = (end_date or date.today().strftime("%Y%m%d")).replace("-", "")
    start = (start_date or "").replace("-", "") if start_date else ""

    # 留空股票 / 显式 market / 超大股票列表 → 按交易日全市场
    if market or (start and len(codes) >= _MARKET_MODE_THRESHOLD):
        if not start:
            start = "20250101"
        return _run_daily_market(start, end)

    return _run_daily_by_stock(codes, start_date, end)
