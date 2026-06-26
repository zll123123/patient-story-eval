"""患者故事 agent 适配层。"""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Dict, List

from loguru import logger
from requests import Session

from story_med.clients.story_client import (
    StoryApiResponse,
    create_session,
    extract_session_id,
    post_json,
)
from story_med.config.app_config import StoryMedConfig
from story_med.config.settings import ASSETS_DIR
from story_med.models.case_model import StoryAgentRunResult, StoryCaseConfig, StoryStepResult
from story_med.services.asset_downloader import download_assets


class PatientStoryAgentAdapter:
    """封装患者故事 5 步链路。"""

    def __init__(self, config: StoryMedConfig, session: Session | None = None) -> None:
        """初始化适配器。"""
        self._config = config
        self._session = session or create_session()

    def run_case(self, case: StoryCaseConfig) -> StoryAgentRunResult:
        """执行单条患者故事用例。"""
        return self._run_case(case, include_visual_steps=True)

    def run_case_until_story(self, case: StoryCaseConfig) -> StoryAgentRunResult:
        """执行到故事正文生成步骤。"""
        return self._run_case(case, include_visual_steps=False)

    def _run_case(self, case: StoryCaseConfig, include_visual_steps: bool) -> StoryAgentRunResult:
        """执行患者故事用例。"""
        run_started_at = self._now_iso()
        run_started_perf = perf_counter()
        steps: List[StoryStepResult] = []
        session_response: Dict[str, Any] = {}
        outline_response: Dict[str, Any] = {}
        story_response: Dict[str, Any] = {}
        images_response: Dict[str, Any] = {}
        final_image_response: Dict[str, Any] = {}
        downloaded_assets: List[Dict[str, Any]] = []
        session_id = ""

        try:
            session_api, session_started_at, session_finished_at, session_duration = self._timed_call(
                lambda: self._create_session_step(case)
            )
            session_response = session_api.body
            session_id = extract_session_id(session_api.body)
            steps.append(
                self._build_step_result(
                    step_name="create_session",
                    endpoint="/api/session",
                    request_payload={},
                    response=session_api,
                    session_id=session_id,
                    started_at=session_started_at,
                    finished_at=session_finished_at,
                    duration_seconds=session_duration,
                )
            )

            outline_api, outline_started_at, outline_finished_at, outline_duration = self._timed_call(
                lambda: self._generate_outline_step(case, session_id)
            )
            outline_response = outline_api.body
            outline_assets = self._download_step_assets(case, session_id, "generate_outline", outline_response)
            downloaded_assets.extend(outline_assets)
            steps.append(
                self._build_step_result(
                    step_name="generate_outline",
                    endpoint=f"/api/{session_id}/outline",
                    request_payload=self._build_story_payload(case),
                    response=outline_api,
                    session_id=session_id,
                    started_at=outline_started_at,
                    finished_at=outline_finished_at,
                    duration_seconds=outline_duration,
                    downloaded_assets=outline_assets,
                )
            )

            story_api, story_started_at, story_finished_at, story_duration = self._timed_call(
                lambda: self._generate_story_step(case, session_id)
            )
            story_response = story_api.body
            story_assets = self._download_step_assets(case, session_id, "generate_story", story_response)
            downloaded_assets.extend(story_assets)
            steps.append(
                self._build_step_result(
                    step_name="generate_story",
                    endpoint=f"/api/{session_id}/story",
                    request_payload=self._build_story_payload(case),
                    response=story_api,
                    session_id=session_id,
                    started_at=story_started_at,
                    finished_at=story_finished_at,
                    duration_seconds=story_duration,
                    downloaded_assets=story_assets,
                )
            )
            if not include_visual_steps:
                return StoryAgentRunResult(
                    case_id=case.case_id,
                    description=case.description,
                    session_id=session_id,
                    success=True,
                    steps=steps,
                    session_response=session_response,
                    outline_response=outline_response,
                    story_response=story_response,
                    images_response=images_response,
                    final_image_response=final_image_response,
                    downloaded_assets=downloaded_assets,
                    started_at=run_started_at,
                    finished_at=self._now_iso(),
                    total_duration_seconds=round(perf_counter() - run_started_perf, 3),
                )

            images_api, images_started_at, images_finished_at, images_duration = self._timed_call(
                lambda: self._generate_images_step(session_id)
            )
            images_response = images_api.body
            image_assets = self._download_step_assets(case, session_id, "generate_images", images_response)
            downloaded_assets.extend(image_assets)
            steps.append(
                self._build_step_result(
                    step_name="generate_images",
                    endpoint=f"/api/{session_id}/images",
                    request_payload={},
                    response=images_api,
                    session_id=session_id,
                    started_at=images_started_at,
                    finished_at=images_finished_at,
                    duration_seconds=images_duration,
                    downloaded_assets=image_assets,
                )
            )

            final_image_api, final_started_at, final_finished_at, final_duration = self._timed_call(
                lambda: self._generate_final_image_step(session_id)
            )
            final_image_response = final_image_api.body
            final_assets = self._download_step_assets(case, session_id, "generate_final_image", final_image_response)
            downloaded_assets.extend(final_assets)
            steps.append(
                self._build_step_result(
                    step_name="generate_final_image",
                    endpoint=f"/api/{session_id}/generate",
                    request_payload={},
                    response=final_image_api,
                    session_id=session_id,
                    started_at=final_started_at,
                    finished_at=final_finished_at,
                    duration_seconds=final_duration,
                    downloaded_assets=final_assets,
                )
            )
            return StoryAgentRunResult(
                case_id=case.case_id,
                description=case.description,
                session_id=session_id,
                success=True,
                steps=steps,
                session_response=session_response,
                outline_response=outline_response,
                story_response=story_response,
                images_response=images_response,
                final_image_response=final_image_response,
                downloaded_assets=downloaded_assets,
                started_at=run_started_at,
                finished_at=self._now_iso(),
                total_duration_seconds=round(perf_counter() - run_started_perf, 3),
            )
        except Exception as exc:
            logger.exception("患者故事 case 执行失败: {}", case.case_id)
            return StoryAgentRunResult(
                case_id=case.case_id,
                description=case.description,
                session_id=session_id,
                success=False,
                steps=steps,
                session_response=session_response,
                outline_response=outline_response,
                story_response=story_response,
                images_response=images_response,
                final_image_response=final_image_response,
                downloaded_assets=downloaded_assets,
                started_at=run_started_at,
                finished_at=self._now_iso(),
                total_duration_seconds=round(perf_counter() - run_started_perf, 3),
                error=str(exc),
                failed_step=self._guess_failed_step(len(steps)),
            )

    def _create_session_step(self, case: StoryCaseConfig) -> StoryApiResponse:
        """创建会话。"""
        del case
        return post_json(self._session, self._config, "/api/session", {})

    def _generate_outline_step(self, case: StoryCaseConfig, session_id: str) -> StoryApiResponse:
        """生成大纲。"""
        return post_json(
            self._session,
            self._config,
            f"/api/{session_id}/outline",
            self._build_story_payload(case),
        )

    def _generate_story_step(self, case: StoryCaseConfig, session_id: str) -> StoryApiResponse:
        """生成正文。"""
        return post_json(
            self._session,
            self._config,
            f"/api/{session_id}/story",
            self._build_story_payload(case),
        )

    def _generate_images_step(self, session_id: str) -> StoryApiResponse:
        """生成图片。"""
        return post_json(self._session, self._config, f"/api/{session_id}/images", {})

    def _generate_final_image_step(self, session_id: str) -> StoryApiResponse:
        """生成最终图片。"""
        return post_json(self._session, self._config, f"/api/{session_id}/generate", {})

    @staticmethod
    def _build_story_payload(case: StoryCaseConfig) -> Dict[str, Any]:
        """构建大纲生成请求体。"""
        return {
            "creative_brief": case.creative_brief,
            "case_facts": case.case_parse or case.case_facts,
        }

    def _download_step_assets(
        self,
        case: StoryCaseConfig,
        session_id: str,
        step_name: str,
        response_body: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """下载当前步骤返回的资源链接。"""
        output_dir = ASSETS_DIR / case.case_id / session_id / step_name
        return download_assets(response_body, output_dir, self._config, step_name)

    @staticmethod
    def _build_step_result(
        step_name: str,
        endpoint: str,
        request_payload: Dict[str, Any],
        response: StoryApiResponse,
        session_id: str,
        started_at: str,
        finished_at: str,
        duration_seconds: float,
        downloaded_assets: List[Dict[str, Any]] | None = None,
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
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
            downloaded_assets=downloaded_assets or [],
        )

    @staticmethod
    def _timed_call(func: Any) -> tuple[StoryApiResponse, str, str, float]:
        """执行接口调用并记录耗时。"""
        started_at = PatientStoryAgentAdapter._now_iso()
        started_perf = perf_counter()
        response = func()
        finished_at = PatientStoryAgentAdapter._now_iso()
        duration_seconds = round(perf_counter() - started_perf, 3)
        return response, started_at, finished_at, duration_seconds

    @staticmethod
    def _now_iso() -> str:
        """返回 ISO 格式 UTC 时间。"""
        return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _guess_failed_step(step_count: int) -> str:
        """根据已完成步骤数推测失败位置。"""
        step_names = [
            "create_session",
            "generate_outline",
            "generate_story",
            "generate_images",
            "generate_final_image",
        ]
        if step_count < len(step_names):
            return step_names[step_count]
        return "unknown"
