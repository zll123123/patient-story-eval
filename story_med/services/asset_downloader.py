"""OSS 资源下载服务。"""

from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import unquote, urlparse

import requests
from loguru import logger

from story_med.config.app_config import StoryMedConfig

URL_PATTERN = re.compile(r"https?://[^\s\"'<>，。；；、)）]+")


def extract_urls(payload: Any) -> List[str]:
    """从任意响应结构中递归提取 HTTP 链接。

    Args:
        payload: 接口响应对象。

    Returns:
        List[str]: 去重后的 URL 列表。
    """
    urls: List[str] = []
    if isinstance(payload, dict):
        for value in payload.values():
            urls.extend(extract_urls(value))
    elif isinstance(payload, list):
        for item in payload:
            urls.extend(extract_urls(item))
    elif isinstance(payload, str):
        urls.extend(URL_PATTERN.findall(payload))
    return list(dict.fromkeys(urls))


def download_assets(
    payload: Dict[str, Any],
    output_dir: Path,
    config: StoryMedConfig,
    step_name: str,
) -> List[Dict[str, Any]]:
    """下载响应中的 OSS 链接内容。

    Args:
        payload: 接口响应。
        output_dir: 当前 case 的资源保存目录。
        config: 运行配置。
        step_name: 当前接口步骤名称。

    Returns:
        List[Dict[str, Any]]: 下载结果列表。
    """
    urls = extract_urls(payload)
    results: List[Dict[str, Any]] = []
    for index, url in enumerate(urls, start=1):
        result = _download_single_asset(
            url=url,
            output_dir=output_dir,
            config=config,
            step_name=step_name,
            index=index,
        )
        results.append(result)
    return results


def _download_single_asset(
    url: str,
    output_dir: Path,
    config: StoryMedConfig,
    step_name: str,
    index: int,
) -> Dict[str, Any]:
    """下载单个资源。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        response = requests.get(
            url,
            timeout=config.timeout_seconds,
            verify=config.verify_ssl,
            headers={"User-Agent": config.user_agent},
        )
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        filename = _build_asset_filename(url, content_type, step_name, index)
        file_path = output_dir / filename
        file_path.write_bytes(response.content)
        return {
            "url": url,
            "local_path": str(file_path),
            "content_type": content_type,
            "size_bytes": len(response.content),
            "success": True,
            "error": "",
            "step_name": step_name,
        }
    except Exception as exc:
        logger.exception("资源下载失败: {}", url)
        return {
            "url": url,
            "local_path": "",
            "content_type": "",
            "size_bytes": 0,
            "success": False,
            "error": str(exc),
            "step_name": step_name,
        }


def _build_asset_filename(url: str, content_type: str, step_name: str, index: int) -> str:
    """构建本地资源文件名。"""
    parsed = urlparse(url)
    source_name = Path(unquote(parsed.path)).name
    if source_name and "." in source_name:
        return f"{step_name}_{index}_{source_name}"
    extension = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".bin"
    return f"{step_name}_{index}{extension}"
