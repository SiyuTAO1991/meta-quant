# -*- coding: utf-8 -*-
"""因子注册表：名称、分类、计算逻辑。"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd
import talib

# 分类与 UI 对齐
CATEGORY_REVERSAL = "反转"
CATEGORY_MOMENTUM = "动量"
CATEGORY_VOLATILITY = "波动"
CATEGORY_VOLUME = "量能"
CATEGORY_TREND = "趋势"


def _safe(series: pd.Series) -> pd.Series:
    return series.replace([np.inf, -np.inf], np.nan)


def _roc(close: np.ndarray, n: int) -> np.ndarray:
    return talib.ROC(close, timeperiod=n)


def _bias(close: np.ndarray, n: int) -> np.ndarray:
    ma = talib.SMA(close, timeperiod=n)
    out = (close - ma) / np.where(ma == 0, np.nan, ma) * 100.0
    return out


def _rsi(close: np.ndarray, n: int = 14) -> np.ndarray:
    return talib.RSI(close, timeperiod=n)


def _atr_pct(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14) -> np.ndarray:
    atr = talib.ATR(high, low, close, timeperiod=n)
    return atr / np.where(close == 0, np.nan, close)


def _adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14) -> np.ndarray:
    return talib.ADX(high, low, close, timeperiod=n)


def _vol_ratio(volume: np.ndarray, n: int = 20) -> np.ndarray:
    ma = talib.SMA(volume.astype(float), timeperiod=n)
    return volume.astype(float) / np.where(ma == 0, np.nan, ma)


def _macd_hist(close: np.ndarray) -> np.ndarray:
    _, _, hist = talib.MACD(close)
    return hist


def _price_position(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 60) -> np.ndarray:
    out = np.full_like(close, np.nan, dtype=float)
    for i in range(n - 1, len(close)):
        hh = np.nanmax(high[i - n + 1 : i + 1])
        ll = np.nanmin(low[i - n + 1 : i + 1])
        span = hh - ll
        out[i] = (close[i] - ll) / span if span > 0 else 0.5
    return out


def _realized_vol(close: np.ndarray, n: int = 20) -> np.ndarray:
    ret = np.diff(np.log(np.where(close <= 0, np.nan, close)), prepend=np.nan)
    out = np.full_like(close, np.nan, dtype=float)
    for i in range(n - 1, len(close)):
        window = ret[i - n + 1 : i + 1]
        out[i] = np.nanstd(window) * np.sqrt(252)
    return out


FactorFn = Callable[[pd.DataFrame], pd.Series]


def _wrap(fn) -> FactorFn:
    def _calc(df: pd.DataFrame) -> pd.Series:
        h = df["high"].values.astype(np.float64)
        l = df["low"].values.astype(np.float64)
        c = df["close"].values.astype(np.float64)
        v = df["volume"].values.astype(np.float64)
        arr = fn(h, l, c, v)
        return _safe(pd.Series(arr, index=df.index))

    return _calc


FACTOR_REGISTRY: dict[str, dict] = {
    "bias_60d": {
        "name": "60日乖离率",
        "category": CATEGORY_REVERSAL,
        "desc": "收盘价相对60日均线偏离",
        "min_bars": 60,
        "compute": _wrap(lambda h, l, c, v: _bias(c, 60)),
    },
    "bias_20d": {
        "name": "20日乖离率",
        "category": CATEGORY_REVERSAL,
        "desc": "收盘价相对20日均线偏离",
        "min_bars": 20,
        "compute": _wrap(lambda h, l, c, v: _bias(c, 20)),
    },
    "rsi_14": {
        "name": "RSI(14)",
        "category": CATEGORY_REVERSAL,
        "desc": "14日相对强弱",
        "min_bars": 20,
        "compute": _wrap(lambda h, l, c, v: _rsi(c, 14)),
    },
    "price_pos_60d": {
        "name": "60日价格位置",
        "category": CATEGORY_REVERSAL,
        "desc": "收盘价在60日高低区间中的位置",
        "min_bars": 60,
        "compute": _wrap(lambda h, l, c, v: _price_position(h, l, c, 60)),
    },
    "ret_5d": {
        "name": "5日收益率",
        "category": CATEGORY_REVERSAL,
        "desc": "近5日涨跌幅（短反转）",
        "min_bars": 10,
        "compute": _wrap(lambda h, l, c, v: _roc(c, 5)),
    },
    "ret_10d": {
        "name": "10日收益率",
        "category": CATEGORY_REVERSAL,
        "desc": "近10日涨跌幅",
        "min_bars": 15,
        "compute": _wrap(lambda h, l, c, v: _roc(c, 10)),
    },
    "momentum_20d": {
        "name": "20日动量",
        "category": CATEGORY_MOMENTUM,
        "desc": "ROC(20)",
        "min_bars": 25,
        "compute": _wrap(lambda h, l, c, v: _roc(c, 20)),
    },
    "momentum_60d": {
        "name": "60日动量",
        "category": CATEGORY_MOMENTUM,
        "desc": "ROC(60)",
        "min_bars": 65,
        "compute": _wrap(lambda h, l, c, v: _roc(c, 60)),
    },
    "momentum_120d": {
        "name": "120日动量",
        "category": CATEGORY_MOMENTUM,
        "desc": "ROC(120)",
        "min_bars": 125,
        "compute": _wrap(lambda h, l, c, v: _roc(c, 120)),
    },
    "macd_hist": {
        "name": "MACD柱",
        "category": CATEGORY_MOMENTUM,
        "desc": "MACD histogram",
        "min_bars": 40,
        "compute": _wrap(lambda h, l, c, v: _macd_hist(c)),
    },
    "volatility_14": {
        "name": "ATR波动率",
        "category": CATEGORY_VOLATILITY,
        "desc": "ATR(14)/Close",
        "min_bars": 20,
        "compute": _wrap(lambda h, l, c, v: _atr_pct(h, l, c, 14)),
    },
    "realized_vol_20": {
        "name": "20日实现波动",
        "category": CATEGORY_VOLATILITY,
        "desc": "对数收益年化波动率",
        "min_bars": 25,
        "compute": _wrap(lambda h, l, c, v: _realized_vol(c, 20)),
    },
    "vol_ratio_20": {
        "name": "量比(20日)",
        "category": CATEGORY_VOLUME,
        "desc": "成交量/20日均量",
        "min_bars": 25,
        "compute": _wrap(lambda h, l, c, v: _vol_ratio(v, 20)),
    },
    "adx_14": {
        "name": "ADX(14)",
        "category": CATEGORY_TREND,
        "desc": "趋势强度",
        "min_bars": 30,
        "compute": _wrap(lambda h, l, c, v: _adx(h, l, c, 14)),
    },
}


def list_factor_meta() -> list[dict]:
    return [
        {
            "code": code,
            "name": meta["name"],
            "category": meta["category"],
            "desc": meta.get("desc", ""),
        }
        for code, meta in FACTOR_REGISTRY.items()
    ]


def list_categories() -> list[str]:
    return sorted({m["category"] for m in FACTOR_REGISTRY.values()})
