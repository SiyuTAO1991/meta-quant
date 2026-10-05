# -*- coding: utf-8 -*-
"""多因子打分选股 API。"""
from fastapi import APIRouter, HTTPException

from app.schemas.common import ApiResponse, MultiFactorBacktestRequest
from app.services import multi_factor_service

router = APIRouter()


@router.post("/multi-factor/meta", response_model=ApiResponse)
def multi_factor_meta():
    return ApiResponse(data=multi_factor_service.get_multi_factor_meta())


@router.post("/multi-factor/backtest", response_model=ApiResponse)
def multi_factor_backtest(body: MultiFactorBacktestRequest):
    try:
        factor_weights = [item.model_dump() for item in (body.factor_weights or [])]
        data = multi_factor_service.run_multi_factor_backtest(
            start_date=body.start_date,
            end_date=body.end_date,
            top_n=body.top_n,
            cash=body.cash,
            universe=body.universe,
            stock_codes=body.stock_codes,
            max_stocks=body.max_stocks,
            holding_days=body.holding_days,
            factor_weights=factor_weights or None,
        )
        return ApiResponse(data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
