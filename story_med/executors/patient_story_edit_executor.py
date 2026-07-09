"""患者故事编辑执行器。"""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Dict, List

from loguru import logger
from requests import Session

from story_med.clients.agent_api.agent_task_client import (
    DEFAULT_AGENT_TYPE,
    create_story_med_download_url,
    download_story_med_file,
    ensure_content_hub_auth,
    stream_agent_adjustment_task,
)
from story_med.clients.base.http_client import create_session
from story_med.config.app_config import StoryMedConfig
from story_med.config.settings import ASSETS_DIR, EDIT_RUNS_DIR
from story_med.executors.content_hub_history import (
    detect_content_hub_upstream_error,
    is_adjustment_history_complete,
    iter_artifacts,
    normalize_content_hub_history,
)
from story_med.executors.content_hub_runtime import now_iso, timed_call, wait_for_terminal_history
from story_med.utils.artifact_cleaner import clear_edit_case_artifacts


class PatientStoryEditExecutor:
    """执行已生成患者故事的自然语言调整。"""

    def __init__(
        self,
        config: StoryMedConfig,
        session: Session | None = None,
        results_dir: Path = EDIT_RUNS_DIR,
        assets_dir: Path = ASSETS_DIR,
        clear_case_artifacts: Callable[[str], None] = clear_edit_case_artifacts,
    ) -> None:
        """初始化编辑执行器。"""
        self._config = config
        self._session = session or create_session()
        self._results_dir = results_dir
        self._assets_dir = assets_dir
        self._clear_case_artifacts = clear_case_artifacts

    def run_adjustment(
        self,
        case_id: str,
        session_id: str,
        task_id: str,
        message: str,
        agent_type: str = DEFAULT_AGENT_TYPE,
    ) -> Dict[str, Any]:
        """执行已生成患者故事的自然语言调整节点。"""
        _validate_inputs(case_id, session_id, task_id, message)
        self._clear_case_artifacts(case_id)
        output_dir = self._results_dir / case_id
        stream_path = output_dir / f"{session_id}_adjustment_stream.txt"
        summary_path = output_dir / "story_adjustment_result.json"
        started_at = now_iso()
        started_perf = perf_counter()
        stream_warning = ""
        try:
            ensure_content_hub_auth(self._session, self._config)
            stream_api = None
            history_api = None
            normalized_history: Dict[str, Any] = {}
            try:
                stream_api, _ = timed_call(
                    lambda: stream_agent_adjustment_task(
                        self._session,
                        self._config,
                        task_id=task_id,
                        agent_type=agent_type,
                        session_id=session_id,
                        message=message,
                        output_path=stream_path,
                    )
                )
            except Exception as exc:
                stream_warning = str(exc)
                logger.warning("患者故事编辑 SSE 提前断开，转为 history 轮询: case_id={}, error={}", case_id, stream_warning)
            stream_errors = extract_stream_errors(stream_path)
            has_task_completed = detect_task_completed(stream_path)
            if self._should_poll_history(stream_warning, has_task_completed):
                history_api = self._wait_for_terminal_history(task_id)
                normalized_history = normalize_content_hub_history(history_api.body)
                upstream_error = detect_content_hub_upstream_error(history_api.body)
                if upstream_error:
                    raise RuntimeError(upstream_error["message"])
                has_task_completed = has_task_completed or is_adjustment_history_complete(normalized_history)
            success = has_task_completed and not stream_errors
            downloaded_assets = (
                self._download_adjustment_assets(case_id, session_id, normalized_history)
                if success and normalized_history
                else []
            )
            response_body = stream_api.body if stream_api else {}
            result = {
                "case_id": case_id,
                "session_id": session_id,
                "task_id": task_id,
                "agent_type": agent_type,
                "message": message,
                "success": success,
                "status_code": stream_api.status_code if stream_api else (history_api.status_code if history_api else 0),
                "response_body": response_body,
                "history_response_body": history_api.body if history_api else {},
                "stream_output_path": str(stream_path),
                "has_task_completed": has_task_completed,
                "stream_warning": stream_warning,
                "stream_errors": stream_errors,
                "downloaded_assets": downloaded_assets,
                "started_at": started_at,
                "finished_at": now_iso(),
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
                "finished_at": now_iso(),
                "duration_seconds": round(perf_counter() - started_perf, 3),
            }
        _write_json(summary_path, result)
        return result

    def _wait_for_terminal_history(self, task_id: str):
        """轮询 history，直到编辑产物可用、失败或超时。"""
        return wait_for_terminal_history(
            self._session,
            self._config,
            task_id,
            is_complete=lambda body: is_adjustment_history_complete(normalize_content_hub_history(body)),
            has_error=lambda body: bool(detect_content_hub_upstream_error(body)),
        )

    def _should_poll_history(self, stream_warning: str, has_task_completed: bool) -> bool:
        """判断当前执行是否需要 fallback 到 history。"""
        if not hasattr(self._session, "get"):
            return False
        return bool(stream_warning) or not has_task_completed

    def _download_adjustment_assets(self, case_id: str, session_id: str, history: Dict[str, Any]) -> List[Dict[str, Any]]:
        """下载编辑 history 中的最终文件。"""
        downloaded_assets: List[Dict[str, Any]] = []
        seen_file_keys: set[str] = set()
        for item in iter_artifacts(history):
            file_key = str(item["file_key"])
            if file_key in seen_file_keys:
                continue
            seen_file_keys.add(file_key)
            output_path = self._assets_dir / case_id / session_id / "adjustment" / Path(file_key).name
            download_info = create_story_med_download_url(self._session, self._config, file_key)
            downloaded = download_story_med_file(str(download_info["download_url"]), output_path, self._config)
            downloaded_assets.append(
                {
                    "oss_key": file_key,
                    "type": str(item["artifact"].get("type") or ""),
                    "title": str(item["artifact"].get("title") or ""),
                    **downloaded,
                }
            )
        return downloaded_assets


def extract_adjustment_files(stream_path: Path) -> List[Dict[str, Any]]:
    """从调整 SSE 原始流中提取最终文件信息。"""
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
                if isinstance(item, dict):
                    files.extend(_expand_file_info(item))
    return files


def extract_stream_errors(stream_path: Path) -> List[str]:
    """从调整 SSE 原始流中提取内部错误。"""
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


def detect_task_completed(stream_path: Path) -> bool:
    """判断调整 SSE 原始流中是否出现任务完成事件。"""
    if not stream_path.exists():
        return False
    for line in stream_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("data:"):
            continue
        raw_data = _safe_json_loads(line[5:].strip())
        if str(raw_data.get("message_type") or "").upper() == "TASK_COMPLETED":
            return True
    return False


def _expand_file_info(file_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """展开单个文件信息，兼容 oss_key 与 oss_keys 两种返回。"""
    oss_key = file_info.get("oss_key")
    if oss_key:
        return [{**file_info, "oss_key": oss_key}]
    oss_keys = file_info.get("oss_keys")
    if not isinstance(oss_keys, list):
        return []
    return [{**file_info, "oss_key": key} for key in oss_keys if isinstance(key, str) and key.strip()]


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
    if str(raw_data.get("message_type") or "").upper() != "TASK_FAILED":
        return
    payload = raw_data.get("payload") if isinstance(raw_data.get("payload"), dict) else {}
    error_message = str(payload.get("error_message") or raw_data.get("content_text") or "").strip()
    errors.append(error_message or "TASK_FAILED")


def _validate_inputs(case_id: str, session_id: str, task_id: str, message: str) -> None:
    """校验调整节点必要参数。"""
    missing_fields = [
        name
        for name, value in {"case_id": case_id, "session_id": session_id, "task_id": task_id, "message": message}.items()
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
