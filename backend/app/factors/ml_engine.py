# -*- coding: utf-8 -*-
"""滚动训练与分类评估（参考训练营 ml_engine.py）。"""
from __future__ import annotations

from inspect import signature
from typing import Any, Callable

import numpy as np
import pandas as pd
from loguru import logger

DEFAULT_XGB_PARAMS: dict[str, Any] = {
    "n_estimators": 200,
    "max_depth": 5,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 10,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "random_state": 42,
    "use_label_encoder": False,
    "eval_metric": "logloss",
    "verbosity": 0,
}


DEFAULT_LGB_PARAMS: dict[str, Any] = {
    "n_estimators": 200,
    "max_depth": 5,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_samples": 20,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "random_state": 42,
    "verbose": -1,
}


def make_labels(df: pd.DataFrame, horizon: int = 1, method: str = "binary") -> pd.Series:
    future_ret = df["close"].shift(-horizon) / df["close"] - 1
    if method == "binary":
        label = (future_ret > 0).astype(float)
        label[future_ret.isna()] = np.nan
        return label
    raise ValueError(f"不支持的标签方法: {method}")


def _filter_estimator_params(cls, params: dict[str, Any]) -> dict[str, Any]:
    try:
        allowed = set(signature(cls).parameters)
    except (TypeError, ValueError):
        return dict(params)
    return {k: v for k, v in params.items() if k in allowed}


def train_xgboost(X_train, y_train, params: dict | None = None):
    import xgboost as xgb

    merged = dict(DEFAULT_XGB_PARAMS)
    if params:
        merged.update({k: v for k, v in params.items() if v is not None})
    cleaned = _filter_estimator_params(xgb.XGBClassifier, merged)
    model = xgb.XGBClassifier(**cleaned)
    model.fit(X_train, y_train)
    return model


def train_lightgbm(X_train, y_train, params: dict | None = None):
    import lightgbm as lgb

    merged = dict(DEFAULT_LGB_PARAMS)
    if params:
        merged.update({k: v for k, v in params.items() if v is not None})
    cleaned = _filter_estimator_params(lgb.LGBMClassifier, merged)
    model = lgb.LGBMClassifier(**cleaned)
    model.fit(X_train, y_train)
    return model


TRAIN_FUNCS = {
    "xgboost": train_xgboost,
    "lightgbm": train_lightgbm,
}


def rolling_train_predict(
    df: pd.DataFrame,
    feature_cols: list[str],
    label_col: str = "label",
    model_type: str = "xgboost",
    train_days: int = 120,
    retrain_interval: int = 20,
    params: dict | None = None,
    verbose: bool = True,
    log_fn: Callable[[str], None] | None = None,
) -> pd.DataFrame:
    """过去 train_days 天训练，预测下一天；每隔 retrain_interval 重训。"""
    train_func = TRAIN_FUNCS.get(model_type)
    if train_func is None:
        raise ValueError(f"不支持的模型类型: {model_type}")

    def _log(msg: str) -> None:
        if log_fn:
            log_fn(msg)
        elif verbose:
            logger.info(msg)

    work = df.dropna(subset=feature_cols + [label_col]).copy()
    if "trade_date" not in work.columns:
        work = work.reset_index()
        if "trade_date" not in work.columns:
            work = work.rename(columns={work.columns[0]: "trade_date"})
    work = work.reset_index(drop=True)

    results: list[dict] = []
    model = None
    last_train_idx = -retrain_interval
    total = max(0, len(work) - train_days)

    for i in range(train_days, len(work)):
        if model is None or (i - last_train_idx) >= retrain_interval:
            train_start = max(0, i - train_days)
            train_data = work.iloc[train_start:i]
            X_train = train_data[feature_cols].to_numpy(dtype=float)
            y_train = train_data[label_col].to_numpy(dtype=int)
            if len(np.unique(y_train)) < 2:
                continue
            model = train_func(X_train, y_train, params)
            last_train_idx = i

        if model is None:
            continue
        row = work.iloc[i]
        X_test = row[feature_cols].to_numpy(dtype=float).reshape(1, -1)
        y_pred = int(model.predict(X_test)[0])
        y_prob = float(model.predict_proba(X_test)[0, 1])
        results.append(
            {
                "date": row["trade_date"],
                "y_true": int(row[label_col]),
                "y_pred": y_pred,
                "y_prob": y_prob,
            }
        )
        if verbose and len(results) % 100 == 0:
            _log(f"  [{model_type}] 已预测 {len(results)}/{total} 天")

    return pd.DataFrame(results)


def evaluate_classification(y_true, y_pred, y_prob=None) -> dict[str, float]:
    from sklearn.metrics import (
        accuracy_score,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "auc": 0.0,
    }
    if y_prob is not None and len(np.unique(y_true)) > 1:
        metrics["auc"] = float(roc_auc_score(y_true, np.asarray(y_prob)))
    return metrics


def confusion_matrix_2x2(y_true, y_pred) -> list[list[int]]:
    from sklearn.metrics import confusion_matrix

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    return [[int(cm[0, 0]), int(cm[0, 1])], [int(cm[1, 0]), int(cm[1, 1])]]
