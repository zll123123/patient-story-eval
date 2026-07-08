"""病例图片解析版患者故事 agent 适配层。"""

from __future__ import annotations

import mimetypes
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter, sleep
from typing import Any, Callable, Dict, List

from loguru import logger
from requests import Session

from story_med.clients.agent_task_client import (
    AGENT_TASK_HISTORY_PATH,
    AGENT_TASK_STREAM_PATH,
    AGENT_TASKS_PATH,
    DEFAULT_AGENT_TYPE,
    create_agent_task,
    create_story_med_download_url,
    create_story_med_upload_url,
    download_story_med_file,
    ensure_content_hub_auth,
    get_agent_task_history,
    stream_agent_task,
    upload_story_med_file,
)
from story_med.clients.story_client import StoryApiResponse, create_session, extract_session_id
from story_med.config.app_config import StoryMedConfig
from story_med.config.settings import ASSETS_DIR, TMP_DIR
from story_med.models.case_model import StoryAgentRunResult, StoryCaseConfig, StoryStepResult
from story_med.services.case_image_input import list_case_images_by_path
from story_med.services.clinical_case_config import normalize_case_parse_text

HISTORY_POLL_TIMEOUT_SECONDS = 600
HISTORY_POLL_INTERVAL_SECONDS = 10


class PatientCaseImageAgentAdapter:
    """封装病例图片解析版患者故事链路。"""

    def __init__(self, config: StoryMedConfig, session: Session | None = None) -> None:
        """初始化适配器。

        Args:
            config: 运行配置。
            session: 可注入 HTTP 会话，便于单测 mock。
        """
        self._config = config
        self._session = session or create_session()

    def run_case(self, case: StoryCaseConfig) -> StoryAgentRunResult:
        """执行单条图片病例患者故事链路。

        Args:
            case: 测试用例。

        Returns:
            标准患者故事运行结果。
        """
        started_at = self._now_iso()
        started_perf = perf_counter()
        steps: List[StoryStepResult] = []
        session_id = ""
        stream_warning = ""
        try:
            ensure_content_hub_auth(self._session, self._config)
            uploaded_files = self._upload_case_images(case)
            task_payload = {"message": _case_generation_message(case), "files": uploaded_files}
            task_api, task_timing = self._timed_call(
                lambda: create_agent_task(self._session, self._config, DEFAULT_AGENT_TYPE, task_payload)
            )
            content_hub_task = _content_hub_task_from_create_response(task_api.body)
            session_id = str(content_hub_task.get("remote_agent_task_id") or extract_session_id(task_api.body))
            task_id = str(content_hub_task.get("task_id") or "")
            if not task_id or not session_id:
                raise RuntimeError(f"内容中台创建任务响应缺少 task_id/session_id: {task_api.body}")
            steps.append(
                self._step(
                    "create_agent_task",
                    AGENT_TASKS_PATH,
                    task_payload,
                    task_api,
                    session_id,
                    task_timing,
                )
            )

            start_payload = {
                "task_id": task_id,
                "agent_type": DEFAULT_AGENT_TYPE,
                "session_id": session_id,
                **task_payload,
                "form": {"session_id": session_id, **task_payload},
            }
            try:
                stream_api, stream_timing = self._timed_call(
                    lambda: self._stream_task(case.case_id, task_id, start_payload)
                )
                steps.append(
                    self._step(
                        "stream_agent_task",
                        AGENT_TASK_STREAM_PATH,
                        start_payload,
                        stream_api,
                        session_id,
                        stream_timing,
                    )
                )
            except Exception as exc:
                stream_warning = str(exc)
                logger.warning("图片病例患者故事 SSE 提前断开，转为 history 轮询: case_id={}, error={}", case.case_id, stream_warning)

            history_api, history_timing = self._timed_call(
                lambda: self._wait_for_terminal_history(task_id)
            )
            steps.append(
                self._step(
                    "get_agent_task_history",
                    AGENT_TASK_HISTORY_PATH,
                    {"task_id": task_id},
                    history_api,
                    session_id,
                    history_timing,
                )
            )
            normalized_history = normalize_content_hub_history(history_api.body)
            upstream_error = detect_content_hub_upstream_error(history_api.body)
            if upstream_error:
                raise ContentHubUpstreamError(upstream_error["message"], upstream_error["failed_step"])
            case_parse_text = self._write_case_parse(case.case_id, session_id, normalized_history)
            downloaded_assets = self._download_history_artifacts(case.case_id, session_id, normalized_history)
            return self._success_result(
                case,
                session_id,
                steps,
                normalized_history,
                downloaded_assets,
                case_parse_text,
                content_hub_task,
                stream_warning,
                started_at,
                started_perf,
            )
        except ContentHubUpstreamError as exc:
            logger.exception("图片病例患者故事 case 上游 Agent 执行失败: {}", case.case_id)
            return self._failed_result(
                case,
                session_id,
                steps,
                str(exc),
                started_at,
                started_perf,
                failed_step=exc.failed_step,
            )
        except Exception as exc:
            logger.exception("图片病例患者故事 case 执行失败: {}", case.case_id)
            return self._failed_result(case, session_id, steps, str(exc), started_at, started_perf)

    def _upload_case_images(self, case: StoryCaseConfig) -> List[Dict[str, str]]:
        """上传当前 case 目录下的全部病例图片。"""
        files: List[Dict[str, str]] = []
        for image_path in self._resolve_case_images(case):
            upload_info = create_story_med_upload_url(self._session, self._config, image_path.name)
            content_type = str(upload_info.get("content_type") or _guess_content_type(image_path))
            upload_story_med_file(str(upload_info["upload_url"]), image_path, content_type, self._config)
            files.append({"file_name": image_path.name, "file_key": str(upload_info["file_key"])})
        return files

    def _resolve_case_images(self, case: StoryCaseConfig) -> List[Path]:
        """按 case.image_dir 读取病例图片。"""
        image_dir = case.image_dir.strip()
        if not image_dir:
            raise FileNotFoundError(f"病例图片目录未配置: {case.case_id}")
        image_path = Path(image_dir).expanduser()
        if not image_path.is_absolute():
            from story_med.config.settings import CASE_IMAGE_DIR

            image_path = CASE_IMAGE_DIR / image_path
        return list_case_images_by_path(image_path.resolve())

    def _stream_task(self, case_id: str, task_id: str, payload: Dict[str, Any]) -> StoryApiResponse:
        """启动 SSE 任务并返回摘要响应。"""
        output_path = TMP_DIR / case_id / f"{task_id}_agent_task_stream.txt"
        return stream_agent_task(self._session, self._config, payload, output_path)

    def _wait_for_terminal_history(self, task_id: str) -> StoryApiResponse:
        """轮询 history，直到任务完整、明确失败或超时。"""
        deadline = perf_counter() + HISTORY_POLL_TIMEOUT_SECONDS
        last_response: StoryApiResponse | None = None
        while perf_counter() < deadline:
            response = get_agent_task_history(self._session, self._config, task_id)
            last_response = response
            body = response.body if isinstance(response.body, dict) else {}
            if detect_content_hub_upstream_error(body):
                return response
            if _is_history_complete(normalize_content_hub_history(body)):
                return response
            sleep(HISTORY_POLL_INTERVAL_SECONDS)
        if last_response is not None:
            return last_response
        raise RuntimeError(f"内容中台 history 轮询超时且未返回有效响应: task_id={task_id}")

    def _download_history_artifacts(
        self,
        case_id: str,
        session_id: str,
        history: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """下载 history 中的全部交付物。"""
        results: List[Dict[str, Any]] = []
        seen_file_keys: set[str] = set()
        for item in _iter_artifacts(history):
            file_key = item["file_key"]
            if file_key in seen_file_keys:
                continue
            seen_file_keys.add(file_key)
            step_name = _artifact_step_name(item["group"], item["artifact"])
            download_info = create_story_med_download_url(self._session, self._config, file_key)
            output_path = ASSETS_DIR / case_id / session_id / step_name / Path(file_key).name
            downloaded = download_story_med_file(str(download_info["download_url"]), output_path, self._config)
            results.append(
                {
                    **downloaded,
                    "url": download_info["download_url"],
                    "step_name": step_name,
                    "success": True,
                    "error": "",
                }
            )
        return results

    def _write_case_parse(self, case_id: str, session_id: str, history: Dict[str, Any]) -> str:
        """将病例解析结果写入 case_parse 目录。"""
        case_parse_dir = ASSETS_DIR / case_id / session_id / "case_parse"
        case_parse_dir.mkdir(parents=True, exist_ok=True)
        case_parse_text = normalize_case_parse_text(case_id, history)
        (case_parse_dir / "case_parse.md").write_text(case_parse_text, encoding="utf-8")
        return case_parse_text

    @staticmethod
    def _step(
        step_name: str,
        endpoint: str,
        request_payload: Dict[str, Any],
        response: StoryApiResponse,
        session_id: str,
        timing: Dict[str, Any],
    ) -> StoryStepResult:
        """构建单步结果。"""
        return StoryStepResult(
            step_name=step_name,
            endpoint=endpoint,
            request_payload=request_payload,
            status_code=response.status_code,
            response_body=response.body,
            response_data=response.data,
            session_id=session_id,
            started_at=str(timing["started_at"]),
            finished_at=str(timing["finished_at"]),
            duration_seconds=float(timing["duration_seconds"]),
        )

    @staticmethod
    def _success_result(
        case: StoryCaseConfig,
        session_id: str,
        steps: List[StoryStepResult],
        history: Dict[str, Any],
        downloaded_assets: List[Dict[str, Any]],
        case_parse_text: str,
        content_hub_task: Dict[str, Any],
        stream_warning: str,
        started_at: str,
        started_perf: float,
    ) -> StoryAgentRunResult:
        """构建成功结果。"""
        return StoryAgentRunResult(
            case_id=case.case_id,
            description=case.description,
            session_id=session_id,
            success=True,
            steps=steps,
            session_response={
                "session_id": session_id,
                "content_hub_task": content_hub_task,
                "stream_warning": stream_warning,
            },
            outline_response=_artifacts_by_group(history, "outline"),
            story_response=_artifacts_by_group(history, "story"),
            images_response=_artifacts_by_group(history, "image"),
            final_image_response={"case_parse": case_parse_text},
            downloaded_assets=downloaded_assets,
            started_at=started_at,
            finished_at=PatientCaseImageAgentAdapter._now_iso(),
            total_duration_seconds=round(perf_counter() - started_perf, 3),
        )

    @staticmethod
    def _failed_result(
        case: StoryCaseConfig,
        session_id: str,
        steps: List[StoryStepResult],
        error: str,
        started_at: str,
        started_perf: float,
        failed_step: str = "",
    ) -> StoryAgentRunResult:
        """构建失败结果。"""
        return StoryAgentRunResult(
            case_id=case.case_id,
            description=case.description,
            session_id=session_id,
            success=False,
            steps=steps,
            session_response={"session_id": session_id} if session_id else {},
            outline_response={},
            story_response={},
            images_response={},
            final_image_response={},
            downloaded_assets=[],
            started_at=started_at,
            finished_at=PatientCaseImageAgentAdapter._now_iso(),
            total_duration_seconds=round(perf_counter() - started_perf, 3),
            error=error,
            failed_step=failed_step or _guess_failed_step(len(steps)),
        )

    @staticmethod
    def _timed_call(func: Callable[[], Any]) -> tuple[Any, Dict[str, Any]]:
        """执行函数并记录耗时。"""
        started_at = PatientCaseImageAgentAdapter._now_iso()
        started_perf = perf_counter()
        result = func()
        return result, {
            "started_at": started_at,
            "finished_at": PatientCaseImageAgentAdapter._now_iso(),
            "duration_seconds": round(perf_counter() - started_perf, 3),
        }

    @staticmethod
    def _now_iso() -> str:
        """返回当前 UTC ISO 时间。"""
        return datetime.now(UTC).isoformat()


def _iter_artifacts(history: Dict[str, Any]) -> List[Dict[str, Any]]:
    """展开 history artifacts 中的 OSS key。"""
    artifacts = history.get("artifacts") or {}
    results: List[Dict[str, Any]] = []
    if not isinstance(artifacts, dict):
        return results
    for group, items in artifacts.items():
        if not isinstance(items, list):
            continue
        for artifact in items:
            if isinstance(artifact, dict):
                results.extend(_artifact_keys(str(group), artifact))
    return results


def _case_generation_message(case: StoryCaseConfig) -> str:
    """读取病例生成要求作为初始生成 message。"""
    return case.creative_brief.strip()


class ContentHubUpstreamError(RuntimeError):
    """内容中台上游 Agent 错误。"""

    def __init__(self, message: str, failed_step: str) -> None:
        """初始化上游错误。

        Args:
            message: 错误信息。
            failed_step: 推断出的失败节点。
        """
        super().__init__(message)
        self.failed_step = failed_step


def _artifact_keys(group: str, artifact: Dict[str, Any]) -> List[Dict[str, Any]]:
    """提取单个 artifact 的 OSS key。"""
    keys: List[str] = []
    if artifact.get("oss_key"):
        keys.append(str(artifact["oss_key"]))
    keys.extend([str(item) for item in artifact.get("oss_keys") or []])
    return [{"group": group, "artifact": artifact, "file_key": key} for key in keys]


def _artifact_step_name(group: str, artifact: Dict[str, Any]) -> str:
    """将解析版 artifact 映射到旧审核目录。"""
    artifact_type = str(artifact.get("type") or "")
    if group == "case_parse":
        return "case_parse"
    if group == "outline":
        return "generate_outline"
    if group == "story":
        return "generate_story"
    if group == "image" or artifact_type in {"json", "image_list"}:
        return "generate_images"
    return "generate_final_image"


def _artifacts_by_group(history: Dict[str, Any], group: str) -> Dict[str, Any]:
    """读取指定 artifact 分组。"""
    artifacts = history.get("artifacts") or {}
    if not isinstance(artifacts, dict):
        return {}
    value = artifacts.get(group)
    return {"artifacts": value} if value else {}


def _is_history_complete(history: Dict[str, Any]) -> bool:
    """判断 history 是否已经具备完整审核所需的核心产物。"""
    artifacts = history.get("artifacts") or {}
    if not isinstance(artifacts, dict):
        return False
    required_groups = ("outline", "story", "image", "html")
    return all(isinstance(artifacts.get(group), list) and bool(artifacts.get(group)) for group in required_groups)


def normalize_content_hub_history(body: Dict[str, Any]) -> Dict[str, Any]:
    """将内容中台 history 转成既有审核链路使用的 history 结构。

    Args:
        body: 内容中台 history 原始响应。

    Returns:
        包含 messages 与 artifacts 的标准 history。
    """
    messages: List[Dict[str, str]] = []
    artifacts: Dict[str, List[Dict[str, Any]]] = {}
    for frame in _content_hub_frames(body):
        raw = _frame_raw(frame)
        data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
        content = str(data.get("content") or "").strip() if isinstance(data, dict) else ""
        if content:
            messages.append({"role": "ai", "content": content})
        files = data.get("files") if isinstance(data, dict) else []
        if isinstance(files, list):
            _append_history_files(artifacts, files)
    return {"messages": messages, "artifacts": artifacts, "raw_history": body}


def detect_content_hub_upstream_error(body: Dict[str, Any]) -> Dict[str, str]:
    """识别内容中台外层完成但上游 Agent 内层失败的情况。

    Args:
        body: 内容中台 history 原始响应。

    Returns:
        错误摘要；未发现错误返回空字典。
    """
    for frame in _content_hub_frames(body):
        message_type = str(frame.get("message_type") or "")
        payload = frame.get("payload") if isinstance(frame.get("payload"), dict) else {}
        raw = _frame_raw(frame)
        raw_text = json.dumps(raw or payload or frame, ensure_ascii=False)
        if message_type == "TASK_FAILED" or str(raw.get("status") or "") == "ERROR" or "graph stream error" in raw_text:
            return {
                "message": _upstream_error_message(frame, raw_text),
                "failed_step": _content_hub_failed_step(body),
            }
    return {}


def _content_hub_task_from_create_response(body: Dict[str, Any]) -> Dict[str, Any]:
    """从创建任务响应中提取内容中台 task 上下文。

    Args:
        body: 创建任务接口响应体。

    Returns:
        内容中台 task 上下文，响应中没有 task_id 时返回空字典。
    """
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    task_id = _first_non_empty(body.get("task_id"), body.get("taskId"), data.get("task_id"), data.get("taskId"))
    session_id = _first_non_empty(
        body.get("remote_agent_task_id"),
        body.get("session_id"),
        data.get("remote_agent_task_id"),
        data.get("session_id"),
    )
    if not task_id:
        return {}
    return {
        "task_id": task_id,
        "remote_agent_task_id": session_id,
        "source": "content_hub_create_agent_task",
    }


def _first_non_empty(*values: Any) -> str:
    """返回第一个非空字符串值。"""
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _content_hub_frames(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    """展开内容中台 history 中的 frames。"""
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    turns = data.get("turns") if isinstance(data.get("turns"), list) else []
    frames: List[Dict[str, Any]] = []
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        for frame in turn.get("frames") or []:
            if isinstance(frame, dict):
                frames.append(frame)
    return frames


def _frame_raw(frame: Dict[str, Any]) -> Dict[str, Any]:
    """提取 frame 中的上游 raw payload。"""
    payload = frame.get("payload") if isinstance(frame.get("payload"), dict) else {}
    raw = payload.get("raw") if isinstance(payload.get("raw"), dict) else {}
    return raw if isinstance(raw, dict) else {}


def _append_history_files(artifacts: Dict[str, List[Dict[str, Any]]], files: List[Any]) -> None:
    """把中台文件事件追加到 artifacts 分组。"""
    for file_item in files:
        if not isinstance(file_item, dict):
            continue
        file_key = _first_non_empty(file_item.get("oss_key"), file_item.get("file_key"))
        oss_keys = [str(item) for item in file_item.get("oss_keys") or [] if str(item).strip()]
        if not file_key and not oss_keys:
            continue
        group = _content_hub_file_group(file_item, file_key or (oss_keys[0] if oss_keys else ""))
        artifact = {
            **file_item,
        }
        if file_key:
            artifact["oss_key"] = file_key
        if oss_keys:
            artifact["oss_keys"] = oss_keys
        artifacts.setdefault(group, []).append(artifact)


def _content_hub_file_group(file_item: Dict[str, Any], file_key: str) -> str:
    """按文件元信息判断产物所属节点。"""
    title = str(file_item.get("title") or "").lower()
    file_type = str(file_item.get("type") or "").lower()
    key = file_key.lower()
    if "病例" in title or "case_parse" in key:
        return "case_parse"
    if "大纲" in title or key.endswith("outline.md"):
        return "outline"
    if "正文" in title or key.endswith("story.md"):
        return "story"
    if file_type in {"json", "image_list"} or "/images/" in key or "image" in title or "图片" in title:
        return "image"
    if file_type in {"html", "png"} or key.endswith(".html") or key.endswith(".png"):
        return "html"
    return "html"


def _upstream_error_message(frame: Dict[str, Any], raw_text: str) -> str:
    """生成上游错误摘要。"""
    raw = _frame_raw(frame)
    data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    error = data.get("error") if isinstance(data, dict) else ""
    title = str(raw.get("title") or "")
    step_id = str(raw.get("parent_step_id") or raw.get("step_id") or "")
    detail = str(error or raw_text[:1000])
    prefix = f"{title or step_id}: " if title or step_id else ""
    return f"内容中台上游 Agent 执行失败: {prefix}{detail}"


def _content_hub_failed_step(body: Dict[str, Any]) -> str:
    """根据已开始但未正常结束的节点推断失败步骤。"""
    step_titles: Dict[str, str] = {}
    latest_started = ""
    for frame in _content_hub_frames(body):
        raw = _frame_raw(frame)
        status = str(raw.get("status") or "")
        step_id = str(raw.get("step_id") or "")
        parent_step_id = str(raw.get("parent_step_id") or "")
        title = str(raw.get("title") or "")
        if status == "START" and step_id:
            latest_started = step_id
            step_titles[step_id] = title
        if status == "ERROR":
            return _agent_title_to_step(step_titles.get(parent_step_id) or title)
    return _agent_title_to_step(step_titles.get(latest_started, ""))


def _agent_title_to_step(title: str) -> str:
    """将 Agent 节点标题映射为本地失败步骤名。"""
    if "解析" in title:
        return "case_parse"
    if "大纲" in title:
        return "generate_outline"
    if "故事" in title or "正文" in title:
        return "generate_story"
    if "图片" in title or "成图" in title:
        return "generate_images"
    if "长图" in title or "html" in title.lower():
        return "generate_final_image"
    return title or "stream_agent_task"



def _guess_content_type(path: Path) -> str:
    """根据文件扩展名推断 MIME 类型。"""
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def _guess_failed_step(completed_steps: int) -> str:
    """根据已完成步骤数猜测失败环节。"""
    steps = ["create_agent_task", "stream_agent_task", "get_agent_task_history", "download_artifacts"]
    if completed_steps < len(steps):
        return steps[completed_steps]
    return "unknown"
