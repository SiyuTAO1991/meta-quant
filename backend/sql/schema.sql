CREATE DATABASE IF NOT EXISTS quantdb DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE quantdb;

CREATE TABLE IF NOT EXISTS trade_stock_daily (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    trade_date DATE NOT NULL COMMENT '交易日期',
    open_price DECIMAL(10,2) COMMENT '开盘价',
    high_price DECIMAL(10,2) COMMENT '最高价',
    low_price DECIMAL(10,2) COMMENT '最低价',
    close_price DECIMAL(10,2) COMMENT '收盘价(前复权)',
    volume BIGINT COMMENT '成交量(股)',
    amount DECIMAL(20,2) COMMENT '成交额(元)',
    turnover_rate DECIMAL(10,4) COMMENT '换手率',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_stock_daily_code_date (stock_code, trade_date),
    KEY idx_stock_daily_code (stock_code),
    KEY idx_stock_daily_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='日K线数据';

CREATE TABLE IF NOT EXISTS trade_stock_news (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(20) COMMENT '股票代码',
    sector_code VARCHAR(20) COMMENT '板块代码',
    news_type VARCHAR(20) NOT NULL COMMENT 'announcement/news/report',
    title VARCHAR(500) NOT NULL,
    content TEXT,
    summary TEXT,
    source VARCHAR(50) COMMENT 'eastmoney/cailianshe/kimi',
    source_url VARCHAR(500),
    published_at DATETIME,
    sentiment VARCHAR(20) COMMENT 'positive/negative/neutral',
    sentiment_score DECIMAL(5,2) COMMENT '-1到1',
    is_important TINYINT DEFAULT 0,
    is_read TINYINT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_stock_news_code (stock_code),
    KEY idx_stock_news_published (published_at),
    KEY idx_stock_news_type (news_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='新闻事件';

CREATE TABLE IF NOT EXISTS trade_stock_financial (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(20) NOT NULL,
    report_date DATE NOT NULL COMMENT '报告期，如 2024-12-31',
    revenue DECIMAL(20,2) COMMENT '营业收入(元)',
    net_profit DECIMAL(20,2) COMMENT '净利润(元)',
    eps DECIMAL(10,4) COMMENT '每股收益',
    roe DECIMAL(10,4) COMMENT 'ROE(%)',
    roa DECIMAL(10,4) COMMENT 'ROA(%)',
    gross_margin DECIMAL(10,4) COMMENT '毛利率(%)',
    net_margin DECIMAL(10,4) COMMENT '净利率(%)',
    debt_ratio DECIMAL(10,4) COMMENT '资产负债率(%)',
    current_ratio DECIMAL(10,4) COMMENT '流动比率',
    operating_cashflow DECIMAL(20,2) COMMENT '经营现金流(元)',
    total_assets DECIMAL(20,2) COMMENT '总资产(元)',
    total_equity DECIMAL(20,2) COMMENT '净资产(元)',
    data_source VARCHAR(20) DEFAULT 'akshare',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_fina_code_date (stock_code, report_date),
    KEY idx_fina_code (stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='季度财务数据';

CREATE TABLE IF NOT EXISTS trade_macro_indicator (
    id INT AUTO_INCREMENT PRIMARY KEY,
    indicator_date DATE NOT NULL COMMENT '指标月份(月末日期)',
    cpi_yoy DECIMAL(10,2) COMMENT 'CPI同比(%)',
    ppi_yoy DECIMAL(10,2) COMMENT 'PPI同比(%)',
    pmi DECIMAL(10,2) COMMENT 'PMI',
    m2_yoy DECIMAL(10,2) COMMENT 'M2同比增速(%)',
    shrzgm DECIMAL(14,0) COMMENT '社融规模增量(亿元)',
    lpr_1y DECIMAL(6,2) COMMENT 'LPR 1年期(%)',
    lpr_5y DECIMAL(6,2) COMMENT 'LPR 5年期(%)',
    data_source VARCHAR(20) DEFAULT 'akshare',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_macro_date (indicator_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='月度宏观指标';

CREATE TABLE IF NOT EXISTS trade_rate_daily (
    id INT AUTO_INCREMENT PRIMARY KEY,
    rate_date DATE NOT NULL COMMENT '日期',
    cn_bond_10y DECIMAL(8,4) COMMENT '中国10年期国债收益率(%)',
    us_bond_10y DECIMAL(8,4) COMMENT '美国10年期国债收益率(%)',
    data_source VARCHAR(20) DEFAULT 'akshare',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_rate_date (rate_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='日频利率指标';

CREATE TABLE IF NOT EXISTS trade_report_consensus (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(20) NOT NULL,
    broker VARCHAR(50) COMMENT '券商',
    report_date DATE,
    rating VARCHAR(20) COMMENT '买入/增持/中性/减持',
    target_price DECIMAL(10,2),
    eps_forecast_current DECIMAL(10,4) COMMENT '当年EPS预测',
    eps_forecast_next DECIMAL(10,4) COMMENT '次年EPS预测',
    revenue_forecast DECIMAL(20,2) COMMENT '营收预测(亿)',
    source_file VARCHAR(500) COMMENT 'PDF文件路径',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_consensus_unique (stock_code, broker, report_date),
    KEY idx_consensus_code (stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='研报一致性预期';

CREATE TABLE IF NOT EXISTS trade_calendar_event (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_date DATE NOT NULL COMMENT '事件日期',
    event_time VARCHAR(10) COMMENT '事件时间(HH:MM)',
    country VARCHAR(10) NOT NULL DEFAULT 'CN' COMMENT 'CN/US/EU/JP',
    category VARCHAR(30) NOT NULL COMMENT 'rate/inflation/employment/gdp/pmi/trade/policy/other',
    title VARCHAR(200) NOT NULL,
    importance TINYINT DEFAULT 0 COMMENT '0=未知 1=低 2=中 3=高',
    previous_value VARCHAR(50) COMMENT '前值',
    forecast_value VARCHAR(50) COMMENT '预测值',
    actual_value VARCHAR(50) COMMENT '实际值',
    impact VARCHAR(200) COMMENT '市场影响说明',
    ai_prompt TEXT COMMENT 'AI提问prompt',
    source VARCHAR(50) COMMENT 'eastmoney/fred/manual',
    source_url VARCHAR(500),
    is_recurring TINYINT DEFAULT 0,
    recurrence_rule VARCHAR(100) COMMENT '周期规则',
    status VARCHAR(20) DEFAULT 'upcoming' COMMENT 'upcoming/released/cancelled',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY idx_calendar_date_title (event_date, title),
    KEY idx_calendar_date (event_date),
    KEY idx_calendar_country (country),
    KEY idx_calendar_category (category),
    KEY idx_calendar_importance (importance)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='财经日历事件';

CREATE TABLE IF NOT EXISTS trade_crawl_task_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id VARCHAR(50) NOT NULL,
    task_name VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'running' COMMENT 'running/success/failed',
    message TEXT,
    rows_affected INT DEFAULT 0,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME NULL,
    KEY idx_crawl_task_id (task_id),
    KEY idx_crawl_started (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采集任务执行日志';

CREATE TABLE IF NOT EXISTS trade_strategy_info (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    strategy_name VARCHAR(100) NOT NULL COMMENT '策略展示名称',
    strategy_category VARCHAR(50) NOT NULL COMMENT '策略分类',
    strategy_code VARCHAR(64) NOT NULL COMMENT '全局唯一标识，对应内存注册表 Key',
    description TEXT COMMENT '策略业务描述',
    status TINYINT(1) NOT NULL DEFAULT 1 COMMENT '1-启用 0-禁用',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_strategy_code (strategy_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='策略信息表';

CREATE TABLE IF NOT EXISTS trade_backtest_task (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '回测ID，接口 backtest_id',
    task_id VARCHAR(64) NOT NULL COMMENT '任务UUID',
    ts_code VARCHAR(500) NOT NULL COMMENT '股票代码，多个逗号分隔',
    strategy_id BIGINT NOT NULL COMMENT '关联策略模板 id',
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_capital DECIMAL(20,2) NOT NULL DEFAULT 100000.00,
    commission DECIMAL(10,6) NOT NULL DEFAULT 0.000300,
    enable_stamp_tax TINYINT(1) NOT NULL DEFAULT 1,
    strategy_params JSON COMMENT '策略参数',
    status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending/running/success/failed',
    error_msg TEXT,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finish_time DATETIME NULL,
    UNIQUE KEY uk_backtest_task_id (task_id),
    KEY idx_backtest_strategy (strategy_id),
    KEY idx_backtest_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='回测任务表';

CREATE TABLE IF NOT EXISTS trade_backtest_result (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL COMMENT '关联回测任务 task_id',
    total_return DECIMAL(16,6) COMMENT '总收益率',
    annual_return DECIMAL(16,6) COMMENT '年化收益率',
    max_drawdown DECIMAL(16,6) COMMENT '最大回撤',
    calmar_ratio DECIMAL(16,6) COMMENT '卡玛比率',
    sharpe_ratio DECIMAL(16,6) COMMENT '夏普比率',
    win_rate DECIMAL(16,6) COMMENT '胜率',
    profit_loss_ratio DECIMAL(16,6) COMMENT '盈亏比',
    trade_count INT DEFAULT 0 COMMENT '总交易次数',
    final_value DECIMAL(20,2) COMMENT '期末资产',
    report_data JSON COMMENT '净值/回撤曲线等完整报告数据',
    UNIQUE KEY uk_backtest_result_task (task_id),
    KEY idx_backtest_result_task (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='回测结果表';

CREATE TABLE IF NOT EXISTS trade_backtest_trade (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL COMMENT '任务 id',
    stock_code VARCHAR(20) COMMENT '股票代码',
    trade_date DATE NOT NULL COMMENT '成交日期',
    direction VARCHAR(10) NOT NULL COMMENT 'buy/sell',
    price DECIMAL(16,4) NOT NULL COMMENT '成交价',
    volume INT NOT NULL COMMENT '股数',
    pnl DECIMAL(20,4) COMMENT '本次盈亏',
    KEY idx_backtest_trade_task (task_id),
    KEY idx_backtest_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='回测交易明细表';

CREATE TABLE IF NOT EXISTS trade_factor_eval_job (
    id INT AUTO_INCREMENT PRIMARY KEY,
    universe VARCHAR(20) NOT NULL COMMENT 'all/custom',
    stock_codes TEXT COMMENT '部分A股代码，逗号分隔',
    stock_count INT DEFAULT 0 COMMENT '实际参评股票数',
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    holding_days INT NOT NULL DEFAULT 20,
    category VARCHAR(50) DEFAULT '全部',
    sort_by VARCHAR(50) DEFAULT 'abs_ir',
    keyword VARCHAR(100) DEFAULT '',
    factor_count INT DEFAULT 0,
    data_end DATE NULL COMMENT '当时日线数据截止日',
    crawl_triggered TINYINT DEFAULT 0,
    crawl_message VARCHAR(500) DEFAULT '',
    status VARCHAR(20) NOT NULL DEFAULT 'success',
    message VARCHAR(1000) DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_factor_eval_job_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='因子评价任务(条件)';

CREATE TABLE IF NOT EXISTS trade_factor_eval_result (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_id INT NOT NULL,
    factor_code VARCHAR(50) NOT NULL,
    factor_name VARCHAR(100) NOT NULL,
    category VARCHAR(50) DEFAULT '',
    ic_mean DECIMAL(16,8) NULL,
    ir DECIMAL(16,8) NULL,
    ic_win_rate DECIMAL(10,6) NULL,
    q1_excess DECIMAL(16,8) NULL,
    q5_excess DECIMAL(16,8) NULL,
    q5_q1 DECIMAL(16,8) NULL,
    q5_turnover DECIMAL(10,6) NULL,
    monotonicity DECIMAL(10,6) NULL,
    sample_stocks INT DEFAULT 0,
    sample_periods INT DEFAULT 0,
    ok TINYINT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_factor_eval_result_job (job_id),
    KEY idx_factor_eval_result_code (factor_code),
    KEY idx_factor_eval_result_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='因子评价结果';
