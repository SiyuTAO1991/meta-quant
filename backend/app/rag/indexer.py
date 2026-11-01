# -*- coding: utf-8 -*-
"""切块、建 FAISS 索引并落盘（参考 CASE process_text_with_splitter）。"""
from __future__ import annotations

import os
import pickle
from typing import Any

from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

from app.config import get_settings
from app.rag.embeddings import BailianEmbeddings
from app.rag.pdf_loader import extract_text_with_page_numbers


def build_page_info(chunks: list[str], char_page_mapping: list[int]) -> dict[str, int]:
    """为每个文本块取众数页码。"""
    page_info: dict[str, int] = {}
    current_pos = 0
    for chunk in chunks:
        chunk_end = current_pos + len(chunk)
        chunk_pages = char_page_mapping[current_pos:chunk_end]
        if chunk_pages:
            counts: dict[int, int] = {}
            for p in chunk_pages:
                counts[p] = counts.get(p, 0) + 1
            page_info[chunk] = max(counts, key=counts.get)
        else:
            page_info[chunk] = 1
        current_pos = chunk_end
    return page_info


def index_pdf_to_faiss(pdf_path: str, vector_dir: str) -> dict[str, Any]:
    """
    抽取 PDF → 切块 → Embedding → 保存 FAISS + page_info.pkl

    Returns:
        {chunk_count, page_count, char_count}
    """
    s = get_settings()
    text, char_page_mapping = extract_text_with_page_numbers(pdf_path)
    if not text.strip():
        raise ValueError("PDF 未能提取到可用文本（可能是扫描件）")

    page_count = max(char_page_mapping) if char_page_mapping else 0
    splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ".", "。", " ", ""],
        chunk_size=s.rag_chunk_size,
        chunk_overlap=s.rag_chunk_overlap,
        length_function=len,
    )
    chunks = splitter.split_text(text)
    if not chunks:
        raise ValueError("文本切块结果为空")

    logger.info(f"rag index: chars={len(text)} pages≈{page_count} chunks={len(chunks)}")
    embeddings = BailianEmbeddings()
    knowledge = FAISS.from_texts(chunks, embeddings)
    page_info = build_page_info(chunks, char_page_mapping)
    knowledge.page_info = page_info

    os.makedirs(vector_dir, exist_ok=True)
    knowledge.save_local(vector_dir)
    with open(os.path.join(vector_dir, "page_info.pkl"), "wb") as f:
        pickle.dump(page_info, f)

    return {
        "chunk_count": len(chunks),
        "page_count": int(page_count),
        "char_count": len(text),
    }


def load_faiss(vector_dir: str) -> FAISS:
    """加载已保存的 FAISS 与页码信息。"""
    if not os.path.isdir(vector_dir):
        raise FileNotFoundError(f"向量目录不存在: {vector_dir}")
    embeddings = BailianEmbeddings()
    knowledge = FAISS.load_local(
        vector_dir,
        embeddings,
        allow_dangerous_deserialization=True,
    )
    page_info_path = os.path.join(vector_dir, "page_info.pkl")
    if os.path.exists(page_info_path):
        with open(page_info_path, "rb") as f:
            knowledge.page_info = pickle.load(f)
    else:
        knowledge.page_info = {}
    return knowledge
