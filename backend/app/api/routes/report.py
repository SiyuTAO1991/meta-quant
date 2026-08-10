# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException

from app.schemas.common import ApiResponse, ReportDetailRequest, ReportListRequest
from app.services import report_service

router = APIRouter()


@router.post("/report/list", response_model=ApiResponse)
def report_list(body: ReportListRequest):
    try:
        data = report_service.query_report_list(
            body.ts_code, body.org, body.rating, body.page, body.size
        )
        return ApiResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/report/detail", response_model=ApiResponse)
def report_detail(body: ReportDetailRequest):
    try:
        data = report_service.query_report_detail(body.report_id)
        if not data:
            raise HTTPException(status_code=404, detail="研报不存在")
        return ApiResponse(data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
