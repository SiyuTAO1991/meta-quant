# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException

from app.schemas.common import ApiResponse, IndexDailyRequest, StockConceptRequest, StockDailyRequest
from app.services import stock_service

router = APIRouter()


@router.post("/stock/daily", response_model=ApiResponse)
def stock_daily(body: StockDailyRequest):
    try:
        data = stock_service.query_stock_daily(body.ts_code, body.start_date, body.end_date)
        return ApiResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stock/index/daily", response_model=ApiResponse)
def index_daily(body: IndexDailyRequest):
    try:
        data = stock_service.query_index_daily(body.index_code, body.start_date, body.end_date)
        return ApiResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stock/concept", response_model=ApiResponse)
def stock_concept(body: StockConceptRequest):
    try:
        data = stock_service.query_stock_concepts(body.ts_code)
        return ApiResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock/list", response_model=ApiResponse)
def stock_list():
    try:
        return ApiResponse(data=stock_service.list_available_stocks())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
