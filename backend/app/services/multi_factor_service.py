# -*- coding: utf-8 -*-
"""多因子打分选股：可配置调仓周期回测服务。"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from loguru import logger

from app.database import execute_query
from app.factors.scoring import (
    batch_calc_factors,
    build_factor_config,
    list_default_factor_configs,
    select_top_stocks,
)
from app.services.stock_service import get_stock_name_map, parse_stock_codes, verify_stock_exists
from app.utils import normalize_date

DEFAULT_MAX_STOCKS = 800
MIN_BARS = 80
ALLOWED_HOLDING_DAYS = {0, 5, 10, 20, 60}


def get_multi_factor_meta() -> dict[str, Any]:
    return {
        "factors": list_default_factor_configs(),
        "universe_options": [
            {"label": "全A股", "value": "all"},
            {"label": "部分A股", "value": "custom"},
        ],
        "holding_periods": [
            {"label": "月末调仓", "value": 0},
            {"label": "5个交易日", "value": 5},
            {"label": "10个交易日", "value": 10},
            {"label": "20个交易日", "value": 20},
            {"label": "60个交易日", "value": 60},
        ],
        "defaults": {
            "top_n": 10,
            "cash": 1000000,
            "max_stocks": DEFAULT_MAX_STOCKS,
            "universe": "all",
            "holding_days": 0,
        },
    }


def _resolve_codes(_universe: str, stock_codes: str, max_stocks: int) -> list[str]:
    """股票代码为空时默认全A股；填写则按自定义股票池。"""
    text = (stock_codes or "").strip()
    if text:
        codes = parse_stock_codes(text)
        for code in codes:
            verify_stock_exists(code)
        return codes

    max_stocks = max(50, min(int(max_stocks or DEFAULT_MAX_STOCKS), 3000))
    rows = execute_query(
        """
        SELECT stock_code, COUNT(*) AS cnt
        FROM trade_stock_daily
        GROUP BY stock_code
        HAVING COUNT(*) >= %s
        ORDER BY cnt DESC, stock_code
        LIMIT %s
        """,
        (MIN_BARS, max_stocks),
    )
    return [r["stock_code"] for r in rows if r.get("stock_code")]


def _enrich_rebalance_names(rebalance_log: list[dict]) -> list[dict]:
    """为调仓持股补充股票名称。"""
    codes: list[str] = []
    seen: set[str] = set()
    for item in rebalance_log:
        for h in item.get("holdings") or []:
            code = h.get("stock_code")
            if code and code not in seen:
                seen.add(code)
                codes.append(code)
        for code in item.get("stocks") or []:
            if code and code not in seen:
                seen.add(code)
                codes.append(code)

    name_map = get_stock_name_map(codes) if codes else {}
    for item in rebalance_log:
        holdings = item.get("holdings") or []
        for h in holdings:
            code = h.get("stock_code") or ""
            name = name_map.get(code) or ""
            h["stock_name"] = name or code
        item["stock_names"] = [h.get("stock_name") or h.get("stock_code") for h in holdings]
        if not item.get("stock_names") and item.get("stocks"):
            item["stock_names"] = [name_map.get(c) or c for c in item["stocks"]]
    return rebalance_log


def _load_price_map(codes: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    if not codes:
        return {}
    # 预热：向前多取约半年（仅用于因子计算，不参与调仓日生成）
    lookback_start = (pd.Timestamp(start) - pd.Timedelta(days=200)).strftime("%Y-%m-%d")
    frames: dict[str, list[dict]] = {}
    batch = 400
    for i in range(0, len(codes), batch):
        part = codes[i : i + batch]
        placeholders = ",".join(["%s"] * len(part))
        rows = execute_query(
            f"""
            SELECT stock_code, trade_date, open_price, high_price, low_price,
                   close_price, volume
            FROM trade_stock_daily
            WHERE stock_code IN ({placeholders})
              AND trade_date BETWEEN %s AND %s
            ORDER BY stock_code, trade_date
            """,
            (*part, lookback_start, end),
        )
        for r in rows:
            frames.setdefault(r["stock_code"], []).append(r)

    price_map: dict[str, pd.DataFrame] = {}
    for code, items in frames.items():
        if len(items) < 60:
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
        in_range = df[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))]
        if len(in_range) < 20:
            continue
        price_map[code] = df[["open", "high", "low", "close", "volume"]]
    return price_map


def _month_end_dates(dates: list[pd.Timestamp]) -> list[pd.Timestamp]:
    """在给定交易日序列中取月末交易日。"""
    out: list[pd.Timestamp] = []
    for i, d in enumerate(dates):
        if i + 1 < len(dates) and dates[i + 1].month != d.month:
            out.append(d)
    return out


def _trading_calendar_to(end: str) -> list[pd.Timestamp]:
    """取库内截止 end 的完整交易日历，用于稳定 N 日调仓相位。"""
    rows = execute_query(
        """
        SELECT DISTINCT trade_date
        FROM trade_stock_daily
        WHERE trade_date <= %s
        ORDER BY trade_date
        """,
        (end,),
    )
    return [pd.Timestamp(r["trade_date"]) for r in rows if r.get("trade_date")]


def _build_rebalance_dates(
    all_dates: list[pd.Timestamp],
    start: str,
    end: str,
    holding_days: int,
) -> list[pd.Timestamp]:
    """
    仅在用户选择的 [start, end] 内生成调仓日。
    holding_days=0：月末；否则每 N 个交易日。

    重要：N 日调仓相位锚定「库内全局交易日历」，不随回测起点平移，
    从而同一结束日下，重叠区间的调仓日/选股可比。
    """
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    in_range = [d for d in all_dates if start_ts <= d <= end_ts]
    if len(in_range) < 2:
        raise ValueError("回测区间内交易日不足，请扩大区间或检查日线数据")

    if holding_days <= 0:
        rb = _month_end_dates(in_range)
    else:
        calendar = _trading_calendar_to(end)
        if len(calendar) < 2:
            calendar = [d for d in all_dates if d <= end_ts]
        grid = calendar[::holding_days]
        rb = [d for d in grid if start_ts <= d <= end_ts]

    if not rb:
        raise ValueError("所选区间内无可用调仓日，请扩大回测区间")

    # 区间末日仅作最后一期平仓日（不新开仓逻辑上由 loop 的 next 承担）
    if rb[-1] != in_range[-1]:
        rb.append(in_range[-1])

    if len(rb) < 2:
        raise ValueError("调仓期数不足，请扩大回测区间或缩短调仓周期")
    return rb


def periodic_rebalance_backtest(
    all_data: dict[str, pd.DataFrame],
    *,
    start: str,
    end: str,
    top_n: int = 10,
    initial_cash: float = 1_000_000,
    factor_config: dict | None = None,
    holding_days: int = 0,
) -> dict[str, Any]:
    """多因子定期调仓回测（调仓日严格落在回测区间内）。"""
    cash = float(initial_cash)
    top_n = max(1, int(top_n))
    holding_days = int(holding_days or 0)

    all_dates = sorted({pd.Timestamp(d) for df in all_data.values() for d in df.index})
    rebalance_dates = _build_rebalance_dates(all_dates, start, end, holding_days)

    nav = cash
    nav_log = [{"date": rebalance_dates[0].strftime("%Y-%m-%d"), "nav": nav}]
    rebalance_log: list[dict] = []

    for i in range(len(rebalance_dates) - 1):
        rb_date = rebalance_dates[i]
        next_rb = rebalance_dates[i + 1]

        period_data = {}
        for code, df in all_data.items():
            sub = df[df.index <= rb_date]
            if len(sub) >= 60:
                period_data[code] = sub

        if len(period_data) < top_n * 2:
            nav_log.append({"date": next_rb.strftime("%Y-%m-%d"), "nav": nav})
            continue

        factor_df = batch_calc_factors(period_data, calc_date=rb_date)
        if factor_df.empty or len(factor_df) < top_n:
            nav_log.append({"date": next_rb.strftime("%Y-%m-%d"), "nav": nav})
            continue

        scored, top_codes = select_top_stocks(factor_df, top_n=top_n, factor_config=factor_config)

        holdings = []
        returns = []
        for code in top_codes:
            df = all_data.get(code)
            if df is None or rb_date not in df.index or next_rb not in df.index:
                continue
            c1 = float(df.loc[rb_date, "close"])
            c2 = float(df.loc[next_rb, "close"])
            if c1 <= 0:
                continue
            ret = c2 / c1 - 1.0
            returns.append(ret)
            score_val = None
            if code in scored.index:
                score_val = float(scored.loc[code, "score"])
            holdings.append(
                {
                    "stock_code": code,
                    "score": score_val,
                    "period_return": ret,
                    "buy_price": c1,
                    "sell_price": c2,
                    "weight": 0.0,
                }
            )

        if holdings:
            w = 1.0 / len(holdings)
            for h in holdings:
                h["weight"] = w
            port_return = float(np.mean(returns)) if returns else 0.0
            nav *= 1 + port_return
        else:
            port_return = 0.0

        nav_log.append({"date": next_rb.strftime("%Y-%m-%d"), "nav": nav})
        rebalance_log.append(
            {
                "date": rb_date.strftime("%Y-%m-%d"),
                "next_date": next_rb.strftime("%Y-%m-%d"),
                "stocks": [h["stock_code"] for h in holdings],
                "holdings": holdings,
                "return": port_return,
                "nav": nav,
                "stock_count": len(holdings),
            }
        )

    return {
        "nav_log": nav_log,
        "rebalance_log": rebalance_log,
        "final_nav": nav,
        "initial_cash": cash,
        "holding_days": holding_days,
        "rebalance_start": rebalance_dates[0].strftime("%Y-%m-%d"),
        "rebalance_end": rebalance_dates[-1].strftime("%Y-%m-%d"),
    }


def calc_backtest_metrics(result: dict[str, Any], holding_days: int = 0) -> dict[str, Any]:
    cash = float(result["initial_cash"])
    nav_log = result["nav_log"]
    if len(nav_log) < 2:
        return {}

    navs = [float(x["nav"]) for x in nav_log]
    dates = [pd.Timestamp(x["date"]) for x in nav_log]

    total_return = navs[-1] / cash - 1
    trading_days = (dates[-1] - dates[0]).days
    years = trading_days / 365.25 if trading_days > 0 else 1
    if years > 0 and total_return > -1:
        annual_return = (1 + total_return) ** (1 / years) - 1
    else:
        annual_return = total_return

    peak = navs[0]
    max_dd = 0.0
    for v in navs:
        if v > peak:
            peak = v
        if peak > 0:
            max_dd = max(max_dd, (peak - v) / peak)

    period_rets = [float(r["return"]) for r in result["rebalance_log"]]
    if holding_days and holding_days > 0:
        periods_per_year = 252.0 / holding_days
    else:
        periods_per_year = 12.0

    if period_rets:
        avg_ret = float(np.mean(period_rets))
        std_ret = float(np.std(period_rets))
        sharpe = (
            float((avg_ret * periods_per_year - 0.02) / (std_ret * np.sqrt(periods_per_year)))
            if std_ret > 0
            else 0.0
        )
        win_rate = float(sum(1 for r in period_rets if r > 0) / len(period_rets))
    else:
        sharpe = 0.0
        win_rate = 0.0

    calmar = float(annual_return / max_dd) if max_dd > 0 else 0.0

    peak = navs[0]
    drawdown_curve = []
    for i, v in enumerate(navs):
        if v > peak:
            peak = v
        dd = (v - peak) / peak if peak > 0 else 0.0
        drawdown_curve.append({"date": nav_log[i]["date"], "drawdown": float(dd)})

    equity_curve = [{"date": x["date"], "equity": float(x["nav"])} for x in nav_log]

    return {
        "total_return": float(total_return),
        "annual_return": float(annual_return),
        "max_drawdown": float(max_dd),
        "sharpe": round(sharpe, 4),
        "calmar": round(calmar, 4),
        "win_rate": float(win_rate),
        "periods": len(period_rets),
        "years": round(float(years), 2),
        "final_value": float(navs[-1]),
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
    }


def run_multi_factor_backtest(
    *,
    start_date: str,
    end_date: str,
    top_n: int = 10,
    cash: float = 1_000_000,
    universe: str = "all",
    stock_codes: str = "",
    max_stocks: int = DEFAULT_MAX_STOCKS,
    holding_days: int = 0,
    factor_weights: list[dict] | None = None,
) -> dict[str, Any]:
    """执行多因子定期调仓回测。"""
    if not start_date or not end_date:
        raise ValueError("请选择回测区间")
    start = normalize_date(start_date, as_dash=True)
    end = normalize_date(end_date, as_dash=True)
    if start > end:
        raise ValueError("开始日期不能晚于结束日期")

    top_n = max(1, min(int(top_n or 10), 100))
    cash = float(cash or 1_000_000)
    if cash < 1000:
        raise ValueError("初始资金过小")

    holding_days = int(holding_days if holding_days is not None else 0)
    if holding_days not in ALLOWED_HOLDING_DAYS:
        raise ValueError("调仓周期仅支持：月末 / 5 / 10 / 20 / 60 个交易日")

    factor_config = build_factor_config(factor_weights)
    codes = _resolve_codes(universe, stock_codes, max_stocks)
    resolved_universe = "custom" if (stock_codes or "").strip() else "all"
    if len(codes) < top_n * 2:
        raise ValueError(f"股票池过小（{len(codes)}），请扩大股票池或减小 Top-N")

    logger.info(
        f"multi-factor backtest: universe={resolved_universe} codes={len(codes)} "
        f"top_n={top_n} holding_days={holding_days} range={start}~{end} "
        f"factors={list(factor_config.keys())}"
    )
    price_map = _load_price_map(codes, start, end)
    if len(price_map) < top_n * 2:
        raise ValueError(
            f"有效K线股票过少（{len(price_map)}），请先采集日线或调整区间/股票池"
        )

    result = periodic_rebalance_backtest(
        price_map,
        start=start,
        end=end,
        top_n=top_n,
        initial_cash=cash,
        factor_config=factor_config,
        holding_days=holding_days,
    )
    metrics = calc_backtest_metrics(result, holding_days=holding_days)
    rebalance_log = _enrich_rebalance_names(result["rebalance_log"])

    used_factors = [
        {
            "code": code,
            "name": cfg["name"],
            "direction": cfg["direction"],
            "weight": round(float(cfg["weight"]), 6),
            "desc": cfg.get("desc", ""),
        }
        for code, cfg in factor_config.items()
    ]

    return {
        "params": {
            "universe": resolved_universe,
            "stock_codes": stock_codes or "",
            "start_date": start,
            "end_date": end,
            "top_n": top_n,
            "cash": cash,
            "max_stocks": max_stocks,
            "holding_days": holding_days,
            "holding_label": "月末调仓" if holding_days <= 0 else f"{holding_days}个交易日",
            "stock_universe_size": len(price_map),
            "rebalance_start": result.get("rebalance_start"),
            "rebalance_end": result.get("rebalance_end"),
            "factors": used_factors,
        },
        "metrics": metrics,
        "equity_curve": metrics.get("equity_curve") or [],
        "drawdown_curve": metrics.get("drawdown_curve") or [],
        "rebalance_log": rebalance_log,
        "final_nav": result["final_nav"],
    }
