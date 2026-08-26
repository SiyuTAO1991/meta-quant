# -*- coding: utf-8 -*-
"""基于 ChanAnalyzer 构建 Backtrader 回测信号列。"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from app.chan.chan_analyzer import ChanAnalyzer
from app.chan.weekly_trend import calc_weekly_trend

SIGNAL_NAMES = {
    "first_buy": "一买",
    "second_buy": "二买",
    "third_buy": "三买",
    "third_sell": "三卖",
    "bi_buy": "向下笔买",
    "bi_sell": "向上笔卖",
}

# 笔端翻转策略信号码（避开 1/2/3/-3 三类买卖点编码）
BI_BUY_SIGNAL = 4   # 向下笔终点 → 买
BI_SELL_SIGNAL = -4  # 向上笔终点 → 卖


def analyze_dataframe(
    df: pd.DataFrame,
    with_weekly_trend: bool = False,
) -> tuple[ChanAnalyzer, pd.DataFrame, dict[str, Any]]:
    """执行 ChanAnalyzer 并返回信号 DataFrame 与可视化数据。"""
    work = df.copy()
    work.index = pd.to_datetime(work.index)
    analyzer = ChanAnalyzer(work)
    analyzer.analyze()
    signal_df = analyzer.get_signal_df()
    if with_weekly_trend:
        signal_df["weekly_trend"] = calc_weekly_trend(work)
    return analyzer, signal_df, export_chan_visual(analyzer)


def export_chan_visual(analyzer: ChanAnalyzer) -> dict[str, Any]:
    """导出与训练营脚本4一致的结构化分析结果。"""
    klc_list: list[dict[str, Any]] = []
    if analyzer.merged_df is not None and not analyzer.merged_df.empty:
        fractal_by_index = {f["index"]: f["type"] for f in analyzer.fractals}
        for idx, (dt, row) in enumerate(analyzer.merged_df.iterrows()):
            klc_list.append(
                {
                    "date": pd.Timestamp(dt).strftime("%Y-%m-%d"),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "idx": idx,
                    "fx": fractal_by_index.get(idx, "unknown"),
                    "raw_count": 1,
                }
            )

    fractals = [
        {
            "date": pd.Timestamp(f["date"]).strftime("%Y-%m-%d"),
            "fx": f["type"],
            "high": float(f["price"]),
            "low": float(f["price"]),
        }
        for f in analyzer.fractals
    ]

    bi_list = [
        {
            "start_date": pd.Timestamp(bi["start_date"]).strftime("%Y-%m-%d"),
            "end_date": pd.Timestamp(bi["end_date"]).strftime("%Y-%m-%d"),
            "start_raw_date": pd.Timestamp(bi.get("start_raw_date", bi["start_date"])).strftime("%Y-%m-%d"),
            "end_raw_date": pd.Timestamp(bi.get("end_raw_date", bi["end_date"])).strftime("%Y-%m-%d"),
            "start_price": float(bi["start_price"]),
            "end_price": float(bi["end_price"]),
            "direction": bi["direction"],
        }
        for bi in analyzer.bi_list
    ]

    zs_list = [
        {
            "ZG": float(zs["ZG"]),
            "ZD": float(zs["ZD"]),
            "center": float(zs["center"]),
            "start_date": pd.Timestamp(zs["start_date"]).strftime("%Y-%m-%d"),
            "end_date": pd.Timestamp(zs["end_date"]).strftime("%Y-%m-%d"),
        }
        for zs in analyzer.zhongshu_list
    ]

    signals = []
    for sig in analyzer.signals:
        item = {
            "date": pd.Timestamp(sig["date"]).strftime("%Y-%m-%d"),
            "type": sig["type"],
            "type_name": SIGNAL_NAMES.get(sig["type"], sig["type"]),
            "price": float(sig["price"]),
            "zhongshu_zg": float(sig["zhongshu_zg"]) if sig.get("zhongshu_zg") is not None else None,
            "zhongshu_zd": float(sig["zhongshu_zd"]) if sig.get("zhongshu_zd") is not None else None,
        }
        signals.append(item)

    return {
        "klc_list": klc_list,
        "fractals": fractals,
        "bi_list": bi_list,
        "seg_list": [],
        "zs_list": zs_list,
        "bsp_list": signals,
        "signals": signals,
    }


def build_signal_stats(signal_df: pd.DataFrame) -> dict[str, int]:
    return {
        "first_buy": int((signal_df["chan_signal"] == 1).sum()),
        "second_buy": int((signal_df["chan_signal"] == 2).sum()),
        "third_buy": int((signal_df["chan_signal"] == 3).sum()),
        "third_sell": int((signal_df["chan_signal"] == -3).sum()),
        "bi_buy": int((signal_df["chan_signal"] == BI_BUY_SIGNAL).sum()),
        "bi_sell": int((signal_df["chan_signal"] == BI_SELL_SIGNAL).sum()),
        "total": int((signal_df["chan_signal"] != 0).sum()),
    }


def apply_bi_flip_signals(analyzer: ChanAnalyzer, signal_df: pd.DataFrame) -> pd.DataFrame:
    """
    用笔端点覆盖 chan_signal（不依赖中枢买卖点）:
      向下笔终点 → 4（买）
      向上笔终点 → -4（卖）
    """
    out = signal_df.copy()
    out["chan_signal"] = 0
    for bi in analyzer.bi_list:
        sig_date = bi.get("end_raw_date", bi["end_date"])
        loc = ChanAnalyzer._loc_signal_date(out, sig_date)
        if loc is None:
            continue
        if bi["direction"] == "down":
            out.loc[loc, "chan_signal"] = BI_BUY_SIGNAL
        elif bi["direction"] == "up":
            out.loc[loc, "chan_signal"] = BI_SELL_SIGNAL
    return out


def extract_bi_flip_points(analyzer: ChanAnalyzer) -> list[dict[str, Any]]:
    """从笔列表提取笔端买卖点（供回测报告）。"""
    points: list[dict[str, Any]] = []
    for bi in analyzer.bi_list:
        if bi["direction"] == "down":
            sig_type = "bi_buy"
            price = float(bi["end_price"])
        elif bi["direction"] == "up":
            sig_type = "bi_sell"
            price = float(bi["end_price"])
        else:
            continue
        points.append(
            {
                "date": pd.Timestamp(bi.get("end_raw_date", bi["end_date"])).strftime("%Y-%m-%d"),
                "type": sig_type,
                "type_name": SIGNAL_NAMES[sig_type],
                "price": price,
                "zhongshu_zg": None,
                "zhongshu_zd": None,
            }
        )
    points.sort(key=lambda x: x["date"])
    return points


def build_signal_dataframe(
    df: pd.DataFrame,
    symbol: str,
    config_dict: Optional[dict[str, Any]] = None,
    with_weekly_trend: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    _ = symbol, config_dict
    _, signal_df, chan_data = analyze_dataframe(df, with_weekly_trend=with_weekly_trend)
    return signal_df, chan_data


def serialize_klines(df: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, row in df.iterrows():
        rows.append(
            {
                "date": pd.Timestamp(idx).strftime("%Y-%m-%d"),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume", 0) or 0),
            }
        )
    return rows


def enrich_dataframes_for_chan(
    dataframes: dict[str, pd.DataFrame],
    strategy_key: str,
) -> dict[str, pd.DataFrame]:
    from app.chan.constants import CHAN_STRATEGY_KEYS

    if strategy_key not in CHAN_STRATEGY_KEYS:
        return dataframes

    enriched: dict[str, pd.DataFrame] = {}
    with_weekly = strategy_key == "chan_multi_period"
    for code, df in dataframes.items():
        analyzer, signal_df, _ = analyze_dataframe(df, with_weekly_trend=with_weekly)
        if strategy_key == "chan_bi_flip":
            signal_df = apply_bi_flip_signals(analyzer, signal_df)
        enriched[code] = signal_df
    return enriched


def extract_signal_points(signal_df: pd.DataFrame) -> list[dict[str, Any]]:
    """从信号列提取全部买卖点（供回测报告展示）。"""
    reverse_map = {
        1: "first_buy",
        2: "second_buy",
        3: "third_buy",
        -3: "third_sell",
        BI_BUY_SIGNAL: "bi_buy",
        BI_SELL_SIGNAL: "bi_sell",
    }
    points: list[dict[str, Any]] = []
    for dt, row in signal_df.iterrows():
        code = int(row.get("chan_signal", 0) or 0)
        if code == 0:
            continue
        sig_type = reverse_map.get(code, "unknown")
        points.append(
            {
                "date": pd.Timestamp(dt).strftime("%Y-%m-%d"),
                "type": sig_type,
                "type_name": SIGNAL_NAMES.get(sig_type, sig_type),
                "price": float(row["close"]),
                "chan_zg": float(row["chan_zg"]) if pd.notna(row.get("chan_zg")) else None,
                "chan_zd": float(row["chan_zd"]) if pd.notna(row.get("chan_zd")) else None,
            }
        )
    return points
