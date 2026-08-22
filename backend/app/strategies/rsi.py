# -*- coding: utf-8 -*-
"""RSI 超买超卖策略（参考训练营 3-RSI策略.py）。"""
from __future__ import annotations

import backtrader as bt

from app.strategies.registry import register_strategy


@register_strategy(
    code="rsi",
    name="RSI超买超卖策略",
    category="超买超卖",
    description="RSI低于阈值买入，高于阈值卖出",
    param_template=[
        {
            "param_name": "period",
            "param_label": "RSI周期",
            "param_type": "int",
            "default_value": 14,
            "min": 2,
            "max": 100,
        },
        {
            "param_name": "oversold",
            "param_label": "超卖阈值",
            "param_type": "int",
            "default_value": 30,
            "min": 1,
            "max": 50,
        },
        {
            "param_name": "overbought",
            "param_label": "超买阈值",
            "param_type": "int",
            "default_value": 70,
            "min": 50,
            "max": 99,
        },
    ],
)
class RSIStrategy(bt.Strategy):
    params = (
        ("period", 14),
        ("oversold", 30),
        ("overbought", 70),
    )

    def __init__(self):
        self.rsi_map = {
            data._name: bt.indicators.RSI(data.close, period=self.p.period) for data in self.datas
        }

    def next(self):
        for data in self.datas:
            rsi = self.rsi_map[data._name]
            pos = self.getposition(data)
            if not pos:
                if rsi[0] < self.p.oversold:
                    self.buy(data=data)
            elif rsi[0] > self.p.overbought:
                self.close(data=data)
