# -*- coding: utf-8 -*-
"""缠论笔端翻转策略：向下笔结束买入，向上笔结束卖出（不依赖中枢）。"""
from __future__ import annotations

import backtrader as bt

from app.strategies.registry import register_strategy


@register_strategy(
    code="chan_bi_flip",
    name="缠论笔端翻转",
    category="缠论",
    description="不判断中枢：向下（绿）笔走完买入，向上（红）笔走完卖出",
    param_template=[],
)
class ChanBiFlipStrategy(bt.Strategy):
    """
    信号约定（由 enrich 写入 chan_signal）:
      4  = 向下笔终点 → 买入
     -4 = 向上笔终点 → 卖出
    """

    def __init__(self):
        self._pending_signals: dict[str, dict] = {}
        self._order = None

    def notify_order(self, order):
        if order.status == order.Completed:
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
            signal = int(data.chan_signal[0])

            if not pos:
                if signal == 4:
                    self._pending_signals[code] = {"direction": "buy", "signal_date": signal_date}
                    self._order = self.buy(data=data)
                continue

            if signal == -4:
                self._pending_signals[code] = {"direction": "sell", "signal_date": signal_date}
                self._order = self.close(data=data)
