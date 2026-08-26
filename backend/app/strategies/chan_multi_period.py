# -*- coding: utf-8 -*-
"""多周期缠论策略（参考训练营 7-多周期缠论策略）。"""
from __future__ import annotations

import backtrader as bt

from app.strategies.registry import register_strategy


@register_strategy(
    code="chan_multi_period",
    name="多周期缠论策略",
    category="缠论",
    description="周线 ChanAnalyzer 趋势向上 + 日线第三类买点入场；周线转空或三卖离场",
    param_template=[
        {
            "param_name": "take_profit_pct",
            "param_label": "止盈比例",
            "param_type": "float",
            "default_value": 0.15,
            "min": 0.05,
            "max": 0.5,
        },
    ],
)
class ChanMultiPeriodStrategy(bt.Strategy):
    params = (("take_profit_pct", 0.15),)

    def __init__(self):
        self._pending_signals: dict[str, dict] = {}
        self._entry_price: dict[str, float] = {}
        self._stop_price: dict[str, float] = {}
        self._order = None

    def notify_order(self, order):
        if order.status == order.Completed:
            code = getattr(order.data, "_name", "") or ""
            if order.isbuy():
                self._entry_price[code] = float(order.executed.price)
            self._order = None
        elif order.status in (order.Canceled, order.Margin, order.Rejected):
            self._order = None

    def next(self):
        if self._order:
            return

        for data in self.datas:
            code = data._name
            pos = self.getposition(data)
            signal_date = data.datetime.date().isoformat()

            if not pos:
                weekly_up = int(data.weekly_trend[0]) == 1
                daily_third_buy = int(data.chan_signal[0]) == 3
                if weekly_up and daily_third_buy:
                    self._pending_signals[code] = {"direction": "buy", "signal_date": signal_date}
                    self._order = self.buy(data=data)
                    zg = float(data.chan_zg[0] or 0)
                    self._stop_price[code] = zg if zg > 0 else float(data.close[0]) * 0.93
                continue

            current_price = float(data.close[0])
            stop = self._stop_price.get(code)
            if stop and current_price < stop:
                self._pending_signals[code] = {"direction": "sell", "signal_date": signal_date}
                self._order = self.close(data=data)
                continue

            entry = self._entry_price.get(code)
            if entry and (current_price / entry - 1) >= float(self.p.take_profit_pct):
                self._pending_signals[code] = {"direction": "sell", "signal_date": signal_date}
                self._order = self.close(data=data)
                continue

            if int(data.chan_signal[0]) == -3 or int(data.weekly_trend[0]) == -1:
                self._pending_signals[code] = {"direction": "sell", "signal_date": signal_date}
                self._order = self.close(data=data)
