# -*- coding: utf-8 -*-
"""TA-Lib K 线形态策略公共模块（参考训练营 CASE-Talib 3-K线形态识别 / 9-形态选股雷达）。"""
from __future__ import annotations

from typing import Callable

import backtrader as bt
import numpy as np
import talib

# 训练营 9-形态选股雷达 中的重点看涨反转形态
BULLISH_PATTERNS: dict[str, str] = {
    "CDLENGULFING": "看涨吞没",
    "CDLHAMMER": "锤子线",
    "CDLMORNINGSTAR": "早晨之星",
    "CDLPIERCING": "曙光初现",
    "CDL3WHITESOLDIERS": "三白兵",
    "CDLINVERTEDHAMMER": "倒锤子线",
    "CDL3INSIDE": "三内部上涨",
    "CDL3OUTSIDE": "三外部上涨",
    "CDLHARAMI": "看涨孕线",
    "CDLDRAGONFLYDOJI": "蜻蜓十字",
}

# 重点看跌反转形态
BEARISH_PATTERNS: dict[str, str] = {
    "CDLSHOOTINGSTAR": "射击之星",
    "CDLEVENINGSTAR": "黄昏之星",
    "CDL3BLACKCROWS": "三黑鸦",
    "CDLDARKCLOUDCOVER": "乌云盖顶",
    "CDLHANGINGMAN": "吊人线",
    "CDLENGULFING": "看跌吞没",
    "CDLGRAVESTONEDOJI": "墓碑十字",
}


def detect_bottom_divergence(
    close: np.ndarray,
    macd_line: np.ndarray,
    lookback: int = 60,
    recent_window: int = 10,
) -> bool:
    """检测 MACD 底背离：价格创新低但 MACD 未创新低。"""
    n = len(close)
    if n < lookback:
        return False

    recent_slice = close[n - recent_window : n]
    prev_slice = close[n - lookback : n - recent_window]
    if len(prev_slice) == 0 or len(recent_slice) == 0:
        return False

    recent_low_local = int(np.argmin(recent_slice))
    prev_low_local = int(np.argmin(prev_slice))
    idx_recent = n - recent_window + recent_low_local
    idx_prev = n - lookback + prev_low_local

    if np.isnan(macd_line[idx_recent]) or np.isnan(macd_line[idx_prev]):
        return False

    price_lower = close[idx_recent] <= close[idx_prev]
    macd_higher = macd_line[idx_recent] > macd_line[idx_prev]
    return bool(price_lower and macd_higher)


def scan_pattern_signal(
    o: np.ndarray,
    h: np.ndarray,
    l: np.ndarray,
    c: np.ndarray,
    patterns: dict[str, str],
    bullish: bool,
) -> tuple[bool, str]:
    """扫描最后一根 K 线是否命中指定形态集合。"""
    for func_name, label in patterns.items():
        func: Callable = getattr(talib, func_name)
        result = func(o, h, l, c)
        if len(result) == 0:
            continue
        last_val = int(result[-1])
        if bullish and last_val > 0:
            return True, label
        if not bullish and last_val < 0:
            return True, label
    return False, ""


class TalibCDLMixin:
    """在 Backtrader 策略中增量维护 OHLC 并调用 TA-Lib CDL 函数。"""

    def _init_cdl_state(self) -> None:
        self._ohlc: dict[str, dict[str, list[float]]] = {}
        self._pending_signals: dict[str, dict] = {}
        for data in self.datas:
            name = data._name
            self._ohlc[name] = {"o": [], "h": [], "l": [], "c": []}

    def _append_bar(self, data: bt.LineSeries) -> None:
        bucket = self._ohlc[data._name]
        bucket["o"].append(float(data.open[0]))
        bucket["h"].append(float(data.high[0]))
        bucket["l"].append(float(data.low[0]))
        bucket["c"].append(float(data.close[0]))

    def _ohlc_arrays(self, data: bt.LineSeries) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        bucket = self._ohlc[data._name]
        o = np.asarray(bucket["o"], dtype=np.float64)
        h = np.asarray(bucket["h"], dtype=np.float64)
        l = np.asarray(bucket["l"], dtype=np.float64)
        c = np.asarray(bucket["c"], dtype=np.float64)
        return o, h, l, c

    def _cdl_last(self, data: bt.LineSeries, func_name: str) -> int:
        o, h, l, c = self._ohlc_arrays(data)
        if len(c) < 3:
            return 0
        func = getattr(talib, func_name)
        result = func(o, h, l, c)
        if len(result) == 0:
            return 0
        return int(result[-1])

    def _record_signal(self, data: bt.LineSeries, direction: str) -> None:
        self._pending_signals[data._name] = {
            "direction": direction,
            "signal_date": data.datetime.date().isoformat(),
        }

    def _trade_on_cdl(
        self,
        data: bt.LineSeries,
        func_name: str,
        buy_on_bullish: bool = True,
        sell_on_bearish: bool = True,
    ) -> None:
        signal = self._cdl_last(data, func_name)
        pos = self.getposition(data)
        if buy_on_bullish and not pos and signal > 0:
            self._record_signal(data, "buy")
            self.buy(data=data)
        elif sell_on_bearish and pos and signal < 0:
            self._record_signal(data, "sell")
            self.close(data=data)
