# -*- coding: utf-8 -*-
"""内置策略包：导入即完成注册。"""
from app.strategies import (  # noqa: F401
    bias,
    bollinger,
    cdl_bullish_scan,
    double_ma,
    macd,
    momentum,
    rsi,
)
from app.strategies.registry import (
    STRATEGY_REGISTRY,
    get_strategy_meta,
    list_registered_strategies,
)

__all__ = [
    "STRATEGY_REGISTRY",
    "get_strategy_meta",
    "list_registered_strategies",
]
