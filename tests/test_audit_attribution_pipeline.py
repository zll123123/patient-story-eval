"""患者故事审核归因流水线单元测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from story_med.services.story_generation_evaluation import audit_analysis_service as pipeline


def test_run_case_audit_attribution_skips_when_all_audits_pass(tmp_path: Path) -> None:
    """验证全部审核通过时跳过归因。"""
    case_dir = tmp_path / "tmp" / "SM_TEST"
    _write_json(
        case_dir / "summary.json",
        {
            "case_id": "SM_TEST",
            "audit_overview": {
                "outline_passed": True,
                "story_passed": True,
                "image_design_passed": True,
                "image_consistency_passed": True,
                "image_fact_passed": True,
            },
        },
    )
    pipeline.STORY_AUDITS_DIR = case_dir.parent  # type: ignore[assignment]
    pipeline.refresh_case_summary = lambda case_id: json.loads((case_dir / "summary.json").read_text(encoding="utf-8"))  # type: ignore[assignment]

    result = pipeline.run_case_audit_attribution(_dummy_llm_config(), "SM_TEST")

    assert result["status"] == "skipped"
    assert result["failed_audits"] == []
    written = json.loads((case_dir / "audit_analysis.json").read_text(encoding="utf-8"))
    assert written["status"] == "skipped"


def test_run_case_audit_attribution_calls_model_when_any_audit_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证存在失败审核项时触发归因。"""
    case_dir = tmp_path / "tmp" / "SM_TEST"
    _write_json(
        case_dir / "summary.json",
        {
            "case_id": "SM_TEST",
            "audit_overview": {
                "outline_passed": False,
                "story_passed": True,
                "image_design_passed": True,
                "image_consistency_passed": False,
                "image_fact_passed": True,
            },
        },
    )
    _write_json(case_dir / "outline_hard_rule_compare.json", {"overall_passed": False, "field_results": {"outcome": {"passed": False}}})
    _write_json(case_dir / "image_consistency_validation.json", {"is_passed": False, "issues": [{"issue_id": "1"}]})
    prompt_file = tmp_path / "prompts" / "audit_analysis.md"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text("请归因", encoding="utf-8")

    pipeline.STORY_AUDITS_DIR = case_dir.parent  # type: ignore[assignment]
    pipeline.ATTRIBUTION_PROMPT_FILE = prompt_file  # type: ignore[assignment]

    captured: dict[str, str] = {}

    def fake_call_llm_json(config, prompt: str):
        captured["prompt"] = prompt
        return {"root_cause": "test"}

    monkeypatch.setattr(pipeline, "call_llm_json", fake_call_llm_json)
    monkeypatch.setattr(pipeline, "load_clinical_baseline", lambda case: "clinical baseline")
    monkeypatch.setattr(pipeline, "refresh_case_summary", lambda case_id: json.loads((case_dir / "summary.json").read_text(encoding="utf-8")))
    monkeypatch.setattr(
        pipeline,
        "_load_case",
        lambda case_id: type(
            "DummyCase",
            (),
            {
                "case_id": case_id,
                "image_dir": "case-images",
                "case_facts": "facts",
                "creative_brief": "brief",
            },
        )(),
    )
    monkeypatch.setattr(pipeline, "_load_intermediate_outputs", lambda case_id, session_id: {})

    result = pipeline.run_case_audit_attribution(_dummy_llm_config(), "SM_TEST")

    assert result["status"] == "success"
    assert result["failed_audits"] == ["outline_passed", "image_consistency_passed"]
    assert result["attribution"] == {"root_cause": "test"}
    assert "outline_passed" in captured["prompt"]
    assert "image_consistency_passed" in captured["prompt"]
    assert "clinical baseline" in captured["prompt"]
    written = json.loads((case_dir / "audit_analysis.json").read_text(encoding="utf-8"))
    assert written["status"] == "success"


def test_run_case_audit_attribution_refreshes_summary_before_skip_decision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证归因前会先刷新 summary，避免旧 summary 误判 skipped。"""
    case_dir = tmp_path / "tmp" / "SM_TEST"
    _write_json(case_dir / "summary.json", {"case_id": "SM_TEST"})
    _write_json(case_dir / "story_hard_rule_compare.json", {"overall_passed": False, "field_results": {"timeline": {"passed": False}}})
    prompt_file = tmp_path / "prompts" / "audit_analysis.md"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text("请归因", encoding="utf-8")

    pipeline.STORY_AUDITS_DIR = case_dir.parent  # type: ignore[assignment]
    pipeline.ATTRIBUTION_PROMPT_FILE = prompt_file  # type: ignore[assignment]

    monkeypatch.setattr(
        pipeline,
        "refresh_case_summary",
        lambda case_id: {
            "case_id": case_id,
            "session_id": "session-1",
            "audit_overview": {
                "outline_passed": True,
                "story_passed": False,
            },
        },
    )
    monkeypatch.setattr(pipeline, "load_clinical_baseline", lambda case: "clinical baseline")
    monkeypatch.setattr(
        pipeline,
        "_load_case",
        lambda case_id: type("DummyCase", (), {"case_id": case_id, "creative_brief": ""})(),
    )
    monkeypatch.setattr(pipeline, "_load_intermediate_outputs", lambda case_id, session_id: {})
    monkeypatch.setattr(pipeline, "call_llm_json", lambda config, prompt: {"ok": True})

    result = pipeline.run_case_audit_attribution(_dummy_llm_config(), "SM_TEST")

    assert result["status"] == "success"
    assert result["failed_audits"] == ["story_passed"]


def _write_json(path: Path, data: dict) -> None:
    """写入 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _dummy_llm_config():
    """构建最小 LLM 配置。"""
    from story_med.config.app_config import StoryMedLlmConfig

    return StoryMedLlmConfig(
        enabled=True,
        base_url="https://example.com",
        model="test-model",
        api_key="test-key",
        timeout_seconds=30,
    )
