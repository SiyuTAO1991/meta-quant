# -*- coding: utf-8 -*-
"""工业级特征工程（参考训练营 feature_engine.py）。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import talib

from app.factors.tech_factor_config import get_all_tech_factor_codes, get_tech_factor_taxonomy

FACTOR_TAXONOMY = get_tech_factor_taxonomy()

FUNDAMENTAL_COLS = [
    "pe_ratio",
    "roe_factor",
    "gross_margin_factor",
    "debt_ratio_factor",
]


def get_all_feature_cols() -> list[str]:
    return get_all_tech_factor_codes()


def calc_features(df: pd.DataFrame) -> pd.DataFrame:
    """从单票 OHLCV 计算 50+ 技术特征。索引为交易日，需含 open/high/low/close/volume。"""
    df = df.copy()
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    lo = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    v = df["volume"].values.astype(float)

    df["ret_1d"] = df["close"].pct_change(1)
    df["ret_3d"] = df["close"].pct_change(3)
    df["ret_5d"] = df["close"].pct_change(5)
    df["ret_10d"] = df["close"].pct_change(10)

    df["amplitude_5d"] = (
        df["high"].rolling(5).max() - df["low"].rolling(5).min()
    ) / df["close"].rolling(5).mean()
    df["amplitude_10d"] = (
        df["high"].rolling(10).max() - df["low"].rolling(10).min()
    ) / df["close"].rolling(10).mean()

    avg_vol_5 = df["volume"].rolling(5).mean()
    avg_vol_10 = df["volume"].rolling(10).mean()
    avg_vol_20 = df["volume"].rolling(20).mean()
    df["vol_ratio_5d"] = df["volume"] / avg_vol_5.replace(0, np.nan)
    df["vol_ratio_10d"] = df["volume"] / avg_vol_10.replace(0, np.nan)
    df["price_volume_corr_10d"] = df["close"].rolling(10).corr(df["volume"])
    df["turnover_change_5d"] = avg_vol_5 / avg_vol_20.replace(0, np.nan)

    df["momentum_5d"] = talib.ROC(c, timeperiod=5)
    df["momentum_10d"] = talib.ROC(c, timeperiod=10)
    df["momentum_20d"] = talib.ROC(c, timeperiod=20)
    df["momentum_60d"] = talib.ROC(c, timeperiod=60)

    mom_10 = pd.Series(talib.ROC(c, timeperiod=10), index=df.index)
    mom_20 = pd.Series(talib.ROC(c, timeperiod=20), index=df.index)
    df["momentum_slope_10d"] = mom_10 - mom_10.shift(5)
    df["momentum_slope_20d"] = mom_20 - mom_20.shift(10)
    df["momentum_accel_10d"] = df["momentum_slope_10d"] - pd.Series(
        df["momentum_slope_10d"]
    ).shift(5).values
    df["momentum_accel_20d"] = df["momentum_slope_20d"] - pd.Series(
        df["momentum_slope_20d"]
    ).shift(10).values

    atr_14 = talib.ATR(h, lo, c, timeperiod=14)
    df["atr_norm_14"] = atr_14 / np.where(c > 0, c, np.nan)
    df["hist_vol_10d"] = df["ret_1d"].rolling(10).std() * np.sqrt(252)
    df["hist_vol_20d"] = df["ret_1d"].rolling(20).std() * np.sqrt(252)
    df["hist_vol_60d"] = df["ret_1d"].rolling(60).std() * np.sqrt(252)
    hv_10 = df["hist_vol_10d"]
    hv_20 = df["hist_vol_20d"]
    df["vol_change_10d"] = hv_10 / hv_10.shift(10).replace(0, np.nan) - 1
    df["vol_change_20d"] = hv_20 / hv_20.shift(20).replace(0, np.nan) - 1

    df["rsi_14"] = talib.RSI(c, timeperiod=14)
    df["rsi_6"] = talib.RSI(c, timeperiod=6)
    df["adx_14"] = talib.ADX(h, lo, c, timeperiod=14)
    macd_dif, macd_signal, macd_hist = talib.MACD(
        c, fastperiod=12, slowperiod=26, signalperiod=9
    )
    df["macd_dif"] = macd_dif
    df["macd_signal"] = macd_signal
    df["macd_hist"] = macd_hist

    upper, _middle, lower = talib.BBANDS(c, timeperiod=20, nbdevup=2, nbdevdn=2)
    band_width = np.where((upper - lower) > 0, upper - lower, np.nan)
    df["bbands_position"] = (c - lower) / band_width

    slowk, slowd = talib.STOCH(
        h,
        lo,
        c,
        fastk_period=9,
        slowk_period=3,
        slowk_matype=0,
        slowd_period=3,
        slowd_matype=0,
    )
    df["kdj_k"] = slowk
    df["kdj_d"] = slowd
    df["cci_14"] = talib.CCI(h, lo, c, timeperiod=14)
    df["willr_14"] = talib.WILLR(h, lo, c, timeperiod=14)

    obv = talib.OBV(c, v)
    obv_series = pd.Series(obv, index=df.index)
    obv_ma = obv_series.rolling(10).mean()
    df["obv_slope_10d"] = (obv_series - obv_ma) / obv_ma.abs().replace(0, np.nan)

    ma5 = talib.SMA(c, timeperiod=5)
    ma10 = talib.SMA(c, timeperiod=10)
    ma20 = talib.SMA(c, timeperiod=20)
    ma60 = talib.SMA(c, timeperiod=60)
    df["ma5_bias"] = (c - ma5) / np.where(ma5 > 0, ma5, np.nan)
    df["ma10_bias"] = (c - ma10) / np.where(ma10 > 0, ma10, np.nan)
    df["ma20_bias"] = (c - ma20) / np.where(ma20 > 0, ma20, np.nan)
    df["ma60_bias"] = (c - ma60) / np.where(ma60 > 0, ma60, np.nan)

    bull_score = np.zeros(len(c))
    bull_score += np.where(c > ma5, 1, 0)
    bull_score += np.where(c > ma10, 1, 0)
    bull_score += np.where(c > ma20, 1, 0)
    bull_score += np.where(c > ma60, 1, 0)
    bull_score += np.where(ma5 > ma10, 1, 0)
    bull_score += np.where(ma10 > ma20, 1, 0)
    df["ma_bull_score"] = bull_score / 6.0

    body = np.abs(c - o)
    full_range = h - lo
    full_range_safe = np.where(full_range > 0, full_range, np.nan)
    df["upper_shadow_ratio"] = (h - np.maximum(c, o)) / full_range_safe
    df["lower_shadow_ratio"] = (np.minimum(c, o) - lo) / full_range_safe
    df["body_ratio"] = body / full_range_safe

    high_20 = pd.Series(h, index=df.index).rolling(20).max()
    low_20 = pd.Series(lo, index=df.index).rolling(20).min()
    df["new_high_20d"] = (pd.Series(h, index=df.index) >= high_20).astype(float)
    df["new_low_20d"] = (pd.Series(lo, index=df.index) <= low_20).astype(float)

    df["mom_vol_cross"] = df["momentum_20d"] * df["atr_norm_14"]
    df["adx_rsi_cross"] = df["adx_14"] * (df["rsi_14"] - 50) / 50
    df["vol_ratio_mom_cross"] = df["vol_ratio_5d"] * df["momentum_10d"]
    df["rsi_bbands_cross"] = (df["rsi_14"] - 50) / 50 * df["bbands_position"]
    df["macd_adx_cross"] = df["macd_hist"] * df["adx_14"]
    df["vol_mom_accel_cross"] = df["hist_vol_10d"] * df["momentum_accel_10d"]
    return df.replace([np.inf, -np.inf], np.nan)


def calc_fundamental_features(
    price_df: pd.DataFrame, fin_df: pd.DataFrame, stock_code: str
) -> pd.DataFrame:
    """财务字段按报告期向前填充，对齐到日线。"""
    result = pd.DataFrame(index=price_df.index)
    for col in FUNDAMENTAL_COLS:
        result[col] = np.nan

    if fin_df is None or fin_df.empty:
        return result
    stock_fin = fin_df[fin_df["stock_code"] == stock_code].copy()
    if stock_fin.empty:
        return result

    stock_fin["report_date"] = pd.to_datetime(stock_fin["report_date"])
    stock_fin = stock_fin.sort_values("report_date")
    stock_fin = stock_fin.drop_duplicates(subset=["report_date"], keep="last")
    stock_fin = stock_fin.set_index("report_date")

    if "eps" in stock_fin.columns:
        eps_daily = stock_fin["eps"].reindex(price_df.index, method="ffill")
        eps_safe = pd.to_numeric(eps_daily, errors="coerce").replace(0, np.nan)
        result["pe_ratio"] = price_df["close"] / eps_safe

    for col_src, col_dst in (
        ("roe", "roe_factor"),
        ("gross_margin", "gross_margin_factor"),
        ("debt_ratio", "debt_ratio_factor"),
    ):
        if col_src in stock_fin.columns:
            result[col_dst] = (
                pd.to_numeric(stock_fin[col_src], errors="coerce")
                .reindex(price_df.index, method="ffill")
            )
    return result


def preprocess_features(
    df: pd.DataFrame, feature_cols: list[str] | None = None, method: str = "mad"
) -> pd.DataFrame:
    """MAD/3σ 去极值 + 中位数填缺失 + Z-score。"""
    df = df.copy()
    if feature_cols is None:
        feature_cols = [c for c in get_all_feature_cols() if c in df.columns]

    for col in feature_cols:
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        if method == "mad":
            median = series.median()
            mad = (series - median).abs().median()
            if mad and mad > 0:
                upper = median + 5 * 1.4826 * mad
                lower = median - 5 * 1.4826 * mad
                series = series.clip(lower=lower, upper=upper)
        elif method == "sigma":
            mean = series.mean()
            std = series.std()
            if std and std > 0:
                series = series.clip(lower=mean - 3 * std, upper=mean + 3 * std)

        fill_val = series.median()
        series = series.fillna(fill_val)
        mean = series.mean()
        std = series.std()
        if std and std > 0:
            series = (series - mean) / std
        else:
            series = series - mean
        df[col] = series
    return df


def neutralize(
    factor_series: pd.Series,
    industry_dummies: pd.DataFrame,
    mktcap_log: pd.Series | None = None,
) -> pd.Series:
    """行业+市值 OLS 残差中性化（numpy lstsq，不依赖 sklearn）。"""
    valid_mask = factor_series.notna()
    if int(valid_mask.sum()) < 10:
        return factor_series

    X_parts = [industry_dummies.loc[valid_mask]]
    if mktcap_log is not None:
        X_parts.append(mktcap_log.loc[valid_mask].to_frame("mktcap"))
    X = pd.concat(X_parts, axis=1).fillna(0).to_numpy(dtype=float)
    X = np.column_stack([np.ones(len(X)), X])
    y = factor_series.loc[valid_mask].to_numpy(dtype=float)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    residual = y - X @ coef
    result = factor_series.copy()
    result.loc[valid_mask] = residual
    return result
