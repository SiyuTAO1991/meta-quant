# -*- coding: utf-8 -*-
"""财经日历采集（百度财经日历）。"""
from __future__ import annotations

import math

import akshare as ak
import pandas as pd
from loguru import logger

from app.database import execute_update

COUNTRIES = {"中国", "美国", "欧元区", "日本", "英国"}
EVENT_TYPE_MAP = {
    "rate": ["利率", "FOMC", "加息", "降息", "LPR"],
    "inflation": ["CPI", "PPI", "通胀"],
    "employment": ["就业", "非农", "失业率"],
    "pmi": ["PMI", "采购经理"],
    "gdp": ["GDP"],
    "trade": ["贸易", "进出口"],
    "policy": ["政策", "两会", "决议"],
}


def _classify(name: str) -> str:
    for etype, kws in EVENT_TYPE_MAP.items():
        if any(k in name for k in kws):
            return etype
    return "other"


def _to_str(val):
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    s = str(val).strip()
    return s or None


def _to_importance(val, default: int = 0) -> int:
    """重要性：0=未知 1=低 2=中 3=高；NaN/空值回退默认值。"""
    if val is None:
        return default
    try:
        if isinstance(val, float) and math.isnan(val):
            return default
        if pd.isna(val):
            return default
    except Exception:
        pass
    try:
        num = int(float(val))
    except (TypeError, ValueError):
        return default
    if num < 0:
        return 0
    if num > 3:
        return 3
    return num


def run_calendar_crawl(start_date: str | None = None, end_date: str | None = None) -> dict:
    today = pd.Timestamp.now().normalize()
    if start_date and end_date:
        start = pd.Timestamp(str(start_date).replace("-", ""))
        end = pd.Timestamp(str(end_date).replace("-", ""))
        dates = pd.date_range(start, end)
    else:
        dates = pd.date_range(today - pd.Timedelta(days=3), today + pd.Timedelta(days=14))
    frames = []
    for d in dates:
        try:
            part = ak.news_economic_baidu(date=d.strftime("%Y%m%d"))
            if part is not None and len(part) > 0:
                frames.append(part)
        except Exception:
            continue
    if not frames:
        return {"rows": 0, "message": "empty calendar"}

    df = pd.concat(frames, ignore_index=True)
    col_map = {}
    for col in df.columns:
        c = str(col)
        if "日期" in c:
            col_map["date"] = col
        elif "时间" in c:
            col_map["time"] = col
        elif "国家" in c or "地区" in c:
            col_map["country"] = col
        elif "事件" in c:
            col_map["event"] = col
        elif "实际" in c:
            col_map["actual"] = col
        elif "预期" in c:
            col_map["forecast"] = col
        elif "前值" in c:
            col_map["previous"] = col
        elif "重要" in c:
            col_map["importance"] = col

    if "date" not in col_map or "event" not in col_map:
        logger.warning(f"calendar columns unrecognized: {list(df.columns)}")
        return {"rows": 0, "message": "unrecognized columns"}

    if "country" in col_map:
        df = df[df[col_map["country"]].isin(COUNTRIES)]

    saved = 0
    skipped = 0
    for _, row in df.iterrows():
        event_date = row[col_map["date"]]
        if pd.isna(event_date):
            skipped += 1
            continue
        event_date_str = event_date.strftime("%Y-%m-%d") if hasattr(event_date, "strftime") else str(event_date)[:10]
        title = str(row[col_map["event"]]).strip()
        if not title or title.lower() in ("nan", "none"):
            skipped += 1
            continue
        country = str(row.get(col_map.get("country", ""), "") or "").strip() or "CN"
        if country.lower() in ("nan", "none"):
            country = "CN"
        importance = _to_importance(row.get(col_map.get("importance", ""), None), default=0)
        try:
            execute_update(
                """
                INSERT INTO trade_calendar_event
                (event_date, event_time, title, country, category, importance,
                 forecast_value, actual_value, previous_value, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'baidu')
                ON DUPLICATE KEY UPDATE
                actual_value=COALESCE(VALUES(actual_value), actual_value),
                forecast_value=COALESCE(VALUES(forecast_value), forecast_value),
                previous_value=COALESCE(VALUES(previous_value), previous_value),
                importance=VALUES(importance)
                """,
                (
                    event_date_str,
                    _to_str(row.get(col_map.get("time", ""), None)),
                    title,
                    country,
                    _classify(title),
                    importance,
                    _to_str(row.get(col_map.get("forecast", ""), None)),
                    _to_str(row.get(col_map.get("actual", ""), None)),
                    _to_str(row.get(col_map.get("previous", ""), None)),
                ),
            )
            saved += 1
        except Exception as e:
            skipped += 1
            logger.warning(f"calendar row skip: {title} err={e}")
    return {
        "rows": saved,
        "message": f"range={start_date or '-'}~{end_date or '-'}, saved={saved}, skipped={skipped}",
    }
