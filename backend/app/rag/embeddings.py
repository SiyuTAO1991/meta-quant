# -*- coding: utf-8 -*-
"""阿里云百炼 OpenAI 兼容 Embedding。"""
from __future__ import annotations

from typing import List

from langchain_core.embeddings import Embeddings
from openai import OpenAI

from app.config import get_settings


class BailianEmbeddings(Embeddings):
    """通过百炼 compatible-mode /embeddings 生成向量。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        s = get_settings()
        key = api_key or s.dashscope_api_key
        url = (base_url or s.dashscope_base_url or "").rstrip("/")
        if not key:
            raise ValueError("未配置 DASHSCOPE_API_KEY")
        if not url:
            raise ValueError("未配置 DASHSCOPE_BASE_URL")
        self.model = model or s.rag_embed_model or "text-embedding-v4"
        self.client = OpenAI(api_key=key, base_url=url)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        # 百炼 v4 单次最多约 10 条，分批调用
        batch_size = 10
        vectors: List[List[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            resp = self.client.embeddings.create(model=self.model, input=batch)
            ordered = sorted(resp.data, key=lambda x: x.index)
            vectors.extend([list(item.embedding) for item in ordered])
        return vectors

    def embed_query(self, text: str) -> List[float]:
        resp = self.client.embeddings.create(model=self.model, input=text)
        return list(resp.data[0].embedding)
