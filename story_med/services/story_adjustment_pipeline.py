"""患者故事生成结果调整流程。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List

from loguru import logger
from requests import Session

from story_med.clients.agent_task_client import (
    DEFAULT_AGENT_TYPE,
    create_story_med_download_url,
    download_story_med_file,
    ensure_content_hub_auth,
    stream_agent_adjustment_task,
)
from story_med.clients.story_client import create_session
from story_med.config.app_config import StoryMedConfig
from story_med.config.settings import ASSETS_DIR, EDIT_RESULTS_DIR


def run_story_adjustment(
    config: StoryMedConfig,
    case_id: str,
    session_id: str,
    task_id: str,
    message: str,
    agent_type: str = DEFAULT_AGENT_TYPE,
    session: Session | None = None,
) -> Dict[str, Any]:
    """执行已生成患者故事的自然语言调整节点。

    Args:
        config: 运行配置。
        case_id: 测试病例 ID。
        session_id: 已生成患者故事的会话 ID。
        task_id: 服务端任务 ID。
        message: 自然语言调整要求。
        agent_type: Agent 类型。
        session: 可注入 HTTP 会话，便于单测 mock。

    Returns:
        调整节点运行摘要。
    """
    _validate_inputs(case_id, session_id, task_id, message)
    http_session = session or create_session()
    output_dir = EDIT_RESULTS_DIR / case_id
    stream_path = output_dir / f"{session_id}_adjustment_stream.txt"
    summary_path = output_dir / "story_adjustment_result.json"
    started_at = _now_iso()
    started_perf = perf_counter()
    try:
        ensure_content_hub_auth(http_session, config)
        response = stream_agent_adjustment_task(
            http_session,
            config,
            task_id=task_id,
            agent_type=agent_type,
            session_id=session_id,
            message=message,
            output_path=stream_path,
        )
        stream_errors = extract_stream_errors(stream_path)
        downloaded_assets = [] if stream_errors else _download_adjustment_assets(
            http_session,
            config,
            case_id,
            session_id,
            stream_path,
        )
        result = {
            "case_id": case_id,
            "session_id": session_id,
            "task_id": task_id,
            "agent_type": agent_type,
            "message": message,
            "success": not stream_errors,
            "status_code": response.status_code,
            "response_body": response.body,
            "stream_output_path": str(stream_path),
            "stream_errors": stream_errors,
            "downloaded_assets": downloaded_assets,
            "started_at": started_at,
            "finished_at": _now_iso(),
            "duration_seconds": round(perf_counter() - started_perf, 3),
        }
    except Exception as exc:
        logger.exception("患者故事调整节点执行失败: case_id={}, session_id={}", case_id, session_id)
        result = {
            "case_id": case_id,
            "session_id": session_id,
            "task_id": task_id,
            "agent_type": agent_type,
            "message": message,
            "success": False,
            "error": str(exc),
            "stream_output_path": str(stream_path),
            "started_at": started_at,
            "finished_at": _now_iso(),
            "duration_seconds": round(perf_counter() - started_perf, 3),
        }
    _write_json(summary_path, result)
    return result


def extract_adjustment_files(stream_path: Path) -> List[Dict[str, Any]]:
    """从调整 SSE 原始流中提取最终文件信息。

    Args:
        stream_path: SSE 原始流路径。

    Returns:
        文件信息列表。
    """
    if not stream_path.exists():
        return []
    files: List[Dict[str, Any]] = []
    for line in stream_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("data:"):
            continue
        raw_data = _safe_json_loads(line[5:].strip())
        payload = raw_data.get("payload") if isinstance(raw_data, dict) else {}
        raw_payload = payload.get("raw") if isinstance(payload, dict) else {}
        event_data = raw_payload.get("data") if isinstance(raw_payload, dict) else {}
        event_files = event_data.get("files") if isinstance(event_data, dict) else []
        if isinstance(event_files, list):
            for item in event_files:
                if not isinstance(item, dict):
                    continue
                files.extend(_expand_file_info(item))
    return files


def _expand_file_info(file_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """展开单个文件信息，兼容 oss_key 与 oss_keys 两种返回。"""
    oss_key = file_info.get("oss_key")
    if oss_key:
        return [{**file_info, "oss_key": oss_key}]
    oss_keys = file_info.get("oss_keys")
    if not isinstance(oss_keys, list):
        return []
    return [{**file_info, "oss_key": key} for key in oss_keys if isinstance(key, str) and key.strip()]


def extract_stream_errors(stream_path: Path) -> List[str]:
    """从调整 SSE 原始流中提取内部错误。

    Args:
        stream_path: SSE 原始流路径。

    Returns:
        错误信息列表。
    """
    if not stream_path.exists():
        return []
    errors: List[str] = []
    for line in stream_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("data:"):
            continue
        raw_data = _safe_json_loads(line[5:].strip())
        _collect_outer_stream_error(raw_data, errors)
        payload = raw_data.get("payload") if isinstance(raw_data, dict) else {}
        raw_payload = payload.get("raw") if isinstance(payload, dict) else {}
        _collect_stream_error(raw_payload, errors)
    return errors


def _download_adjustment_assets(
    session: Session,
    config: StoryMedConfig,
    case_id: str,
    session_id: str,
    stream_path: Path,
) -> List[Dict[str, Any]]:
    """下载调整接口返回的最终文件。"""
    downloaded_assets: List[Dict[str, Any]] = []
    for file_info in extract_adjustment_files(stream_path):
        oss_key = str(file_info["oss_key"])
        output_path = ASSETS_DIR / case_id / session_id / "adjustment" / Path(oss_key).name
        download_info = create_story_med_download_url(session, config, oss_key)
        downloaded = download_story_med_file(str(download_info["download_url"]), output_path, config)
        downloaded_assets.append(
            {
                "oss_key": oss_key,
                "type": str(file_info.get("type") or ""),
                "title": str(file_info.get("title") or ""),
                **downloaded,
            }
        )
    return downloaded_assets


def _collect_stream_error(raw_payload: Any, errors: List[str]) -> None:
    """从单条 SSE payload 中收集错误。"""
    if not isinstance(raw_payload, dict):
        return
    status = str(raw_payload.get("status") or "").upper()
    raw_type = str(raw_payload.get("type") or "").lower()
    data = raw_payload.get("data")
    if status == "ERROR":
        errors.append(json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else str(data))
    if raw_type == "error":
        errors.append(str(data))


def _collect_outer_stream_error(raw_data: Dict[str, Any], errors: List[str]) -> None:
    """从内容中台外层 SSE payload 中收集错误。"""
    message_type = str(raw_data.get("message_type") or "").upper()
    if message_type != "TASK_FAILED":
        return
    payload = raw_data.get("payload") if isinstance(raw_data.get("payload"), dict) else {}
    error_message = str(payload.get("error_message") or raw_data.get("content_text") or "").strip()
    errors.append(error_message or "TASK_FAILED")


def _validate_inputs(case_id: str, session_id: str, task_id: str, message: str) -> None:
    """校验调整节点必要参数。"""
    missing_fields = [
        name
        for name, value in {
            "case_id": case_id,
            "session_id": session_id,
            "task_id": task_id,
            "message": message,
        }.items()
        if not value.strip()
    ]
    if missing_fields:
        raise ValueError(f"调整节点缺少必要参数: {', '.join(missing_fields)}")


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    """写入 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_json_loads(text: str) -> Dict[str, Any]:
    """安全解析 JSON 对象。"""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _now_iso() -> str:
    """返回当前 UTC ISO 时间。"""
    return datetime.now(UTC).isoformat()
