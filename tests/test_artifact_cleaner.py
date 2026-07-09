"""评估产物清理工具单元测试。"""

from __future__ import annotations

from pathlib import Path

from story_med.utils import artifact_cleaner
from story_med.utils.artifact_cleaner import should_clear_evaluation_artifacts, target_case_ids_for_cleanup


def test_should_clear_evaluation_artifacts_for_image_case_pipeline_all_cases() -> None:
    """验证全量图片病例生成运行会清空历史产物。"""
    env = {
        "STORY_MED_RUN_DEEPEVAL_PIPELINE": "true",
        "STORY_MED_DEEPEVAL_MODE": "image_case_pipeline",
    }

    assert should_clear_evaluation_artifacts(env) is True


def test_should_not_clear_evaluation_artifacts_for_specific_cases() -> None:
    """验证指定 case 运行不会触发全量清空。"""
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


def test_target_case_ids_for_cleanup_supports_multiple_delimiters() -> None:
    """验证单病例清理支持多分隔符解析。"""
    env = {
        "STORY_MED_RUN_DEEPEVAL_PIPELINE": "true",
        "STORY_MED_DEEPEVAL_MODE": "image_case_pipeline",
        "STORY_MED_CASE_IDS": "SM_001;SM_002|SM_003,SM_004",
    }

    assert target_case_ids_for_cleanup(env) == ["SM_001", "SM_002", "SM_003", "SM_004"]


def test_clear_case_evaluation_artifacts_removes_single_case_directories(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """验证单病例重跑前会清理该病例所有历史目录。"""
    monkeypatch.setattr(artifact_cleaner, "STORY_AUDITS_DIR", tmp_path / "temp")
    monkeypatch.setattr(artifact_cleaner, "ASSETS_DIR", tmp_path / "assets")
    monkeypatch.setattr(artifact_cleaner, "GENERATION_RUNS_DIR", tmp_path / "results" / "generation_runs")
    monkeypatch.setattr(artifact_cleaner, "EDIT_RUNS_DIR", tmp_path / "edit")
    monkeypatch.setattr(artifact_cleaner, "EDIT_AUDITS_DIR", tmp_path / "edit_dialogue")
    case_id = "SM_002"
    targets = [
        artifact_cleaner.STORY_AUDITS_DIR / case_id,
        artifact_cleaner.ASSETS_DIR / case_id,
        artifact_cleaner.GENERATION_RUNS_DIR / case_id,
        artifact_cleaner.EDIT_RUNS_DIR / case_id,
        artifact_cleaner.EDIT_AUDITS_DIR / case_id,
    ]
    for path in targets:
        path.mkdir(parents=True, exist_ok=True)
        (path / "stub.txt").write_text("x", encoding="utf-8")

    artifact_cleaner.clear_case_evaluation_artifacts(case_id)

    assert all(not path.exists() for path in targets)
