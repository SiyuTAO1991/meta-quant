# -*- coding: utf-8 -*-
"""看涨形态扫描策略（参考训练营 9-形态选股雷达 BULLISH_PATTERNS）。"""
from __future__ import annotations

import backtrader as bt

from app.strategies.cdl_base import BEARISH_PATTERNS, BULLISH_PATTERNS, TalibCDLMixin, scan_pattern_signal
from app.strategies.registry import register_strategy


@register_strategy(
    code="cdl_bullish_scan",
    name="看涨形态扫描策略",
    category="K线形态",
    description="扫描 10 种 TA-Lib 看涨反转形态入场，命中看跌形态离场",
    param_template=[],
)
class CDLBullishScanStrategy(TalibCDLMixin, bt.Strategy):
    def __init__(self):
        self._init_cdl_state()

    def next(self):
        for data in self.datas:
            self._append_bar(data)
            o, h, l, c = self._ohlc_arrays(data)
            if len(c) < 3:
                continue
            pos = self.getposition(data)
            bullish_hit, _ = scan_pattern_signal(o, h, l, c, BULLISH_PATTERNS, bullish=True)
            bearish_hit, _ = scan_pattern_signal(o, h, l, c, BEARISH_PATTERNS, bullish=False)
            if not pos and bullish_hit:
                self._record_signal(data, "buy")
                self.buy(data=data)
            elif pos and bearish_hit:
                self._record_signal(data, "sell")
                self.close(data=data)
