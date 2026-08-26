# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException

from app.schemas.common import ApiResponse, ChanAnalyzeRequest
from app.services import chan_service

router = APIRouter()


@router.post("/chan/analyze", response_model=ApiResponse)
def chan_analyze(body: ChanAnalyzeRequest):
    try:
        data = chan_service.analyze_chan(
            ts_code=body.ts_code,
            start_date=body.start_date,
            end_date=body.end_date,
            config=body.config or None,
        )
        return ApiResponse(data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
