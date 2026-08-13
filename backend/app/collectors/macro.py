# -*- coding: utf-8 -*-
"""宏观数据采集（AkShare）。"""
from __future__ import annotations

import re
from functools import reduce

import akshare as ak
import pandas as pd
from loguru import logger

from app.database import execute_many


def _parse_cn_date(series: pd.Series) -> pd.Series:
    def _one(s):
        if pd.isna(s):
            return pd.NaT
        s = str(s).strip()
        m = re.match(r"(\d{4})\D+(\d{1,2})", s)
        if m:
            return pd.Timestamp(year=int(m.group(1)), month=int(m.group(2)), day=1)
        m = re.match(r"^(\d{4})(\d{2})$", s)
        if m:
            return pd.Timestamp(year=int(m.group(1)), month=int(m.group(2)), day=1)
        return pd.NaT

    return series.apply(_one)


def _find_col(columns, keywords):
    for kw in keywords:
        for col in columns:
            if kw in str(col):
                return col
    return None


def _fetch_simple(fn, value_keys, col_name: str) -> pd.DataFrame:
    try:
        df = fn()
        if df is None or len(df) == 0:
            return pd.DataFrame()
        date_col = df.columns[0]
        value_col = _find_col(df.columns, value_keys) or df.columns[1]
        out = pd.DataFrame(
            {
                "date": _parse_cn_date(df[date_col]),
                col_name: pd.to_numeric(df[value_col], errors="coerce"),
            }
        ).dropna()
        return out
    except Exception as e:
        logger.warning(f"macro fetch {col_name} failed: {e}")
        return pd.DataFrame()


def run_macro_crawl(start_date: str | None = None, end_date: str | None = None) -> dict:
    frames = [
        _fetch_simple(ak.macro_china_cpi, ["全国-同比增长", "同比增长", "同比"], "cpi_yoy"),
        _fetch_simple(ak.macro_china_ppi, ["当月同比增长", "同比增长", "同比"], "ppi_yoy"),
        _fetch_simple(ak.macro_china_pmi, ["制造业-指标", "制造业", "PMI"], "pmi"),
        _fetch_simple(ak.macro_china_supply_of_money, ["M2）同比增长", "M2)同比", "M2同比"], "m2_yoy"),
        _fetch_simple(ak.macro_china_lpr, ["1年", "LPR"], "lpr_1y"),
    ]

    valid = [f for f in frames if f is not None and len(f) > 0]
    if not valid:
        return {"rows": 0, "message": "no macro data"}

    merged = reduce(lambda l, r: pd.merge(l, r, on="date", how="outer"), valid)
    merged = merged.sort_values("date").dropna(subset=["date"])

    sql = """
        INSERT INTO trade_macro_indicator
        (indicator_date, cpi_yoy, ppi_yoy, pmi, m2_yoy, lpr_1y, data_source)
        VALUES (%s, %s, %s, %s, %s, %s, 'akshare')
        ON DUPLICATE KEY UPDATE
        cpi_yoy=COALESCE(VALUES(cpi_yoy), cpi_yoy),
        ppi_yoy=COALESCE(VALUES(ppi_yoy), ppi_yoy),
        pmi=COALESCE(VALUES(pmi), pmi),
        m2_yoy=COALESCE(VALUES(m2_yoy), m2_yoy),
        lpr_1y=COALESCE(VALUES(lpr_1y), lpr_1y)
    """
    rows = []
    for _, row in merged.iterrows():
        rows.append(
            (
                row["date"].strftime("%Y-%m-%d"),
                None if pd.isna(row.get("cpi_yoy")) else float(row.get("cpi_yoy")),
                None if pd.isna(row.get("ppi_yoy")) else float(row.get("ppi_yoy")),
                None if pd.isna(row.get("pmi")) else float(row.get("pmi")),
                None if pd.isna(row.get("m2_yoy")) else float(row.get("m2_yoy")),
                None if pd.isna(row.get("lpr_1y")) else float(row.get("lpr_1y")),
            )
        )
    n = execute_many(sql, rows)

    # 国债收益率
    rate_rows = 0
    try:
        bond = ak.bond_zh_us_rate()
        if bond is not None and len(bond) > 0:
            date_col = bond.columns[0]
            cn_col = _find_col(bond.columns, ["中国国债收益率10年", "中国"])
            us_col = _find_col(bond.columns, ["美国国债收益率10年", "美国"])
            rate_sql = """
                INSERT INTO trade_rate_daily (rate_date, cn_bond_10y, us_bond_10y, data_source)
                VALUES (%s, %s, %s, 'akshare')
                ON DUPLICATE KEY UPDATE
                cn_bond_10y=COALESCE(VALUES(cn_bond_10y), cn_bond_10y),
                us_bond_10y=COALESCE(VALUES(us_bond_10y), us_bond_10y)
            """
            rdata = []
            for _, row in bond.tail(400).iterrows():
                d = pd.to_datetime(row[date_col], errors="coerce")
                if pd.isna(d):
                    continue
                rdata.append(
                    (
                        d.strftime("%Y-%m-%d"),
                        None if not cn_col or pd.isna(row.get(cn_col)) else float(row[cn_col]),
                        None if not us_col or pd.isna(row.get(us_col)) else float(row[us_col]),
                    )
                )
            rate_rows = execute_many(rate_sql, rdata)
    except Exception as e:
        logger.warning(f"bond rate crawl failed: {e}")

    return {
        "rows": n + rate_rows,
        "message": f"range={start_date or '-'}~{end_date or '-'}, macro={n}, rate={rate_rows}",
    }
