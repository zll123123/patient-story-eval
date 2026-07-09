"""患者故事图片多模态评估测试。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from story_med.config.app_config import load_vision_config
from story_med.services.clinical_case_preparation.yaml_case_service import load_story_cases
from story_med.services.story_generation_evaluation.image_audit_pipeline import (
    _build_success_report,
    run_case_latest_image_audit,
    run_latest_image_audit,
)


def test_latest_patient_story_images_compare() -> None:
    """评估最近一次真实链路生成的图片。"""
    if os.getenv("STORY_MED_RUN_IMAGE_COMPARE", "").lower() != "true":
        pytest.skip("需要设置 STORY_MED_RUN_IMAGE_COMPARE=true 才执行图片多模态评估")

    cases = load_story_cases()
    case = next(item for item in cases if item.case_id == os.getenv("STORY_MED_IMAGE_CASE_ID", "SM_001"))
    report = run_latest_image_audit(load_vision_config(), case)

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
        report = run_case_latest_image_audit(config, case)
        if report["status"] not in {"success", "blocked"}:
            failures.append({"case_id": case.case_id, "status": report["status"]})

    assert not failures, failures


def test_build_success_report_writes_image_design_validation_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """验证图片设计审核结果单独落盘并参与总通过判断。"""
    from story_med.models.case_model import StoryCaseConfig
    from story_med.services.story_generation_evaluation import image_audit_pipeline as pipeline

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
    monkeypatch.setattr(pipeline, "STORY_AUDITS_DIR", tmp_path / "tmp")
    monkeypatch.setattr(pipeline, "_read_image_design", lambda _: {"illustrations": [{"id": 1, "image_path": "a.png"}]})
    monkeypatch.setattr(pipeline, "_build_consistency_images_payload", lambda asset_dir, image_design: [{"local_path": "dummy.png"}])
    monkeypatch.setattr(
        pipeline,
        "_validate_image_design",
        lambda case, asset_dir, image_design: {"is_passed": False, "summary": "bad design", "issues": [{"issue_id": "1"}]},
    )
    monkeypatch.setattr(
        pipeline,
        "_audit_image_consistency",
        lambda config, asset_dir, image_design: {"is_passed": False, "summary": "bad", "issues": [{"issue_id": "2"}]},
    )
    monkeypatch.setattr(
        pipeline,
        "_compare_illustrations",
        lambda config, case, asset_dir, image_design: [{"result": {"overall_passed": True}}],
    )
    monkeypatch.setattr(
        pipeline,
        "validate_final_image_layout",
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


def test_build_success_report_writes_image_consistency_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """验证图片一致性审核结果单独落盘。"""
    from story_med.models.case_model import StoryCaseConfig
    from story_med.services.story_generation_evaluation import image_audit_pipeline as pipeline

    case = StoryCaseConfig(
        case_id="SM_TEST",
        description="test",
        creative_brief="brief",
        case_facts="facts",
        hard_rules={},
    )

    monkeypatch.setattr(pipeline, "RESULTS_DIR", tmp_path / "assets_root")
    monkeypatch.setattr(pipeline, "STORY_AUDITS_DIR", tmp_path / "tmp")
    monkeypatch.setattr(pipeline, "_read_image_design", lambda _: {"illustrations": [{"id": 1, "image_path": "a.png"}]})
    monkeypatch.setattr(pipeline, "_build_consistency_images_payload", lambda asset_dir, image_design: [{"local_path": "dummy.png"}])
    monkeypatch.setattr(pipeline, "_validate_image_design", lambda case, asset_dir, image_design: {"is_passed": True, "summary": "ok", "issues": []})
    monkeypatch.setattr(
        pipeline,
        "_audit_image_consistency",
        lambda config, asset_dir, image_design: {"is_passed": False, "summary": "bad", "issues": [{"issue_id": "1"}]},
    )
    monkeypatch.setattr(
        pipeline,
        "_compare_illustrations",
        lambda config, case, asset_dir, image_design: [{"result": {"overall_passed": True}}],
    )
    monkeypatch.setattr(
        pipeline,
        "validate_final_image_layout",
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

    validation_file = tmp_path / "tmp" / case.case_id / "image_consistency_validation.json"
    assert validation_file.exists()
    assert '"is_passed": false' in validation_file.read_text(encoding="utf-8")
    assert "image_design_validation" not in report
    assert "image_consistency_validation" not in report


def test_build_success_report_writes_final_image_layout_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """验证最终长图结构审核结果单独落盘。"""
    from story_med.models.case_model import StoryCaseConfig
    from story_med.services.story_generation_evaluation import image_audit_pipeline as pipeline

    case = StoryCaseConfig(
        case_id="SM_TEST",
        description="test",
        creative_brief="brief",
        case_facts="facts",
        hard_rules={},
    )

    monkeypatch.setattr(pipeline, "RESULTS_DIR", tmp_path / "assets_root")
    monkeypatch.setattr(pipeline, "STORY_AUDITS_DIR", tmp_path / "tmp")
    monkeypatch.setattr(pipeline, "_read_image_design", lambda _: {"illustrations": [{"id": 1, "image_path": "a.png"}]})
    monkeypatch.setattr(pipeline, "_build_consistency_images_payload", lambda asset_dir, image_design: [{"local_path": "dummy.png"}])
    monkeypatch.setattr(pipeline, "_validate_image_design", lambda case, asset_dir, image_design: {"is_passed": True, "summary": "ok", "issues": []})
    monkeypatch.setattr(
        pipeline,
        "_audit_image_consistency",
        lambda config, asset_dir, image_design: {"is_passed": True, "summary": "ok", "issues": []},
    )
    monkeypatch.setattr(
        pipeline,
        "validate_final_image_layout",
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
    from story_med.services.story_generation_evaluation import final_image_layout_audit_service as pipeline

    case = StoryCaseConfig(
        case_id="SM_TEST",
        description="test",
        creative_brief="brief",
        image_dir="case-images",
        case_facts="facts",
        hard_rules={},
    )
    asset_dir = tmp_path / "assets"
    (asset_dir / "generate_final_image").mkdir(parents=True)
    (asset_dir / "generate_final_image" / "final.png").write_text("x", encoding="utf-8")
    prompt_file = tmp_path / "final_image_layout_validate.md"
    prompt_file.write_text("prompt", encoding="utf-8")
    _write_clinical_baseline(tmp_path, "case-images", "clinical baseline")

    captured: dict = {}

    monkeypatch.setattr(pipeline, "PROMPTS_DIR", tmp_path)
    monkeypatch.setattr(
        "story_med.services.clinical_case_preparation.clinical_extract_baseline_service.BASELINES_DIR",
        tmp_path / "baselines",
    )
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

    result = pipeline.validate_final_image_layout(DummyConfig(), case, asset_dir, {"illustrations": []})

    assert captured["use_thumbnail"] is False
    assert result["status"] == "success"


def test_build_image_prompt_only_uses_patient_case_and_images(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """验证单张图片事实审核不再注入图片设计细节。"""
    from story_med.models.case_model import StoryCaseConfig
    from story_med.services.story_generation_evaluation import image_audit_pipeline as pipeline

    case = StoryCaseConfig(
        case_id="SM_TEST",
        description="test",
        creative_brief="brief",
        image_dir="case-images",
        case_facts="facts",
        hard_rules={},
    )
    _write_clinical_baseline(tmp_path, "case-images", "clinical baseline")
    monkeypatch.setattr(
        "story_med.services.clinical_case_preparation.clinical_extract_baseline_service.BASELINES_DIR",
        tmp_path / "baselines",
    )
    prompt = pipeline._build_image_prompt(
        case,
        {
            "id": 3,
            "source_text": "source text",
            "composition": "短发背影",
            "prompt": "prompt text",
        },
    )

    assert '"patient_case": "clinical baseline"' in prompt
    assert '"images"' in prompt
    assert '"image_id": 3' in prompt
    assert '"source_text": "source text"' in prompt
    assert '"expected_image"' not in prompt
    assert '"composition": "短发背影"' not in prompt


def test_compare_final_image_only_uses_patient_case_and_images(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """验证最终长图事实审核不再注入 image_design。"""
    from story_med.models.case_model import StoryCaseConfig
    from story_med.services.story_generation_evaluation import image_audit_pipeline as pipeline

    case = StoryCaseConfig(
        case_id="SM_TEST",
        description="test",
        creative_brief="brief",
        image_dir="case-images",
        case_facts="facts",
        hard_rules={},
    )
    _write_clinical_baseline(tmp_path, "case-images", "clinical baseline")
    asset_dir = tmp_path / "assets"
    (asset_dir / "generate_final_image").mkdir(parents=True)
    final_path = asset_dir / "generate_final_image" / "final.png"
    final_path.write_text("x", encoding="utf-8")
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "story_med.services.clinical_case_preparation.clinical_extract_baseline_service.BASELINES_DIR",
        tmp_path / "baselines",
    )
    monkeypatch.setattr(pipeline, "_find_single_image", lambda _: final_path)
    monkeypatch.setattr(
        pipeline,
        "call_multimodal_json",
        lambda config, prompt, image_paths: captured.update(
            {"prompt": prompt, "image_paths": image_paths}
        )
        or {"overall_passed": True},
    )

    class DummyConfig:
        pass

    result = pipeline._compare_final_image(DummyConfig(), case, asset_dir, {"illustrations": [{"composition": "短发"}]})

    assert result["result"]["overall_passed"] is True
    assert '"patient_case": "clinical baseline"' in str(captured["prompt"])
    assert '"images"' in str(captured["prompt"])
    assert '"image_type": "final_composite"' in str(captured["prompt"])
    assert '"image_design"' not in str(captured["prompt"])


def test_build_image_prompt_prefers_clinical_extract(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """验证图片事实审核优先使用 clinical_extract.md 作为病例基准。"""
    from story_med.models.case_model import StoryCaseConfig
    from story_med.services.clinical_case_preparation import clinical_extract_baseline_service as clinical_baseline
    from story_med.services.story_generation_evaluation import image_audit_pipeline as pipeline

    baseline_file = tmp_path / "baselines" / "case-images" / "clinical_extract.md"
    baseline_file.parent.mkdir(parents=True)
    baseline_file.write_text("clinical baseline", encoding="utf-8")
    monkeypatch.setattr(clinical_baseline, "BASELINES_DIR", tmp_path / "baselines")

    case = StoryCaseConfig(
        case_id="SM_TEST",
        description="test",
        creative_brief="brief",
        image_dir="case-images",
        case_facts="facts",
        hard_rules={},
    )

    prompt = pipeline._build_image_prompt(case, {"id": 1, "source_text": "source"})

    assert '"patient_case": "clinical baseline"' in prompt


def _write_clinical_baseline(tmp_path: Path, image_dir: str, content: str) -> None:
    """写入测试用病例基准文件。"""
    baseline_file = tmp_path / "baselines" / image_dir / "clinical_extract.md"
    baseline_file.parent.mkdir(parents=True, exist_ok=True)
    baseline_file.write_text(content, encoding="utf-8")
