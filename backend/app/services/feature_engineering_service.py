# -*- coding: utf-8 -*-
"""工业级特征工程流水线（参考 CASE 2-工业级特征工程.py）。"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from loguru import logger

from app.database import execute_query
from app.factors.feature_engine import (
    FACTOR_TAXONOMY,
    FUNDAMENTAL_COLS,
    calc_features,
    calc_fundamental_features,
    get_all_feature_cols,
    neutralize,
    preprocess_features,
)
from app.services.stock_service import parse_stock_codes
from app.utils import normalize_date

DEFAULT_STOCK_POOL = [
    "600519.SH",
    "688981.SH",
    "000001.SZ",
    "300750.SZ",
]

_industry_cache: dict[str, str] | None = None


def _log(logs: list[str], message: str) -> None:
    logs.append(message)
    logger.info(message)


def _section(logs: list[str], title: str) -> None:
    _log(logs, "=" * 60)
    _log(logs, f"  {title}")
    _log(logs, "=" * 60)


def _series_stats(s: pd.Series) -> dict[str, float | None]:
    x = pd.to_numeric(s, errors="coerce").dropna()
    if x.empty:
        return {"min": None, "max": None, "mean": None, "std": None, "count": 0}
    return {
        "min": float(x.min()),
        "max": float(x.max()),
        "mean": float(x.mean()),
        "std": float(x.std()) if len(x) > 1 else 0.0,
        "count": int(len(x)),
    }


def _preview_rows(df: pd.DataFrame, cols: list[str], n: int = 5) -> list[dict]:
    use = [c for c in cols if c in df.columns]
    if not use:
        return []
    tail = df[use].tail(n).copy()
    if "trade_date" in tail.columns:
        tail["trade_date"] = pd.to_datetime(tail["trade_date"]).dt.strftime("%Y-%m-%d")
    records = []
    for rec in tail.to_dict(orient="records"):
        out = {}
        for k, v in rec.items():
            if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                out[k] = None
            elif isinstance(v, (np.floating, float)):
                out[k] = round(float(v), 6)
            elif isinstance(v, (np.integer, int)):
                out[k] = int(v)
            else:
                out[k] = v
        records.append(out)
    return records


def _load_industry_map(codes: list[str], override: dict[str, str] | None = None) -> dict[str, str]:
    global _industry_cache
    result = {c: "其他" for c in codes}
    override_norm = {
        str(code).strip().upper(): str(industry).strip()
        for code, industry in (override or {}).items()
        if str(code).strip() and str(industry).strip()
    }
    for key, industry in override_norm.items():
        if key in result:
            result[key] = industry

    if _industry_cache is None:
        name_map: dict[str, str] = {}
        try:
            from app.collectors.daily import _get_pro

            pro = _get_pro()
            df = pro.stock_basic(
                exchange="", list_status="L", fields="ts_code,industry"
            )
            if df is not None and len(df) > 0:
                for _, row in df.iterrows():
                    code = str(row.get("ts_code") or "").strip().upper()
                    industry = str(row.get("industry") or "").strip() or "其他"
                    if code:
                        name_map[code] = industry
            logger.info(f"loaded industry map size={len(name_map)}")
        except Exception as e:
            logger.warning(f"load industry map failed: {e}")
        _industry_cache = name_map

    for code in codes:
        if code in override_norm:
            continue
        result[code] = _industry_cache.get(code) or "其他"
    return result


def _load_price_map(codes: list[str], start: str, end: str, min_bars: int) -> dict[str, pd.DataFrame]:
    if not codes:
        return {}
    placeholders = ",".join(["%s"] * len(codes))
    rows = execute_query(
        f"""
        SELECT stock_code, trade_date, open_price, high_price, low_price,
               close_price, volume
        FROM trade_stock_daily
        WHERE stock_code IN ({placeholders})
          AND trade_date BETWEEN %s AND %s
        ORDER BY stock_code, trade_date
        """,
        (*codes, start, end),
    )
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        grouped.setdefault(r["stock_code"], []).append(r)

    price_map: dict[str, pd.DataFrame] = {}
    for code, items in grouped.items():
        if len(items) < min_bars:
            continue
        df = pd.DataFrame(items)
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df = df.set_index("trade_date").sort_index()
        df = df.rename(
            columns={
                "open_price": "open",
                "high_price": "high",
                "low_price": "low",
                "close_price": "close",
            }
        )
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        price_map[code] = df[["open", "high", "low", "close", "volume"]]
    return price_map


def _load_financial(codes: list[str], report_date_min: str) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame()
    placeholders = ",".join(["%s"] * len(codes))
    rows = execute_query(
        f"""
        SELECT stock_code, report_date, eps, roe, gross_margin, debt_ratio
        FROM trade_stock_financial
        WHERE stock_code IN ({placeholders})
          AND report_date >= %s
        ORDER BY stock_code, report_date
        """,
        (*codes, report_date_min),
    )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def run_feature_engineering(
    stock_codes: str = "",
    start_date: str = "",
    end_date: str = "",
    min_bars: int = 120,
    include_fundamental: bool = True,
    neutralize_factor: str = "momentum_20d",
    neutralize_all: bool = False,
    corr_threshold: float = 0.8,
    industry_map: dict[str, str] | None = None,
    return_frame: bool = False,
) -> dict[str, Any]:
    """
    执行 7 步特征工程。返回摘要（不含全量矩阵，全量由返回的内部约定供后续 ML 调用）。

    后续 XGBoost/LightGBM 可直接复用本函数产出的 feature_cols / kept_features。
    """ 
    logs: list[str] = []
    start = normalize_date(start_date, as_dash=True)
    end = normalize_date(end_date, as_dash=True)
    if not start or not end:
        raise ValueError("请提供 start_date 和 end_date")

    codes = parse_stock_codes(stock_codes) if str(stock_codes or "").strip() else list(DEFAULT_STOCK_POOL)
    _section(logs, "工业级特征工程流水线")
    _log(logs, f"[条件] stocks={codes} range={start}~{end} min_bars={min_bars}")
    _log(
        logs,
        f"[条件] include_fundamental={include_fundamental} neutralize_factor={neutralize_factor} "
        f"neutralize_all={neutralize_all} corr_threshold={corr_threshold}",
    )

    # ---------- 1. 加载日K ----------
    _section(logs, "第1步: 加载目标股票日K线")
    stock_data = _load_price_map(codes, start, end, min_bars)
    skipped = [c for c in codes if c not in stock_data]
    _log(logs, f"成功加载 {len(stock_data)} 只股票 (请求 {len(codes)} 只)")
    if skipped:
        _log(logs, f"[跳过] 样本不足或无行情: {skipped}")
    for code, df in stock_data.items():
        _log(
            logs,
            f"  {code}: {len(df)} 个交易日, "
            f"{df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}, "
            f"close={float(df['close'].min()):.2f}~{float(df['close'].max()):.2f}",
        )
    if not stock_data:
        raise ValueError("未加载到任何目标股票，请检查日线数据和 min_bars")

    # ---------- 2. 技术特征 ----------
    _section(logs, "第2步: 计算50+技术特征 (calc_features)")
    featured_data: dict[str, pd.DataFrame] = {}
    for code, df in stock_data.items():
        featured_data[code] = calc_features(df)
        _log(logs, f"  {code}: 特征列 {featured_data[code].shape[1]} (含OHLCV)")

    all_feature_cols = get_all_feature_cols()
    sample_code = next(iter(featured_data))
    sample_df = featured_data[sample_code]
    available_features = [c for c in all_feature_cols if c in sample_df.columns]
    _log(logs, f"因子分类体系 ({len(FACTOR_TAXONOMY)} 大类):")
    total_count = 0
    for cat_key, cat_info in FACTOR_TAXONOMY.items():
        n = len(cat_info["features"])
        total_count += n
        shown = ", ".join(cat_info["features"][:4])
        if n > 4:
            shown += f" ... 共{n}个"
        _log(logs, f"  {cat_info['name']} ({cat_key}): {n} 个因子")
        _log(logs, f"    -> {shown}")
    _log(logs, f"因子总数: {total_count} 个, 实际可用: {len(available_features)} 个")
    show_cols = ["close", "ret_1d", "momentum_20d", "rsi_14", "macd_hist", "ma20_bias"]
    show_cols = [c for c in show_cols if c in sample_df.columns]
    tmp_preview = sample_df[show_cols].tail(5).copy()
    tmp_preview.insert(0, "trade_date", tmp_preview.index.strftime("%Y-%m-%d"))
    preview_tech = _preview_rows(tmp_preview, list(tmp_preview.columns))
    _log(logs, f"以 {sample_code} 为例, 最近5行部分特征:")
    for row in preview_tech:
        _log(logs, f"  {row}")

    # ---------- 3. 基本面 ----------
    fundamental_preview: list[dict] = []
    avail_fund: list[str] = []
    if include_fundamental:
        _section(logs, "第3步: 加载财务数据, 补充基本面因子")
        fin_min = f"{int(start[:4]) - 1}-01-01"
        fin_df = _load_financial(list(featured_data.keys()), fin_min)
        if fin_df.empty:
            _log(logs, "[警告] 财务数据为空, 跳过基本面因子计算")
        else:
            _log(
                logs,
                f"加载财务数据: {len(fin_df)} 条记录, 覆盖 {fin_df['stock_code'].nunique()} 只股票 "
                f"(report_date>={fin_min})",
            )
            for code, df in featured_data.items():
                fund_df = calc_fundamental_features(df, fin_df, code)
                non_null = {}
                for col in FUNDAMENTAL_COLS:
                    if col in fund_df.columns:
                        featured_data[code][col] = fund_df[col]
                        non_null[col] = int(pd.to_numeric(fund_df[col], errors="coerce").notna().sum())
                _log(logs, f"  {code} 基本面非空点数: {non_null}")
            sample_df = featured_data[sample_code]
            avail_fund = [c for c in FUNDAMENTAL_COLS if c in sample_df.columns]
            _log(logs, f"基本面因子: {avail_fund}")
            if avail_fund:
                tmp_f = sample_df[avail_fund].tail(5).copy()
                tmp_f.insert(0, "trade_date", tmp_f.index.strftime("%Y-%m-%d"))
                fundamental_preview = _preview_rows(tmp_f, list(tmp_f.columns))
                _log(logs, f"以 {sample_code} 为例, 最近5行:")
                for row in fundamental_preview:
                    _log(logs, f"  {row}")
    else:
        _section(logs, "第3步: 跳过基本面因子 (include_fundamental=False)")

    # ---------- 4. 行业 one-hot ----------
    _section(logs, "第4步: 构造行业因子 (one-hot编码)")
    ind_map = _load_industry_map(list(featured_data.keys()), industry_map)
    for code, industry in ind_map.items():
        _log(logs, f"  {code} -> {industry}")
    industries = sorted(set(ind_map.values()))
    _log(logs, f"行业列表: {industries}")

    all_frames = []
    for code, df in featured_data.items():
        tmp = df.copy()
        tmp["stock_code"] = code
        tmp["trade_date"] = tmp.index
        industry = ind_map.get(code, "其他")
        for ind in industries:
            tmp[f"ind_{ind}"] = 1.0 if ind == industry else 0.0
        all_frames.append(tmp.reset_index(drop=True))
    merged = pd.concat(all_frames, ignore_index=True)
    ind_cols = [f"ind_{ind}" for ind in industries]
    _log(logs, f"合并后数据: {merged.shape[0]} 行 x {merged.shape[1]} 列")
    _log(logs, f"行业哑变量列: {ind_cols}")
    for ind in industries:
        col = f"ind_{ind}"
        count = int(merged[col].sum())
        _log(logs, f"  {ind}: {count} 条记录")

    # ---------- 5. 预处理 ----------
    _section(logs, "第5步: 华泰标准预处理 (MAD去极值 + Z-score标准化)")
    feature_cols = [c for c in get_all_feature_cols() if c in merged.columns]
    if include_fundamental:
        feature_cols += [c for c in FUNDAMENTAL_COLS if c in merged.columns and c not in feature_cols]
    demo_factors = [f for f in ("momentum_20d", "rsi_14", "macd_hist") if f in merged.columns]
    preprocess_before = {}
    _log(logs, "--- 去极值前的分布统计 ---")
    for col in demo_factors:
        stats = _series_stats(merged[col])
        preprocess_before[col] = stats
        _log(
            logs,
            f"  {col:20s}: min={stats['min']}  max={stats['max']}  "
            f"mean={stats['mean']}  std={stats['std']}",
        )

    preprocessed = merged.copy()
    for code in merged["stock_code"].unique():
        mask = preprocessed["stock_code"] == code
        stock_df = preprocessed.loc[mask].copy()
        stock_df_processed = preprocess_features(stock_df, feature_cols=feature_cols, method="mad")
        for col in feature_cols:
            preprocessed.loc[mask, col] = stock_df_processed[col].values
        _log(logs, f"  已预处理 {code}: rows={int(mask.sum())}")

    preprocess_after = {}
    _log(logs, "--- 去极值+标准化后的分布统计 ---")
    for col in demo_factors:
        stats = _series_stats(preprocessed[col])
        preprocess_after[col] = stats
        _log(
            logs,
            f"  {col:20s}: min={stats['min']}  max={stats['max']}  "
            f"mean={stats['mean']}  std={stats['std']}",
        )
    _log(logs, "预处理效果: 极端值按 中位数 +/- 5*1.4826*MAD 截断; 标准化后均值近0、标准差近1")

    # ---------- 6. 中性化 ----------
    _section(logs, "第6步: 行业市值中性化")
    _log(logs, "原理: factor = beta_industry * industry + beta_mktcap * ln(mktcap) + residual")
    preprocessed["mktcap_proxy"] = (
        preprocessed["close"] * preprocessed["volume"]
    ).rolling(20, min_periods=1).mean()
    preprocessed["mktcap_log"] = np.log(preprocessed["mktcap_proxy"].clip(lower=1))
    industry_dummies = preprocessed[ind_cols]
    mktcap_log = preprocessed["mktcap_log"]

    neutralize_info: dict[str, Any] = {"factor": neutralize_factor}
    if neutralize_factor not in preprocessed.columns:
        _log(logs, f"[警告] {neutralize_factor} 不在数据中, 跳过中性化演示")
    else:
        factor_before = preprocessed[neutralize_factor].copy()
        factor_neutralized = neutralize(
            factor_series=preprocessed[neutralize_factor],
            industry_dummies=industry_dummies,
            mktcap_log=mktcap_log,
        )
        preprocessed[f"{neutralize_factor}_neutral"] = factor_neutralized
        before_stats = _series_stats(factor_before)
        after_stats = _series_stats(factor_neutralized)
        neutralize_info["before"] = before_stats
        neutralize_info["after"] = after_stats
        _log(logs, f"因子: {neutralize_factor}")
        _log(logs, f"--- 中性化前 --- mean={before_stats['mean']} std={before_stats['std']} min={before_stats['min']} max={before_stats['max']}")
        _log(logs, f"--- 中性化后 --- mean={after_stats['mean']} std={after_stats['std']} min={after_stats['min']} max={after_stats['max']}")
        _log(logs, f"  {'行业':<12s} {'中性化前':>12s} {'中性化后':>12s}")
        by_industry = []
        for col in ind_cols:
            ind_name = col.replace("ind_", "")
            mask = preprocessed[col] == 1.0
            if int(mask.sum()) == 0:
                continue
            mean_before = float(factor_before.loc[mask].mean())
            mean_after = float(factor_neutralized.loc[mask].mean())
            by_industry.append({"industry": ind_name, "before": mean_before, "after": mean_after})
            _log(logs, f"  {ind_name:<12s} {mean_before:>12.6f} {mean_after:>12.6f}")
        neutralize_info["by_industry"] = by_industry
        _log(logs, "中性化效果: 消除行业间因子均值差异, 残差反映个股相对行业的超额信息")

    neutralized_all: list[str] = []
    if neutralize_all:
        _log(logs, "neutralize_all=True, 对全部特征列做行业市值中性化 (供后续模型)")
        for col in feature_cols:
            preprocessed[col] = neutralize(
                factor_series=preprocessed[col],
                industry_dummies=industry_dummies,
                mktcap_log=mktcap_log,
            )
            neutralized_all.append(col)
        _log(logs, f"  已中性化 {len(neutralized_all)} 列")

    # ---------- 7. 相关性 ----------
    _section(logs, "第7步: 特征相关性分析")
    avail_cols = [c for c in feature_cols if c in preprocessed.columns]
    corr_matrix = preprocessed[avail_cols].corr()
    _log(logs, f"计算 {len(avail_cols)} 个特征的相关系数矩阵: {tuple(corr_matrix.shape)}")
    high_corr_pairs: list[tuple[str, str, float]] = []
    for i in range(len(avail_cols)):
        for j in range(i + 1, len(avail_cols)):
            corr_val = corr_matrix.iloc[i, j]
            if pd.notna(corr_val) and abs(float(corr_val)) > corr_threshold:
                high_corr_pairs.append((avail_cols[i], avail_cols[j], float(corr_val)))
    high_corr_pairs.sort(key=lambda x: abs(x[2]), reverse=True)
    _log(logs, f"高相关特征对 (|corr| > {corr_threshold}): 共 {len(high_corr_pairs)} 对")
    show_limit = 20
    for feat_a, feat_b, corr_val in high_corr_pairs[:show_limit]:
        _log(logs, f"  {feat_a:<25s} {feat_b:<25s} {corr_val:>10.4f}")
    if len(high_corr_pairs) > show_limit:
        _log(logs, f"  ... 共 {len(high_corr_pairs)} 对, 仅展示前 {show_limit} 对")

    redundant_features: set[str] = set()
    for _feat_a, feat_b, _ in high_corr_pairs:
        redundant_features.add(feat_b)
    kept_features = [c for c in avail_cols if c not in redundant_features]
    _log(logs, f"冗余特征建议 (可考虑剔除): {len(redundant_features)} 个")
    for feat in sorted(redundant_features):
        _log(logs, f"  - {feat}")
    _log(logs, f"保留后特征数: {len(kept_features)} 个 (原 {len(avail_cols)} 个)")

    _section(logs, "特征工程流水线总结")
    _log(logs, "原始OHLCV -> 50+因子 -> 基本面 -> 行业哑变量 -> MAD去极值 -> Z-score -> 中性化 -> 相关性筛选")
    _log(logs, "后续 XGBoost / LightGBM 建议使用 kept_features 作为输入列")

    high_corr_payload = [
        {"feature_a": a, "feature_b": b, "corr": round(c, 6)}
        for a, b, c in high_corr_pairs[:50]
    ]
    payload = {
        "ok": True,
        "stock_codes": list(stock_data.keys()),
        "skipped": skipped,
        "start_date": start,
        "end_date": end,
        "rows": int(preprocessed.shape[0]),
        "cols": int(preprocessed.shape[1]),
        "tech_feature_count": len(available_features),
        "fundamental_features": avail_fund,
        "industries": industries,
        "industry_columns": ind_cols,
        "feature_cols": avail_cols,
        "kept_features": kept_features,
        "redundant_features": sorted(redundant_features),
        "high_corr_pairs": high_corr_payload,
        "high_corr_count": len(high_corr_pairs),
        "preprocess_demo": {"before": preprocess_before, "after": preprocess_after},
        "neutralize": neutralize_info,
        "neutralized_all_cols": neutralized_all,
        "sample_code": sample_code,
        "sample_preview_tech": preview_tech,
        "sample_preview_fundamental": fundamental_preview,
        "logs": logs,
    }
    if return_frame:
        payload["_frame"] = preprocessed
    return payload
