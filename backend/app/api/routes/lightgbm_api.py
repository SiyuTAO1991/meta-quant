# -*- coding: utf-8 -*-
"""LightGBM 涨跌预测 API。"""
from fastapi import APIRouter, HTTPException

from app.schemas.common import ApiResponse, LightgbmPredictRequest
from app.services import lightgbm_service

router = APIRouter()


@router.post("/lightgbm/meta", response_model=ApiResponse)
def lightgbm_meta():
    return ApiResponse(data=lightgbm_service.get_lightgbm_meta())


@router.post("/lightgbm/predict", response_model=ApiResponse)
def lightgbm_predict(body: LightgbmPredictRequest):
    try:
        data = lightgbm_service.run_lightgbm_predict(
            stock_codes=body.stock_codes,
            start_date=body.start_date,
            end_date=body.end_date,
            label_horizon=body.label_horizon,
            min_bars=body.min_bars,
            train_days=body.train_days,
            retrain_interval=body.retrain_interval,
            feature_cols=body.feature_cols,
            lgb_params=body.lgb_params.model_dump(),
        )
        return ApiResponse(data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
