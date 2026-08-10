# Meta Quant · 量化交易数据平台

前后端分离的量化数据应用，按《量化交易系统方案设计》实现：

- **前端**：Vue3 + Vite + Element Plus + ECharts
- **后端**：FastAPI + Pandas + Tushare / AkShare
- **存储**：MySQL（方案阶段仅 MySQL）

采集逻辑参考 `quant_trading_test/CASE-数据采集`。

## 目录结构

```text
meta-quant/
├── backend/                 # Python FastAPI
│   ├── app/
│   │   ├── api/routes/      # /quant/* 接口
│   │   ├── collectors/      # Tushare/AkShare 采集
│   │   ├── services/        # 业务查询
│   │   ├── schemas/         # 入参出参
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   ├── sql/schema.sql
│   ├── requirements.txt
│   └── .env.example
└── frontend/                # Vue3 前端
    ├── src/views/           # 行情/财务/宏观/新闻/研报/日历/催化剂/采集
    ├── src/api/
    └── package.json
```

## 快速开始

### 1. 初始化数据库

```bash
mysql -u root -p < backend/sql/schema.sql
```

### 2. 配置后端

```bash
cd backend
copy .env.example .env
# 编辑 .env：填写 MySQL 与 TUSHARE_TOKEN
pip install -r requirements.txt
python -m app
```

服务地址：

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

前端地址：http://127.0.0.1:5173  
开发环境已代理 `/quant` 到后端。

## 主要接口（与方案文档对齐）

| 模块 | 路径 |
|------|------|
| 日线行情 | `POST /quant/stock/daily` |
| 指数日线 | `POST /quant/stock/index/daily` |
| 概念板块 | `POST /quant/stock/concept` |
| 财务指标 | `POST /quant/finance/indicator` |
| 利润表/资产负债/现金流 | `POST /quant/finance/income|balance|cashflow` |
| 财务对比 | `POST /quant/finance/compare` |
| 宏观目录/趋势 | `POST /quant/macro/list|trend` |
| 新闻 | `POST /quant/news/stock|hot|detail` |
| 研报 | `POST /quant/report/list|detail` |
| 财经日历 | `POST /quant/calendar/list|today` |
| 催化剂 | `POST /quant/catalyst/event|event_today` |
| 采集任务 | `POST /quant/crawl/task/list|trigger|log|retry` |

## 使用建议

1. 先在「采集任务」页面触发 `daily_bar` / `macro` / `calendar` 等任务写入 MySQL。
2. 再在行情、财务、宏观等页面查询展示。
3. 测试模式默认股票：`600519.SH,000001.SZ,600036.SH`（可在 `.env` 的 `CRAWL_STOCK_LIST` 修改）。

## 环境变量说明

| 变量 | 说明 |
|------|------|
| `MYSQL_*` / `WUCAI_SQL_*` | MySQL 连接（兼容参考项目命名） |
| `TUSHARE_TOKEN` | Tushare Pro Token |
| `CORS_ORIGINS` | 前端跨域白名单 |
| `CRAWL_STOCK_LIST` | 默认采集股票列表 |
