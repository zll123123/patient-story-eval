"""OpenAI-compatible LLM 客户端。"""

from __future__ import annotations

import json
from typing import Any, Dict

import requests

from story_med.config.llm_app_config import StoryMedLlmConfig


def call_llm_json(config: StoryMedLlmConfig, prompt: str) -> Dict[str, Any]:
    """调用 LLM 并解析 JSON 响应。"""
    content = call_llm_text(config, prompt)
    return normalize_llm_json(content)


def call_llm_text(config: StoryMedLlmConfig, prompt: str) -> str:
    """调用 LLM 并返回文本内容。"""
    if not config.enabled:
        raise RuntimeError("LLM 未启用，请设置 STORY_MED_LLM_ENABLED=true")
    if not config.api_key:
        raise RuntimeError("缺少 LLM API Key，请设置 STORY_MED_LLM_API_KEY 或 CSL_LLM_API_KEY")
    payload = {
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }
    response = requests.post(
        _build_request_url(config.base_url),
        json=payload,
        headers=_build_headers(config),
        timeout=config.timeout_seconds,
    )
    response.raise_for_status()
    body = response.json()
    content = (((body.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    if not content:
        raise RuntimeError("LLM 返回内容为空")
    return content


def normalize_llm_json(content: str) -> Dict[str, Any]:
    """从 LLM 文本中提取 JSON 对象。"""
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"LLM 未返回 JSON 对象: {content[:200]}")
    return json.loads(text[start : end + 1])


def _build_request_url(base_url: str) -> str:
    """构建 chat completions 请求地址。"""
    if base_url.endswith("/chat/completions"):
        return base_url
    return f"{base_url}/chat/completions"


def _build_headers(config: StoryMedLlmConfig) -> Dict[str, str]:
    """构建 LLM 请求头。"""
    return {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
