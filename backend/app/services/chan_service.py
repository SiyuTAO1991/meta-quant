# -*- coding: utf-8 -*-
"""缠论分析与回测辅助服务。"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from app.backtest.data_loader import bars_to_dataframe
from app.chan.constants import CHAN_STRATEGY_KEYS
from app.chan.signals import (
    analyze_dataframe,
    build_signal_stats,
    enrich_dataframes_for_chan,
    export_chan_visual,
    serialize_klines,
)
from app.services import stock_service
from app.utils import normalize_date

__all__ = [
    "CHAN_STRATEGY_KEYS",
    "analyze_chan",
    "load_dataframe",
    "enrich_dataframes_for_chan",
    "calc_chan_min_bars",
    "build_chan_report_extras",
]

_CHAN_MIN_BARS = 120


def calc_chan_min_bars(start_date: str, end_date: str) -> int:
    """按回测区间估算缠论分析所需最少 K 线数（约 85% 交易日覆盖）。"""
    start = pd.Timestamp(normalize_date(start_date, as_dash=True))
    end = pd.Timestamp(normalize_date(end_date, as_dash=True))
    span_days = max((end - start).days, 1)
    expected = int(span_days * 252 / 365 * 0.85)
    return max(_CHAN_MIN_BARS, expected)


def load_dataframe(ts_code: str, start_date: str, end_date: str, min_bars: int | None = None) -> pd.DataFrame:
    start = normalize_date(start_date, as_dash=True)
    end = normalize_date(end_date, as_dash=True)
    if min_bars is None:
        min_bars = calc_chan_min_bars(start, end)
    codes = stock_service.ensure_daily_data([ts_code], start, end, min_bars=min_bars)
    code = codes[0]
    bars = stock_service.query_stock_daily(code, start, end)
    if not bars:
        raise ValueError(f"{code} 在区间内无日线数据")
    df = bars_to_dataframe(bars)
    if df.empty:
        raise ValueError(f"{code} 在区间内无有效日线数据")
    if len(df) < min_bars:
        actual_start = pd.Timestamp(df.index.min()).strftime("%Y-%m-%d")
        actual_end = pd.Timestamp(df.index.max()).strftime("%Y-%m-%d")
        raise ValueError(
            f"{code} 可用K线仅 {len(df)} 根（{actual_start}~{actual_end}），"
            f"缠论分析建议至少 {min_bars} 根；请扩大回测区间或先采集更久历史数据"
        )
    return df


def analyze_chan(
    ts_code: str,
    start_date: str,
    end_date: str,
    config: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """执行缠论结构识别并返回可视化所需数据（对齐训练营脚本4）。"""
    _ = config
    df = load_dataframe(ts_code, start_date, end_date)
    code = ts_code.strip().upper()
    analyzer, signal_df, chan_data = analyze_dataframe(df, with_weekly_trend=True)
    stats = build_signal_stats(signal_df)
    filtered_buy = int(((signal_df["chan_signal"] == 3) & (signal_df["weekly_trend"] == 1)).sum())

    return {
        "ts_code": code,
        "start_date": normalize_date(start_date, as_dash=True),
        "end_date": normalize_date(end_date, as_dash=True),
        "data_range": {
            "start": pd.Timestamp(df.index.min()).strftime("%Y-%m-%d"),
            "end": pd.Timestamp(df.index.max()).strftime("%Y-%m-%d"),
            "bars": len(df),
        },
        "summary": {
            "merged_kline_count": len(chan_data.get("klc_list") or []),
            "fractal_count": len(chan_data.get("fractals") or []),
            "bi_count": len(analyzer.bi_list),
            "seg_count": 0,
            "zs_count": len(analyzer.zhongshu_list),
            "bsp_count": len(analyzer.signals),
        },
        "signal_stats": {
            **stats,
            "weekly_up_third_buy": filtered_buy,
        },
        "signals": chan_data.get("signals") or [],
        "klines": serialize_klines(df),
        "klc_list": chan_data["klc_list"],
        "fractals": chan_data["fractals"],
        "bi_list": chan_data["bi_list"],
        "seg_list": chan_data["seg_list"],
        "zs_list": chan_data["zs_list"],
        "bsp_list": chan_data["signals"],
    }


def build_chan_report_extras(stock_bars: dict[str, list[dict]], strategy_key: str) -> dict[str, Any]:
    """为缠论回测报告附加全部买卖点列表。"""
    if strategy_key not in CHAN_STRATEGY_KEYS:
        return {}
    from app.chan.signals import apply_bi_flip_signals, extract_bi_flip_points

    all_signals: list[dict[str, Any]] = []
    stats: dict[str, int] = {}
    for code, bars in stock_bars.items():
        df = bars_to_dataframe(bars)
        if df.empty:
            continue
        analyzer, signal_df, chan_data = analyze_dataframe(
            df, with_weekly_trend=strategy_key == "chan_multi_period"
        )
        if strategy_key == "chan_bi_flip":
            signal_df = apply_bi_flip_signals(analyzer, signal_df)
            stats = build_signal_stats(signal_df)
            for sig in extract_bi_flip_points(analyzer):
                item = dict(sig)
                item["stock_code"] = code
                all_signals.append(item)
        else:
            stats = build_signal_stats(signal_df)
            for sig in chan_data.get("signals") or []:
                item = dict(sig)
                item["stock_code"] = code
                all_signals.append(item)
    return {"chan_signals": all_signals, "chan_signal_stats": stats if stock_bars else {}}
