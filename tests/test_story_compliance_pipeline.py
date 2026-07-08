"""Story 合规审核流水线单元测试。"""

from __future__ import annotations

import json
from pathlib import Path

from story_med.models.case_model import StoryCaseConfig
from story_med.services import story_compliance_pipeline as pipeline


def test_run_story_compliance_validation_writes_result(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """验证 Story 合规审核会读取 Story 并写入结果。"""
    case = StoryCaseConfig(
        case_id="SM_TEST",
        description="test",
        creative_brief="brief",
        image_dir="case-images",
        hard_rules={},
    )
    session_dir = tmp_path / "results" / "assets" / case.case_id / "session-1"
    story_dir = session_dir / "generate_story"
    story_dir.mkdir(parents=True)
    (story_dir / "story.md").write_text("患者故事正文", encoding="utf-8")
    prompt_file = tmp_path / "prompts" / "story_compliance_validate.md"
    prompt_file.parent.mkdir(parents=True)
    prompt_file.write_text("prompt", encoding="utf-8")
    _write_clinical_baseline(tmp_path, "case-images", "clinical baseline")
    captured: dict = {}

    monkeypatch.setattr(pipeline, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(pipeline, "TMP_DIR", tmp_path / "tmp")
    monkeypatch.setattr(pipeline, "STORY_COMPLIANCE_PROMPT_FILE", prompt_file)
    monkeypatch.setattr("story_med.services.clinical_extract_baseline_service.RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(
        pipeline,
        "call_llm_json",
        lambda config, prompt: _capture_prompt(captured, prompt),
    )

    result = pipeline.run_story_compliance_validation(object(), case)

    output_path = tmp_path / "tmp" / case.case_id / "story_compliance_validation.json"
    assert output_path.exists()
    assert result["is_passed"] is True
    assert result["session_id"] == "session-1"
    assert "患者故事正文" in captured["prompt"]
    assert "clinical baseline" in captured["prompt"]
    assert json.loads(output_path.read_text(encoding="utf-8"))["summary"] == "ok"


def test_run_story_compliance_validation_blocks_when_missing_story(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """验证缺少 Story 产物时写入阻塞结果。"""
    case = StoryCaseConfig(case_id="SM_TEST", description="test", creative_brief="", hard_rules={})

    monkeypatch.setattr(pipeline, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(pipeline, "TMP_DIR", tmp_path / "tmp")

    result = pipeline.run_story_compliance_validation(object(), case)

    assert result["status"] == "blocked"
    assert result["is_passed"] is False
    assert (tmp_path / "tmp" / case.case_id / "story_compliance_validation.json").exists()


def _write_clinical_baseline(tmp_path: Path, image_dir: str, text: str) -> None:
    """写入测试用病例基准文件。"""
    baseline_path = tmp_path / "output" / image_dir / "clinical_extract.md"
    baseline_path.parent.mkdir(parents=True)
    baseline_path.write_text(text, encoding="utf-8")


def _capture_prompt(captured: dict, prompt: str) -> dict:
    """记录提示词并返回模型结果。"""
    captured["prompt"] = prompt
    return {"is_passed": True, "summary": "ok", "issues": []}
