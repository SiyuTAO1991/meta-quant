# -*- coding: utf-8 -*-
"""MACD 策略（参考训练营 2-MACD策略.py）。"""
from __future__ import annotations

import backtrader as bt

from app.strategies.registry import register_strategy


@register_strategy(
    code="macd",
    name="MACD策略",
    category="趋势跟踪",
    description="DIF 上穿 DEA 买入，DIF 下穿 DEA 卖出",
    param_template=[
        {
            "param_name": "short",
            "param_label": "短周期",
            "param_type": "int",
            "default_value": 12,
            "min": 2,
            "max": 50,
        },
        {
            "param_name": "long",
            "param_label": "长周期",
            "param_type": "int",
            "default_value": 26,
            "min": 5,
            "max": 100,
        },
        {
            "param_name": "signal",
            "param_label": "信号线",
            "param_type": "int",
            "default_value": 9,
            "min": 2,
            "max": 50,
        },
    ],
)
class MACDStrategy(bt.Strategy):
    params = (
        ("short", 12),
        ("long", 26),
        ("signal", 9),
    )

    def __init__(self):
        self.crossovers = {}
        for data in self.datas:
            macd = bt.indicators.MACD(
                data.close,
                period_me1=self.p.short,
                period_me2=self.p.long,
                period_signal=self.p.signal,
            )
            self.crossovers[data._name] = bt.indicators.CrossOver(macd.macd, macd.signal)

    def next(self):
        for data in self.datas:
            crossover = self.crossovers[data._name]
            pos = self.getposition(data)
            if not pos:
                if crossover[0] > 0:
                    self.buy(data=data)
            elif crossover[0] < 0:
                self.close(data=data)
