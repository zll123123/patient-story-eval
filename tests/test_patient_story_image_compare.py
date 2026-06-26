"""患者故事图片多模态评估测试。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from story_med.config.settings import DEFAULT_CASE_FILE
from story_med.config.vision_app_config import load_vision_config
from story_med.services.case_loader import load_story_cases
from story_med.services.image_compare_pipeline import (
    _build_success_report,
    run_case_latest_image_compare,
    run_latest_image_compare,
)


def test_latest_patient_story_images_compare() -> None:
    """评估最近一次真实链路生成的图片。"""
    if os.getenv("STORY_MED_RUN_IMAGE_COMPARE", "").lower() != "true":
        pytest.skip("需要设置 STORY_MED_RUN_IMAGE_COMPARE=true 才执行图片多模态评估")

    cases = load_story_cases()
    case = next(item for item in cases if item.case_id == os.getenv("STORY_MED_IMAGE_CASE_ID", "SM_001"))
    report = run_latest_image_compare(load_vision_config(), case)

    assert report["status"] in {"success", "blocked"}


def test_seed_cases_latest_images_compare() -> None:
    """批量评估各 case 最近一次真实链路生成的图片。"""
    if os.getenv("STORY_MED_RUN_IMAGE_COMPARE_BATCH", "").lower() != "true":
        pytest.skip("需要设置 STORY_MED_RUN_IMAGE_COMPARE_BATCH=true 才执行批量图片多模态评估")

    target_case_ids = {
        item.strip()
        for item in os.getenv("STORY_MED_CASE_IDS", "").split(",")
        if item.strip()
    }
    cases = load_story_cases()
    selected_cases = [case for case in cases if not target_case_ids or case.case_id in target_case_ids]
    assert selected_cases, "未找到需要执行图片评估的 case"

    config = load_vision_config()
    failures = []
    for case in selected_cases:
        report = run_case_latest_image_compare(config, case)
        if report["status"] not in {"success", "blocked"}:
            failures.append({"case_id": case.case_id, "status": report["status"]})

    assert not failures, failures


def test_build_success_report_writes_image_design_validation_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """验证图片设计审核结果单独落盘并参与总通过判断。"""
    from story_med.models.case_model import StoryCaseConfig
    from story_med.services import image_compare_pipeline as pipeline

    case = StoryCaseConfig(
        case_id="SM_TEST",
        description="test",
        creative_brief="brief",
        case_facts="facts",
        hard_rules={},
    )

    asset_dir = tmp_path / "assets" / case.case_id / "session-1"
    (asset_dir / "generate_images").mkdir(parents=True)
    (asset_dir / "generate_final_image").mkdir(parents=True)
    (asset_dir / "generate_images" / "generate_images_6_image_design.json").write_text(
        '{"illustrations":[{"id":1,"image_path":"a.png","source_text":"text"}]}',
        encoding="utf-8",
    )
    (asset_dir / "generate_images" / "generate_images_1_a.png").write_text("x", encoding="utf-8")
    (asset_dir / "generate_final_image" / "generate_final_image_1_index.png").write_text("x", encoding="utf-8")

    monkeypatch.setattr(pipeline, "RESULTS_DIR", tmp_path / "assets_root")
    monkeypatch.setattr(pipeline, "TMP_DIR", tmp_path / "tmp")
    monkeypatch.setattr(pipeline, "_read_image_design", lambda _: {"illustrations": [{"id": 1, "image_path": "a.png"}]})
    monkeypatch.setattr(pipeline, "_build_consistance_images_payload", lambda asset_dir, image_design: [{"local_path": "dummy.png"}])
    monkeypatch.setattr(
        pipeline,
        "_validate_image_design",
        lambda case, image_design: {"is_passed": False, "summary": "bad design", "issues": [{"issue_id": "1"}]},
    )
    monkeypatch.setattr(
        pipeline,
        "_validate_image_consistance",
        lambda config, asset_dir, image_design: {"is_passed": False, "summary": "bad", "issues": [{"issue_id": "2"}]},
    )
    monkeypatch.setattr(
        pipeline,
        "_compare_illustrations",
        lambda config, case, asset_dir, image_design: [{"result": {"overall_passed": True}}],
    )
    monkeypatch.setattr(
        pipeline,
        "_validate_final_image_layout",
        lambda config, case, asset_dir, image_design: {"status": "success", "is_passed": True, "summary": "ok", "issues": []},
    )
    monkeypatch.setattr(
        pipeline,
        "_compare_final_image",
        lambda config, case, asset_dir, image_design: {"result": {"overall_passed": True}},
    )

    class DummyConfig:
        pass

    report = _build_success_report(DummyConfig(), case, "session-1")

    validation_file = tmp_path / "tmp" / case.case_id / "image_design_validation.json"
    assert validation_file.exists()
    assert '"is_passed": false' in validation_file.read_text(encoding="utf-8")
    assert "image_design_validation" not in report
    assert report["overall_passed"] is True


def test_build_success_report_writes_image_consistance_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """验证图片一致性审核结果单独落盘。"""
    from story_med.models.case_model import StoryCaseConfig
    from story_med.services import image_compare_pipeline as pipeline

    case = StoryCaseConfig(
        case_id="SM_TEST",
        description="test",
        creative_brief="brief",
        case_facts="facts",
        hard_rules={},
    )

    monkeypatch.setattr(pipeline, "RESULTS_DIR", tmp_path / "assets_root")
    monkeypatch.setattr(pipeline, "TMP_DIR", tmp_path / "tmp")
    monkeypatch.setattr(pipeline, "_read_image_design", lambda _: {"illustrations": [{"id": 1, "image_path": "a.png"}]})
    monkeypatch.setattr(pipeline, "_build_consistance_images_payload", lambda asset_dir, image_design: [{"local_path": "dummy.png"}])
    monkeypatch.setattr(pipeline, "_validate_image_design", lambda case, image_design: {"is_passed": True, "summary": "ok", "issues": []})
    monkeypatch.setattr(
        pipeline,
        "_validate_image_consistance",
        lambda config, asset_dir, image_design: {"is_passed": False, "summary": "bad", "issues": [{"issue_id": "1"}]},
    )
    monkeypatch.setattr(
        pipeline,
        "_compare_illustrations",
        lambda config, case, asset_dir, image_design: [{"result": {"overall_passed": True}}],
    )
    monkeypatch.setattr(
        pipeline,
        "_validate_final_image_layout",
        lambda config, case, asset_dir, image_design: {"status": "success", "is_passed": True, "summary": "ok", "issues": []},
    )
    monkeypatch.setattr(
        pipeline,
        "_compare_final_image",
        lambda config, case, asset_dir, image_design: {"result": {"overall_passed": True}},
    )

    class DummyConfig:
        pass

    report = pipeline._build_success_report(DummyConfig(), case, "session-1")

    validation_file = tmp_path / "tmp" / case.case_id / "image_consistant_validation.json"
    assert validation_file.exists()
    assert '"is_passed": false' in validation_file.read_text(encoding="utf-8")
    assert "image_design_validation" not in report
    assert "image_consistant_validation" not in report


def test_build_success_report_writes_final_image_layout_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """验证最终长图结构审核结果单独落盘。"""
    from story_med.models.case_model import StoryCaseConfig
    from story_med.services import image_compare_pipeline as pipeline

    case = StoryCaseConfig(
        case_id="SM_TEST",
        description="test",
        creative_brief="brief",
        case_facts="facts",
        hard_rules={},
    )

    monkeypatch.setattr(pipeline, "RESULTS_DIR", tmp_path / "assets_root")
    monkeypatch.setattr(pipeline, "TMP_DIR", tmp_path / "tmp")
    monkeypatch.setattr(pipeline, "_read_image_design", lambda _: {"illustrations": [{"id": 1, "image_path": "a.png"}]})
    monkeypatch.setattr(pipeline, "_build_consistance_images_payload", lambda asset_dir, image_design: [{"local_path": "dummy.png"}])
    monkeypatch.setattr(pipeline, "_validate_image_design", lambda case, image_design: {"is_passed": True, "summary": "ok", "issues": []})
    monkeypatch.setattr(
        pipeline,
        "_validate_image_consistance",
        lambda config, asset_dir, image_design: {"is_passed": True, "summary": "ok", "issues": []},
    )
    monkeypatch.setattr(
        pipeline,
        "_validate_final_image_layout",
        lambda config, case, asset_dir, image_design: {"status": "success", "is_passed": False, "summary": "bad layout", "issues": [{"issue_id": "1"}]},
    )
    monkeypatch.setattr(
        pipeline,
        "_compare_illustrations",
        lambda config, case, asset_dir, image_design: [{"result": {"overall_passed": True}}],
    )
    monkeypatch.setattr(
        pipeline,
        "_compare_final_image",
        lambda config, case, asset_dir, image_design: {"result": {"overall_passed": True}},
    )

    class DummyConfig:
        pass

    pipeline._build_success_report(DummyConfig(), case, "session-1")

    validation_file = tmp_path / "tmp" / case.case_id / "final_image_layout_validation.json"
    assert validation_file.exists()
    assert '"is_passed": false' in validation_file.read_text(encoding="utf-8")


def test_validate_final_image_layout_uses_original_image(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """验证最终长图审核走原图直传，不走缩略图。"""
    from story_med.models.case_model import StoryCaseConfig
    from story_med.services import image_compare_pipeline as pipeline

    case = StoryCaseConfig(
        case_id="SM_TEST",
        description="test",
        creative_brief="brief",
        case_facts="facts",
        hard_rules={},
    )
    asset_dir = tmp_path / "assets"
    (asset_dir / "generate_final_image").mkdir(parents=True)
    (asset_dir / "generate_final_image" / "final.png").write_text("x", encoding="utf-8")
    prompt_file = tmp_path / "final_image_layout_validate.md"
    prompt_file.write_text("prompt", encoding="utf-8")

    captured: dict = {}

    monkeypatch.setattr(pipeline, "PROMPTS_DIR", tmp_path)
    monkeypatch.setattr(pipeline, "_find_single_image", lambda _: asset_dir / "generate_final_image" / "final.png")
    monkeypatch.setattr(
        pipeline,
        "call_multimodal_json",
        lambda config, prompt, image_paths, use_thumbnail=True: captured.update(
            {"use_thumbnail": use_thumbnail, "image_paths": image_paths}
        )
        or {"overall_passed": True},
    )

    class DummyConfig:
        pass

    result = pipeline._validate_final_image_layout(DummyConfig(), case, asset_dir, {"illustrations": []})

    assert captured["use_thumbnail"] is False
    assert result["status"] == "success"

