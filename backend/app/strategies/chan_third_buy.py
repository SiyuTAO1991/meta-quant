# -*- coding: utf-8 -*-
"""缠论3买策略（参考训练营 5-缠论三买策略回测）。"""
from __future__ import annotations

import backtrader as bt

from app.strategies.registry import register_strategy


@register_strategy(
    code="chan_third_buy",
    name="缠论三买策略",
    category="缠论",
    description="ChanAnalyzer 第三类买点入场；跌破中枢 ZG 止损，固定止盈或三卖离场",
    param_template=[
        {
            "param_name": "take_profit_pct",
            "param_label": "止盈比例",
            "param_type": "float",
            "default_value": 0.15,
            "min": 0.05,
            "max": 0.5,
        },
        {
            "param_name": "use_chan_stop",
            "param_label": "中枢止损",
            "param_type": "int",
            "default_value": 1,
            "min": 0,
            "max": 1,
        },
    ],
)
class ChanThirdBuyStrategy(bt.Strategy):
    params = (
        ("take_profit_pct", 0.15),
        ("use_chan_stop", 1),
    )

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
                if int(data.chan_signal[0]) == 3:
                    self._pending_signals[code] = {"direction": "buy", "signal_date": signal_date}
                    self._order = self.buy(data=data)
                    zg = float(data.chan_zg[0] or 0)
                    if self.p.use_chan_stop and zg > 0:
                        self._stop_price[code] = zg
                    else:
                        self._stop_price[code] = float(data.close[0]) * 0.93
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

            if int(data.chan_signal[0]) == -3:
                self._pending_signals[code] = {"direction": "sell", "signal_date": signal_date}
                self._order = self.close(data=data)
