# -*- coding: utf-8 -*-
"""多周期缠论：周线趋势判定（参考训练营脚本7，基于 ChanAnalyzer）。"""
from __future__ import annotations

import pandas as pd

from app.chan.chan_analyzer import ChanAnalyzer


def calc_weekly_trend(df: pd.DataFrame) -> pd.Series:
    """基于周线 ChanAnalyzer 分析结果，生成对齐到日线的趋势序列。"""
    work = df.copy()
    work.index = pd.to_datetime(work.index)
    weekly_df = work.resample("W").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()

    if len(weekly_df) < 20:
        return pd.Series(0, index=work.index, dtype=int)

    w_analyzer = ChanAnalyzer(weekly_df)
    w_analyzer.analyze()
    weekly_trend = pd.Series(0, index=weekly_df.index, dtype=int)

    if len(w_analyzer.zhongshu_list) >= 2:
        for i in range(1, len(w_analyzer.zhongshu_list)):
            curr = w_analyzer.zhongshu_list[i]
            prev = w_analyzer.zhongshu_list[i - 1]
            if curr["ZG"] > prev["ZG"] and curr["ZD"] > prev["ZD"]:
                trend = 1
            elif curr["ZG"] < prev["ZG"] and curr["ZD"] < prev["ZD"]:
                trend = -1
            else:
                trend = 0
            mask = weekly_trend.index >= curr["start_date"]
            weekly_trend.loc[mask] = trend

    if w_analyzer.zhongshu_list:
        for zs in w_analyzer.zhongshu_list:
            for date in weekly_df.index[weekly_df.index >= zs["start_date"]]:
                if weekly_trend.loc[date] != 0:
                    continue
                close = float(weekly_df.loc[date, "close"])
                if close > zs["ZG"]:
                    weekly_trend.loc[date] = 1
                elif close < zs["ZD"]:
                    weekly_trend.loc[date] = -1

    ma20 = weekly_df["close"].rolling(20).mean()
    for idx in range(20, len(weekly_df)):
        date = weekly_df.index[idx]
        if weekly_trend.loc[date] != 0:
            continue
        if weekly_df["close"].iloc[idx] > ma20.iloc[idx]:
            weekly_trend.loc[date] = 1
        elif weekly_df["close"].iloc[idx] < ma20.iloc[idx]:
            weekly_trend.loc[date] = -1

    return weekly_trend.reindex(work.index, method="ffill").fillna(0).astype(int)
