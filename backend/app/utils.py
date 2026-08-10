# -*- coding: utf-8 -*-
"""通用工具。"""
from __future__ import annotations

from datetime import datetime


def normalize_date(value: str, as_dash: bool = True) -> str:
    """将 YYYYMMDD / YYYY-MM-DD 转为统一格式。"""
    if not value:
        return value
    raw = value.strip().replace("-", "").replace("/", "")
    if len(raw) != 8 or not raw.isdigit():
        return value
    if as_dash:
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return raw


def parse_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text or text.lower() in ("none", "nan", "nat"):
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y%m%d",
    ):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    return None


def level_to_importance(level: str) -> int | None:
    mapping = {
        "high": 3,
        "medium": 2,
        "mid": 2,
        "low": 1,
        "高": 3,
        "中": 2,
        "低": 1,
    }
    if not level:
        return None
    return mapping.get(level.strip().lower())


def code_to_symbol(ts_code: str) -> str:
    return ts_code.split(".")[0] if ts_code else ts_code
