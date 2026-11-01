# -*- coding: utf-8 -*-
"""PDF 文本提取与页码映射（参考 CASE-ChatPDF-Faiss）。"""
from __future__ import annotations

from typing import List, Tuple

from PyPDF2 import PdfReader


def extract_text_with_page_numbers(pdf_path: str) -> Tuple[str, List[int]]:
    """
    从 PDF 提取全文，并记录每个字符对应的页码（1-based）。

    Returns:
        text, char_page_mapping
    """
    reader = PdfReader(pdf_path)
    text = ""
    char_page_mapping: List[int] = []

    for page_number, page in enumerate(reader.pages, start=1):
        extracted = page.extract_text() or ""
        if not extracted:
            continue
        text += extracted
        char_page_mapping.extend([page_number] * len(extracted))

    return text, char_page_mapping
