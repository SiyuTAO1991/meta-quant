# -*- coding: utf-8 -*-
"""策略内存注册表：strategy_code -> 策略类与元数据。"""
from __future__ import annotations

from typing import Any, Callable, Optional, Type

STRATEGY_REGISTRY: dict[str, dict[str, Any]] = {}


def register_strategy(
    code: str,
    name: str,
    category: str,
    description: str,
    param_template: list[dict[str, Any]],
) -> Callable:
    """装饰器：将 Backtrader Strategy 注册到内存 Map。"""

    def decorator(cls: Type) -> Type:
        STRATEGY_REGISTRY[code] = {
            "cls": cls,
            "strategy_code": code,
            "strategy_name": name,
            "strategy_category": category,
            "description": description,
            "param_template": param_template,
            "is_built_in": True,
        }
        return cls

    return decorator


def get_strategy_meta(code: str) -> Optional[dict[str, Any]]:
    return STRATEGY_REGISTRY.get(code)


def list_registered_strategies() -> list[dict[str, Any]]:
    items = []
    for meta in STRATEGY_REGISTRY.values():
        items.append(
            {
                "strategy_code": meta["strategy_code"],
                "strategy_name": meta["strategy_name"],
                "strategy_category": meta["strategy_category"],
                "description": meta["description"],
                "param_template": meta["param_template"],
                "is_built_in": meta.get("is_built_in", True),
            }
        )
    return items
