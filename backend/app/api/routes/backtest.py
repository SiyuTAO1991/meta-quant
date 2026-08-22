# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException

from app.schemas.common import (
    ApiResponse,
    BacktestReportRequest,
    BacktestRunRequest,
    StrategyDetailRequest,
    StrategyListRequest,
)
from app.services import backtest_service, strategy_service

router = APIRouter()


@router.post("/strategy/list", response_model=ApiResponse)
def strategy_list(body: StrategyListRequest):
    try:
        data = strategy_service.list_strategies(page=body.page, page_size=body.page_size)
        return ApiResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strategy/detail", response_model=ApiResponse)
def strategy_detail(body: StrategyDetailRequest):
    try:
        data = strategy_service.get_strategy_detail(body.strategy_key)
        return ApiResponse(data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backtest/run", response_model=ApiResponse)
def backtest_run(body: BacktestRunRequest):
    try:
        data = backtest_service.run_backtest_task(
            stock_list=body.stock_list,
            start_date=body.start_date,
            end_date=body.end_date,
            strategy_key=body.strategy_key,
            strategy_params=body.strategy_params,
            cash=body.cash,
            commission=body.commission,
            enable_stamp_tax=body.enable_stamp_tax,
            plot_curve=body.plot_curve,
        )
        return ApiResponse(data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backtest/report", response_model=ApiResponse)
def backtest_report(body: BacktestReportRequest):
    try:
        data = backtest_service.get_backtest_report(body.backtest_id)
        return ApiResponse(data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
