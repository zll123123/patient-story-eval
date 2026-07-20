"""患者故事生成执行器。"""

from __future__ import annotations

import mimetypes
from time import perf_counter
from pathlib import Path
from typing import Any, Callable, Dict, List

from loguru import logger
from requests import Session

from story_med.clients.agent_api.agent_task_client import (
    AGENT_TASK_HISTORY_PATH,
    AGENT_TASK_STREAM_PATH,
    AGENT_TASKS_PATH,
    DEFAULT_AGENT_TYPE,
    create_agent_task,
    create_story_med_download_url,
    create_story_med_upload_url,
    download_story_med_file,
    ensure_content_hub_auth,
    stream_agent_task,
    STREAM_TASK_TIMEOUT_SECONDS,
    upload_story_med_file,
)
from story_med.clients.base.http_client import (
    StoryApiResponse,
    create_session,
    extract_session_id,
)
from story_med.config.app_config import StoryMedConfig
from story_med.config.settings import ASSETS_DIR, CASE_IMAGE_DIR, STORY_AUDITS_DIR
from story_med.executors.content_hub_history import (
    artifact_step_name,
    artifacts_by_group,
    content_hub_task_from_create_response,
    detect_content_hub_upstream_error,
    is_generation_history_complete,
    iter_artifacts,
    normalize_content_hub_history,
)
from story_med.executors.content_hub_runtime import wait_for_terminal_history
from story_med.models.case_model import (
    StoryAgentRunResult,
    StoryCaseConfig,
    StoryStepResult,
)
from story_med.services.clinical_case_preparation.case_image_input import (
    list_case_images_by_path,
)
from story_med.services.clinical_case_preparation.case_parse_service import (
    normalize_case_parse_text,
)
from story_med.utils.timing import TimingCollector, now_iso


class PatientStoryGenerationExecutor:
    """封装病例图片版患者故事生成链路。"""

    def __init__(self, config: StoryMedConfig, session: Session | None = None) -> None:
        """初始化执行器。"""
        self._config = config
        self._session = session or create_session()

    def run_case(self, case: StoryCaseConfig) -> StoryAgentRunResult:
        """执行单条图片病例患者故事链路。"""
        started_at = now_iso()
        steps: List[StoryStepResult] = []
        timings = TimingCollector()
        session_id = ""
        task_id = ""
        stream_warning = ""
        try:
            with timings.stage("ensure_content_hub_auth", "content_hub_request"):
                ensure_content_hub_auth(self._session, self._config)
            uploaded_files = self._upload_case_images(case, timings)
            task_payload = {
                "message": _case_generation_message(case),
                "files": uploaded_files,
            }
            with timings.stage("create_agent_task", "content_hub_request") as timer:
                task_api = create_agent_task(
                    self._session, self._config, DEFAULT_AGENT_TYPE, task_payload
                )
            content_hub_task = content_hub_task_from_create_response(task_api.body)
            session_id = str(
                content_hub_task.get("remote_agent_task_id")
                or extract_session_id(task_api.body)
            )
            task_id = str(content_hub_task.get("task_id") or "")
            timer.update(task_id=task_id, session_id=session_id)
            if not task_id or not session_id:
                raise RuntimeError(f"内容中台创建任务响应缺少 task_id/session_id: {task_api.body}")
            task_deadline = perf_counter() + STREAM_TASK_TIMEOUT_SECONDS
            steps.append(
                self._step(
                    "create_agent_task",
                    AGENT_TASKS_PATH,
                    task_payload,
                    task_api,
                    session_id,
                )
            )
            start_payload = self._build_start_payload(task_id, session_id, task_payload)
            try:
                with timings.stage(
                    "stream_agent_task",
                    "content_hub_request",
                    task_id=task_id,
                    session_id=session_id,
                ) as timer:
                    stream_api = self._stream_task(
                        case.case_id, task_id, start_payload, task_deadline
                    )
                    timer.update(
                        metadata={"event_count": stream_api.body.get("event_count", 0)}
                    )
                steps.append(
                    self._step(
                        "stream_agent_task",
                        AGENT_TASK_STREAM_PATH,
                        start_payload,
                        stream_api,
                        session_id,
                    )
                )
                timings.add_agent_nodes(
                    list(
                        (stream_api.body.get("agent_node_timings") or {}).get("steps")
                        or []
                    ),
                    task_id=task_id,
                    session_id=session_id,
                )
            except Exception as exc:
                stream_warning = str(exc)
                logger.warning(
                    "图片病例患者故事 SSE 提前断开，转为 history 轮询: case_id={}, error={}",
                    case.case_id,
                    stream_warning,
                )
            with timings.stage(
                "history_polling",
                "content_hub_request",
                task_id=task_id,
                session_id=session_id,
            ):
                history_api = self._wait_for_terminal_history(task_id, task_deadline)
            steps.append(
                self._step(
                    "get_agent_task_history",
                    AGENT_TASK_HISTORY_PATH,
                    {"task_id": task_id},
                    history_api,
                    session_id,
                )
            )
            normalized_history = normalize_content_hub_history(history_api.body)
            upstream_error = detect_content_hub_upstream_error(history_api.body)
            if upstream_error:
                raise ContentHubUpstreamError(
                    upstream_error["message"], upstream_error["failed_step"]
                )
            with timings.stage(
                "write_case_parse",
                "content_hub_request",
                task_id=task_id,
                session_id=session_id,
            ):
                case_parse_text = self._write_case_parse(
                    case.case_id, session_id, normalized_history
                )
            downloaded_assets = self._download_history_artifacts(
                case.case_id, session_id, normalized_history, timings, task_id
            )
            return self._success_result(
                case,
                session_id,
                steps,
                normalized_history,
                downloaded_assets,
                case_parse_text,
                content_hub_task,
                stream_warning,
                task_id,
                timings.to_list(),
            )
        except ContentHubUpstreamError as exc:
            logger.exception("图片病例患者故事 case 上游 Agent 执行失败: {}", case.case_id)
            return self._failed_result(
                case,
                session_id,
                task_id,
                steps,
                str(exc),
                timings.to_list(),
                failed_step=exc.failed_step,
            )
        except Exception as exc:
            logger.exception("图片病例患者故事 case 执行失败: {}", case.case_id)
            return self._failed_result(
                case, session_id, task_id, steps, str(exc), timings.to_list()
            )

    def _upload_case_images(
        self, case: StoryCaseConfig, timings: TimingCollector
    ) -> List[Dict[str, str]]:
        """上传当前 case 目录下的全部病例图片。"""
        files: List[Dict[str, str]] = []
        for image_path in self._resolve_case_images(case):
            with timings.stage(
                "presign_upload",
                "content_hub_request",
                metadata={"file_name": image_path.name},
            ):
                upload_info = create_story_med_upload_url(
                    self._session, self._config, image_path.name
                )
            content_type = str(
                upload_info.get("content_type") or _guess_content_type(image_path)
            )
            with timings.stage(
                "upload_case_image",
                "content_hub_request",
                metadata={
                    "file_name": image_path.name,
                    "size_bytes": image_path.stat().st_size,
                },
            ):
                upload_story_med_file(
                    str(upload_info["upload_url"]),
                    image_path,
                    content_type,
                    self._config,
                )
            files.append(
                {"file_name": image_path.name, "file_key": str(upload_info["file_key"])}
            )
        return files

    def _resolve_case_images(self, case: StoryCaseConfig) -> List[Path]:
        """按 case.image_dir 读取病例图片。"""
        image_dir = case.image_dir.strip()
        if not image_dir:
            raise FileNotFoundError(f"病例图片目录未配置: {case.case_id}")
        image_path = Path(image_dir).expanduser()
        if not image_path.is_absolute():
            image_path = CASE_IMAGE_DIR / image_path
        return list_case_images_by_path(image_path.resolve())

    def _stream_task(
        self, case_id: str, task_id: str, payload: Dict[str, Any], deadline: float
    ) -> StoryApiResponse:
        """启动 SSE 任务并返回摘要响应。"""
        output_path = STORY_AUDITS_DIR / case_id / f"{task_id}_agent_task_stream.txt"
        return stream_agent_task(
            self._session, self._config, payload, output_path, deadline
        )

    def _wait_for_terminal_history(self, task_id: str, deadline: float) -> StoryApiResponse:
        """轮询 history，直到任务完整、失败或超时。"""
        return wait_for_terminal_history(
            self._session,
            self._config,
            task_id,
            is_complete=lambda body: is_generation_history_complete(
                normalize_content_hub_history(body)
            ),
            has_error=lambda body: bool(detect_content_hub_upstream_error(body)),
            deadline=deadline,
        )

    def _download_history_artifacts(
        self,
        case_id: str,
        session_id: str,
        history: Dict[str, Any],
        timings: TimingCollector,
        task_id: str,
    ) -> List[Dict[str, Any]]:
        """下载 history 中的全部交付物。"""
        results: List[Dict[str, Any]] = []
        seen_file_keys: set[str] = set()
        for item in iter_artifacts(history):
            file_key = item["file_key"]
            if file_key in seen_file_keys:
                continue
            seen_file_keys.add(file_key)
            step_name = artifact_step_name(item["group"], item["artifact"])
            with timings.stage(
                "presign_download",
                "content_hub_request",
                task_id=task_id,
                session_id=session_id,
                metadata={"file_key": file_key, "step_name": step_name},
            ):
                download_info = create_story_med_download_url(
                    self._session, self._config, file_key
                )
            output_path = (
                ASSETS_DIR / case_id / session_id / step_name / Path(file_key).name
            )
            with timings.stage(
                "download_artifact",
                "content_hub_request",
                task_id=task_id,
                session_id=session_id,
                metadata={"file_key": file_key, "step_name": step_name},
            ):
                downloaded = download_story_med_file(
                    str(download_info["download_url"]), output_path, self._config
                )
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

    def _write_case_parse(
        self, case_id: str, session_id: str, history: Dict[str, Any]
    ) -> str:
        """将病例解析结果写入 case_parse 目录。"""
        case_parse_dir = ASSETS_DIR / case_id / session_id / "case_parse"
        case_parse_dir.mkdir(parents=True, exist_ok=True)
        case_parse_text = normalize_case_parse_text(case_id, history)
        (case_parse_dir / "case_parse.md").write_text(case_parse_text, encoding="utf-8")
        return case_parse_text

    @staticmethod
    def _build_start_payload(
        task_id: str, session_id: str, task_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """构建启动任务请求体。"""
        return {
            "task_id": task_id,
            "agent_type": DEFAULT_AGENT_TYPE,
            "session_id": session_id,
            **task_payload,
            "form": {"session_id": session_id, **task_payload},
        }

    @staticmethod
    def _step(
        step_name: str,
        endpoint: str,
        request_payload: Dict[str, Any],
        response: StoryApiResponse,
        session_id: str,
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
        task_id: str,
        execution_stages: List[Dict[str, Any]],
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
            outline_response=artifacts_by_group(history, "outline"),
            story_response=artifacts_by_group(history, "story"),
            images_response=artifacts_by_group(history, "image"),
            final_image_response={"case_parse": case_parse_text},
            downloaded_assets=downloaded_assets,
            task_id=task_id,
            execution_stages=execution_stages,
        )

    @staticmethod
    def _failed_result(
        case: StoryCaseConfig,
        session_id: str,
        task_id: str,
        steps: List[StoryStepResult],
        error: str,
        execution_stages: List[Dict[str, Any]],
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
            task_id=task_id,
            execution_stages=execution_stages,
            error=error,
            failed_step=failed_step or _guess_failed_step(len(steps)),
        )


class ContentHubUpstreamError(RuntimeError):
    """内容中台上游 Agent 错误。"""

    def __init__(self, message: str, failed_step: str) -> None:
        """初始化上游错误。"""
        super().__init__(message)
        self.failed_step = failed_step


def _case_generation_message(case: StoryCaseConfig) -> str:
    """读取病例生成要求作为初始生成 message。"""
    return case.creative_brief.strip()


def _guess_content_type(path: Path) -> str:
    """根据文件扩展名推断 MIME 类型。"""
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def _guess_failed_step(completed_steps: int) -> str:
    """根据已完成步骤数猜测失败环节。"""
    steps = [
        "create_agent_task",
        "stream_agent_task",
        "get_agent_task_history",
        "download_artifacts",
    ]
    if completed_steps < len(steps):
        return steps[completed_steps]
    return "unknown"
