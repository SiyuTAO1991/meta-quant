# -*- coding: utf-8 -*-
"""布林带策略（参考训练营 4-布林带策略.py）。"""
from __future__ import annotations

import backtrader as bt

from app.strategies.registry import register_strategy


@register_strategy(
    code="bollinger",
    name="布林带策略",
    category="波动率",
    description="价格触及下轨买入，触及上轨卖出",
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
            "param_name": "devfactor",
            "param_label": "标准差倍数",
            "param_type": "float",
            "default_value": 2.0,
            "min": 0.5,
            "max": 4.0,
        },
    ],
)
class BollingerBandStrategy(bt.Strategy):
    params = (
        ("period", 20),
        ("devfactor", 2.0),
    )

    def __init__(self):
        self.boll_map = {}
        for data in self.datas:
            self.boll_map[data._name] = bt.indicators.BollingerBands(
                data.close,
                period=self.p.period,
                devfactor=self.p.devfactor,
            )

    def next(self):
        for data in self.datas:
            boll = self.boll_map[data._name]
            pos = self.getposition(data)
            if not pos:
                if data.close[0] < boll.bot[0]:
                    self.buy(data=data)
            elif data.close[0] > boll.top[0]:
                self.close(data=data)
