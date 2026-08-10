# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException

from app.schemas.common import ApiResponse, CatalystEventRequest, CatalystTodayRequest
from app.services import calendar_service

router = APIRouter()


@router.post("/catalyst/event", response_model=ApiResponse)
def catalyst_event(body: CatalystEventRequest):
    try:
        data = calendar_service.query_catalyst_events(
            body.ts_code, body.event_type, body.start_date, body.end_date, body.level
        )
        return ApiResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/catalyst/event_today", response_model=ApiResponse)
def catalyst_today(body: CatalystTodayRequest):
    try:
        data = calendar_service.query_catalyst_today(body.level)
        return ApiResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
