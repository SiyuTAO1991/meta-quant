# -*- coding: utf-8 -*-
"""因子库 API。"""
from fastapi import APIRouter, HTTPException

from app.schemas.common import (
    ApiResponse,
    FactorEvaluateRequest,
    FactorResultListRequest,
    FactorValidateRequest,
)
from app.services import factor_service

router = APIRouter()


@router.post("/factor/meta", response_model=ApiResponse)
def factor_meta():
    return ApiResponse(data=factor_service.get_factor_meta())


@router.post("/factor/validate_stocks", response_model=ApiResponse)
def factor_validate_stocks(body: FactorValidateRequest):
    try:
        data = factor_service.validate_stocks(body.stock_codes)
        return ApiResponse(data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/factor/evaluate", response_model=ApiResponse)
def factor_evaluate(body: FactorEvaluateRequest):
    try:
        data = factor_service.run_factor_evaluation(
            universe=body.universe,
            stock_codes=body.stock_codes,
            start_date=body.start_date,
            end_date=body.end_date,
            holding_days=body.holding_days,
            category=body.category,
            sort_by=body.sort_by,
            keyword=body.keyword,
        )
        return ApiResponse(data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/factor/results", response_model=ApiResponse)
def factor_results(body: FactorResultListRequest):
    try:
        data = factor_service.list_factor_results(page=body.page, size=body.size)
        return ApiResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
