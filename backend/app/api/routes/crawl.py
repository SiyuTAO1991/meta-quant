# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException

from app.schemas.common import (
    ApiResponse,
    CrawlLogRequest,
    CrawlRetryRequest,
    CrawlTriggerRequest,
)
from app.services import crawl_service

router = APIRouter()


@router.post("/crawl/task/list", response_model=ApiResponse)
def crawl_task_list():
    return ApiResponse(data=crawl_service.list_tasks())


@router.post("/crawl/task/trigger", response_model=ApiResponse)
def crawl_task_trigger(body: CrawlTriggerRequest):
    try:
        data = crawl_service.trigger_task(body.task_id, body.ts_codes)
        return ApiResponse(data=data, message=data.get("message", "ok"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crawl/task/log", response_model=ApiResponse)
def crawl_task_log(body: CrawlLogRequest):
    try:
        data = crawl_service.query_task_logs(body.task_id, body.start_date, body.page, body.size)
        return ApiResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crawl/task/retry", response_model=ApiResponse)
def crawl_task_retry(body: CrawlRetryRequest):
    try:
        data = crawl_service.retry_task(body.log_id)
        return ApiResponse(data=data, message=data.get("message", "ok"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
