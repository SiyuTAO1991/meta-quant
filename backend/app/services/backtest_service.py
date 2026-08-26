# -*- coding: utf-8 -*-
"""回测业务服务：建表、跑回测、持久化结果、查询报告。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from loguru import logger

from app.backtest.engine import run_backtest
from app.database import execute_many, execute_query, execute_update
from app.schemas.common import serialize_row
from app.services import stock_service, strategy_service
from app.services.chan_service import CHAN_STRATEGY_KEYS, build_chan_report_extras, calc_chan_min_bars
from app.strategies.registry import get_strategy_meta
from app.utils import normalize_date


def _ensure_tables() -> None:
    execute_update(
        """
        CREATE TABLE IF NOT EXISTS trade_backtest_task (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            task_id VARCHAR(64) NOT NULL,
            ts_code VARCHAR(500) NOT NULL,
            strategy_id BIGINT NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            initial_capital DECIMAL(20,2) NOT NULL DEFAULT 100000.00,
            commission DECIMAL(10,6) NOT NULL DEFAULT 0.000300,
            enable_stamp_tax TINYINT(1) NOT NULL DEFAULT 1,
            strategy_params JSON,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            error_msg TEXT,
            create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finish_time DATETIME NULL,
            UNIQUE KEY uk_backtest_task_id (task_id),
            KEY idx_backtest_strategy (strategy_id),
            KEY idx_backtest_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )
    execute_update(
        """
        CREATE TABLE IF NOT EXISTS trade_backtest_result (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            task_id VARCHAR(64) NOT NULL,
            total_return DECIMAL(16,6),
            annual_return DECIMAL(16,6),
            max_drawdown DECIMAL(16,6),
            calmar_ratio DECIMAL(16,6),
            sharpe_ratio DECIMAL(16,6),
            win_rate DECIMAL(16,6),
            profit_loss_ratio DECIMAL(16,6),
            trade_count INT DEFAULT 0,
            final_value DECIMAL(20,2),
            report_data JSON,
            UNIQUE KEY uk_backtest_result_task (task_id),
            KEY idx_backtest_result_task (task_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )
    execute_update(
        """
        CREATE TABLE IF NOT EXISTS trade_backtest_trade (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            task_id VARCHAR(64) NOT NULL,
            stock_code VARCHAR(20),
            trade_date DATE NOT NULL,
            direction VARCHAR(10) NOT NULL,
            price DECIMAL(16,4) NOT NULL,
            volume INT NOT NULL,
            pnl DECIMAL(20,4),
            KEY idx_backtest_trade_task (task_id),
            KEY idx_backtest_trade_date (trade_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )


def _load_stock_bars(stock_list: list[str], start_date: str, end_date: str) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for code in stock_list:
        code = (code or "").strip().upper()
        if not code:
            continue
        bars = stock_service.query_stock_daily(code, start_date, end_date)
        if bars:
            result[code] = bars
    return result


def _validate_params(strategy_key: str, strategy_params: dict[str, Any]) -> dict[str, Any]:
    meta = get_strategy_meta(strategy_key)
    if not meta:
        raise ValueError(f"未知策略: {strategy_key}")
    cleaned = dict(strategy_params or {})
    for item in meta.get("param_template", []):
        name = item["param_name"]
        if name not in cleaned:
            cleaned[name] = item.get("default_value")
        value = cleaned[name]
        ptype = item.get("param_type", "int")
        if ptype == "int":
            value = int(value)
        elif ptype == "float":
            value = float(value)
        min_v = item.get("min")
        max_v = item.get("max")
        if min_v is not None and value < min_v:
            raise ValueError(f"参数 {name} 不能小于 {min_v}")
        if max_v is not None and value > max_v:
            raise ValueError(f"参数 {name} 不能大于 {max_v}")
        cleaned[name] = value

    if strategy_key == "double_ma":
        if int(cleaned.get("fast_period", 0)) >= int(cleaned.get("slow_period", 0)):
            raise ValueError("快线周期必须小于慢线周期")
    if strategy_key == "rsi":
        if int(cleaned.get("oversold", 0)) >= int(cleaned.get("overbought", 0)):
            raise ValueError("超卖阈值必须小于超买阈值")
    if strategy_key == "macd":
        if int(cleaned.get("short", 0)) >= int(cleaned.get("long", 0)):
            raise ValueError("MACD 短周期必须小于长周期")
    if strategy_key == "bias":
        if float(cleaned.get("buy_threshold", 0)) >= float(cleaned.get("sell_threshold", 0)):
            raise ValueError("买入阈值必须小于卖出阈值")
    return cleaned


def run_backtest_task(
    stock_list: list[str],
    start_date: str,
    end_date: str,
    strategy_key: str,
    strategy_params: Optional[dict[str, Any]] = None,
    cash: float = 100000.0,
    commission: float = 0.0003,
    enable_stamp_tax: bool = True,
    plot_curve: bool = True,
) -> dict:
    """同步执行回测并落库，返回摘要指标。"""
    _ensure_tables()
    if not stock_list:
        raise ValueError("stock_list 不能为空")

    meta = get_strategy_meta(strategy_key)
    if not meta:
        raise ValueError(f"未知策略: {strategy_key}")

    params = _validate_params(strategy_key, strategy_params or {})
    strategy_id = strategy_service.get_strategy_db_id(strategy_key)
    start = normalize_date(start_date, as_dash=True)
    end = normalize_date(end_date, as_dash=True)
    if start > end:
        raise ValueError("开始日期不能晚于结束日期")

    # 校验股票、检查数据覆盖，不足则自动采集
    min_bars = calc_chan_min_bars(start, end) if strategy_key in CHAN_STRATEGY_KEYS else 20
    stock_list = stock_service.ensure_daily_data(stock_list, start, end, min_bars=min_bars)

    task_uuid = uuid.uuid4().hex
    ts_code_text = ",".join([c.strip().upper() for c in stock_list if c and c.strip()])

    execute_update(
        """
        INSERT INTO trade_backtest_task
            (task_id, ts_code, strategy_id, start_date, end_date, initial_capital,
             commission, enable_stamp_tax, strategy_params, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'running')
        """,
        (
            task_uuid,
            ts_code_text,
            strategy_id,
            start,
            end,
            cash,
            commission,
            1 if enable_stamp_tax else 0,
            json.dumps(params, ensure_ascii=False),
        ),
    )
    task_rows = execute_query(
        "SELECT id FROM trade_backtest_task WHERE task_id = %s LIMIT 1",
        (task_uuid,),
    )
    backtest_id = int(task_rows[0]["id"])

    try:
        stock_bars = _load_stock_bars(stock_list, start, end)
        if not stock_bars:
            raise ValueError("所选标的在区间内无日线数据，请先调用数据采集模块采集")

        result = run_backtest(
            strategy_cls=meta["cls"],
            stock_bars=stock_bars,
            strategy_params=params,
            cash=cash,
            commission=commission,
            enable_stamp_tax=enable_stamp_tax,
            plot_curve=plot_curve,
            strategy_key=strategy_key,
        )

        report_data = {
            "equity_curve": result.equity_curve,
            "drawdown_curve": result.drawdown_curve,
            "trade_logs": result.trade_logs,
            "trade_marks": result.trade_marks,
            "strategy_params": params,
            "stock_list": list(stock_bars.keys()),
            "benchmark_return": result.benchmark_return,
            "profit_factor": result.profit_factor,
            "max_consecutive_losses": result.max_consecutive_losses,
            "total_pnl": result.total_pnl,
            "realized_pnl": result.realized_pnl,
            "unrealized_pnl": result.unrealized_pnl,
            "open_positions": result.open_positions,
            **build_chan_report_extras(stock_bars, strategy_key),
        }

        execute_update(
            """
            INSERT INTO trade_backtest_result
                (task_id, total_return, annual_return, max_drawdown, calmar_ratio,
                 sharpe_ratio, win_rate, profit_loss_ratio, trade_count, final_value, report_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                total_return=VALUES(total_return),
                annual_return=VALUES(annual_return),
                max_drawdown=VALUES(max_drawdown),
                calmar_ratio=VALUES(calmar_ratio),
                sharpe_ratio=VALUES(sharpe_ratio),
                win_rate=VALUES(win_rate),
                profit_loss_ratio=VALUES(profit_loss_ratio),
                trade_count=VALUES(trade_count),
                final_value=VALUES(final_value),
                report_data=VALUES(report_data)
            """,
            (
                task_uuid,
                result.total_return,
                result.annual_return,
                result.max_drawdown,
                result.calmar_ratio,
                result.sharpe_ratio,
                result.win_rate,
                result.profit_loss_ratio,
                result.trade_count,
                result.final_value,
                json.dumps(report_data, ensure_ascii=False),
            ),
        )

        execute_update("DELETE FROM trade_backtest_trade WHERE task_id = %s", (task_uuid,))
        fill_rows = []
        for fill in result.trade_fills:
            fill_rows.append(
                (
                    task_uuid,
                    fill.get("stock_code"),
                    fill.get("trade_date"),
                    fill.get("direction"),
                    fill.get("price"),
                    fill.get("volume"),
                    fill.get("pnl") or 0,
                )
            )
        if fill_rows:
            execute_many(
                """
                INSERT INTO trade_backtest_trade
                    (task_id, stock_code, trade_date, direction, price, volume, pnl)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                fill_rows,
            )

        execute_update(
            """
            UPDATE trade_backtest_task
            SET status = 'success', finish_time = %s, error_msg = NULL
            WHERE task_id = %s
            """,
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), task_uuid),
        )

        return {
            "backtest_id": backtest_id,
            "strategy_key": strategy_key,
            "stock_list": list(stock_bars.keys()),
            "start_date": start,
            "end_date": end,
            "total_return": result.total_return,
            "sharpe": result.sharpe_ratio,
            "max_drawdown": result.max_drawdown,
            "win_rate": result.win_rate,
        }
    except Exception as e:
        logger.exception(f"backtest failed task_id={task_uuid}")
        execute_update(
            """
            UPDATE trade_backtest_task
            SET status = 'failed', finish_time = %s, error_msg = %s
            WHERE task_id = %s
            """,
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(e)[:2000], task_uuid),
        )
        raise


def get_backtest_report(backtest_id: int) -> dict:
    _ensure_tables()
    tasks = execute_query(
        """
        SELECT t.id, t.task_id, t.ts_code, t.strategy_id, t.start_date, t.end_date,
               t.initial_capital, t.status, t.error_msg, t.create_time, t.finish_time,
               s.strategy_code, s.strategy_name
        FROM trade_backtest_task t
        LEFT JOIN trade_strategy_info s ON s.id = t.strategy_id
        WHERE t.id = %s
        LIMIT 1
        """,
        (backtest_id,),
    )
    if not tasks:
        raise ValueError(f"回测任务不存在: {backtest_id}")

    task = serialize_row(tasks[0])
    if task["status"] == "failed":
        raise ValueError(task.get("error_msg") or "回测失败")
    if task["status"] != "success":
        raise ValueError(f"回测尚未完成，当前状态: {task['status']}")

    results = execute_query(
        """
        SELECT total_return, annual_return, max_drawdown, calmar_ratio, sharpe_ratio,
               win_rate, profit_loss_ratio, trade_count, final_value, report_data
        FROM trade_backtest_result
        WHERE task_id = %s
        LIMIT 1
        """,
        (task["task_id"],),
    )
    if not results:
        raise ValueError("回测结果不存在")

    result = serialize_row(results[0])
    report_data = result.get("report_data") or {}
    if isinstance(report_data, str):
        report_data = json.loads(report_data)

    trades = execute_query(
        """
        SELECT id, stock_code, trade_date, direction, price, volume, pnl
        FROM trade_backtest_trade
        WHERE task_id = %s
        ORDER BY trade_date ASC, id ASC
        """,
        (task["task_id"],),
    )
    trade_fills = [serialize_row(r) for r in trades]
    trade_marks = report_data.get("trade_marks") or []
    mark_lookup = {
        (m.get("stock_code"), m.get("date"), m.get("type")): m.get("signal_date") or m.get("date")
        for m in trade_marks
    }
    for fill in trade_fills:
        direction = str(fill.get("direction") or "").lower()
        side = "BUY" if direction == "buy" else "SELL"
        key = (fill.get("stock_code"), fill.get("trade_date"), side)
        fill["signal_date"] = mark_lookup.get(key) or fill.get("trade_date")

    stock_list = report_data.get("stock_list") or [
        c for c in str(task.get("ts_code") or "").split(",") if c
    ]
    trade_logs = report_data.get("trade_logs") or []
    for i, item in enumerate(trade_logs):
        item.setdefault("trade_id", i + 1)

    return {
        "backtest_id": backtest_id,
        "strategy_key": task.get("strategy_code"),
        "strategy_name": task.get("strategy_name"),
        "stock_list": stock_list,
        "start_date": task.get("start_date"),
        "end_date": task.get("end_date"),
        "initial_cash": task.get("initial_capital"),
        "final_value": result.get("final_value"),
        "total_return": result.get("total_return"),
        "annual_return": result.get("annual_return"),
        "sharpe": result.get("sharpe_ratio"),
        "max_drawdown": result.get("max_drawdown"),
        "calmar_ratio": result.get("calmar_ratio"),
        "win_rate": result.get("win_rate"),
        "profit_loss_ratio": result.get("profit_loss_ratio"),
        "trade_count": result.get("trade_count"),
        "equity_curve": report_data.get("equity_curve") or [],
        "drawdown_curve": report_data.get("drawdown_curve") or [],
        "trade_logs": trade_logs,
        "trade_fills": trade_fills,
        "strategy_params": report_data.get("strategy_params") or {},
        "benchmark_return": report_data.get("benchmark_return"),
        "profit_factor": report_data.get("profit_factor"),
        "max_consecutive_losses": report_data.get("max_consecutive_losses"),
        "total_pnl": report_data.get("total_pnl"),
        "realized_pnl": report_data.get("realized_pnl"),
        "unrealized_pnl": report_data.get("unrealized_pnl"),
        "open_positions": report_data.get("open_positions") or [],
        "trade_marks": report_data.get("trade_marks") or [],
        "chan_signals": report_data.get("chan_signals") or [],
        "chan_signal_stats": report_data.get("chan_signal_stats") or {},
    }
