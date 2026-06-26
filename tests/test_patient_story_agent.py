"""患者故事 agent 真实链路测试。"""

from __future__ import annotations

from pathlib import Path

from story_med.adapters.patient_story_agent import PatientStoryAgentAdapter
from story_med.config.app_config import load_app_config
from story_med.config.settings import BASE_DIR, DEFAULT_CONFIG_FILE
from story_med.services.case_loader import load_story_cases
from story_med.services.result_writer import write_run_result


def test_patient_story_agent_smoke() -> None:
    """执行一条患者故事真实链路并落盘结果。"""
    config = load_app_config(DEFAULT_CONFIG_FILE)
    cases = load_story_cases()
    assert cases, "患者故事测试数据为空"

    adapter = PatientStoryAgentAdapter(config)
    result = adapter.run_case(cases[0])
    result_path = Path(config.result_file)
    if not result_path.is_absolute():
        result_path = BASE_DIR / result_path
    write_run_result(result, result_path)

    assert result.case_id == cases[0].case_id
    assert result.session_id
    assert len(result.steps) == 5
    assert result.session_response
    assert result.outline_response
    assert result.story_response
    assert result.images_response
    assert result.final_image_response
    assert isinstance(result.downloaded_assets, list)
