# -*- coding: utf-8 -*-
"""
因子评价引擎。

参考训练营《4-多因子评价框架》:
  - Rank IC / IR
  - 五分位分层超额
  - 单调性
  - Q5 换手
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd
from loguru import logger

from app.factors.registry import FACTOR_REGISTRY


def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    """Spearman 相关（不依赖 scipy）。"""
    if len(x) < 5:
        return float("nan")
    sx = pd.Series(x).rank().values
    sy = pd.Series(y).rank().values
    if np.nanstd(sx) == 0 or np.nanstd(sy) == 0:
        return float("nan")
    return float(np.corrcoef(sx, sy)[0, 1])


def _rebalance_dates(all_dates: list[pd.Timestamp], holding_days: int) -> list[pd.Timestamp]:
    """按调仓周期从交易日序列取样（预留足够回看与持有窗口）。"""
    if holding_days <= 0:
        holding_days = 20
    # 至少预留 60 根用于因子计算，末尾预留 holding_days
    start_idx = 60
    end_idx = len(all_dates) - holding_days - 1
    if end_idx <= start_idx:
        return []
    dates = []
    i = start_idx
    while i <= end_idx:
        dates.append(all_dates[i])
        i += holding_days
    return dates


def _monotonicity(q_means: list[float]) -> float:
    """
    单调性: 相邻分位收益同向变化的比例。
    Q1→Q5 递增或递减均可，取较强方向。
    """
    if len(q_means) < 2:
        return 0.0
    diffs = np.diff(q_means)
    if np.all(np.isnan(diffs)):
        return 0.0
    up = np.nansum(diffs > 0)
    down = np.nansum(diffs < 0)
    total = up + down
    if total == 0:
        return 0.0
    return float(max(up, down) / total)


def _turnover(prev: set[str], curr: set[str]) -> float:
    if not prev and not curr:
        return 0.0
    if not prev:
        return 1.0
    changed = len(prev.symmetric_difference(curr)) / 2.0
    return float(changed / max(len(prev), 1))


def compute_factor_panel(
    price_map: dict[str, pd.DataFrame],
    factor_codes: Iterable[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """
    计算因子面板。

    Args:
        price_map: {ts_code: DataFrame(index=date, columns=open/high/low/close/volume)}
        factor_codes: 指定因子；默认全部

    Returns:
        {factor_code: DataFrame(index=date, columns=ts_code)}
    """
    codes = list(factor_codes) if factor_codes else list(FACTOR_REGISTRY.keys())
    panels: dict[str, dict[str, pd.Series]] = {fc: {} for fc in codes}

    for ts_code, df in price_map.items():
        if df is None or len(df) < 30:
            continue
        work = df.sort_index()
        for fc in codes:
            meta = FACTOR_REGISTRY.get(fc)
            if not meta:
                continue
            if len(work) < int(meta.get("min_bars", 30)):
                continue
            try:
                series = meta["compute"](work)
                panels[fc][ts_code] = series
            except Exception as e:
                logger.debug(f"factor {fc} compute failed {ts_code}: {e}")

    result: dict[str, pd.DataFrame] = {}
    for fc, series_map in panels.items():
        if not series_map:
            continue
        result[fc] = pd.DataFrame(series_map).sort_index()
    return result


def evaluate_single_factor(
    factor_panel: pd.DataFrame,
    forward_returns: pd.DataFrame,
    holding_days: int,
    rebalance_dates: list[pd.Timestamp],
) -> dict:
    """
    对单因子做截面 IC + 五分位评价。

    Args:
        factor_panel: index=date, columns=ts_code
        forward_returns: 同形状，值为未来 holding_days 收益
        holding_days: 持有期
        rebalance_dates: 调仓日列表
    """
    ic_list: list[float] = []
    q_excess_hist = {i: [] for i in range(1, 6)}
    q5_members_prev: set[str] = set()
    turnover_list: list[float] = []
    n_stocks_list: list[int] = []

    for dt in rebalance_dates:
        if dt not in factor_panel.index or dt not in forward_returns.index:
            continue
        frow = factor_panel.loc[dt].dropna()
        rrow = forward_returns.loc[dt].dropna()
        common = frow.index.intersection(rrow.index)
        # 截面样本过少则跳过；自定义小股票池也需能跑通
        if len(common) < 10:
            continue

        fv = frow.loc[common].astype(float)
        rv = rrow.loc[common].astype(float)
        ic = _spearman(fv.values, rv.values)
        if np.isnan(ic):
            continue
        ic_list.append(ic)
        n_stocks_list.append(len(common))

        # 五分位：Q1=因子最小，Q5=因子最大
        try:
            labels = pd.qcut(fv, 5, labels=False, duplicates="drop")
        except ValueError:
            continue
        if labels.nunique() < 5:
            continue

        mkt = float(rv.mean())
        q_sets: dict[int, set[str]] = {}
        for q in range(5):
            members = set(labels[labels == q].index.tolist())
            q_sets[q + 1] = members
            if not members:
                q_excess_hist[q + 1].append(np.nan)
                continue
            q_ret = float(rv.loc[list(members)].mean())
            q_excess_hist[q + 1].append(q_ret - mkt)

        turnover_list.append(_turnover(q5_members_prev, q_sets.get(5, set())))
        q5_members_prev = q5_sets if (q5_sets := q_sets.get(5, set())) else set()

    if not ic_list:
        return {
            "ic_mean": None,
            "ir": None,
            "ic_win_rate": None,
            "q1_excess": None,
            "q5_excess": None,
            "q5_q1": None,
            "q5_turnover": None,
            "monotonicity": None,
            "sample_stocks": 0,
            "sample_periods": 0,
            "ok": False,
        }

    ic_arr = np.array(ic_list, dtype=float)
    ic_mean = float(np.nanmean(ic_arr))
    ic_std = float(np.nanstd(ic_arr, ddof=1)) if len(ic_arr) > 1 else 0.0
    ir = float(ic_mean / ic_std) if ic_std > 1e-12 else 0.0
    ic_win = float(np.mean(ic_arr > 0))

    q_means = []
    for q in range(1, 6):
        vals = np.array(q_excess_hist[q], dtype=float)
        q_means.append(float(np.nanmean(vals)) if len(vals) else float("nan"))

    q1 = q_means[0]
    q5 = q_means[4]
    mono = _monotonicity(q_means)
    q5_to = float(np.nanmean(turnover_list)) if turnover_list else 0.0

    return {
        "ic_mean": ic_mean,
        "ir": ir,
        "ic_win_rate": ic_win,
        "q1_excess": q1,
        "q5_excess": q5,
        "q5_q1": (q5 - q1) if (q5 == q5 and q1 == q1) else None,
        "q5_turnover": q5_to,
        "monotonicity": mono,
        "sample_stocks": int(np.median(n_stocks_list)) if n_stocks_list else 0,
        "sample_periods": len(ic_list),
        "ok": True,
    }


def build_forward_returns(
    price_map: dict[str, pd.DataFrame],
    holding_days: int,
) -> pd.DataFrame:
    """构建未来 N 日收益面板。"""
    series_map = {}
    for code, df in price_map.items():
        if df is None or "close" not in df.columns or len(df) <= holding_days:
            continue
        close = df["close"].astype(float).sort_index()
        fwd = close.shift(-holding_days) / close - 1.0
        series_map[code] = fwd
    if not series_map:
        return pd.DataFrame()
    return pd.DataFrame(series_map).sort_index()


def evaluate_factors(
    price_map: dict[str, pd.DataFrame],
    holding_days: int = 20,
    factor_codes: list[str] | None = None,
) -> list[dict]:
    """
    批量评价因子。

    Returns:
        因子评价结果列表（含元数据）
    """
    if not price_map:
        return []

    all_dates = sorted({d for df in price_map.values() if df is not None for d in df.index})
    all_dates = [pd.Timestamp(d) for d in all_dates]
    reb_dates = _rebalance_dates(all_dates, holding_days)
    if not reb_dates:
        logger.warning("factor evaluate: no rebalance dates")
        return []

    fwd = build_forward_returns(price_map, holding_days)
    panels = compute_factor_panel(price_map, factor_codes)

    rows: list[dict] = []
    for code, meta in FACTOR_REGISTRY.items():
        if factor_codes and code not in factor_codes:
            continue
        panel = panels.get(code)
        item = {
            "code": code,
            "name": meta["name"],
            "category": meta["category"],
            "desc": meta.get("desc", ""),
        }
        if panel is None or panel.empty:
            item.update(
                {
                    "ic_mean": None,
                    "ir": None,
                    "ic_win_rate": None,
                    "q1_excess": None,
                    "q5_excess": None,
                    "q5_q1": None,
                    "q5_turnover": None,
                    "monotonicity": None,
                    "sample_stocks": 0,
                    "sample_periods": 0,
                    "ok": False,
                }
            )
        else:
            # 对齐日期索引类型
            panel = panel.copy()
            panel.index = pd.to_datetime(panel.index)
            stats = evaluate_single_factor(panel, fwd, holding_days, reb_dates)
            item.update(stats)
        rows.append(item)

    rows.sort(key=lambda r: abs(r.get("ir") or 0), reverse=True)
    return rows
