# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException

from app.schemas.common import ApiResponse, MacroListRequest, MacroTrendRequest
from app.services import macro_service

router = APIRouter()


@router.post("/macro/list", response_model=ApiResponse)
def macro_list(body: MacroListRequest):
    try:
        data = macro_service.list_macro_indicators(body.indicator_type, body.page, body.size)
        return ApiResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/macro/trend", response_model=ApiResponse)
def macro_trend(body: MacroTrendRequest):
    try:
        data = macro_service.query_macro_trend(body.indicator_code, body.start_date, body.end_date)
        return ApiResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
