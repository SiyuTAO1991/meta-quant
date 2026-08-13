# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException

from app.schemas.common import ApiResponse, CalendarListRequest, CalendarTodayRequest
from app.services import calendar_service

router = APIRouter()


@router.post("/calendar/list", response_model=ApiResponse)
def calendar_list(body: CalendarListRequest):
    try:
        data = calendar_service.query_calendar(
            body.start_date,
            body.end_date,
            body.level,
            page=body.page,
            size=body.size,
        )
        return ApiResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calendar/today", response_model=ApiResponse)
def calendar_today(body: CalendarTodayRequest):
    try:
        data = calendar_service.query_calendar_today(
            body.level,
            page=body.page,
            size=body.size,
        )
        return ApiResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
