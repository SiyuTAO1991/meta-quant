# Meta Quant · 量化交易数据平台

前后端分离的量化数据与回测应用：

- **前端**：Vue3 + Vite + Element Plus + ECharts
- **后端**：FastAPI + Pandas + Backtrader + Tushare / AkShare
- **存储**：MySQL


## 功能概览

| 模块 | 说明 |
|------|------|
| 策略回测 | Backtrader 引擎，内置 7 种策略（含 TA-Lib K 线形态扫描），支持参数配置、净值/回撤曲线、交易明细 |
| 采集任务 | Tushare / AkShare 日线、财务、宏观、新闻、研报、日历等数据入库 |
| 数据 API | 行情、财务、宏观、新闻、研报、日历等查询接口（后端保留，前端暂未开放页面） |

前端当前仅展示 **策略回测**、**采集任务** 两个页面。

## 目录结构

```text
meta-quant/
├── backend/
│   ├── app/
│   │   ├── api/routes/      # /quant/* 接口
│   │   ├── backtest/        # Backtrader 回测引擎
│   │   ├── strategies/      # 内置策略注册（双均线/RSI/MACD 等）
│   │   ├── collectors/      # Tushare/AkShare 采集
│   │   ├── services/        # 业务逻辑（含 backtest_service、strategy_service）
│   │   ├── schemas/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   ├── sql/schema.sql       # 含回测相关表
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/views/BacktestView.vue   # 策略回测
    ├── src/views/CrawlView.vue      # 采集任务
    ├── src/api/
    └── package.json
```

## 快速开始

### 1. 初始化数据库

```bash
mysql -u root -p < backend/sql/schema.sql
```

建表包括：`trade_stock_daily`（日线）、`trade_strategy_info`（策略）、`trade_backtest_task` / `trade_backtest_result` / `trade_backtest_trade`（回测）等。

### 2. 配置并启动后端

```bash
cd backend
copy .env.example .env
# 编辑 .env：填写 MySQL 与 TUSHARE_TOKEN
pip install -r requirements.txt
python -m app
```

- API: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

### 3. 启动前端

需先安装 [Node.js LTS](https://nodejs.org/)。

```bash
cd frontend
npm install
npm run dev
```

- 前端: http://127.0.0.1:5173
- 默认进入 **策略回测** 页
- 开发环境已代理 `/quant`、`/health` 到后端

## 内置策略

| 标识 | 名称 | 分类 |
|------|------|------|
| `double_ma` | 双均线策略 | 趋势跟踪 |
| `rsi` | RSI 超买超卖策略 | 超买超卖 |
| `macd` | MACD 策略 | 趋势跟踪 |
| `bollinger` | 布林带策略 | 波动率 |
| `bias` | 乖离率策略 | 均值回归 |
| `momentum` | 动量策略 | 动量因子 |
| `cdl_bullish_scan` | 看涨形态扫描策略 | K线形态 |

K 线形态策略基于 [TA-Lib](https://github.com/TA-Lib/ta-lib-python) 的 `CDL_*` 函数（需 `pip install TA-Lib`）。

策略通过装饰器注册于 `backend/app/strategies/`，启动时自动同步到 `trade_strategy_info` 表。

## 主要接口

### 策略 / 回测

| 路径 | 说明 |
|------|------|
| `POST /quant/strategy/list` | 获取策略列表 |
| `POST /quant/strategy/detail` | 获取策略详情与参数模板 |
| `POST /quant/backtest/run` | 执行回测（同步） |
| `POST /quant/backtest/report` | 查询回测报告 |

### 采集 / 数据

| 路径 | 说明 |
|------|------|
| `POST /quant/crawl/task/list\|trigger\|log\|retry` | 采集任务管理 |
| `POST /quant/stock/daily` | 日线行情查询 |
| `POST /quant/finance/*` | 财务数据 |
| `POST /quant/macro/*` | 宏观数据 |
| `POST /quant/news/*` | 财经新闻 |
| `POST /quant/report/*` | 券商研报 |
| `POST /quant/calendar/*` | 财经日历 |
| `POST /quant/catalyst/*` | 事件催化剂 |

## 使用建议

1. 在 **策略回测** 页填写股票代码（如 `600519.SH`）、回测区间与策略参数，点击「开始回测」。
2. 回测前会自动校验股票是否存在；若库内日线不足，会同步触发 `daily_bar` 采集补齐。
3. 也可在 **采集任务** 页手动触发 `daily_bar`、`macro`、`calendar` 等任务。
4. 交叉类策略：信号在交叉当日收盘确认，下一交易日开盘成交；总收益含已实现盈亏与期末持仓浮动盈亏。
5. 默认采集股票：`600519.SH,000001.SZ,600036.SH`（可在 `.env` 的 `CRAWL_STOCK_LIST` 修改）。

## 环境变量

| 变量 | 说明 |
|------|------|
| `MYSQL_*` / `WUCAI_SQL_*` | MySQL 连接（兼容参考项目命名） |
| `TUSHARE_TOKEN` | Tushare Pro Token（采集与股票校验） |
| `CORS_ORIGINS` | 前端跨域白名单 |
| `CRAWL_STOCK_LIST` | 默认采集股票列表 |
