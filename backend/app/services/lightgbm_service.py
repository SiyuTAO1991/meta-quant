# -*- coding: utf-8 -*-
"""LightGBM 涨跌二分类预测（参考 CASE 4-LightGBM对比与调参.py）。结果不落库。"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from loguru import logger

from app.database import execute_query
from app.factors.feature_engine import calc_features, get_all_feature_cols, preprocess_features
from app.factors.tech_factor_config import (
    get_all_tech_factor_codes,
    get_tech_factor_categories,
    get_tech_factor_options,
)
from app.factors.ml_engine import (
    DEFAULT_LGB_PARAMS,
    confusion_matrix_2x2,
    evaluate_classification,
    make_labels,
    rolling_train_predict,
)
from app.services.stock_service import get_stock_name_map, parse_stock_codes
from app.utils import normalize_date

DEFAULT_STOCK_CODES = "600519.SH,688981.SH"
DEFAULT_START = "2023-01-01"
DEFAULT_END = "2025-12-31"
DEFAULT_LABEL_HORIZON = 1
DEFAULT_MIN_BARS = 120
DEFAULT_TRAIN_DAYS = 120
DEFAULT_RETRAIN_INTERVAL = 20


def _log(logs: list[str], msg: str) -> None:
    logs.append(msg)
    logger.info(msg)


def get_lightgbm_meta() -> dict[str, Any]:
    categories = []
    for cat in get_tech_factor_categories():
        categories.append(
            {
                "key": cat["key"],
                "name": cat.get("name") or cat["key"],
                "desc": cat.get("desc") or "",
                "features": [
                    {
                        "code": item["code"],
                        "name": item.get("name") or item["code"],
                    }
                    for item in cat.get("features") or []
                ],
            }
        )
    return {
        "default_stock_codes": DEFAULT_STOCK_CODES,
        "default_start_date": DEFAULT_START,
        "default_end_date": DEFAULT_END,
        "default_label_horizon": DEFAULT_LABEL_HORIZON,
        "default_min_bars": DEFAULT_MIN_BARS,
        "default_train_days": DEFAULT_TRAIN_DAYS,
        "default_retrain_interval": DEFAULT_RETRAIN_INTERVAL,
        "default_feature_cols": get_all_tech_factor_codes(),
        "default_lgb_params": dict(DEFAULT_LGB_PARAMS),
        "features": get_tech_factor_options(),
        "categories": categories,
    }


def _load_price(code: str, start: str, end: str) -> pd.DataFrame:
    rows = execute_query(
        """
        SELECT stock_code, trade_date, open_price, high_price, low_price,
               close_price, volume
        FROM trade_stock_daily
        WHERE stock_code=%s AND trade_date BETWEEN %s AND %s
        ORDER BY trade_date
        """,
        (code, start, end),
    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
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
    return df[["open", "high", "low", "close", "volume"]]


def _prepare_features(code: str, start: str, end: str, min_bars: int, feature_cols: list[str]):
    df = _load_price(code, start, end)
    if len(df) < min_bars:
        raise ValueError(f"{code} 有效交易日 {len(df)} < {min_bars}")
    df = calc_features(df)
    available = [c for c in get_all_feature_cols() if c in df.columns]
    use_cols = [c for c in (feature_cols or available) if c in df.columns]
    if not use_cols:
        raise ValueError(f"{code} 所选 X 列均不存在")
    missing = [c for c in (feature_cols or []) if c not in df.columns]
    df = preprocess_features(df, feature_cols=use_cols, method="mad")
    return df, use_cols, missing


def _monthly_stats(pred_df: pd.DataFrame) -> list[dict[str, Any]]:
    work = pred_df.copy()
    work["date"] = pd.to_datetime(work["date"])
    rows: list[dict[str, Any]] = []
    for period, g in work.groupby(work["date"].dt.to_period("M")):
        y_true = g["y_true"].to_numpy()
        y_pred = g["y_pred"].to_numpy()
        y_prob = g["y_prob"].to_numpy()
        acc = float((y_true == y_pred).mean()) if len(g) else None
        auc = None
        if len(np.unique(y_true)) > 1:
            auc = evaluate_classification(y_true, y_pred, y_prob)["auc"]
        rows.append(
            {
                "month": str(period),
                "samples": int(len(g)),
                "accuracy": acc,
                "auc": auc,
            }
        )
    return rows


def _run_single_stock(
    code: str,
    name: str,
    start: str,
    end: str,
    label_horizon: int,
    min_bars: int,
    train_days: int,
    retrain_interval: int,
    feature_cols: list[str],
    lgb_params: dict[str, Any],
    logs: list[str],
) -> dict[str, Any]:
    _log(logs, "=" * 60)
    _log(logs, f"  {name} ({code})")
    _log(logs, "=" * 60)
    _log(logs, f"[1] 加载数据: {start} ~ {end}")
    df, use_cols, missing = _prepare_features(code, start, end, min_bars, feature_cols)
    _log(
        logs,
        f"    共 {len(df)} 个交易日, 价格区间: {float(df['close'].min()):.2f} ~ {float(df['close'].max()):.2f}",
    )
    _log(logs, "[2] 计算技术特征 + 预处理（已完成）")
    _log(logs, f"    使用 X 列数: {len(use_cols)}")
    if missing:
        _log(logs, f"    [跳过不存在的列] {missing}")

    _log(logs, f"[3] 构建标签: 未来第{label_horizon}日涨=1, 跌=0 (相对今日收盘)")
    df["label"] = make_labels(df, horizon=label_horizon, method="binary")
    df = df.dropna(subset=["label"])
    label_dist = df["label"].value_counts().sort_index()
    n_down = int(label_dist.get(0, 0))
    n_up = int(label_dist.get(1, 0))
    _log(
        logs,
        f"    标签分布: 跌(0)={n_down}, 涨(1)={n_up}, 涨占比={n_up / max(len(df), 1) * 100:.1f}%",
    )

    _log(logs, f"[4] LightGBM 滚动预测 (train_days={train_days}, retrain_interval={retrain_interval})")
    df_reset = df.reset_index()
    pred_df = rolling_train_predict(
        df_reset,
        use_cols,
        label_col="label",
        train_days=train_days,
        retrain_interval=retrain_interval,
        params=lgb_params,
        model_type="lightgbm",
        verbose=True,
        log_fn=lambda m: _log(logs, m),
    )
    if pred_df.empty:
        raise ValueError(f"{code} 预测样本为空，请检查窗口长度与标签")
    _log(logs, f"    预测样本数: {len(pred_df)}")

    _log(logs, "[5] 整体评估指标")
    metrics = evaluate_classification(
        pred_df["y_true"].values,
        pred_df["y_pred"].values,
        pred_df["y_prob"].values,
    )
    for k in ("auc", "accuracy", "precision", "recall", "f1"):
        _log(logs, f"    {k.capitalize():<10s} {metrics[k]:.4f}")

    cm = confusion_matrix_2x2(pred_df["y_true"].values, pred_df["y_pred"].values)
    _log(logs, "[6] 混淆矩阵")
    _log(logs, f"              预测跌  预测涨")
    _log(logs, f"    实际跌    {cm[0][0]:>5d}   {cm[0][1]:>5d}")
    _log(logs, f"    实际涨    {cm[1][0]:>5d}   {cm[1][1]:>5d}")

    monthly = _monthly_stats(pred_df)
    _log(logs, "[7] 按月准确率变化")
    for row in monthly:
        auc_str = f"{row['auc']:.4f}" if row.get("auc") is not None else "N/A"
        _log(
            logs,
            f"    {row['month']:<12s} n={row['samples']:>4d} acc={row['accuracy']:.4f} auc={auc_str}",
        )

    acc_series = pd.Series([r["accuracy"] for r in monthly if r.get("accuracy") is not None])
    monthly_std = float(acc_series.std()) if len(acc_series) > 1 else 0.0
    stability = "稳定" if monthly_std < 0.08 else "波动较大"

    pred_tail = pred_df.tail(60).copy()
    pred_tail["date"] = pd.to_datetime(pred_tail["date"]).dt.strftime("%Y-%m-%d")
    predictions = [
        {
            "date": r["date"],
            "y_true": int(r["y_true"]),
            "y_pred": int(r["y_pred"]),
            "y_prob": round(float(r["y_prob"]), 6),
        }
        for r in pred_tail.to_dict(orient="records")
    ]

    return {
        "stock_code": code,
        "stock_name": name,
        "n_bars": int(len(df)),
        "n_samples": int(len(pred_df)),
        "feature_cols": use_cols,
        "skipped_feature_cols": missing,
        "label_dist": {"down": n_down, "up": n_up},
        "metrics": {k: round(float(v), 6) for k, v in metrics.items()},
        "confusion_matrix": cm,
        "monthly": monthly,
        "monthly_accuracy_mean": float(acc_series.mean()) if len(acc_series) else None,
        "monthly_accuracy_std": monthly_std,
        "monthly_accuracy_max": float(acc_series.max()) if len(acc_series) else None,
        "monthly_accuracy_min": float(acc_series.min()) if len(acc_series) else None,
        "stability": stability,
        "predictions": predictions,
    }


def run_lightgbm_predict(
    stock_codes: str = "",
    start_date: str = "",
    end_date: str = "",
    label_horizon: int = DEFAULT_LABEL_HORIZON,
    min_bars: int = DEFAULT_MIN_BARS,
    train_days: int = DEFAULT_TRAIN_DAYS,
    retrain_interval: int = DEFAULT_RETRAIN_INTERVAL,
    feature_cols: list[str] | None = None,
    lgb_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    logs: list[str] = []
    start = normalize_date(start_date or DEFAULT_START, as_dash=True)
    end = normalize_date(end_date or DEFAULT_END, as_dash=True)
    codes = parse_stock_codes(stock_codes or DEFAULT_STOCK_CODES)
    params = dict(DEFAULT_LGB_PARAMS)
    if lgb_params:
        params.update({k: v for k, v in lgb_params.items() if v is not None})
    x_cols = list(feature_cols or [])

    title = "次日涨跌" if label_horizon == 1 else f"未来第{label_horizon}日涨跌"
    _log(logs, "=" * 60)
    _log(logs, f"  LightGBM {title} 二分类预测模型")
    _log(logs, "=" * 60)
    names = get_stock_name_map(codes)
    _log(logs, f"  数据区间: {start} ~ {end}")
    _log(
        logs,
        f"  标的（{len(codes)}只）: {', '.join(f'{names.get(c) or c}({c})' for c in codes)}",
    )
    _log(logs, f"  标签定义: 未来第{label_horizon}个交易日收盘 > 今日收盘 => 1(涨), 否则 => 0(跌)")
    _log(
        logs,
        f"  模型: LightGBM | 滚动窗口={train_days}天 | 重训间隔={retrain_interval}天 | X列={len(x_cols) or '全部技术因子'}",
    )
    _log(logs, f"  超参: {params}")

    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for code in codes:
        name = names.get(code) or code
        try:
            results.append(
                _run_single_stock(
                    code,
                    name,
                    start,
                    end,
                    label_horizon,
                    min_bars,
                    train_days,
                    retrain_interval,
                    x_cols,
                    params,
                    logs,
                )
            )
        except Exception as e:
            logger.exception(f"lightgbm {code} failed")
            _log(logs, f"[错误] {name}({code}) 处理失败: {e}")
            errors.append({"stock_code": code, "stock_name": name, "message": str(e)})

    comparison = []
    if results:
        _log(logs, "=" * 60)
        _log(logs, "  LightGBM 预测结果对比")
        _log(logs, "=" * 60)
        for r in results:
            m = r["metrics"]
            comparison.append(
                {
                    "stock_code": r["stock_code"],
                    "stock_name": r["stock_name"],
                    **m,
                    "n_samples": r["n_samples"],
                }
            )
            _log(
                logs,
                f"    {r['stock_name']:<12s} AUC={m['auc']:.4f} Acc={m['accuracy']:.4f} "
                f"P={m['precision']:.4f} R={m['recall']:.4f} F1={m['f1']:.4f} n={r['n_samples']}",
            )
        _log(logs, "    月度准确率统计:")
        for r in results:
            _log(
                logs,
                f"    {r['stock_name']}: 均值={r['monthly_accuracy_mean']}, "
                f"标准差={r['monthly_accuracy_std']:.4f}, 最高={r['monthly_accuracy_max']}, "
                f"最低={r['monthly_accuracy_min']}",
            )
        _log(logs, "  可预测性分析")
        for r in results:
            _log(
                logs,
                f"    {r['stock_name']}: 整体准确率={r['metrics']['accuracy']:.4f}, "
                f"月度波动std={r['monthly_accuracy_std']:.4f}, 稳定性={r['stability']}",
            )
        avg_acc = float(np.mean([r["metrics"]["accuracy"] for r in results]))
        hz = "次日" if label_horizon == 1 else f"未来第{label_horizon}日"
        conclusion = (
            f"LightGBM 二分类完成，{hz}方向准确率约 {avg_acc * 100:.0f}%。"
            "输出的上涨概率可作为多因子 alpha 信号。"
        )
        _log(logs, f"  结论: {conclusion}")
    else:
        avg_acc = None
        conclusion = "没有成功完成的股票"

    return {
        "ok": bool(results),
        "start_date": start,
        "end_date": end,
        "label_horizon": label_horizon,
        "train_days": train_days,
        "retrain_interval": retrain_interval,
        "feature_cols": x_cols or get_all_feature_cols(),
        "lgb_params": params,
        "results": results,
        "comparison": comparison,
        "errors": errors,
        "avg_accuracy": avg_acc,
        "conclusion": conclusion,
        "logs": logs,
    }
