# -*- coding: utf-8 -*-
"""
行情查询与回测数据保障服务。

职责：
  - 日线/指数/概念等行情查询（读 MySQL trade_stock_daily）
  - 回测前股票代码校验、数据覆盖检查、自动触发日线采集
"""
from __future__ import annotations

import re  # 用于股票代码格式校验与分隔符解析
from typing import Iterable

from loguru import logger  # 记录采集/校验过程中的 info、warning

from app.database import execute_query  # 执行 MySQL 只读查询
from app.schemas.common import serialize_row  # 将 Decimal/datetime 转为 JSON 友好类型
from app.utils import normalize_date  # 统一 YYYYMMDD / YYYY-MM-DD 日期格式

# A 股代码格式：6 位数字 + .SH / .SZ / .BJ
_TS_CODE_RE = re.compile(r"^\d{6}\.(SH|SZ|BJ)$")
# 回测所需最少 K 线根数（低于此值视为数据不足，需触发采集）
_MIN_BACKTEST_BARS = 20


def normalize_ts_code(code: str) -> str:
    """
    校验并规范化股票代码。

    Args:
        code: 原始代码，如 ``600519.SH``、``600519.sh``

    Returns:
        大写格式的标准代码

    Raises:
        ValueError: 格式不符合 ``\\d{6}.(SH|SZ|BJ)``
    """
    # 去首尾空格并转大写，统一后缀 SH/SZ/BJ
    text = (code or "").strip().upper()
    # 不匹配标准格式则直接拒绝，避免脏数据进入回测
    if not _TS_CODE_RE.match(text):
        raise ValueError(f"股票代码格式错误: {code}，请使用如 600519.SH")
    return text


def parse_stock_codes(stock_list: Iterable[str] | str) -> list[str]:
    """
    解析股票代码列表，去重并保持顺序。

    支持逗号、中文逗号、空格分隔；也支持传入单个字符串或字符串列表。

    Args:
        stock_list: 如 ``"600519.SH, 000001.SZ"`` 或 ``["600519.SH", "000001.SZ"]``

    Returns:
        规范化后的代码列表

    Raises:
        ValueError: 解析后为空或存在非法格式
    """
    if isinstance(stock_list, str):
        # 前端手填字符串：按逗号/中文逗号/空白切分
        raw_parts = re.split(r"[,，\s]+", stock_list.strip())
    else:
        # API 传入列表：逐项处理，列表项内仍可能含逗号分隔
        raw_parts = []
        for item in stock_list:
            if not item:
                continue
            if isinstance(item, str) and re.search(r"[,，\s]", item):
                raw_parts.extend(re.split(r"[,，\s]+", item.strip()))
            else:
                raw_parts.append(str(item))

    codes: list[str] = []
    seen: set[str] = set()  # 去重集合，保留首次出现顺序
    for part in raw_parts:
        part = part.strip()
        if not part:
            continue
        code = normalize_ts_code(part)  # 每个片段单独校验格式
        if code not in seen:
            seen.add(code)
            codes.append(code)
    if not codes:
        raise ValueError("请填写至少一个股票代码")
    return codes


def verify_stock_exists(ts_code: str) -> dict:
    """
    校验股票是否存在且处于上市状态。

    优先调用 Tushare ``stock_basic``；若 Token 不可用，则降级为
    检查 ``trade_stock_daily`` 中是否已有该代码的历史数据。

    Args:
        ts_code: 标准股票代码

    Returns:
        ``{"ts_code": ..., "name": ...}``，降级模式下 name 可能为空字符串

    Raises:
        ValueError: 代码不存在、已退市，或无法完成校验
    """
    try:
        from app.collectors.daily import _get_pro  # 延迟导入，避免启动时强依赖 Tushare

        pro = _get_pro()  # 获取 Tushare Pro 客户端（需 .env 中 TUSHARE_TOKEN）
        # 按 ts_code 精确查询基础信息
        df = pro.stock_basic(ts_code=ts_code, fields="ts_code,name,list_status")
        if df is None or len(df) == 0:
            raise ValueError(f"股票代码不存在: {ts_code}")
        row = df.iloc[0]
        # list_status=L 表示上市中；非 L（如 D 退市、P 暂停）不允许回测
        if str(row.get("list_status") or "") != "L":
            raise ValueError(f"股票 {ts_code} 当前非上市状态，无法回测")
        return {"ts_code": ts_code, "name": str(row.get("name") or "")}
    except ValueError:
        # 业务校验错误（不存在/未上市）原样抛出
        raise
    except Exception as e:
        # Tushare 不可用（无 Token、网络异常等）时走降级逻辑
        logger.warning(f"verify stock via tushare failed {ts_code}: {e}")
        rows = execute_query(
            "SELECT COUNT(1) AS cnt FROM trade_stock_daily WHERE stock_code = %s LIMIT 1",
            (ts_code,),
        )
        # 库中已有该股票历史日线，视为“存在”继续回测
        if rows and int(rows[0]["cnt"]) > 0:
            return {"ts_code": ts_code, "name": ""}
        raise ValueError(f"无法校验股票 {ts_code}，请检查 TUSHARE_TOKEN 配置或先采集数据") from e


def get_daily_coverage(ts_code: str, start_date: str, end_date: str) -> dict:
    """
    查询指定区间内日线数据覆盖情况。

    Args:
        ts_code: 股票代码
        start_date: 起始日期，支持 ``YYYY-MM-DD`` / ``YYYYMMDD``
        end_date: 结束日期

    Returns:
        包含 count、min_date、max_date、sufficient 的字典；
        sufficient 表示 count 是否达到回测最低根数要求
    """
    start = normalize_date(start_date, as_dash=True)  # 统一为 YYYY-MM-DD 供 SQL 使用
    end = normalize_date(end_date, as_dash=True)
    rows = execute_query(
        """
        SELECT COUNT(1) AS cnt, MIN(trade_date) AS min_date, MAX(trade_date) AS max_date
        FROM trade_stock_daily
        WHERE stock_code = %s AND trade_date BETWEEN %s AND %s
        """,
        (ts_code, start, end),
    )
    row = rows[0] if rows else {}
    count = int(row.get("cnt") or 0)  # 区间内实际 K 线条数
    min_date = row.get("min_date")  # 区间内最早交易日
    max_date = row.get("max_date")  # 区间内最晚交易日
    return {
        "ts_code": ts_code,
        "count": count,
        "min_date": min_date.isoformat() if min_date else None,
        "max_date": max_date.isoformat() if max_date else None,
        "sufficient": count >= _MIN_BACKTEST_BARS,  # 是否满足回测最低数据量
    }


def ensure_daily_data(
    stock_list: Iterable[str] | str,
    start_date: str,
    end_date: str,
    min_bars: int = _MIN_BACKTEST_BARS,
) -> list[str]:
    """
    回测前数据保障（同步执行）。

    流程：
      1. 解析并校验股票代码格式
      2. 通过 Tushare 确认股票存在且已上市
      3. 检查 ``trade_stock_daily`` 在回测区间内是否有足够 K 线
      4. 不足时同步调用 ``run_daily_crawl`` 补齐，并再次校验

    Args:
        stock_list: 单个或多个股票代码
        start_date: 回测起始日期
        end_date: 回测结束日期
        min_bars: 最低 K 线根数，默认 20

    Returns:
        校验通过的规范化代码列表

    Raises:
        ValueError: 校验失败、采集失败或补齐后仍不足
    """
    # ---------- 第一步：解析代码并统一日期格式 ----------
    codes = parse_stock_codes(stock_list)
    start = normalize_date(start_date, as_dash=True)
    end = normalize_date(end_date, as_dash=True)

    # ---------- 第二步：逐只校验股票是否存在 ----------
    for code in codes:
        verify_stock_exists(code)

    # ---------- 第三步：检查回测区间内数据是否充足 ----------
    need_crawl: list[str] = []  # 需要补采的股票列表
    for code in codes:
        coverage = get_daily_coverage(code, start, end)
        if coverage["count"] < min_bars:
            need_crawl.append(code)
            logger.info(
                f"backtest data insufficient {code}: count={coverage['count']} "
                f"range={coverage['min_date']}~{coverage['max_date']}"
            )

    # ---------- 第四步：数据不足则同步触发日线采集 ----------
    if need_crawl:
        from app.collectors.daily import run_daily_crawl  # 延迟导入采集器

        logger.info(f"backtest auto crawl daily_bar for {need_crawl}, range={start}~{end}")
        # run_daily_crawl 接受 YYYYMMDD，故去掉日期中的 "-"
        result = run_daily_crawl(
            need_crawl,
            start_date=start.replace("-", ""),
            end_date=end.replace("-", ""),
        )
        failed = result.get("failed") or []
        if failed:
            raise ValueError(f"自动采集失败: {', '.join(failed)}")

        # ---------- 第五步：采集后再次校验，仍不足则报错 ----------
        still_bad: list[str] = []
        for code in need_crawl:
            coverage = get_daily_coverage(code, start, end)
            if coverage["count"] < min_bars:
                still_bad.append(f"{code}(仅{coverage['count']}条)")
        if still_bad:
            raise ValueError(
                f"采集后数据仍不足以回测: {', '.join(still_bad)}，请检查 TUSHARE_TOKEN 或调整回测区间"
            )

    return codes


def query_stock_daily(ts_code: str, start_date: str, end_date: str) -> list[dict]:
    """
    查询个股日 K 线（前复权，来源 trade_stock_daily）。

    Args:
        ts_code: 股票代码
        start_date: 起始日期
        end_date: 结束日期

    Returns:
        按 trade_date 升序排列的 K 线字典列表
    """
    start = normalize_date(start_date, as_dash=True)
    end = normalize_date(end_date, as_dash=True)
    sql = """
        SELECT stock_code, trade_date, open_price, high_price, low_price,
               close_price, volume, amount, turnover_rate
        FROM trade_stock_daily
        WHERE stock_code = %s AND trade_date BETWEEN %s AND %s
        ORDER BY trade_date ASC
    """
    rows = execute_query(sql, (ts_code, start, end))  # 闭区间查询 [start, end]
    # serialize_row 处理 Decimal/datetime，便于 JSON 序列化返回给 API
    return [serialize_row(r) for r in rows]


def query_index_daily(index_code: str, start_date: str, end_date: str) -> list[dict]:
    """
    查询指数日线。

    与个股共用 ``trade_stock_daily`` 表；库中无数据时返回空列表，
    可由采集模块补齐后再查。

    Args:
        index_code: 指数代码，如 ``000001.SH``
        start_date: 起始日期
        end_date: 结束日期
    """
    # 指数与个股结构相同，复用 query_stock_daily
    return query_stock_daily(index_code, start_date, end_date)


def query_stock_concepts(ts_code: str) -> list[dict]:
    """
    查询个股所属概念板块（AkShare 兜底）。

    接口不稳定时返回热门概念列表前 30 条作为兜底，失败则返回空列表。

    Args:
        ts_code: 股票代码

    Returns:
        概念列表，每项含 ts_code、concept_name、symbol
    """
    try:
        import akshare as ak  # 延迟导入，仅在需要概念数据时加载

        symbol = ts_code.split(".")[0]  # 取 6 位数字代码，如 600519
        df = ak.stock_board_concept_name_em()  # 东方财富概念板块列表
        if df is None or len(df) == 0:
            return []
        items = []
        # 个股所属概念接口不稳定，此处返回热门概念前 30 条作展示兜底
        for _, row in df.head(30).iterrows():
            items.append(
                {
                    "ts_code": ts_code,
                    "concept_name": str(row.get("板块名称") or row.iloc[1]),
                    "symbol": symbol,
                }
            )
        return items
    except Exception as e:
        logger.warning(f"concept query failed: {e}")
        return []  # 概念查询失败不影响主流程，返回空列表


def list_available_stocks(limit: int = 50) -> list[str]:
    """
    列出库内已有日线数据的股票代码。

    Args:
        limit: 最多返回条数，默认 50

    Returns:
        按 stock_code 排序的代码列表
    """
    rows = execute_query(
        "SELECT DISTINCT stock_code FROM trade_stock_daily ORDER BY stock_code LIMIT %s",
        (limit,),
    )
    # 只返回代码字符串列表，供下拉/筛选等场景使用
    return [r["stock_code"] for r in rows]
