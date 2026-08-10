# -*- coding: utf-8 -*-
"""MySQL 连接与查询辅助。"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterable, Optional

import pymysql
from pymysql.cursors import DictCursor

from app.config import get_settings


def get_connection():
    s = get_settings()
    return pymysql.connect(
        host=s.db_host,
        user=s.db_user,
        password=s.db_password,
        database=s.db_name,
        port=s.db_port,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )


@contextmanager
def db_cursor():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            yield cursor
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute_query(sql: str, params: Optional[Iterable[Any]] = None) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            return list(cursor.fetchall())
    finally:
        conn.close()


def execute_update(sql: str, params: Optional[Iterable[Any]] = None) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            conn.commit()
            return cursor.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute_many(sql: str, data_list: list[tuple]) -> int:
    if not data_list:
        return 0
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.executemany(sql, data_list)
            conn.commit()
            return cursor.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ping_db() -> bool:
    try:
        rows = execute_query("SELECT 1 AS ok")
        return bool(rows and rows[0].get("ok") == 1)
    except Exception:
        return False
