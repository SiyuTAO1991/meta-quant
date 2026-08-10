# -*- coding: utf-8 -*-
"""应用配置，从 .env 读取。"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Meta Quant API"
    app_version: str = "0.1.0"
    debug: bool = True
    api_prefix: str = "/quant"

    # MySQL（兼容参考项目 WUCAI_SQL_* 命名）
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "quantdb"

    # 兼容旧环境变量名
    wucai_sql_host: str | None = None
    wucai_sql_port: int | None = None
    wucai_sql_username: str | None = None
    wucai_sql_password: str | None = None
    wucai_sql_db: str | None = None

    tushare_token: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    crawl_test_mode: bool = True
    crawl_stock_list: str = "600519.SH,000001.SZ,600036.SH"

    @property
    def db_host(self) -> str:
        return self.wucai_sql_host or self.mysql_host

    @property
    def db_port(self) -> int:
        return self.wucai_sql_port or self.mysql_port

    @property
    def db_user(self) -> str:
        return self.wucai_sql_username or self.mysql_user

    @property
    def db_password(self) -> str:
        return self.wucai_sql_password if self.wucai_sql_password is not None else self.mysql_password

    @property
    def db_name(self) -> str:
        return self.wucai_sql_db or self.mysql_database

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def default_stocks(self) -> list[str]:
        return [s.strip() for s in self.crawl_stock_list.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
