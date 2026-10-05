# -*- coding: utf-8 -*-
"""财务数据采集（AkShare）。"""
from __future__ import annotations

import akshare as ak
import pandas as pd
from loguru import logger

from app.config import get_settings
from app.database import execute_many, execute_query

INSERT_SQL = """
    INSERT INTO trade_stock_financial
    (stock_code, report_date, revenue, net_profit, eps, roe, roa,
     gross_margin, net_margin, debt_ratio, current_ratio,
     operating_cashflow, total_assets, total_equity, data_source)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
    revenue=VALUES(revenue), net_profit=VALUES(net_profit), eps=VALUES(eps),
    roe=VALUES(roe), roa=VALUES(roa), gross_margin=VALUES(gross_margin),
    net_margin=VALUES(net_margin), debt_ratio=VALUES(debt_ratio),
    current_ratio=VALUES(current_ratio), operating_cashflow=VALUES(operating_cashflow),
    total_assets=VALUES(total_assets), total_equity=VALUES(total_equity)
"""


def _safe_float(val):
    if val is None:
        return None
    try:
        if str(val).strip() in ("", "--", "None", "nan", "NaN"):
            return None
        v = float(val)
        return v if v == v else None
    except (ValueError, TypeError):
        return None


def _to_symbol(ts_code: str) -> str:
    return ts_code.split(".")[0]


def _pick(row: pd.Series, *names):
    """按候选列名取值；优先精确匹配，避免误命中增长率等衍生字段。"""
    cols = [str(c) for c in row.index]

    def _ok(col: str, name: str) -> bool:
        if "增长率" in col or "比重" in col:
            return False
        return col == name or col.startswith(name)

    for name in names:
        if name in row.index:
            val = _safe_float(row[name])
            if val is not None:
                return val
    for name in names:
        for col in cols:
            if _ok(col, name):
                val = _safe_float(row[col])
                if val is not None:
                    return val
    return None


def _crawl_one(stock_code: str, start_date: str | None = None, end_date: str | None = None) -> int:
    symbol = _to_symbol(stock_code)
    try:
        df = ak.stock_financial_analysis_indicator(symbol=symbol)
    except Exception as e:
        logger.warning(f"finance indicator {stock_code} failed: {e}")
        return 0
    if df is None or len(df) == 0:
        return 0

    date_col = "日期" if "日期" in df.columns else df.columns[0]
    df = df.copy()
    df["_report_date"] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=["_report_date"]).sort_values("_report_date")

    if start_date:
        start = pd.to_datetime(str(start_date).replace("-", ""), format="%Y%m%d", errors="coerce")
        if not pd.isna(start):
            df = df[df["_report_date"] >= start]
    if end_date:
        end = pd.to_datetime(str(end_date).replace("-", ""), format="%Y%m%d", errors="coerce")
        if not pd.isna(end):
            df = df[df["_report_date"] <= end]

    # 未指定区间时保留最近 40 期，避免只采到早期数据
    if not start_date and not end_date:
        df = df.tail(40)

    rows = []
    for _, row in df.iterrows():
        report_date = row["_report_date"].strftime("%Y-%m-%d")
        rows.append(
            (
                stock_code,
                report_date,
                None,  # 分析指标接口无营业收入，后续可接利润表补齐
                _pick(
                    row,
                    "扣除非经常性损益后的净利润(元)",
                    "净利润(元)",
                    "净利润",
                ),
                _pick(row, "摊薄每股收益(元)", "加权每股收益(元)", "每股收益_调整后(元)", "摊薄每股收益", "每股收益"),
                _pick(row, "净资产收益率(%)", "加权净资产收益率(%)", "净资产收益率", "加权净资产收益率"),
                _pick(row, "总资产净利润率(%)", "总资产利润率(%)", "资产报酬率(%)", "总资产净利率"),
                _pick(row, "销售毛利率(%)", "销售毛利率", "毛利率"),
                _pick(row, "销售净利率(%)", "销售净利率", "净利率"),
                _pick(row, "资产负债率(%)", "资产负债率"),
                _pick(row, "流动比率"),
                _pick(row, "每股经营性现金流(元)"),
                _pick(row, "总资产(元)", "总资产"),
                None,
                "akshare",
            )
        )
    return execute_many(INSERT_SQL, rows)


def _ymd_to_sql_date(value: str | None) -> str | None:
    """YYYYMMDD / YYYY-MM-DD → YYYY-MM-DD；无效则 None。"""
    if not value:
        return None
    raw = str(value).strip().replace("-", "")
    if len(raw) != 8 or not raw.isdigit():
        return None
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"


def _codes_with_data_in_range(start_date: str | None, end_date: str | None) -> set[str]:
    """区间内至少有 1 条财务记录的股票代码。"""
    start = _ymd_to_sql_date(start_date)
    end = _ymd_to_sql_date(end_date)
    if not start or not end:
        return set()
    rows = execute_query(
        """
        SELECT DISTINCT stock_code
        FROM trade_stock_financial
        WHERE report_date >= %s AND report_date <= %s
        """,
        (start, end),
    )
    return {r["stock_code"] for r in rows if r.get("stock_code")}


def run_financial_crawl(
    stock_codes: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    *,
    skip_existing_in_range: bool = False,
) -> dict:
    settings = get_settings()
    codes = list(stock_codes or settings.default_stocks)
    skipped = 0
    if skip_existing_in_range and start_date and end_date:
        existing = _codes_with_data_in_range(start_date, end_date)
        if existing:
            before = len(codes)
            codes = [c for c in codes if c not in existing]
            skipped = before - len(codes)
            logger.info(
                f"financial skip existing in range "
                f"{start_date}~{end_date}: skipped={skipped}, remain={len(codes)}"
            )

    total = 0
    failed = []
    for code in codes:
        try:
            total += _crawl_one(code, start_date=start_date, end_date=end_date)
        except Exception as e:
            logger.error(f"financial crawl {code}: {e}")
            failed.append(code)
    return {
        "rows": total,
        "message": (
            f"range={start_date or '-'}~{end_date or '-'}, "
            f"rows={total}, skipped={skipped}, failed={len(failed)}"
        ),
        "failed": failed,
        "skipped": skipped,
    }
