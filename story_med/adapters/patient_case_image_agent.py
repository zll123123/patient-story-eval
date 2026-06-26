"""病例图片解析版患者故事 agent 适配层。"""

from __future__ import annotations

import mimetypes
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Dict, List

from loguru import logger
from requests import Session

from story_med.clients.patient_case_client import (
    create_download_url,
    create_patient_case_task,
    create_upload_url,
    download_signed_file,
    get_patient_case_history,
    stream_patient_case_task,
    upload_file,
)
from story_med.clients.story_client import StoryApiResponse, create_session, extract_session_id
from story_med.config.app_config import StoryMedConfig
from story_med.config.settings import ASSETS_DIR, TMP_DIR
from story_med.models.case_model import StoryAgentRunResult, StoryCaseConfig, StoryStepResult
from story_med.services.case_image_input import list_case_images


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
        try:
            uploaded_files = self._upload_case_images(case)
            task_payload = {"message": "", "files": uploaded_files}
            task_api, task_timing = self._timed_call(
                lambda: create_patient_case_task(self._session, self._config, task_payload)
            )
            session_id = extract_session_id(task_api.body)
            steps.append(
                self._step(
                    "create_patient_case_task",
                    "/api/patient_case/tasks",
                    task_payload,
                    task_api,
                    session_id,
                    task_timing,
                )
            )

            start_payload = {"session_id": session_id, **task_payload}
            stream_api, stream_timing = self._timed_call(
                lambda: self._stream_task(case.case_id, session_id, start_payload)
            )
            steps.append(
                self._step(
                    "start_patient_case_task",
                    "/api/patient_case/tasks/start",
                    start_payload,
                    stream_api,
                    session_id,
                    stream_timing,
                )
            )

            history_api, history_timing = self._timed_call(
                lambda: get_patient_case_history(self._session, self._config, session_id)
            )
            steps.append(
                self._step(
                    "get_patient_case_history",
                    f"/api/patient_case/tasks/{session_id}/history",
                    {},
                    history_api,
                    session_id,
                    history_timing,
                )
            )
            downloaded_assets = self._download_history_artifacts(case.case_id, session_id, history_api.body)
            return self._success_result(case, session_id, steps, history_api.body, downloaded_assets, started_at, started_perf)
        except Exception as exc:
            logger.exception("图片病例患者故事 case 执行失败: {}", case.case_id)
            return self._failed_result(case, session_id, steps, str(exc), started_at, started_perf)

    def _upload_case_images(self, case: StoryCaseConfig) -> List[Dict[str, str]]:
        """上传当前 case 目录下的全部病例图片。"""
        files: List[Dict[str, str]] = []
        for image_path in list_case_images(case.case_id):
            upload_info = create_upload_url(self._session, self._config, image_path.name)
            content_type = str(upload_info.get("content_type") or _guess_content_type(image_path))
            upload_file(str(upload_info["upload_url"]), image_path, content_type, self._config)
            files.append({"file_name": image_path.name, "file_key": str(upload_info["file_key"])})
        return files

    def _stream_task(self, case_id: str, session_id: str, payload: Dict[str, Any]) -> StoryApiResponse:
        """启动 SSE 任务并返回摘要响应。"""
        output_path = TMP_DIR / case_id / f"{session_id}_patient_case_stream.txt"
        body = stream_patient_case_task(self._session, self._config, payload, output_path)
        return StoryApiResponse(status_code=int(body["status_code"]), body=body, data=body)

    def _download_history_artifacts(
        self,
        case_id: str,
        session_id: str,
        history: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """下载 history 中的全部交付物。"""
        results: List[Dict[str, Any]] = []
        for item in _iter_artifacts(history):
            step_name = _artifact_step_name(item["group"], item["artifact"])
            output_path = ASSETS_DIR / case_id / session_id / step_name / Path(item["file_key"]).name
            download_info = create_download_url(self._session, self._config, item["file_key"])
            downloaded = download_signed_file(str(download_info["download_url"]), output_path, self._config)
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
            session_response={"session_id": session_id},
            outline_response=_artifacts_by_group(history, "outline"),
            story_response=_artifacts_by_group(history, "story"),
            images_response=_artifacts_by_group(history, "image"),
            final_image_response=_artifacts_by_group(history, "final_image"),
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
            failed_step=_guess_failed_step(len(steps)),
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


def _guess_content_type(path: Path) -> str:
    """根据文件扩展名推断 MIME 类型。"""
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def _guess_failed_step(completed_steps: int) -> str:
    """根据已完成步骤数猜测失败环节。"""
    steps = ["create_patient_case_task", "start_patient_case_task", "get_patient_case_history", "download_artifacts"]
    if completed_steps < len(steps):
        return steps[completed_steps]
    return "unknown"
