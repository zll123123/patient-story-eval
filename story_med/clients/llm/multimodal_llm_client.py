"""多模态 LLM 客户端。"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import Any, Dict, List

import requests
from PIL import Image

from story_med.clients.llm.llm_client import normalize_llm_json
from story_med.config.app_config import StoryMedVisionConfig


def call_multimodal_json(
    config: StoryMedVisionConfig,
    prompt: str,
    image_paths: List[Path],
    use_thumbnail: bool = True,
) -> Dict[str, Any]:
    """调用多模态模型并解析 JSON。"""
    content = call_multimodal_text(config, prompt, image_paths, use_thumbnail=use_thumbnail)
    return normalize_llm_json(content)


def call_multimodal_text(
    config: StoryMedVisionConfig,
    prompt: str,
    image_paths: List[Path],
    use_thumbnail: bool = True,
) -> str:
    """调用多模态模型并返回文本。"""
    _validate_config(config)
    image_urls = [
        encode_image_to_data_url(
            path,
            config.max_image_side,
            config.jpeg_quality,
            use_thumbnail=use_thumbnail,
        )
        for path in image_paths
    ]
    if config.provider == "nhtai":
        return _call_nhtai(config, prompt, image_urls)
    return _call_openai_compatible(config, prompt, image_urls)


def encode_image_to_data_url(
    image_path: Path,
    max_side: int,
    jpeg_quality: int,
    use_thumbnail: bool = True,
) -> str:
    """将本地图片压缩并编码为 data URL。"""
    with Image.open(image_path) as image:
        image = image.convert("RGB")
        if use_thumbnail:
            image.thumbnail((max_side, max_side))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=jpeg_quality, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _validate_config(config: StoryMedVisionConfig) -> None:
    """校验多模态配置。"""
    if not config.enabled:
        raise RuntimeError("多模态模型未启用，请设置 STORY_MED_VISION_ENABLED=true")
    if not config.base_url:
        raise RuntimeError("缺少多模态模型 base_url，请设置 STORY_MED_VISION_BASE_URL")
    if not config.model:
        raise RuntimeError("缺少多模态模型名称，请设置 STORY_MED_VISION_MODEL")
    if config.provider != "nhtai" and not config.api_key:
        raise RuntimeError("缺少多模态模型 API Key，请设置 STORY_MED_VISION_API_KEY")


def _call_openai_compatible(config: StoryMedVisionConfig, prompt: str, image_urls: List[str]) -> str:
    """调用 OpenAI-compatible 视觉模型。"""
    content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
    content.extend({"type": "image_url", "image_url": {"url": image_url}} for image_url in image_urls)
    payload = {
        "model": config.model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    response = requests.post(
        _chat_completions_url(config.base_url),
        json=payload,
        headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
        timeout=config.timeout_seconds,
    )
    _raise_for_status(response)
    return _extract_openai_content(response.json())


def _call_nhtai(config: StoryMedVisionConfig, prompt: str, image_urls: List[str]) -> str:
    """调用 NHTAI 多模态网关。"""
    image_content = [{"type": "image_url", "image_url": image_url} for image_url in image_urls]
    payload = {
        "service": config.nhtai_service_name,
        "payload": {
            "model_name": config.model,
            "model_version": config.nhtai_model_version,
            "request_params": {
                "json": {
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": image_content},
                    ],
                    "stream": False,
                    "response_format": {"type": "json_object"},
                },
                "timeout": config.timeout_seconds,
            },
            "return_cost": True,
        },
    }
    headers = {"Content-Type": "application/json"}
    if config.nhtai_host_header:
        headers["Host"] = config.nhtai_host_header
    response = requests.post(
        f"{config.base_url}/{config.nhtai_service_name}",
        json=payload,
        headers=headers,
        timeout=config.timeout_seconds,
    )
    _raise_for_status(response)
    return _extract_nhtai_content(response.json())


def _chat_completions_url(base_url: str) -> str:
    """构建 chat completions 请求地址。"""
    if base_url.endswith("/chat/completions"):
        return base_url
    return f"{base_url}/chat/completions"


def _extract_openai_content(response_json: Dict[str, Any]) -> str:
    """提取 OpenAI-compatible 响应文本。"""
    content = (((response_json.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    if not content:
        raise ValueError(f"视觉模型返回为空: {json.dumps(response_json, ensure_ascii=False)[:300]}")
    return content


def _raise_for_status(response: requests.Response) -> None:
    """抛出包含响应体摘要的 HTTP 异常，便于定位模型网关问题。"""
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        body = response.text[:800]
        raise requests.HTTPError(f"{exc}; response_body={body}") from exc


def _extract_nhtai_content(response_json: Dict[str, Any]) -> str:
    """提取 NHTAI 响应文本。"""
    choices = response_json.get("data", {}).get("choices", [])
    content = (((choices or [{}])[0].get("message") or {}).get("content") or "").strip()
    if not content:
        raise ValueError(f"NHTAI 视觉模型返回为空: {json.dumps(response_json, ensure_ascii=False)[:300]}")
    return content
