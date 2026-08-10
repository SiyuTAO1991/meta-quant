# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException

from app.schemas.common import (
    ApiResponse,
    FinanceCompareRequest,
    FinanceIndicatorRequest,
    FinanceStatementRequest,
)
from app.services import finance_service

router = APIRouter()


@router.post("/finance/indicator", response_model=ApiResponse)
def finance_indicator(body: FinanceIndicatorRequest):
    try:
        data = finance_service.query_finance_indicator(body.ts_code, body.start_year, body.end_year)
        return ApiResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/finance/income", response_model=ApiResponse)
def finance_income(body: FinanceStatementRequest):
    try:
        data = finance_service.query_finance_by_period(body.ts_code, body.period)
        return ApiResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/finance/balance", response_model=ApiResponse)
def finance_balance(body: FinanceStatementRequest):
    try:
        data = finance_service.query_finance_by_period(body.ts_code, body.period)
        return ApiResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/finance/cashflow", response_model=ApiResponse)
def finance_cashflow(body: FinanceStatementRequest):
    try:
        data = finance_service.query_finance_by_period(body.ts_code, body.period)
        return ApiResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/finance/compare", response_model=ApiResponse)
def finance_compare(body: FinanceCompareRequest):
    try:
        data = finance_service.compare_finance(body.ts_codes, body.year)
        return ApiResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
