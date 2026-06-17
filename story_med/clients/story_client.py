"""患者故事接口客户端。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import requests
from loguru import logger
from requests import Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from story_med.config.app_config import StoryMedConfig

DEFAULT_HEADERS = {"Content-Type": "application/json"}


@dataclass
class StoryApiResponse:
    """接口返回结果。"""

    status_code: int
    body: Dict[str, Any]
    data: Dict[str, Any]


def create_session() -> Session:
    """创建带重试能力的请求会话。"""
    retry_kwargs = {
        "total": 2,
        "read": 0,
        "connect": 2,
        "backoff_factor": 1,
        "status_forcelist": [429, 500, 502, 503, 504],
    }
    try:
        retry = Retry(allowed_methods=["POST"], **retry_kwargs)
    except TypeError:
        retry = Retry(method_whitelist=["POST"], **retry_kwargs)
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def build_headers(config: StoryMedConfig) -> Dict[str, str]:
    """构建统一请求头。"""
    headers = dict(DEFAULT_HEADERS)
    headers["Accept"] = config.accept
    headers["Connection"] = "keep-alive"
    headers["User-Agent"] = config.user_agent
    if config.origin:
        headers["Origin"] = config.origin
    if config.referer:
        headers["Referer"] = config.referer
    return headers


def _extract_body(response: Response, url: str) -> Dict[str, Any]:
    """解析响应体。"""
    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError(f"接口返回非 JSON 对象: {url}")
    return body


def post_json(
    session: Session,
    config: StoryMedConfig,
    path: str,
    payload: Dict[str, Any],
) -> StoryApiResponse:
    """发送 POST JSON 请求。"""
    url = f"{config.base_url}{path}"
    logger.debug("POST {}", url)
    response: Response = session.post(
        url,
        json=payload,
        headers=build_headers(config),
        timeout=config.timeout_seconds,
        verify=config.verify_ssl,
    )
    body = _extract_body(response, url)
    if response.status_code >= 400:
        raise RuntimeError(f"{response.status_code} {url}: {body}")
    data = body.get("data")
    if not isinstance(data, dict):
        data = body
    return StoryApiResponse(status_code=response.status_code, body=body, data=data)


def extract_session_id(body: Dict[str, Any]) -> str:
    """从会话创建响应中提取 session_id。"""
    candidates = [
        body.get("session_id"),
        body.get("id"),
    ]
    data = body.get("data")
    if isinstance(data, dict):
        candidates.extend([data.get("session_id"), data.get("id")])
    for candidate in candidates:
        if candidate is not None and str(candidate).strip():
            return str(candidate).strip()
    raise RuntimeError("未从 /api/session 响应中提取到 session_id，请根据真实响应结构调整提取逻辑。")
