# -*- coding: utf-8 -*-
"""技术因子配置加载（tech_factors.json）。"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_CONFIG_PATH = Path(__file__).with_name("tech_factors.json")


@lru_cache(maxsize=1)
def load_tech_factor_config() -> dict:
    with _CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_tech_factor_categories() -> list[dict]:
    return list(load_tech_factor_config().get("categories") or [])


def get_tech_factor_taxonomy() -> dict[str, dict]:
    taxonomy: dict[str, dict] = {}
    for cat in get_tech_factor_categories():
        taxonomy[cat["key"]] = {
            "name": cat.get("name") or cat["key"],
            "desc": cat.get("desc") or "",
            "features": [item["code"] for item in cat.get("features") or []],
        }
    return taxonomy


def get_all_tech_factor_codes() -> list[str]:
    codes: list[str] = []
    for cat in get_tech_factor_categories():
        for item in cat.get("features") or []:
            code = item.get("code")
            if code:
                codes.append(code)
    return codes


def get_tech_factor_options() -> list[dict]:
    options: list[dict] = []
    for cat in get_tech_factor_categories():
        for item in cat.get("features") or []:
            options.append(
                {
                    "code": item["code"],
                    "name": item.get("name") or item["code"],
                    "category": cat.get("name") or cat["key"],
                    "category_key": cat["key"],
                }
            )
    return options
