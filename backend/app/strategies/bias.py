# -*- coding: utf-8 -*-
"""乖离率策略（参考训练营 5-乖离率策略.py）。"""
from __future__ import annotations

import backtrader as bt

from app.strategies.registry import register_strategy


@register_strategy(
    code="bias",
    name="乖离率策略",
    category="均值回归",
    description="乖离率低于阈值买入，高于阈值卖出",
    param_template=[
        {
            "param_name": "period",
            "param_label": "均线周期",
            "param_type": "int",
            "default_value": 20,
            "min": 5,
            "max": 120,
        },
        {
            "param_name": "buy_threshold",
            "param_label": "买入阈值(%)",
            "param_type": "float",
            "default_value": -6.0,
            "min": -30.0,
            "max": 0.0,
        },
        {
            "param_name": "sell_threshold",
            "param_label": "卖出阈值(%)",
            "param_type": "float",
            "default_value": 6.0,
            "min": 0.0,
            "max": 30.0,
        },
    ],
)
class BIASStrategy(bt.Strategy):
    params = (
        ("period", 20),
        ("buy_threshold", -6.0),
        ("sell_threshold", 6.0),
    )

    def __init__(self):
        self.sma_map = {
            data._name: bt.indicators.SMA(data.close, period=self.p.period) for data in self.datas
        }

    def next(self):
        for data in self.datas:
            sma = self.sma_map[data._name][0]
            if not sma:
                continue
            bias = (data.close[0] - sma) / sma * 100
            pos = self.getposition(data)
            if not pos:
                if bias < self.p.buy_threshold:
                    self.buy(data=data)
            elif bias > self.p.sell_threshold:
                self.close(data=data)
