# -*- coding: utf-8 -*-
"""工业级特征工程 API（无前端，供后续 XGBoost/LightGBM 调用）。"""
from fastapi import APIRouter, HTTPException

from app.schemas.common import ApiResponse, FeatureEngineeringRequest
from app.services.feature_engineering_service import run_feature_engineering

router = APIRouter()


@router.post("/feature_engineering/run", response_model=ApiResponse)
def feature_engineering_run(body: FeatureEngineeringRequest):
    try:
        data = run_feature_engineering(
            stock_codes=body.stock_codes,
            start_date=body.start_date,
            end_date=body.end_date,
            min_bars=body.min_bars,
            include_fundamental=body.include_fundamental,
            neutralize_factor=body.neutralize_factor,
            neutralize_all=body.neutralize_all,
            corr_threshold=body.corr_threshold,
            industry_map=body.industry_map or None,
        )
        return ApiResponse(data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
