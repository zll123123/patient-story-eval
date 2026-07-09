"""患者故事生成结果调整流程。"""

from __future__ import annotations

from typing import Dict

from requests import Session

from story_med.clients.agent_api.agent_task_client import DEFAULT_AGENT_TYPE
from story_med.config.app_config import StoryMedConfig
from story_med.config.settings import ASSETS_DIR, EDIT_RUNS_DIR
from story_med.executors.patient_story_edit_executor import PatientStoryEditExecutor, detect_task_completed, extract_adjustment_files, extract_stream_errors
from story_med.utils.artifact_cleaner import clear_edit_case_artifacts


def run_story_adjustment(
    config: StoryMedConfig,
    case_id: str,
    session_id: str,
    task_id: str,
    message: str,
    agent_type: str = DEFAULT_AGENT_TYPE,
    session: Session | None = None,
) -> Dict[str, Any]:
    """执行已生成患者故事的自然语言调整节点。"""
    executor = PatientStoryEditExecutor(
        config=config,
        session=session,
        results_dir=EDIT_RUNS_DIR,
        assets_dir=ASSETS_DIR,
        clear_case_artifacts=clear_edit_case_artifacts,
    )
    return executor.run_adjustment(
        case_id=case_id,
        session_id=session_id,
        task_id=task_id,
        message=message,
        agent_type=agent_type,
    )
