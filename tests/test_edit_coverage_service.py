"""患者故事编辑覆盖共享服务单元测试。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from story_med.services.story_edit_evaluation import edit_coverage_service as service


class FakeLlmConfig:
    """模拟 LLM 配置对象。"""


def test_evaluate_edit_coverage_uses_final_html_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证编辑审核只基于最终长图 HTML。"""
    monkeypatch.setattr(service, "ASSETS_DIR", tmp_path / "assets")
    monkeypatch.setattr(service, "EDIT_COVERAGE_PROMPT_FILE", _write_prompt(tmp_path))
    _write_text(tmp_path / "assets/SM_001/session-1/generate_final_image/index_old.html", "old html")
    html_path = tmp_path / "assets/EC_001/session-1/adjustment/index_new.html"
    _write_text(html_path, "new html with company")
    adjustment_result = {"downloaded_assets": [{"type": "html", "local_path": str(html_path)}]}
    calls: list[str] = []

    def fake_call_llm_text(_config: Any, prompt: str) -> str:
        calls.append(prompt)
        return "Score: 9\nPass: true\nReason: html ok\nEvidence: company"

    monkeypatch.setattr(service, "call_llm_text", fake_call_llm_text)
    result = service.evaluate_edit_coverage(
        FakeLlmConfig(),
        _edit_case(),
        "session-1",
        adjustment_result,
        "fallback input",
        "fallback output",
    )

    assert result["passed"] is True
    assert result["required_nodes"] == ["html"]
    assert "new html with company" in calls[0]
    assert "old html" not in calls[0]


def test_evaluate_edit_coverage_returns_missing_html_when_only_story_exists(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证缺少最终长图时直接返回失败。"""
    monkeypatch.setattr(service, "ASSETS_DIR", tmp_path / "assets")
    monkeypatch.setattr(service, "EDIT_COVERAGE_PROMPT_FILE", _write_prompt(tmp_path))
    story_path = tmp_path / "assets/EC_001/session-1/adjustment/story.md"
    _write_text(story_path, "new story")
    monkeypatch.setattr(
        service,
        "call_llm_text",
        lambda _config, _prompt: "Score: 9\nPass: true\nReason: should not be used\nEvidence: story",
    )
    result = service.evaluate_edit_coverage(
        FakeLlmConfig(),
        _edit_case(),
        "session-1",
        {"downloaded_assets": [{"type": "markdown", "local_path": str(story_path)}]},
        "",
        "",
    )

    assert result["passed"] is False
    assert result["score"] == 0
    assert result["artifact_coverage"]["missing_nodes"] == ["html"]


def test_html_failure_is_rechecked_by_visual_model(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证 HTML 未通过的 focus 可由最终 PNG 视觉审核通过。"""
    monkeypatch.setattr(service, "ASSETS_DIR", tmp_path / "assets")
    monkeypatch.setattr(service, "EDIT_COVERAGE_PROMPT_FILE", _write_prompt(tmp_path))
    image_prompt = tmp_path / "edit_image_coverage_validate.md"
    _write_text(image_prompt, "{{message}}\n{{evaluation_focus}}")
    monkeypatch.setattr(service, "EDIT_IMAGE_COVERAGE_PROMPT_FILE", image_prompt)
    html_path = tmp_path / "assets/EC_001/session-1/adjustment/index_new.html"
    image_path = tmp_path / "assets/EC_001/session-1/adjustment/index_new.png"
    _write_text(html_path, "new html")
    _write_text(image_path, "not a real image")

    vision_calls: list[Path] = []

    def fake_call_multimodal(_config: Any, _prompt: str, image_paths: list[Path]) -> str:
        vision_calls.extend(image_paths)
        return (
            "Score: 10\nPass: true\nItem_Results:\n"
            "- id: T1\n  passed: true\n  reason: visual ok\n  evidence: image evidence\n"
            "Overall_Reason:\n1. visual ok"
        )

    monkeypatch.setattr(
        service,
        "call_llm_text",
        lambda _config, _prompt: (
            "Score: 5\nPass: false\nItem_Results:\n"
            "- id: T1\n  passed: false\n  reason: html insufficient\n  evidence: \n"
            "Overall_Reason:\n1. html insufficient"
        ),
    )
    monkeypatch.setattr(service, "call_multimodal_text", fake_call_multimodal)

    result = service.evaluate_edit_coverage(
        FakeLlmConfig(),
        _edit_case(),
        "session-1",
        {"downloaded_assets": [{"type": "html", "local_path": str(html_path)}, {"type": "png", "local_path": str(image_path)}]},
        "fallback input",
        "fallback output",
        vision_config=FakeLlmConfig(),
    )

    assert result["passed"] is True
    assert result["score"] == 10
    assert result["evaluated_nodes"] == ["html", "image"]
    assert vision_calls == [image_path]


def test_html_success_does_not_call_visual_model(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证 HTML 全部通过时不调用视觉模型。"""
    monkeypatch.setattr(service, "ASSETS_DIR", tmp_path / "assets")
    monkeypatch.setattr(service, "EDIT_COVERAGE_PROMPT_FILE", _write_prompt(tmp_path))
    html_path = tmp_path / "assets/EC_001/session-1/adjustment/index_new.html"
    _write_text(html_path, "new html")
    monkeypatch.setattr(
        service,
        "call_llm_text",
        lambda _config, _prompt: (
            "Score: 10\nPass: true\nItem_Results:\n"
            "- id: T1\n  passed: true\n  reason: html ok\n  evidence: text\n"
            "Overall_Reason:\n1. html ok"
        ),
    )
    monkeypatch.setattr(
        service,
        "call_multimodal_text",
        lambda *_args, **_kwargs: pytest.fail("HTML 通过后不应调用视觉模型"),
    )

    result = service.evaluate_edit_coverage(
        FakeLlmConfig(),
        _edit_case(),
        "session-1",
        {"downloaded_assets": [{"type": "html", "local_path": str(html_path)}]},
        "fallback input",
        "fallback output",
        vision_config=FakeLlmConfig(),
    )

    assert result["passed"] is True
    assert result["evaluated_nodes"] == ["html"]


def test_resolve_reference_artifact_session_id_uses_latest_original_case_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证审核基准使用原始患者故事目录下的最新会话产物。"""
    monkeypatch.setattr(service, "ASSETS_DIR", tmp_path / "assets")
    old_dir = tmp_path / "assets/SM_001/old-session"
    latest_dir = tmp_path / "assets/SM_001/latest-session"
    _write_text(old_dir / "generate_story/story_old.md", "old story")
    _write_text(old_dir / "generate_final_image/index_old.html", "old html")
    _write_text(latest_dir / "generate_story/story_latest.md", "latest story")
    _write_text(latest_dir / "generate_final_image/index_latest.html", "latest html")
    os.utime(old_dir, (100, 100))
    os.utime(latest_dir, (200, 200))

    assert service.resolve_reference_artifact_session_id("SM_001", "edit-session") == "latest-session"


def test_reference_content_reads_hashed_generation_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证编辑前置能读取生成链路的 hash 文件名产物。"""
    monkeypatch.setattr(service, "ASSETS_DIR", tmp_path / "assets")
    story_dir = tmp_path / "assets/SM_001/session-1/generate_story"
    html_dir = tmp_path / "assets/SM_001/session-1/generate_final_image"
    _write_text(story_dir / "story_abc123.md", "story")
    _write_text(html_dir / "index_def456.html", "html")

    assert service._infer_latest_complete_session_id("SM_001") == "session-1"
    assert service.read_reference_content("SM_001", "session-1") == "html"


def test_resolve_reference_context_uses_saved_content_hub_task_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证编辑上下文优先复用运行结果中保存的 task_id。"""
    monkeypatch.setattr(service, "ASSETS_DIR", tmp_path / "assets")
    monkeypatch.setattr(service, "GENERATION_RUNS_DIR", tmp_path / "results" / "generation_runs")
    _write_text(tmp_path / "assets/SM_001/session-1/generate_story/story_abc123.md", "story")
    _write_text(tmp_path / "assets/SM_001/session-1/generate_final_image/index_def456.html", "html")
    _write_text(
        tmp_path / "results/generation_runs/SM_001/session-1.json",
        '{"session_response":{"content_hub_task":{"task_id":"task-1"}}}',
    )

    result = service.resolve_reference_context(
        {"ref_clinical_case_id": "SM_001", "session_id": "", "task_id": ""},
    )

    assert result == {"session_id": "session-1", "task_id": "task-1"}


def test_write_edit_coverage_result_uses_expected_filename(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证编辑审核结果使用统一文件名落盘。"""
    monkeypatch.setattr(service, "EDIT_RUNS_DIR", tmp_path / "edit")

    service.write_edit_coverage_result("EC_001", {"passed": True})

    assert (tmp_path / "edit/EC_001/edit_coverage_validation.json").exists()


def _edit_case() -> dict[str, Any]:
    """构建最小编辑用例。"""
    return {
        "case_id": "EC_001",
        "ref_clinical_case_id": "SM_001",
        "message": "增加一个底部说明文本：由零假设科技有限公司生成",
        "evaluation_focus": [{"id": "T1", "description": "页脚新增说明文本"}],
    }


def _write_prompt(tmp_path: Path) -> Path:
    """写入测试提示词模板。"""
    prompt_path = tmp_path / "edit_coverage_validate.md"
    _write_text(prompt_path, "{{output_content}}")
    return prompt_path


def _write_text(path: Path, content: str) -> None:
    """写入测试文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
