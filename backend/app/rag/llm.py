# -*- coding: utf-8 -*-
"""DeepSeek OpenAI 兼容对话。"""
from __future__ import annotations

from openai import OpenAI

from app.config import get_settings


def get_deepseek_client() -> OpenAI:
    s = get_settings()
    if not s.deepseek_api_key:
        raise ValueError("未配置 DEEPSEEK_API_KEY")
    return OpenAI(
        api_key=s.deepseek_api_key,
        base_url=(s.deepseek_base_url or "https://api.deepseek.com").rstrip("/"),
    )


def chat_answer(prompt: str, *, temperature: float = 0.2, max_tokens: int = 2048) -> str:
    """财报问答：关闭 thinking，降低延迟。"""
    s = get_settings()
    client = get_deepseek_client()
    resp = client.chat.completions.create(
        model=s.deepseek_model or "deepseek-flash",
        messages=[
            {
                "role": "system",
                "content": (
                    "你是专业的上市公司财报分析助手。"
                    "只能根据用户提供的上下文回答；上下文没有的信息请明确说「财报中未找到」。"
                    "涉及金额、比率时尽量保留原文单位与报告期。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        extra_body={"thinking": {"type": "disabled"}},
    )
    return (resp.choices[0].message.content or "").strip()
