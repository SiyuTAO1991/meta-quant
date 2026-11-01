# -*- coding: utf-8 -*-
"""财报 RAG 业务：上传、自动建索、单文档问答。"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from app.config import BASE_DIR, get_settings
from app.database import execute_insert, execute_query, execute_update
from app.rag.indexer import index_pdf_to_faiss, load_faiss
from app.rag.llm import chat_answer
from app.schemas.common import serialize_row


def _rag_root() -> Path:
    s = get_settings()
    root = Path(s.rag_data_dir)
    if not root.is_absolute():
        root = BASE_DIR / root
    root.mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir(exist_ok=True)
    (root / "vectors").mkdir(exist_ok=True)
    return root


def _ensure_table() -> None:
    execute_update(
        """
        CREATE TABLE IF NOT EXISTS trade_rag_document (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            stock_code VARCHAR(20) NOT NULL,
            stock_name VARCHAR(100) DEFAULT '',
            report_type VARCHAR(20) DEFAULT 'annual' COMMENT 'annual/semi/quarter/other',
            report_period VARCHAR(20) DEFAULT '' COMMENT '如 2025',
            title VARCHAR(255) DEFAULT '',
            file_name VARCHAR(255) NOT NULL,
            file_path VARCHAR(500) NOT NULL,
            file_hash VARCHAR(64) DEFAULT '',
            file_size BIGINT DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'uploaded'
                COMMENT 'uploaded/indexing/ready/failed',
            chunk_count INT DEFAULT 0,
            page_count INT DEFAULT 0,
            vector_dir VARCHAR(500) DEFAULT '',
            error_msg VARCHAR(1000) DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            KEY idx_rag_doc_code (stock_code),
            KEY idx_rag_doc_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='财报RAG文档'
        """
    )


def get_rag_meta() -> dict[str, Any]:
    s = get_settings()
    return {
        "llm_model": s.deepseek_model,
        "embed_model": s.rag_embed_model,
        "chunk_size": s.rag_chunk_size,
        "chunk_overlap": s.rag_chunk_overlap,
        "top_k": s.rag_top_k,
        "report_types": [
            {"value": "annual", "label": "年报"},
            {"value": "semi", "label": "半年报"},
            {"value": "quarter", "label": "季报"},
            {"value": "other", "label": "其他"},
        ],
    }


def _safe_filename(name: str) -> str:
    base = os.path.basename(name or "report.pdf")
    base = re.sub(r"[^\w.\u4e00-\u9fff\-]+", "_", base)
    if not base.lower().endswith(".pdf"):
        base += ".pdf"
    return base[:180]


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def list_documents(stock_code: str = "", page: int = 1, size: int = 20) -> dict[str, Any]:
    _ensure_table()
    where = "1=1"
    params: list[Any] = []
    code = (stock_code or "").strip().upper()
    if code:
        where += " AND stock_code=%s"
        params.append(code)
    total_rows = execute_query(
        f"SELECT COUNT(*) AS cnt FROM trade_rag_document WHERE {where}",
        tuple(params),
    )
    total = int(total_rows[0]["cnt"]) if total_rows else 0
    page = max(1, page)
    size = max(1, min(size, 100))
    offset = (page - 1) * size
    rows = execute_query(
        f"""
        SELECT id, stock_code, stock_name, report_type, report_period, title,
               file_name, file_size, status, chunk_count, page_count,
               error_msg, created_at, updated_at
        FROM trade_rag_document
        WHERE {where}
        ORDER BY id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [size, offset]),
    )
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [serialize_row(r) for r in rows],
    }


def get_document(doc_id: int) -> dict[str, Any]:
    _ensure_table()
    rows = execute_query(
        """
        SELECT id, stock_code, stock_name, report_type, report_period, title,
               file_name, file_path, file_size, file_hash, status, chunk_count,
               page_count, vector_dir, error_msg, created_at, updated_at
        FROM trade_rag_document WHERE id=%s LIMIT 1
        """,
        (doc_id,),
    )
    if not rows:
        raise ValueError(f"文档不存在: {doc_id}")
    return serialize_row(rows[0])


def _set_status(doc_id: int, status: str, **extra) -> None:
    fields = ["status=%s", "updated_at=%s"]
    params: list[Any] = [status, datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    for key in ("chunk_count", "page_count", "vector_dir", "error_msg"):
        if key in extra:
            fields.append(f"{key}=%s")
            params.append(extra[key])
    params.append(doc_id)
    execute_update(
        f"UPDATE trade_rag_document SET {', '.join(fields)} WHERE id=%s",
        tuple(params),
    )


def _index_document_job(doc_id: int) -> None:
    try:
        doc = get_document(doc_id)
        _set_status(doc_id, "indexing", error_msg=None)
        root = _rag_root()
        vector_dir = root / "vectors" / str(doc_id)
        if vector_dir.exists():
            shutil.rmtree(vector_dir, ignore_errors=True)
        result = index_pdf_to_faiss(doc["file_path"], str(vector_dir))
        _set_status(
            doc_id,
            "ready",
            chunk_count=result["chunk_count"],
            page_count=result["page_count"],
            vector_dir=str(vector_dir),
            error_msg=None,
        )
        logger.info(
            f"rag index ready doc_id={doc_id} chunks={result['chunk_count']} pages={result['page_count']}"
        )
    except Exception as e:
        logger.exception(f"rag index failed doc_id={doc_id}")
        _set_status(doc_id, "failed", error_msg=str(e)[:900])


def upload_and_index(
    *,
    file_bytes: bytes,
    file_name: str,
    stock_code: str,
    stock_name: str = "",
    report_type: str = "annual",
    report_period: str = "",
    title: str = "",
) -> dict[str, Any]:
    _ensure_table()
    code = (stock_code or "").strip().upper()
    if not code:
        raise ValueError("请填写股票代码")
    if not file_bytes:
        raise ValueError("空文件")
    if not (file_name or "").lower().endswith(".pdf"):
        raise ValueError("仅支持 PDF 文件")

    root = _rag_root()
    safe_name = _safe_filename(file_name)
    # 先占位插入拿 id，再落盘
    doc_id = execute_insert(
        """
        INSERT INTO trade_rag_document
            (stock_code, stock_name, report_type, report_period, title,
             file_name, file_path, file_hash, file_size, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'uploaded')
        """,
        (
            code,
            (stock_name or "").strip(),
            report_type or "annual",
            (report_period or "").strip(),
            (title or "").strip() or safe_name,
            safe_name,
            "",
            "",
            len(file_bytes),
        ),
    )
    if not doc_id:
        raise ValueError("写入文档记录失败")

    dest = root / "docs" / f"{doc_id}_{safe_name}"
    dest.write_bytes(file_bytes)
    digest = _file_hash(dest)
    execute_update(
        """
        UPDATE trade_rag_document
        SET file_path=%s, file_hash=%s, updated_at=%s
        WHERE id=%s
        """,
        (
            str(dest),
            digest,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            doc_id,
        ),
    )

    # 后台自动建索，接口立即返回
    thread = threading.Thread(target=_index_document_job, args=(doc_id,), daemon=True)
    thread.start()

    return get_document(doc_id)


def delete_document(doc_id: int) -> dict[str, Any]:
    doc = get_document(doc_id)
    execute_update("DELETE FROM trade_rag_document WHERE id=%s", (doc_id,))
    try:
        if doc.get("file_path") and os.path.isfile(doc["file_path"]):
            os.remove(doc["file_path"])
    except OSError:
        pass
    try:
        vdir = doc.get("vector_dir")
        if vdir and os.path.isdir(vdir):
            shutil.rmtree(vdir, ignore_errors=True)
    except OSError:
        pass
    return {"ok": True, "id": doc_id}


def ask_document(doc_id: int, question: str, top_k: int | None = None) -> dict[str, Any]:
    s = get_settings()
    q = (question or "").strip()
    if not q:
        raise ValueError("请输入问题")
    doc = get_document(doc_id)
    if doc.get("status") != "ready":
        raise ValueError(f"文档尚未就绪，当前状态: {doc.get('status')}")
    vector_dir = doc.get("vector_dir")
    if not vector_dir or not os.path.isdir(vector_dir):
        raise ValueError("向量索引不存在，请重新上传建索")

    k = int(top_k or s.rag_top_k or 10)
    k = max(1, min(k, 20))
    knowledge = load_faiss(vector_dir)
    docs = knowledge.similarity_search(q, k=k)
    if not docs:
        return {
            "answer": "未能从该财报中检索到相关内容。",
            "sources": [],
            "doc": {
                "id": doc["id"],
                "stock_code": doc["stock_code"],
                "title": doc["title"],
            },
        }

    context = "\n\n".join(d.page_content for d in docs)
    prompt = (
        f"根据以下财报上下文回答问题。若上下文没有答案，请明确说明。\n\n"
        f"【上下文】\n{context}\n\n"
        f"【问题】\n{q}"
    )
    answer = chat_answer(prompt)

    page_info = getattr(knowledge, "page_info", {}) or {}
    sources = []
    seen_pages = set()
    for d in docs:
        text = (d.page_content or "").strip()
        page = page_info.get(text) or page_info.get(d.page_content) or "未知"
        snippet = text[:180] + ("..." if len(text) > 180 else "")
        item = {"page": page, "snippet": snippet}
        # 同页去重展示，但仍保留不同片段
        key = (page, snippet[:40])
        if key in seen_pages:
            continue
        seen_pages.add(key)
        sources.append(item)

    return {
        "answer": answer,
        "sources": sources,
        "top_k": k,
        "doc": {
            "id": doc["id"],
            "stock_code": doc["stock_code"],
            "stock_name": doc.get("stock_name"),
            "title": doc["title"],
            "report_period": doc.get("report_period"),
        },
    }
