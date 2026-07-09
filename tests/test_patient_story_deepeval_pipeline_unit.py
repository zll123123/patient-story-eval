"""患者故事 DeepEval 编排单元测试。"""

from __future__ import annotations

import pytest

from story_med.models.case_model import StoryCaseConfig
from story_med.services.story_generation_evaluation import patient_story_deepeval_pipeline as pipeline


def test_eval_mode_defaults_to_audit_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证默认模式为仅审核。"""
    monkeypatch.delenv("STORY_MED_DEEPEVAL_MODE", raising=False)

    assert pipeline._eval_mode() == "audit_only"


def test_eval_mode_rejects_invalid_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证非法模式会报错。"""
    monkeypatch.setenv("STORY_MED_DEEPEVAL_MODE", "bad_mode")

    with pytest.raises(ValueError):
        pipeline._eval_mode()


def test_eval_mode_accepts_image_case_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证支持病例图片解析链路模式。"""
    monkeypatch.setenv("STORY_MED_DEEPEVAL_MODE", "image_case_pipeline")

    assert pipeline._eval_mode() == "image_case_pipeline"


def test_selected_cases_filters_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证可按环境变量筛选 case。"""
    cases = [
        StoryCaseConfig(case_id="SM_001", description="", creative_brief="", case_facts="", hard_rules={}),
        StoryCaseConfig(case_id="SM_002", description="", creative_brief="", case_facts="", hard_rules={}),
        StoryCaseConfig(case_id="SM_003", description="", creative_brief="", case_facts="", hard_rules={}),
    ]
    monkeypatch.setenv("STORY_MED_CASE_IDS", "SM_001,SM_003")

    selected = pipeline._selected_cases(cases)

    assert [case.case_id for case in selected] == ["SM_001", "SM_003"]


def test_target_case_ids_supports_multiple_delimiters(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证 case 过滤支持多种分隔符。"""
    monkeypatch.setenv("STORY_MED_CASE_IDS", "SM_001;SM_002|SM_003,SM_004")

    assert pipeline._target_case_ids() == ["SM_001", "SM_002", "SM_003", "SM_004"]


def test_run_attribution_defaults_to_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证归因默认开启。"""
    monkeypatch.delenv("STORY_MED_RUN_AUDIT_ATTRIBUTION", raising=False)

    assert pipeline._run_attribution() is True
