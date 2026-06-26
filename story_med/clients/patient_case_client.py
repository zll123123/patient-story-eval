"""解析版患者病例接口客户端。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable

import requests
from requests import Session

from story_med.clients.story_client import StoryApiResponse, build_headers
from story_med.config.app_config import StoryMedConfig

STREAM_HEADERS = {"Accept": "text/event-stream", "Content-Type": "application/json"}


def create_upload_url(session: Session, config: StoryMedConfig, filename: str) -> Dict[str, Any]:
    """获取病例图片 OSS 上传 URL。

    Args:
        session: HTTP 会话。
        config: 运行配置。
        filename: 上传文件名。

    Returns:
        上传 URL 响应体。
    """
    response = session.post(
        f"{config.base_url}/api/oss/upload-url",
        params={"filename": filename},
        headers={"Accept": config.accept, "User-Agent": config.user_agent},
        timeout=config.timeout_seconds,
        verify=config.verify_ssl,
    )
    return _json_body(response, "/api/oss/upload-url")


def upload_file(upload_url: str, file_path: Path, content_type: str, config: StoryMedConfig) -> Dict[str, Any]:
    """上传单张病例图片到 OSS。

    Args:
        upload_url: 预签名上传 URL。
        file_path: 本地图片路径。
        content_type: 文件 MIME 类型。
        config: 运行配置。

    Returns:
        上传结果摘要。
    """
    with file_path.open("rb") as file_obj:
        response = requests.put(
            upload_url,
            data=file_obj,
            headers={"Content-Type": content_type},
            timeout=config.timeout_seconds,
            verify=config.verify_ssl,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"OSS 上传失败: {file_path} {response.status_code} {response.text[:500]}")
    return {"status_code": response.status_code, "size_bytes": file_path.stat().st_size}


def create_patient_case_task(
    session: Session,
    config: StoryMedConfig,
    payload: Dict[str, Any],
) -> StoryApiResponse:
    """创建解析版患者病例任务。

    Args:
        session: HTTP 会话。
        config: 运行配置。
        payload: 请求体。

    Returns:
        接口响应。
    """
    return _post_json(session, config, "/api/patient_case/tasks", payload)


def stream_patient_case_task(
    session: Session,
    config: StoryMedConfig,
    payload: Dict[str, Any],
    output_path: Path,
) -> Dict[str, Any]:
    """启动解析版患者病例 SSE 任务并保存原始流。

    Args:
        session: HTTP 会话。
        config: 运行配置。
        payload: 请求体。
        output_path: SSE 原始内容保存路径。

    Returns:
        SSE 读取摘要。
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    response = session.post(
        f"{config.base_url}/api/patient_case/tasks/start",
        json=payload,
        headers=_stream_headers(config),
        stream=True,
        timeout=(30, None),
        verify=config.verify_ssl,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"{response.status_code} /api/patient_case/tasks/start: {response.text[:500]}")
    event_count = _write_stream_chunks(response.iter_content(chunk_size=1024, decode_unicode=True), output_path)
    return {"status_code": response.status_code, "stream_output_path": str(output_path), "event_count": event_count}


def get_patient_case_history(session: Session, config: StoryMedConfig, session_id: str) -> StoryApiResponse:
    """查询解析版患者病例任务历史。

    Args:
        session: HTTP 会话。
        config: 运行配置。
        session_id: 任务会话 ID。

    Returns:
        接口响应。
    """
    path = f"/api/patient_case/tasks/{session_id}/history"
    response = session.get(
        f"{config.base_url}{path}",
        headers={"Accept": config.accept, "User-Agent": config.user_agent},
        timeout=config.timeout_seconds,
        verify=config.verify_ssl,
    )
    body = _json_body(response, path)
    return StoryApiResponse(status_code=response.status_code, body=body, data=body)


def create_download_url(session: Session, config: StoryMedConfig, file_key: str) -> Dict[str, Any]:
    """获取 OSS 文件预签名下载 URL。

    Args:
        session: HTTP 会话。
        config: 运行配置。
        file_key: OSS 文件 key。

    Returns:
        下载 URL 响应体。
    """
    response = session.get(
        f"{config.base_url}/api/oss/download",
        params={"file_key": file_key},
        headers={"Accept": config.accept, "User-Agent": config.user_agent},
        timeout=config.timeout_seconds,
        verify=config.verify_ssl,
    )
    return _json_body(response, "/api/oss/download")


def download_signed_file(download_url: str, output_path: Path, config: StoryMedConfig) -> Dict[str, Any]:
    """下载预签名 OSS 文件。

    Args:
        download_url: 预签名下载 URL。
        output_path: 本地保存路径。
        config: 运行配置。

    Returns:
        下载结果摘要。
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(download_url, timeout=config.timeout_seconds, verify=config.verify_ssl)
    if response.status_code >= 400:
        raise RuntimeError(f"OSS 下载失败: {output_path} {response.status_code} {response.text[:500]}")
    output_path.write_bytes(response.content)
    return {
        "local_path": str(output_path),
        "content_type": response.headers.get("Content-Type", ""),
        "size_bytes": len(response.content),
    }


def _post_json(session: Session, config: StoryMedConfig, path: str, payload: Dict[str, Any]) -> StoryApiResponse:
    """发送解析版 JSON POST 请求。"""
    response = session.post(
        f"{config.base_url}{path}",
        json=payload,
        headers=build_headers(config),
        timeout=config.timeout_seconds,
        verify=config.verify_ssl,
    )
    body = _json_body(response, path)
    return StoryApiResponse(status_code=response.status_code, body=body, data=body)


def _json_body(response: requests.Response, path: str) -> Dict[str, Any]:
    """解析 JSON 响应并处理错误状态。"""
    try:
        body = response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"接口返回非 JSON: {path} {response.text[:500]}") from exc
    if response.status_code >= 400:
        raise RuntimeError(f"{response.status_code} {path}: {body}")
    if not isinstance(body, dict):
        raise RuntimeError(f"接口返回非 JSON 对象: {path}")
    return body


def _stream_headers(config: StoryMedConfig) -> Dict[str, str]:
    """构建 SSE 请求头。"""
    headers = dict(STREAM_HEADERS)
    headers["User-Agent"] = config.user_agent
    if config.origin:
        headers["Origin"] = config.origin
    if config.referer:
        headers["Referer"] = config.referer
    return headers


def _write_stream_chunks(chunks: Iterable[str | bytes], output_path: Path) -> int:
    """写入 SSE 分块内容。"""
    event_count = 0
    with output_path.open("w", encoding="utf-8") as file_obj:
        for chunk in chunks:
            if not chunk:
                continue
            text = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
            event_count += text.count("data:")
            file_obj.write(text)
            file_obj.flush()
    return event_count
