# -*- coding: utf-8 -*-
"""动量策略（参考训练营 6-动量策略.py）。"""
from __future__ import annotations

import backtrader as bt

from app.strategies.registry import register_strategy


@register_strategy(
    code="momentum",
    name="动量策略",
    category="动量因子",
    description="N 日涨幅超过阈值买入，跌幅超过阈值卖出",
    param_template=[
        {
            "param_name": "period",
            "param_label": "观察周期",
            "param_type": "int",
            "default_value": 20,
            "min": 5,
            "max": 120,
        },
        {
            "param_name": "threshold",
            "param_label": "涨跌幅阈值(%)",
            "param_type": "float",
            "default_value": 5.0,
            "min": 1.0,
            "max": 30.0,
        },
    ],
)
class MomentumStrategy(bt.Strategy):
    params = (
        ("period", 20),
        ("threshold", 5.0),
    )

    def __init__(self):
        self.roc_map = {
            data._name: bt.indicators.ROC100(data.close, period=self.p.period) for data in self.datas
        }

    def next(self):
        for data in self.datas:
            roc = self.roc_map[data._name]
            pos = self.getposition(data)
            if not pos:
                if roc[0] > self.p.threshold:
                    self.buy(data=data)
            elif roc[0] < -self.p.threshold:
                self.close(data=data)
