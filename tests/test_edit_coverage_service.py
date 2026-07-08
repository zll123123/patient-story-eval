"""患者故事编辑覆盖共享服务单元测试。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from story_med.services import edit_coverage_service as service


class FakeLlmConfig:
    """模拟 LLM 配置对象。"""


def test_evaluate_edit_coverage_uses_final_html_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证编辑审核只基于最终长图 HTML。"""
    monkeypatch.setattr(service, "ASSETS_DIR", tmp_path / "assets")
    monkeypatch.setattr(service, "EDIT_COVERAGE_PROMPT_FILE", _write_prompt(tmp_path))
    _write_text(tmp_path / "assets/SM_001/session-1/generate_final_image/index.html", "old html")
    html_path = tmp_path / "assets/EC_001/session-1/adjustment/index.html"
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


def test_resolve_reference_artifact_session_id_uses_latest_original_case_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证审核基准使用原始患者故事目录下的最新会话产物。"""
    monkeypatch.setattr(service, "ASSETS_DIR", tmp_path / "assets")
    old_dir = tmp_path / "assets/SM_001/old-session"
    latest_dir = tmp_path / "assets/SM_001/latest-session"
    _write_text(old_dir / "generate_story/story.md", "old story")
    _write_text(old_dir / "generate_final_image/index.html", "old html")
    _write_text(latest_dir / "generate_story/story.md", "latest story")
    _write_text(latest_dir / "generate_final_image/index.html", "latest html")
    os.utime(old_dir, (100, 100))
    os.utime(latest_dir, (200, 200))

    assert service.resolve_reference_artifact_session_id("SM_001", "edit-session") == "latest-session"


def test_resolve_reference_context_uses_saved_content_hub_task_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证编辑上下文优先复用运行结果中保存的 task_id。"""
    monkeypatch.setattr(service, "ASSETS_DIR", tmp_path / "assets")
    monkeypatch.setattr(service, "RESULTS_DIR", tmp_path / "results")
    _write_text(tmp_path / "assets/SM_001/session-1/generate_story/story.md", "story")
    _write_text(tmp_path / "assets/SM_001/session-1/generate_final_image/index.html", "html")
    _write_text(
        tmp_path / "results/runs/SM_001/session-1.json",
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
    monkeypatch.setattr(service, "EDIT_RESULTS_DIR", tmp_path / "edit")

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
