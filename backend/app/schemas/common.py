# -*- coding: utf-8 -*-
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: Any = None


class PageResult(BaseModel):
    total: int = 0
    page: int = 1
    size: int = 20
    items: list[Any] = Field(default_factory=list)


# ---------- 行情 ----------
class StockDailyRequest(BaseModel):
    ts_code: str = Field(..., description="如 600519.SH")
    start_date: str = Field(..., description="YYYYMMDD")
    end_date: str = Field(..., description="YYYYMMDD")


class IndexDailyRequest(BaseModel):
    index_code: str = "000001.SH"
    start_date: str
    end_date: str


class StockConceptRequest(BaseModel):
    ts_code: str


class DailyBarItem(BaseModel):
    stock_code: str
    trade_date: date | str
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    close_price: Optional[float] = None
    volume: Optional[int] = None
    amount: Optional[float] = None
    turnover_rate: Optional[float] = None


# ---------- 财务 ----------
class FinanceIndicatorRequest(BaseModel):
    ts_code: str
    start_year: int = 2020
    end_year: int = 2026
    report_type: int = 1


class FinanceStatementRequest(BaseModel):
    ts_code: str
    period: str = Field(..., description="如 20260630")


class FinanceCompareRequest(BaseModel):
    ts_codes: list[str]
    year: int = 2025


# ---------- 宏观 ----------
class MacroListRequest(BaseModel):
    indicator_type: str = ""
    page: int = 1
    size: int = 20


class MacroTrendRequest(BaseModel):
    indicator_code: str = "CPI"
    start_date: str = "20240101"
    end_date: str = "20260801"


# ---------- 新闻 ----------
class NewsStockRequest(BaseModel):
    ts_code: str
    keyword: str = ""
    start_date: str = ""
    page: int = 1
    size: int = 20


class NewsHotRequest(BaseModel):
    page: int = 1
    size: int = 20


class NewsDetailRequest(BaseModel):
    news_id: int


# ---------- 研报 ----------
class ReportListRequest(BaseModel):
    ts_code: str
    org: str = ""
    rating: str = ""
    page: int = 1
    size: int = 20


class ReportDetailRequest(BaseModel):
    report_id: int


# ---------- 日历 ----------
class CalendarListRequest(BaseModel):
    start_date: str
    end_date: str
    level: str = ""
    page: int = 1
    size: int = 20


class CalendarTodayRequest(BaseModel):
    level: str = ""
    page: int = 1
    size: int = 20


# ---------- 催化剂 ----------
class CatalystEventRequest(BaseModel):
    ts_code: str = ""
    event_type: str = ""
    start_date: str = ""
    end_date: str = ""
    level: str = "high"


class CatalystTodayRequest(BaseModel):
    level: str = "high"


# ---------- 采集任务 ----------
class CrawlTriggerRequest(BaseModel):
    task_id: str
    ts_codes: str = ""
    start_date: str = ""
    end_date: str = ""


class CrawlLogRequest(BaseModel):
    task_id: str = ""
    start_date: str = ""
    page: int = 1
    size: int = 30


class CrawlRetryRequest(BaseModel):
    log_id: int


# ---------- 策略 / 回测 ----------
class StrategyListRequest(BaseModel):
    page: int = 1
    page_size: int = 50


class StrategyDetailRequest(BaseModel):
    strategy_key: str = Field(..., description="策略唯一标识，如 double_ma")


class BacktestRunRequest(BaseModel):
    stock_list: list[str] = Field(..., min_length=1)
    start_date: str = Field(..., description="YYYY-MM-DD 或 YYYYMMDD")
    end_date: str = Field(..., description="YYYY-MM-DD 或 YYYYMMDD")
    strategy_key: str
    strategy_params: dict[str, Any] = Field(default_factory=dict)
    cash: float = 100000
    commission: float = 0.0003
    enable_stamp_tax: bool = True
    plot_curve: bool = True


class BacktestReportRequest(BaseModel):
    backtest_id: int


class ChanAnalyzeRequest(BaseModel):
    ts_code: str = Field(..., description="如 600519.SH")
    start_date: str = Field(..., description="YYYY-MM-DD 或 YYYYMMDD")
    end_date: str = Field(..., description="YYYY-MM-DD 或 YYYYMMDD")
    config: dict[str, Any] = Field(default_factory=dict)


class FactorValidateRequest(BaseModel):
    stock_codes: str = Field(..., description="逗号分隔股票代码，如 600519.SH,000001.SZ")


class FactorEvaluateRequest(BaseModel):
    universe: str = Field("all", description="all=全A股 / custom=部分A股")
    stock_codes: str = Field("", description="部分A股时必填")
    start_date: str = Field(..., description="评价起始日 YYYY-MM-DD / YYYYMMDD")
    end_date: str = Field(..., description="评价结束日")
    holding_days: int = Field(20, description="调仓周期：5/10/20/60")
    category: str = Field("全部", description="因子分类筛选")
    sort_by: str = Field("abs_ir", description="排序字段")
    keyword: str = Field("", description="因子名/代码搜索")


class FactorResultListRequest(BaseModel):
    page: int = Field(1, ge=1)
    size: int = Field(10, ge=1, le=100, description="每页因子结果行数，默认10")


class MultiFactorWeightItem(BaseModel):
    code: str
    weight: float = 0.1
    direction: int = 1
    enabled: bool = True


class MultiFactorBacktestRequest(BaseModel):
    universe: str = Field("all", description="all=全A股 / custom=部分A股；股票代码为空时强制全A")
    stock_codes: str = Field("", description="逗号分隔；留空则默认全部A股")
    start_date: str = Field(..., description="回测起始日 YYYY-MM-DD / YYYYMMDD")
    end_date: str = Field(..., description="回测结束日")
    top_n: int = Field(10, ge=1, le=100, description="每期持仓 Top-N")
    cash: float = Field(1_000_000, ge=1000, description="初始资金")
    max_stocks: int = Field(800, ge=50, le=3000, description="全A股股票池上限")
    holding_days: int = Field(
        0,
        description="调仓周期：5/10/20/60=交易日；0=月末调仓",
    )
    factor_weights: list[MultiFactorWeightItem] = Field(
        default_factory=list,
        description="因子权重配置；空则用默认8因子",
    )


def serialize_row(row: dict) -> dict:
    """将 Decimal/datetime 转为可 JSON 序列化类型。"""
    out = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        elif isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out
