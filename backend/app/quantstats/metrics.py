# -*- coding: utf-8 -*-
"""
QuantStats 指标与序列（参考 CASE report_engine.calc_quantstats_metrics）。

基准为回测标的买入持有日收益（多标的等权），不使用固定指数。
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from loguru import logger


def equity_to_nav_series(equity_curve: list[dict], initial_cash: float | None = None) -> pd.Series:
    """equity_curve[{date, equity}] -> 归一化净值 Series（起点约 1.0）。"""
    if not equity_curve:
        return pd.Series(dtype=float)
    df = pd.DataFrame(equity_curve)
    if "equity" not in df.columns and "nav" in df.columns:
        df = df.rename(columns={"nav": "equity"})
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=["date", "equity"]).sort_values("date")
    df = df.drop_duplicates(subset=["date"], keep="last").set_index("date")
    equity = pd.to_numeric(df["equity"], errors="coerce").dropna()
    if equity.empty:
        return pd.Series(dtype=float)
    base = float(initial_cash) if initial_cash and initial_cash > 0 else float(equity.iloc[0])
    if base <= 0:
        base = float(equity.iloc[0])
    return equity / base


def nav_to_returns(nav_series: pd.Series) -> pd.Series:
    """净值 -> 日收益率。"""
    if nav_series is None or len(nav_series) < 2:
        return pd.Series(dtype=float)
    returns = nav_series.pct_change().dropna()
    returns.index = pd.to_datetime(returns.index)
    return returns


def buy_hold_returns_from_bars(stock_bars: dict[str, list[dict]]) -> pd.Series:
    """
    由回测标的日线构建买入持有等权日收益。
    单票：收盘价日收益；多票：各票日收益等权平均（仅在双方有数据的交易日）。
    """
    if not stock_bars:
        return pd.Series(dtype=float)

    series_list: list[pd.Series] = []
    for code, bars in stock_bars.items():
        if not bars:
            continue
        df = pd.DataFrame(bars)
        if "trade_date" not in df.columns or "close_price" not in df.columns:
            continue
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        close = pd.to_numeric(df["close_price"], errors="coerce")
        df = df.assign(close=close).dropna(subset=["trade_date", "close"])
        df = df[df["close"] > 0].drop_duplicates(subset=["trade_date"], keep="last")
        df = df.set_index("trade_date").sort_index()
        if len(df) < 2:
            continue
        ret = df["close"].pct_change().dropna()
        ret.name = code
        series_list.append(ret)

    if not series_list:
        return pd.Series(dtype=float)
    if len(series_list) == 1:
        out = series_list[0]
        out.index = pd.to_datetime(out.index)
        return out

    aligned = pd.concat(series_list, axis=1, join="inner")
    if aligned.empty:
        aligned = pd.concat(series_list, axis=1, join="outer")
    out = aligned.mean(axis=1, skipna=True).dropna()
    out.index = pd.to_datetime(out.index)
    out.name = "buy_hold"
    return out


def buy_hold_returns_from_dataframes(dataframes: dict[str, pd.DataFrame]) -> pd.Series:
    """由已转换的 OHLCV DataFrame 构建等权买入持有日收益。"""
    series_list: list[pd.Series] = []
    for code, df in (dataframes or {}).items():
        if df is None or df.empty or "close" not in df.columns:
            continue
        close = pd.to_numeric(df["close"], errors="coerce")
        close = close[close > 0].dropna()
        if len(close) < 2:
            continue
        ret = close.pct_change().dropna()
        ret.name = code
        series_list.append(ret)
    if not series_list:
        return pd.Series(dtype=float)
    if len(series_list) == 1:
        out = series_list[0]
        out.index = pd.to_datetime(out.index)
        return out
    aligned = pd.concat(series_list, axis=1, join="inner")
    out = aligned.mean(axis=1, skipna=True).dropna()
    out.index = pd.to_datetime(out.index)
    return out


def _safe(func, *args, default=0.0, **kwargs):
    try:
        val = func(*args, **kwargs)
        if val is None or (isinstance(val, float) and (np.isinf(val) or np.isnan(val))):
            return default
        return float(val)
    except Exception:
        return default


def calc_quantstats_metrics(returns: pd.Series, benchmark: pd.Series | None = None) -> dict[str, Any]:
    """计算 QuantStats 全量绩效指标。"""
    import quantstats as qs

    if returns is None or len(returns) < 2:
        return {}

    returns = returns.copy()
    returns.index = pd.to_datetime(returns.index)
    if float(returns.mean()) > 1:
        returns = returns.pct_change().dropna()

    metrics: dict[str, Any] = {
        "total_return": _safe(qs.stats.comp, returns),
        "cagr": _safe(qs.stats.cagr, returns),
        "best_day": float(returns.max()) if len(returns) else 0.0,
        "worst_day": float(returns.min()) if len(returns) else 0.0,
        "volatility": _safe(qs.stats.volatility, returns),
        "max_drawdown": _safe(qs.stats.max_drawdown, returns),
        "var_95": _safe(qs.stats.value_at_risk, returns),
        "cvar_95": _safe(qs.stats.cvar, returns),
        "sharpe": _safe(qs.stats.sharpe, returns),
        "sortino": _safe(qs.stats.sortino, returns),
        "calmar": _safe(qs.stats.calmar, returns),
        "omega": _safe(qs.stats.omega, returns, default=1.0),
        "gain_to_pain": _safe(qs.stats.gain_to_pain_ratio, returns),
        "skew": _safe(qs.stats.skew, returns),
        "kurtosis": _safe(qs.stats.kurtosis, returns),
        "win_rate": _safe(qs.stats.win_rate, returns, default=0.5),
        "avg_win": _safe(qs.stats.avg_win, returns),
        "avg_loss": _safe(qs.stats.avg_loss, returns),
        "profit_factor": _safe(qs.stats.profit_factor, returns, default=1.0),
        "payoff_ratio": _safe(qs.stats.payoff_ratio, returns, default=1.0),
        "consecutive_wins": _safe(qs.stats.consecutive_wins, returns, default=0),
        "consecutive_losses": _safe(qs.stats.consecutive_losses, returns, default=0),
    }

    if benchmark is not None and len(benchmark) > 20:
        try:
            benchmark = benchmark.copy()
            benchmark.index = pd.to_datetime(benchmark.index)
            common = returns.index.intersection(benchmark.index)
            if len(common) > 20:
                r = returns.loc[common]
                b = benchmark.loc[common]
                metrics["information_ratio"] = _safe(qs.stats.information_ratio, r, b)
                metrics["alpha"] = float(r.mean() * 252 - b.mean() * 252)
                cov = np.cov(r.values, b.values)
                metrics["beta"] = float(cov[0, 1] / cov[1, 1]) if cov[1, 1] > 0 else 0.0
                metrics["tracking_error"] = float((r - b).std() * np.sqrt(252))
                metrics["benchmark_total_return"] = _safe(qs.stats.comp, b)
        except Exception as e:
            logger.warning(f"quantstats benchmark metrics skipped: {e}")

    return {k: (None if v is None else round(float(v), 6)) for k, v in metrics.items()}


def _build_series(returns: pd.Series, benchmark: pd.Series | None) -> dict[str, Any]:
    """前端绘图用序列。"""
    if returns is None or returns.empty:
        return {}

    cum = (1 + returns).cumprod()
    peak = cum.cummax()
    dd = (cum - peak) / peak

    strategy_nav = [{"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 6)} for d, v in cum.items()]
    drawdown = [{"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 6)} for d, v in dd.items()]

    hold_nav: list[dict] = []
    if benchmark is not None and len(benchmark) > 1:
        common = returns.index.intersection(benchmark.index)
        if len(common) > 1:
            hold_cum = (1 + benchmark.loc[common]).cumprod()
            hold_nav = [
                {"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 6)} for d, v in hold_cum.items()
            ]

    monthly = returns.resample("ME").apply(lambda x: float((1 + x).prod() - 1) if len(x) else np.nan)
    monthly_rows: list[dict] = []
    if len(monthly):
        m_df = pd.DataFrame(
            {"year": monthly.index.year, "month": monthly.index.month, "return": monthly.values}
        )
        for year, g in m_df.groupby("year"):
            row = {"year": int(year)}
            for _, r in g.iterrows():
                row[f"m{int(r['month'])}"] = None if pd.isna(r["return"]) else round(float(r["return"]), 6)
            yearly = g["return"].dropna()
            if len(yearly):
                row["eoy"] = round(float((1 + yearly).prod() - 1), 6)
            monthly_rows.append(row)

    rolling_sharpe: list[dict] = []
    rolling_vol: list[dict] = []
    if len(returns) > 20:
        rs = returns.rolling(60).apply(
            lambda x: float(x.mean() / x.std() * np.sqrt(252)) if len(x) and x.std() > 0 else 0.0,
            raw=False,
        )
        rv = returns.rolling(20).std() * np.sqrt(252)
        for d, v in rs.dropna().items():
            rolling_sharpe.append({"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 6)})
        for d, v in rv.dropna().items():
            rolling_vol.append({"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 6)})

    return {
        "strategy_nav": strategy_nav,
        "hold_nav": hold_nav,
        "drawdown": drawdown,
        "monthly": monthly_rows,
        "rolling_sharpe": rolling_sharpe,
        "rolling_vol": rolling_vol,
    }


def analyze_from_equity(
    equity_curve: list[dict],
    *,
    initial_cash: float | None = None,
    stock_bars: dict[str, list[dict]] | None = None,
    dataframes: dict[str, pd.DataFrame] | None = None,
    engine_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    基于回测净值与标的日线，输出 QuantStats 评估结果。

    Returns:
        { ok, metrics, series, compare_with_engine, message }
    """
    try:
        nav = equity_to_nav_series(equity_curve, initial_cash=initial_cash)
        returns = nav_to_returns(nav)
        if len(returns) < 5:
            return {
                "ok": False,
                "metrics": {},
                "series": {},
                "compare_with_engine": {},
                "message": "净值样本不足，无法计算 QuantStats",
            }

        benchmark = None
        if dataframes:
            benchmark = buy_hold_returns_from_dataframes(dataframes)
        elif stock_bars:
            benchmark = buy_hold_returns_from_bars(stock_bars)

        if benchmark is not None and not benchmark.empty:
            common = returns.index.intersection(benchmark.index)
            if len(common) >= 5:
                returns_aligned = returns.loc[common]
                benchmark = benchmark.loc[common]
            else:
                returns_aligned = returns
                benchmark = None
        else:
            returns_aligned = returns
            benchmark = None

        metrics = calc_quantstats_metrics(returns_aligned, benchmark=benchmark)
        series = _build_series(returns_aligned, benchmark)

        compare: dict[str, Any] = {}
        if engine_metrics:
            compare = {
                "total_return": {
                    "engine": engine_metrics.get("total_return"),
                    "quantstats": metrics.get("total_return"),
                },
                "sharpe": {
                    "engine": engine_metrics.get("sharpe") or engine_metrics.get("sharpe_ratio"),
                    "quantstats": metrics.get("sharpe"),
                },
                "max_drawdown": {
                    "engine": engine_metrics.get("max_drawdown"),
                    "quantstats": metrics.get("max_drawdown"),
                },
            }

        return {
            "ok": True,
            "metrics": metrics,
            "series": series,
            "compare_with_engine": compare,
            "message": "ok",
            "n_days": int(len(returns_aligned)),
            "has_benchmark": benchmark is not None and len(benchmark) > 0,
        }
    except Exception as e:
        logger.exception("quantstats analyze failed")
        return {
            "ok": False,
            "metrics": {},
            "series": {},
            "compare_with_engine": {},
            "message": str(e),
        }
