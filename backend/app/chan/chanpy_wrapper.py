# -*- coding: utf-8 -*-
"""缠论分析封装（基于 ChanAnalyzer，参考训练营 chanpy_wrapper）。"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from app.chan.chan_analyzer import ChanAnalyzer
from app.chan.signals import analyze_dataframe, build_signal_stats, export_chan_visual


def run_chan(df: pd.DataFrame, symbol: str = "stock", config_dict: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    _ = symbol, config_dict
    work = df.copy()
    work.index = pd.to_datetime(work.index)
    analyzer = ChanAnalyzer(work)
    analyzer.analyze()
    return export_chan_visual(analyzer)


def build_summary(chan_data: dict[str, Any]) -> dict[str, int]:
    return {
        "merged_kline_count": len(chan_data.get("klc_list") or []),
        "fractal_count": len(chan_data.get("fractals") or []),
        "bi_count": len(chan_data.get("bi_list") or []),
        "seg_count": len(chan_data.get("seg_list") or []),
        "zs_count": len(chan_data.get("zs_list") or []),
        "bsp_count": len(chan_data.get("signals") or []),
    }


def draw_chan_chart(
    ax,
    df: pd.DataFrame,
    chan_data: dict[str, Any],
    show_bi: bool = True,
    show_seg: bool = True,
    show_zs: bool = True,
    show_bsp: bool = True,
    show_fractals: bool = False,
):
    import matplotlib.patches as patches

    d2x = ChanAnalyzer._draw_candlestick(ax, df, width_ratio=0.6)

    def _lx(date_val):
        if date_val in d2x:
            return d2x[date_val]
        ts = pd.Timestamp(date_val)
        if ts in d2x:
            return d2x[ts]
        if hasattr(ts, "date"):
            return d2x.get(ts.date())
        for k, v in d2x.items():
            if pd.Timestamp(k).normalize() == ts.normalize():
                return v
        return None

    if show_bi and chan_data.get("bi_list"):
        for bi in chan_data["bi_list"]:
            c = "#e74c3c" if bi["direction"] == "up" else "#27ae60"
            sx = _lx(bi["start_raw_date"])
            ex = _lx(bi["end_raw_date"])
            if sx is not None and ex is not None:
                ax.plot([sx, ex], [bi["start_price"], bi["end_price"]], color=c, linewidth=1.8, alpha=0.85, zorder=4)

    if show_zs and chan_data.get("zs_list"):
        for zs in chan_data["zs_list"]:
            if zs.get("start_date") and zs.get("end_date"):
                xl = _lx(zs["start_date"])
                xr = _lx(zs["end_date"])
                if xl is not None and xr is not None:
                    rect = patches.Rectangle(
                        (xl, zs["ZD"]),
                        xr - xl,
                        zs["ZG"] - zs["ZD"],
                        linewidth=1.5,
                        edgecolor="#3498db",
                        facecolor="#3498db",
                        alpha=0.15,
                        zorder=2,
                    )
                    ax.add_patch(rect)

    if show_bsp and chan_data.get("signals"):
        colors = {
            "一买": "#8e44ad",
            "二买": "#e67e22",
            "三买": "#e74c3c",
            "三卖": "#27ae60",
        }
        for sig in chan_data["signals"]:
            x = _lx(sig["date"])
            if x is None:
                continue
            is_buy = "buy" in sig["type"]
            marker = "^" if is_buy else "v"
            color = colors.get(sig["type_name"], "#333333")
            ax.scatter(x, sig["price"], marker=marker, color=color, s=200, zorder=7, edgecolors="black", linewidths=1)
            ax.annotate(
                sig["type_name"],
                (x, sig["price"]),
                textcoords="offset points",
                xytext=(10, 10 if is_buy else -15),
                fontsize=9,
                fontweight="bold",
                color=color,
            )

    return d2x
