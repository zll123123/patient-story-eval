"""评估产物清理工具单元测试。"""

from __future__ import annotations

from story_med.utils.artifact_cleaner import should_clear_evaluation_artifacts


def test_should_clear_evaluation_artifacts_for_full_pipeline_all_cases() -> None:
    """验证全量生成运行会清空历史产物。"""
    env = {
        "STORY_MED_RUN_DEEPEVAL_PIPELINE": "true",
        "STORY_MED_DEEPEVAL_MODE": "image_case_pipeline",
    }

    assert should_clear_evaluation_artifacts(env) is True


def test_should_not_clear_evaluation_artifacts_for_specific_cases() -> None:
    """验证指定 case 运行不会清空历史产物。"""
    env = {
        "STORY_MED_RUN_DEEPEVAL_PIPELINE": "true",
        "STORY_MED_DEEPEVAL_MODE": "image_case_pipeline",
        "STORY_MED_CASE_IDS": "SM_003,SM_004",
    }

    assert should_clear_evaluation_artifacts(env) is False


def test_should_not_clear_evaluation_artifacts_for_audit_only() -> None:
    """验证仅审核模式不会清空历史产物。"""
    env = {
        "STORY_MED_RUN_DEEPEVAL_PIPELINE": "true",
        "STORY_MED_DEEPEVAL_MODE": "audit_only",
    }

    assert should_clear_evaluation_artifacts(env) is False

