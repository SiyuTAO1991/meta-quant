# -*- coding: utf-8 -*-
"""新闻事件采集（AkShare 东方财富）。"""
from __future__ import annotations

import akshare as ak
from loguru import logger

from app.config import get_settings
from app.database import execute_query, execute_update
from app.utils import parse_datetime

POSITIVE_WORDS = ["涨停", "大涨", "利好", "增长", "突破", "新高", "预增", "增持", "盈利", "超预期"]
NEGATIVE_WORDS = ["跌停", "大跌", "利空", "下降", "跌破", "新低", "预减", "减持", "亏损", "违规", "处罚"]
IMPORTANT_WORDS = ["资产重组", "业绩预增", "业绩预减", "股权激励", "股东减持", "股东增持", "重大合同", "并购", "回购"]


def _sentiment(title: str) -> str:
    for w in POSITIVE_WORDS:
        if w in title:
            return "positive"
    for w in NEGATIVE_WORDS:
        if w in title:
            return "negative"
    return "neutral"


def _important(title: str) -> int:
    return 1 if any(w in title for w in IMPORTANT_WORDS) else 0


def run_news_crawl(stock_codes: list[str] | None = None) -> dict:
    settings = get_settings()
    codes = stock_codes or settings.default_stocks
    existing = {r["title"] for r in execute_query("SELECT title FROM trade_stock_news")}
    saved = 0
    for code in codes:
        symbol = code.split(".")[0]
        try:
            df = ak.stock_news_em(symbol=symbol)
        except Exception as e:
            logger.warning(f"news crawl {code}: {e}")
            continue
        if df is None or len(df) == 0:
            continue
        for _, row in df.iterrows():
            title = str(row.get("新闻标题", "")).strip()
            if not title or title in existing:
                continue
            content = str(row.get("新闻内容", "") or "")[:2000]
            url = str(row.get("新闻链接", "") or "")
            pub = parse_datetime(row.get("发布时间"))
            source = str(row.get("文章来源", "") or "eastmoney")
            execute_update(
                """
                INSERT INTO trade_stock_news
                (stock_code, news_type, title, content, source, source_url, published_at, sentiment, is_important)
                VALUES (%s, 'news', %s, %s, %s, %s, %s, %s, %s)
                """,
                (code, title, content, source, url, pub, _sentiment(title), _important(title)),
            )
            existing.add(title)
            saved += 1
    return {"rows": saved, "message": f"saved={saved}"}
