# -*- coding: utf-8 -*-
"""双均线策略（参考训练营 1-双均线策略.py）。"""
from __future__ import annotations

import backtrader as bt

from app.strategies.registry import register_strategy


@register_strategy(
    code="double_ma",
    name="双均线策略",
    category="趋势跟踪",
    description="快线向上穿越慢线买入，快线向下穿越慢线卖出；信号产生于交叉当日收盘，次日开盘成交",
    param_template=[
        {
            "param_name": "fast_period",
            "param_label": "快线周期",
            "param_type": "int",
            "default_value": 10,
            "min": 1,
            "max": 100,
        },
        {
            "param_name": "slow_period",
            "param_label": "慢线周期",
            "param_type": "int",
            "default_value": 30,
            "min": 1,
            "max": 200,
        },
    ],
)
class DoubleMAStrategy(bt.Strategy):
    params = (
        ("fast_period", 10),
        ("slow_period", 30),
    )

    def __init__(self):
        self.crossovers = {}
        self._pending_signals: dict[str, dict] = {}
        for data in self.datas:
            fast = bt.indicators.SMA(data.close, period=self.p.fast_period)
            slow = bt.indicators.SMA(data.close, period=self.p.slow_period)
            self.crossovers[data._name] = bt.indicators.CrossOver(fast, slow)

    def next(self):
        for data in self.datas:
            name = data._name
            crossover = self.crossovers[name]
            pos = self.getposition(data)
            signal_date = data.datetime.date().isoformat()
            if not pos:
                if crossover[0] > 0:
                    self._pending_signals[name] = {
                        "direction": "buy",
                        "signal_date": signal_date,
                    }
                    self.buy(data=data)
            elif crossover[0] < 0:
                self._pending_signals[name] = {
                    "direction": "sell",
                    "signal_date": signal_date,
                }
                self.close(data=data)
