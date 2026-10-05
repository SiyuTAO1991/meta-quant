# -*- coding: utf-8 -*-
"""多因子打分引擎（参考训练营 factor_engine.py）。"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import numpy as np
import pandas as pd
import talib

# 默认 8 因子打分体系（与课程一致）
DEFAULT_FACTOR_CONFIG: dict[str, dict[str, Any]] = {
    "momentum_20d": {
        "name": "20日动量",
        "direction": 1,
        "weight": 0.20,
        "desc": "ROC(20), 短期动量",
        "enabled": True,
    },
    "momentum_60d": {
        "name": "60日动量",
        "direction": 1,
        "weight": 0.15,
        "desc": "ROC(60), 中期动量",
        "enabled": True,
    },
    "volatility": {
        "name": "波动率",
        "direction": -1,
        "weight": 0.15,
        "desc": "ATR(14)/Close, 低波动优先",
        "enabled": True,
    },
    "rsi_14": {
        "name": "RSI(14)",
        "direction": -1,
        "weight": 0.10,
        "desc": "超卖区间更优",
        "enabled": True,
    },
    "adx_14": {
        "name": "ADX(14)",
        "direction": 1,
        "weight": 0.10,
        "desc": "趋势强度",
        "enabled": True,
    },
    "turnover_ratio": {
        "name": "换手率指标",
        "direction": 1,
        "weight": 0.10,
        "desc": "当日量/20日均量",
        "enabled": True,
    },
    "price_position": {
        "name": "价格位置",
        "direction": -1,
        "weight": 0.10,
        "desc": "60日区间位置，越低越好",
        "enabled": True,
    },
    "macd_signal": {
        "name": "MACD信号",
        "direction": 1,
        "weight": 0.10,
        "desc": "MACD柱状图",
        "enabled": True,
    },
}


def list_default_factor_configs() -> list[dict[str, Any]]:
    """前端配置用列表。"""
    items = []
    for code, cfg in DEFAULT_FACTOR_CONFIG.items():
        items.append(
            {
                "code": code,
                "name": cfg["name"],
                "direction": cfg["direction"],
                "weight": cfg["weight"],
                "desc": cfg["desc"],
                "enabled": cfg.get("enabled", True),
            }
        )
    return items


def build_factor_config(factor_weights: list[dict] | None) -> dict[str, dict[str, Any]]:
    """
    根据前端传入的因子权重列表构建配置。
    未传则用默认；权重会按启用项归一化。
    """
    if not factor_weights:
        return deepcopy(DEFAULT_FACTOR_CONFIG)

    config: dict[str, dict[str, Any]] = {}
    for item in factor_weights:
        code = str(item.get("code") or "").strip()
        if not code or code not in DEFAULT_FACTOR_CONFIG:
            continue
        enabled = bool(item.get("enabled", True))
        if not enabled:
            continue
        base = deepcopy(DEFAULT_FACTOR_CONFIG[code])
        if "direction" in item and item["direction"] in (-1, 1):
            base["direction"] = int(item["direction"])
        try:
            w = float(item.get("weight", base["weight"]))
        except (TypeError, ValueError):
            w = float(base["weight"])
        if w <= 0:
            continue
        base["weight"] = w
        base["enabled"] = True
        config[code] = base

    if not config:
        return deepcopy(DEFAULT_FACTOR_CONFIG)

    total_w = sum(c["weight"] for c in config.values())
    if total_w > 0:
        for c in config.values():
            c["weight"] = c["weight"] / total_w
    return config


def calc_all_factors(df: pd.DataFrame) -> dict[str, float] | None:
    """对单只股票计算 8 个技术因子（取最新截面）。"""
    if df is None or len(df) < 60:
        return None

    h = df["high"].values.astype(np.float64)
    l = df["low"].values.astype(np.float64)
    c = df["close"].values.astype(np.float64)
    v = df["volume"].values.astype(np.float64)

    if c[-1] <= 0 or np.isnan(c[-1]):
        return None

    try:
        roc_20 = talib.ROC(c, timeperiod=20)
        roc_60 = talib.ROC(c, timeperiod=60)
        atr = talib.ATR(h, l, c, timeperiod=14)
        rsi = talib.RSI(c, timeperiod=14)
        adx = talib.ADX(h, l, c, timeperiod=14)
        vol_ma = talib.SMA(v, timeperiod=20)
        _, _, macd_hist = talib.MACD(c)

        high_60 = float(np.nanmax(h[-60:]))
        low_60 = float(np.nanmin(l[-60:]))
        price_range = high_60 - low_60
        vol_ma_val = vol_ma[-1] if not np.isnan(vol_ma[-1]) and vol_ma[-1] > 0 else 1.0

        return {
            "momentum_20d": float(roc_20[-1]) if not np.isnan(roc_20[-1]) else 0.0,
            "momentum_60d": float(roc_60[-1]) if not np.isnan(roc_60[-1]) else 0.0,
            "volatility": float(atr[-1] / c[-1]) if not np.isnan(atr[-1]) and c[-1] > 0 else 0.0,
            "rsi_14": float(rsi[-1]) if not np.isnan(rsi[-1]) else 50.0,
            "adx_14": float(adx[-1]) if not np.isnan(adx[-1]) else 0.0,
            "turnover_ratio": float(v[-1] / vol_ma_val) if vol_ma_val > 0 else 1.0,
            "price_position": float((c[-1] - low_60) / price_range) if price_range > 0 else 0.5,
            "macd_signal": float(macd_hist[-1]) if not np.isnan(macd_hist[-1]) else 0.0,
            "close": float(c[-1]),
        }
    except Exception:
        return None


def batch_calc_factors(
    all_data: dict[str, pd.DataFrame],
    calc_date=None,
) -> pd.DataFrame:
    """批量计算截面因子。"""
    factor_dict = {}
    for code, df in all_data.items():
        work = df
        if calc_date is not None:
            work = df[df.index <= calc_date]
        f = calc_all_factors(work)
        if f is not None:
            factor_dict[code] = f
    if not factor_dict:
        return pd.DataFrame()
    return pd.DataFrame(factor_dict).T


def score_stocks(factor_df: pd.DataFrame, factor_config: dict | None = None) -> pd.DataFrame:
    """横截面排名打分：正向用 rank，反向用 1-rank，再按权重加权。"""
    config = factor_config or DEFAULT_FACTOR_CONFIG
    result = factor_df.copy()
    result["score"] = 0.0

    for fname, cfg in config.items():
        if fname not in result.columns:
            continue
        rank = result[fname].rank(pct=True)
        if int(cfg.get("direction", 1)) < 0:
            rank = 1 - rank
        result[f"{fname}_rank"] = rank
        result["score"] = result["score"] + rank * float(cfg.get("weight", 0))

    return result.sort_values("score", ascending=False)


def select_top_stocks(
    factor_df: pd.DataFrame,
    top_n: int = 10,
    factor_config: dict | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    scored = score_stocks(factor_df, factor_config)
    if scored.empty:
        return scored, []
    top_n = max(1, int(top_n))
    top_codes = scored.head(top_n).index.tolist()
    return scored, top_codes
