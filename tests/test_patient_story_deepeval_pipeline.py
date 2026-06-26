"""患者故事 Deepeval 双模式评估入口。"""

from __future__ import annotations

import json
import os
from typing import List

import pytest

from story_med.services.patient_story_deepeval_pipeline import run_single_case, _selected_cases, _eval_mode, _include_visual_steps, _run_attribution, _target_case_ids
from story_med.config.llm_app_config import load_llm_config
from story_med.config.app_config import load_app_config
from story_med.config.vision_app_config import load_vision_config
from story_med.config.settings import DEFAULT_CONFIG_FILE
from story_med.services.case_loader import load_story_cases
from story_med.adapters.patient_case_image_agent import PatientCaseImageAgentAdapter
from story_med.adapters.patient_story_agent import PatientStoryAgentAdapter
from story_med.evals.patient_story_deepeval_metrics import build_patient_story_metrics
from deepeval import assert_test
from deepeval.test_case.llm_test_case import LLMTestCase


def _selected_case_ids() -> List[str]:
    """按环境变量选择需要执行的 case_id 列表。"""
    cases = load_story_cases()
    selected_cases = _selected_cases(cases)
    return [case.case_id for case in selected_cases]


def _build_deepeval_test_case(case_id: str, summary: dict) -> LLMTestCase:
    """构造 Deepeval 可识别的单 case 测试对象。"""
    actual_output = json.dumps(summary, ensure_ascii=False, sort_keys=True)
    return LLMTestCase(input=case_id, actual_output=actual_output, expected_output=actual_output, name=case_id)


@pytest.mark.parametrize("case_id", _selected_case_ids(), ids=str)
def test_patient_story_deepeval_pipeline(case_id: str) -> None:
    """按模式执行单个患者故事评估并写入统一汇总。"""
    if os.getenv("STORY_MED_RUN_DEEPEVAL_PIPELINE", "").lower() != "true":
        pytest.skip("需要设置 STORY_MED_RUN_DEEPEVAL_PIPELINE=true 才执行 Deepeval 评估")

    cases = {case.case_id: case for case in load_story_cases()}
    case = cases.get(case_id)
    assert case is not None, f"未找到需要执行的 case: {case_id}"

    llm_config = load_llm_config()
    vision_config = load_vision_config()
    app_config = load_app_config(DEFAULT_CONFIG_FILE)
    adapter = PatientStoryAgentAdapter(app_config)
    image_adapter = PatientCaseImageAgentAdapter(app_config)
    result = run_single_case(
        adapter=adapter,
        image_adapter=image_adapter,
        llm_config=llm_config,
        vision_config=vision_config,
        case=case,
        mode=_eval_mode(),
        include_visual_steps=_include_visual_steps(),
        run_attribution=_run_attribution(),
    )

    assert_test(
        test_case=_build_deepeval_test_case(case_id=case_id, summary=result["summary"]),
        metrics=build_patient_story_metrics(),
        run_async=False,
    )
