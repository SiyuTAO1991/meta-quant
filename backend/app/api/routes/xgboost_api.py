# -*- coding: utf-8 -*-
"""XGBoost 涨跌预测 API。"""
from fastapi import APIRouter, HTTPException

from app.schemas.common import ApiResponse, XgboostPredictRequest
from app.services import xgboost_service

router = APIRouter()


@router.post("/xgboost/meta", response_model=ApiResponse)
def xgboost_meta():
    return ApiResponse(data=xgboost_service.get_xgboost_meta())


@router.post("/xgboost/predict", response_model=ApiResponse)
def xgboost_predict(body: XgboostPredictRequest):
    try:
        data = xgboost_service.run_xgboost_predict(
            stock_codes=body.stock_codes,
            start_date=body.start_date,
            end_date=body.end_date,
            label_horizon=body.label_horizon,
            min_bars=body.min_bars,
            train_days=body.train_days,
            retrain_interval=body.retrain_interval,
            feature_cols=body.feature_cols,
            xgb_params=body.xgb_params.model_dump(),
        )
        return ApiResponse(data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
