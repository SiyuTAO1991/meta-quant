# -*- coding: utf-8 -*-
"""Backtrader 回测引擎入口。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger

from app.backtest.data_loader import ChanPandasData, bars_to_dataframe, calc_metrics, setup_cerebro
from app.chan.constants import CHAN_STRATEGY_KEYS
from app.chan.signals import enrich_dataframes_for_chan


@dataclass
class BacktestRunResult:
    total_return: float = 0.0
    annual_return: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    profit_loss_ratio: float = 0.0
    profit_factor: float = 0.0
    max_consecutive_losses: int = 0
    benchmark_return: float = 0.0
    total_pnl: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    open_positions: list[dict] = field(default_factory=list)
    trade_count: int = 0
    initial_cash: float = 0.0
    final_value: float = 0.0
    equity_curve: list[dict] = field(default_factory=list)
    drawdown_curve: list[dict] = field(default_factory=list)
    trade_fills: list[dict] = field(default_factory=list)
    trade_logs: list[dict] = field(default_factory=list)
    trade_marks: list[dict] = field(default_factory=list)


def run_backtest(
    strategy_cls: type,
    stock_bars: dict[str, list[dict]],
    strategy_params: Optional[dict[str, Any]] = None,
    cash: float = 100000.0,
    commission: float = 0.0003,
    enable_stamp_tax: bool = True,
    plot_curve: bool = True,
    position_pct: int = 95,
    strategy_key: str = "",
) -> BacktestRunResult:
    """同步执行 Backtrader 回测。"""
    strategy_params = strategy_params or {}
    dataframes: dict[str, Any] = {}

    for code, bars in stock_bars.items():
        df = bars_to_dataframe(bars)
        if df.empty or len(df) < 5:
            logger.warning(f"skip {code}: insufficient or invalid bars")
            continue
        dataframes[code] = df

    if not dataframes:
        raise ValueError("所选标的在回测区间内无可用日线数据，请先完成数据采集")

    if strategy_key in CHAN_STRATEGY_KEYS:
        dataframes = enrich_dataframes_for_chan(dataframes, strategy_key)
        feed_cls = ChanPandasData
    else:
        feed_cls = None

    cerebro = setup_cerebro(
        strategy_class=strategy_cls,
        dataframes=dataframes,
        cash=cash,
        commission=commission,
        enable_stamp_tax=enable_stamp_tax,
        strategy_params=strategy_params,
        position_pct=position_pct,
        data_class=feed_cls,
    )

    initial = float(cerebro.broker.getvalue())
    results = cerebro.run()
    strat = results[0]
    metrics = calc_metrics(cerebro, strat, dataframes, initial)

    if not plot_curve:
        metrics["equity_curve"] = []
        metrics["drawdown_curve"] = []

    return BacktestRunResult(
        total_return=metrics["total_return"],
        annual_return=metrics["annual_return"],
        max_drawdown=metrics["max_drawdown"],
        calmar_ratio=metrics["calmar_ratio"],
        sharpe_ratio=metrics["sharpe_ratio"],
        win_rate=metrics["win_rate"],
        profit_loss_ratio=metrics["profit_loss_ratio"],
        profit_factor=metrics["profit_factor"],
        max_consecutive_losses=metrics["max_consecutive_losses"],
        benchmark_return=metrics["benchmark_return"],
        total_pnl=metrics["total_pnl"],
        realized_pnl=metrics["realized_pnl"],
        unrealized_pnl=metrics["unrealized_pnl"],
        open_positions=metrics["open_positions"],
        trade_count=metrics["trade_count"],
        initial_cash=round(initial, 2),
        final_value=metrics["final_value"],
        equity_curve=metrics["equity_curve"],
        drawdown_curve=metrics["drawdown_curve"],
        trade_fills=metrics["trade_fills"],
        trade_logs=metrics["trade_logs"],
        trade_marks=metrics["trade_marks"],
    )
