# -*- coding: utf-8 -*-
"""
回测数据加载与指标计算（参考 CASE-Backtrader 训练营 data_loader.py）
"""
from __future__ import annotations

from typing import Any, Optional

import backtrader as bt
import pandas as pd


def bars_to_dataframe(bars: list[dict]) -> pd.DataFrame:
    """将 trade_stock_daily 查询结果转为 Backtrader 可用的 DataFrame。"""
    df = pd.DataFrame(bars)
    if df.empty:
        return df

    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.rename(
        columns={
            "open_price": "open",
            "high_price": "high",
            "low_price": "low",
            "close_price": "close",
        }
    )
    for col in ("open", "high", "low", "close", "volume"):
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df = df.set_index("trade_date").sort_index()
    # 过滤无效价格，避免后复权异常导致信号错误
    valid_mask = (df["open"] > 0) & (df["high"] > 0) & (df["low"] > 0) & (df["close"] > 0)
    df = df.loc[valid_mask]
    if df.empty:
        return df
    return df[["open", "high", "low", "close", "volume"]]


def wrap_strategy(strategy_class: type) -> type:
    """
    包装策略类，自动记录买卖明细与每日净值，不影响原策略逻辑。
    参考训练营 _wrap_strategy 实现，并兼容多标的。
    """

    class WrappedStrategy(strategy_class):
        def __init__(self):
            super().__init__()
            self._trade_log: list[dict] = []
            self._nav_log: list[dict] = []
            self._closed_bt_trades: list[dict] = []

        def notify_order(self, order):
            if order.status == order.Completed:
                stock_code = getattr(order.data, "_name", "") or ""
                direction = "BUY" if order.isbuy() else "SELL"
                entry = {
                    "date": bt.num2date(order.executed.dt).date().isoformat(),
                    "type": direction,
                    "price": round(float(order.executed.price), 4),
                    "size": abs(int(order.executed.size)),
                    "stock_code": stock_code,
                }
                pending = getattr(self, "_pending_signals", {}).get(stock_code)
                if pending and pending.get("direction") == direction.lower():
                    entry["signal_date"] = pending["signal_date"]
                self._trade_log.append(entry)
            parent = super()
            if hasattr(parent, "notify_order"):
                parent.notify_order(order)

        def notify_trade(self, trade):
            if trade.isclosed:
                data = trade.data
                code = getattr(data, "_name", "") or ""
                buy_fills = [x for x in self._trade_log if x.get("stock_code") == code and x.get("type") == "BUY"]
                sell_fills = [x for x in self._trade_log if x.get("stock_code") == code and x.get("type") == "SELL"]
                idx = len(self._closed_bt_trades)
                buy_item = buy_fills[idx] if idx < len(buy_fills) else {}
                sell_item = sell_fills[idx] if idx < len(sell_fills) else {}
                self._closed_bt_trades.append(
                    {
                        "trade_id": idx + 1,
                        "stock_code": code,
                        "buy_signal_date": buy_item.get("signal_date") or buy_item.get("date"),
                        "buy_date": buy_item.get("date"),
                        "buy_price": buy_item.get("price") or round(float(trade.price), 4),
                        "sell_signal_date": sell_item.get("signal_date") or sell_item.get("date"),
                        "sell_date": sell_item.get("date"),
                        "sell_price": sell_item.get("price") or round(float(trade.price), 4),
                        "pnl": round(float(trade.pnl), 4),
                        "pnlcomm": round(float(trade.pnlcomm), 4),
                    }
                )
            parent = super()
            if hasattr(parent, "notify_trade"):
                parent.notify_trade(trade)

        def next(self):
            self._nav_log.append(
                {
                    "date": self.datetime.date().isoformat(),
                    "nav": round(float(self.broker.getvalue()), 2),
                }
            )
            super().next()

    WrappedStrategy.__name__ = strategy_class.__name__
    WrappedStrategy.__qualname__ = strategy_class.__qualname__
    WrappedStrategy.__module__ = strategy_class.__module__
    return WrappedStrategy


def calc_benchmark_return(dataframes: dict[str, pd.DataFrame]) -> float:
    """计算买入持有基准收益；多标的时取各标的基准收益的算术平均。"""
    returns: list[float] = []
    for df in dataframes.values():
        valid_close = df["close"][df["close"] > 0]
        if len(valid_close) < 2:
            continue
        start = float(valid_close.iloc[0])
        end = float(valid_close.iloc[-1])
        if start > 0:
            returns.append(end / start - 1.0)
    if not returns:
        return 0.0
    return sum(returns) / len(returns)


def calc_drawdown_curve(nav_log: list[dict]) -> tuple[list[dict], float]:
    """由净值序列计算回撤曲线，返回 (曲线, 最大回撤，负值)。"""
    if not nav_log:
        return [], 0.0

    peak = nav_log[0]["nav"]
    max_drawdown = 0.0
    curve: list[dict] = []
    for point in nav_log:
        nav = point["nav"]
        if nav > peak:
            peak = nav
        dd = (nav - peak) / peak if peak else 0.0
        max_drawdown = max(max_drawdown, abs(dd))
        curve.append({"date": point["date"], "drawdown": round(-abs(dd), 6)})
    return curve, -round(max_drawdown, 6)


def calc_metrics(
    cerebro: bt.Cerebro,
    strat: Any,
    dataframes: dict[str, pd.DataFrame],
    initial_cash: float,
) -> dict[str, Any]:
    """从 Backtrader 结果中提取完整绩效指标（参考训练营 _calc_metrics）。"""
    final_value = float(cerebro.broker.getvalue())
    total_return = (final_value - initial_cash) / initial_cash if initial_cash else 0.0

    trading_days = max((len(df) for df in dataframes.values()), default=0)
    years = trading_days / 252 if trading_days else 0.0
    if years > 0 and total_return > -1:
        annual_return = (1 + total_return) ** (1 / years) - 1
    else:
        annual_return = total_return

    sharpe_ratio = strat.analyzers.sharpe.get_analysis().get("sharperatio", 0) or 0

    nav_log = getattr(strat, "_nav_log", [])
    max_drawdown = 0.0
    if nav_log:
        _, max_drawdown = calc_drawdown_curve(nav_log)
    else:
        dd = strat.analyzers.drawdown.get_analysis()
        bt_dd = float(dd.get("max", {}).get("drawdown", 0) or 0) / 100
        max_drawdown = -min(bt_dd, 1.0)

    calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0.0

    ta = strat.analyzers.trades.get_analysis()
    total_trades = int(ta.get("total", {}).get("total", 0) or 0)
    won_trades = int(ta.get("won", {}).get("total", 0) or 0)
    win_rate = won_trades / total_trades if total_trades > 0 else 0.0

    avg_win = float(ta.get("won", {}).get("pnl", {}).get("average", 0) or 0)
    avg_loss = float(ta.get("lost", {}).get("pnl", {}).get("average", 0) or 0)
    profit_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0.0

    gross_profit = float(ta.get("won", {}).get("pnl", {}).get("total", 0) or 0)
    gross_loss = float(ta.get("lost", {}).get("pnl", {}).get("total", 0) or 0)
    profit_factor = abs(gross_profit / gross_loss) if gross_loss != 0 else 0.0

    streak = ta.get("streak", {})
    lost_streak = streak.get("lost", {}) if streak else {}
    max_consecutive_losses = int(lost_streak.get("longest", 0) or 0) if lost_streak else 0

    benchmark_return = calc_benchmark_return(dataframes)

    equity_curve = [{"date": x["date"], "equity": x["nav"]} for x in nav_log]
    drawdown_curve, _ = calc_drawdown_curve(nav_log)

    trade_fills = []
    for item in getattr(strat, "_trade_log", []):
        trade_fills.append(
            {
                "stock_code": item.get("stock_code", ""),
                "trade_date": item.get("date"),
                "signal_date": item.get("signal_date") or item.get("date"),
                "direction": "buy" if item.get("type") == "BUY" else "sell",
                "price": item.get("price"),
                "volume": item.get("size"),
                "pnl": 0.0,
            }
        )

    trade_logs = getattr(strat, "_closed_bt_trades", None) or _build_closed_trades(
        getattr(strat, "_trade_log", []), trade_fills
    )
    for i, item in enumerate(trade_logs):
        item.setdefault("trade_id", i + 1)

    open_positions = _collect_open_positions(strat)
    total_pnl = round(final_value - initial_cash, 2)
    realized_pnl = round(sum(float(t.get("pnlcomm", t.get("pnl", 0)) or 0) for t in trade_logs), 2)
    unrealized_pnl = round(total_pnl - realized_pnl, 2)

    return {
        "final_value": round(final_value, 2),
        "total_return": round(total_return, 6),
        "annual_return": round(annual_return, 6),
        "max_drawdown": round(max_drawdown, 6),
        "calmar_ratio": round(calmar_ratio, 6),
        "sharpe_ratio": round(float(sharpe_ratio or 0), 6),
        "win_rate": round(win_rate, 6),
        "profit_loss_ratio": round(profit_loss_ratio, 6),
        "profit_factor": round(profit_factor, 6),
        "max_consecutive_losses": max_consecutive_losses,
        "trade_count": total_trades,
        "benchmark_return": round(benchmark_return, 6),
        "trading_days": trading_days,
        "total_pnl": total_pnl,
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "open_positions": open_positions,
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "trade_fills": trade_fills,
        "trade_logs": trade_logs,
        "trade_marks": getattr(strat, "_trade_log", []),
    }


def _build_closed_trades(trade_log: list[dict], trade_fills: list[dict]) -> list[dict]:
    """将买卖流水配对为闭环交易记录。"""
    open_lots: dict[str, list[dict]] = {}
    closed: list[dict] = []

    for item in trade_log:
        code = item.get("stock_code") or "default"
        if item.get("type") == "BUY":
            open_lots.setdefault(code, []).append(item)
            continue
        if item.get("type") != "SELL":
            continue
        if not open_lots.get(code):
            continue
        buy_item = open_lots[code].pop(0)
        buy_price = float(buy_item.get("price") or 0)
        sell_price = float(item.get("price") or 0)
        size = float(item.get("size") or buy_item.get("size") or 0)
        pnl = (sell_price - buy_price) * size
        closed.append(
            {
                "trade_id": len(closed) + 1,
                "stock_code": code,
                "buy_signal_date": buy_item.get("signal_date") or buy_item.get("date"),
                "buy_date": buy_item.get("date"),
                "buy_price": round(buy_price, 4),
                "sell_signal_date": item.get("signal_date") or item.get("date"),
                "sell_date": item.get("date"),
                "sell_price": round(sell_price, 4),
                "pnl": round(pnl, 4),
                "pnlcomm": round(pnl, 4),
            }
        )

    for fill in reversed(trade_fills):
        for trade in reversed(closed):
            if (
                fill.get("stock_code") == trade.get("stock_code")
                and fill.get("trade_date") == trade.get("sell_date")
                and fill.get("direction") == "sell"
            ):
                fill["pnl"] = trade.get("pnlcomm", 0)
                break

    return closed


def _collect_open_positions(strat: Any) -> list[dict]:
    """收集回测结束时仍持有的仓位及浮动盈亏。"""
    open_positions: list[dict] = []
    for data in strat.datas:
        pos = strat.getposition(data)
        size = float(pos.size)
        if not size:
            continue
        code = getattr(data, "_name", "") or ""
        avg_price = float(pos.price)
        last_price = float(data.close[0])
        buy_date = None
        buy_signal_date = None
        for item in reversed(getattr(strat, "_trade_log", [])):
            if item.get("stock_code") == code and item.get("type") == "BUY":
                buy_date = item.get("date")
                buy_signal_date = item.get("signal_date") or buy_date
                break
        market_value = size * last_price
        cost_value = size * avg_price
        open_positions.append(
            {
                "stock_code": code,
                "volume": int(size),
                "buy_signal_date": buy_signal_date,
                "buy_date": buy_date,
                "avg_price": round(avg_price, 4),
                "last_price": round(last_price, 4),
                "market_value": round(market_value, 2),
                "cost_value": round(cost_value, 2),
                "unrealized_pnl": round(market_value - cost_value, 2),
            }
        )
    return open_positions


class ChanPandasData(bt.feeds.PandasData):
    """携带缠论信号列的 Backtrader 数据源。"""

    lines = ("chan_signal", "chan_zg", "chan_zd", "weekly_trend")
    params = (
        ("chan_signal", "chan_signal"),
        ("chan_zg", "chan_zg"),
        ("chan_zd", "chan_zd"),
        ("weekly_trend", "weekly_trend"),
    )


def setup_cerebro(
    strategy_class: type,
    dataframes: dict[str, pd.DataFrame],
    cash: float,
    commission: float,
    enable_stamp_tax: bool,
    strategy_params: Optional[dict[str, Any]] = None,
    position_pct: int = 95,
    data_class: Optional[type] = None,
) -> bt.Cerebro:
    """创建并配置 Cerebro 引擎。"""
    strategy_params = strategy_params or {}
    feed_cls = data_class or bt.feeds.PandasData
    wrapped = wrap_strategy(strategy_class)

    cerebro = bt.Cerebro(stdstats=False)
    cerebro.broker.setcash(cash)
    cerebro.broker.addcommissioninfo(
        _build_commission(commission=commission, enable_stamp_tax=enable_stamp_tax)
    )

    added = 0
    for code, df in dataframes.items():
        if df.empty or len(df) < 5:
            continue
        cerebro.adddata(feed_cls(dataname=df, name=code))
        added += 1

    if added == 0:
        raise ValueError("所选标的在回测区间内无可用日线数据，请先完成数据采集")

    percents = max(5, min(position_pct, int(position_pct / added)))
    cerebro.addsizer(bt.sizers.PercentSizer, percents=percents)
    cerebro.addstrategy(wrapped, **strategy_params)

    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.02)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
    return cerebro


class _ChinaStockCommission(bt.CommInfoBase):
    params = (
        ("commission", 0.0003),
        ("stamp_duty", 0.001),
        ("enable_stamp_tax", True),
        ("stocklike", True),
        ("commtype", bt.CommInfoBase.COMM_PERC),
        ("percabs", True),
    )

    def _getcommission(self, size, price, pseudoexec):
        turnover = abs(size) * price
        fee = turnover * self.p.commission
        if size < 0 and self.p.enable_stamp_tax:
            fee += turnover * self.p.stamp_duty
        return fee


def _build_commission(commission: float, enable_stamp_tax: bool) -> _ChinaStockCommission:
    return _ChinaStockCommission(commission=commission, enable_stamp_tax=enable_stamp_tax)
