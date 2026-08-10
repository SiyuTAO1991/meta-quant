# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException

from app.schemas.common import ApiResponse, NewsDetailRequest, NewsHotRequest, NewsStockRequest
from app.services import news_service

router = APIRouter()


@router.post("/news/stock", response_model=ApiResponse)
def news_stock(body: NewsStockRequest):
    try:
        data = news_service.query_stock_news(
            body.ts_code, body.keyword, body.start_date, body.page, body.size
        )
        return ApiResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/news/hot", response_model=ApiResponse)
def news_hot(body: NewsHotRequest):
    try:
        data = news_service.query_hot_news(body.page, body.size)
        return ApiResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/news/detail", response_model=ApiResponse)
def news_detail(body: NewsDetailRequest):
    try:
        data = news_service.query_news_detail(body.news_id)
        if not data:
            raise HTTPException(status_code=404, detail="新闻不存在")
        return ApiResponse(data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
