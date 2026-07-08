"""患者故事编辑审核流程单元测试。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from story_med.services import edit_story_pipeline as pipeline


class FakeLlmConfig:
    """模拟 LLM 配置对象。"""


def test_evaluate_edit_coverage_uses_final_html_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证编辑审核只基于最终长图 HTML。"""
    monkeypatch.setattr(pipeline, "ASSETS_DIR", tmp_path / "assets")
    monkeypatch.setattr(pipeline, "EDIT_COVERAGE_PROMPT_FILE", _write_prompt(tmp_path))
    _write_text(tmp_path / "assets/SM_001/session-1/generate_final_image/index.html", "old html")
    html_path = tmp_path / "assets/EC_001/session-1/adjustment/index.html"
    _write_text(html_path, "new html with company")
    edit_case = _edit_case(["html"])
    adjustment_result = {"downloaded_assets": [{"type": "html", "local_path": str(html_path)}]}
    calls: list[str] = []

    def fake_call_llm_text(_config: Any, prompt: str) -> str:
        calls.append(prompt)
        return "Score: 9\nPass: true\nReason: html ok\nEvidence: company"

    monkeypatch.setattr(pipeline, "call_llm_text", fake_call_llm_text)

    result = pipeline.evaluate_edit_coverage(
        FakeLlmConfig(),
        edit_case,
        "session-1",
        adjustment_result,
        "fallback input",
        "fallback output",
    )

    assert result["metric_name"] == "修改覆盖"
    assert result["passed"] is True
    assert result["required_nodes"] == ["html"]
    assert result["artifact_coverage"] == {
        "passed": True,
        "present_nodes": ["html"],
        "missing_nodes": [],
    }
    assert len(result["node_results"]) == 1
    assert "new html with company" in calls[0]
    assert "old html" not in calls[0]


def test_evaluate_edit_coverage_ignores_non_html_artifacts_in_pass_fail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证非长图产物即使存在，也不参与编辑通过判定。"""
    monkeypatch.setattr(pipeline, "ASSETS_DIR", tmp_path / "assets")
    monkeypatch.setattr(pipeline, "EDIT_COVERAGE_PROMPT_FILE", _write_prompt(tmp_path))
    story_path = tmp_path / "assets/EC_001/session-1/adjustment/story.md"
    _write_text(story_path, "new story")
    edit_case = _edit_case(["story", "html"])
    adjustment_result = {"downloaded_assets": [{"type": "markdown", "local_path": str(story_path)}]}
    monkeypatch.setattr(
        pipeline,
        "call_llm_text",
        lambda _config, _prompt: "Score: 9\nPass: true\nReason: story ok\nEvidence: story",
    )

    result = pipeline.evaluate_edit_coverage(
        FakeLlmConfig(),
        edit_case,
        "session-1",
        adjustment_result,
        "",
        "",
    )

    assert result["passed"] is False
    assert result["score"] == 0
    assert result["artifact_coverage"] == {
        "passed": False,
        "present_nodes": [],
        "missing_nodes": ["html"],
    }
    assert result["node_results"][0]["node"] == "html"
    assert result["node_results"][0]["artifact_present"] is False
    assert result["node_results"][0]["score"] == 0


def test_evaluate_edit_coverage_can_pass_when_artifact_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证最终长图即使未变化，也允许直接基于最终状态做判断。"""
    monkeypatch.setattr(pipeline, "ASSETS_DIR", tmp_path / "assets")
    monkeypatch.setattr(pipeline, "EDIT_COVERAGE_PROMPT_FILE", _write_prompt(tmp_path))
    _write_text(tmp_path / "assets/SM_001/session-1/generate_final_image/index.html", "same html")
    html_path = tmp_path / "assets/EC_001/session-1/adjustment/index.html"
    _write_text(html_path, "same html")
    edit_case = _edit_case(["html"])
    adjustment_result = {"downloaded_assets": [{"type": "html", "local_path": str(html_path)}]}

    monkeypatch.setattr(
        pipeline,
        "call_llm_text",
        lambda _config, _prompt: "Score: 9\nPass: true\nOverall_Reason: html ok\nEvidence: same html",
    )

    result = pipeline.evaluate_edit_coverage(
        FakeLlmConfig(),
        edit_case,
        "session-1",
        adjustment_result,
        "",
        "",
    )

    assert result["passed"] is True
    assert result["artifact_coverage"]["passed"] is True
    assert result["node_results"][0]["score"] == 9


def test_resolve_reference_artifact_session_id_uses_latest_original_case_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证审核基准使用原始患者故事目录下的最新会话产物。"""
    monkeypatch.setattr(pipeline, "ASSETS_DIR", tmp_path / "assets")
    old_dir = tmp_path / "assets/SM_001/old-session"
    latest_dir = tmp_path / "assets/SM_001/latest-session"
    _write_text(old_dir / "generate_story/story.md", "old story")
    _write_text(old_dir / "generate_final_image/index.html", "old html")
    _write_text(latest_dir / "generate_story/story.md", "latest story")
    _write_text(latest_dir / "generate_final_image/index.html", "latest html")
    os.utime(old_dir, (100, 100))
    os.utime(latest_dir, (200, 200))

    result = pipeline.resolve_reference_artifact_session_id("SM_001", "edit-session")

    assert result == "latest-session"


def test_resolve_reference_artifact_session_id_ignores_incomplete_latest_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证审核基准不会选择只有部分产物的新会话目录。"""
    monkeypatch.setattr(pipeline, "ASSETS_DIR", tmp_path / "assets")
    complete_dir = tmp_path / "assets/SM_001/complete-session"
    incomplete_dir = tmp_path / "assets/SM_001/incomplete-session"
    _write_text(complete_dir / "generate_story/story.md", "story")
    _write_text(complete_dir / "generate_final_image/index.html", "html")
    _write_text(incomplete_dir / "case_parse/case_parse.md", "parse only")
    os.utime(complete_dir, (100, 100))
    os.utime(incomplete_dir, (200, 200))

    result = pipeline.resolve_reference_artifact_session_id("SM_001", "edit-session")

    assert result == "complete-session"


def test_resolve_reference_context_uses_saved_content_hub_task_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证编辑上下文优先复用运行结果中保存的 task_id。"""
    monkeypatch.setattr(pipeline, "ASSETS_DIR", tmp_path / "assets")
    monkeypatch.setattr(pipeline, "RESULTS_DIR", tmp_path / "results")
    _write_text(tmp_path / "assets/SM_001/session-1/generate_story/story.md", "story")
    _write_text(tmp_path / "assets/SM_001/session-1/generate_final_image/index.html", "html")
    run_path = tmp_path / "results/runs/SM_001/session-1.json"
    _write_text(
        run_path,
        '{"session_response":{"content_hub_task":{"task_id":"task-1"}}}',
    )
    edit_case = {
        "ref_clinical_case_id": "SM_001",
        "session_id": "",
        "task_id": "",
    }

    result = pipeline.resolve_reference_context(edit_case)

    assert result == {"session_id": "session-1", "task_id": "task-1"}


def test_build_failed_edit_result_includes_exception_error() -> None:
    """验证调整异常会写入失败证据，便于排查服务端问题。"""
    result = pipeline._build_failed_edit_result(
        _edit_case(["html"]),
        {"session_id": "session-1", "task_id": "task-1"},
        "session-1",
        {"success": False, "error": "server failed"},
    )

    assert result["edit_coverage_validation"]["evidence"] == "server failed"


def test_write_edit_validation_result_uses_coverage_filename(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证编辑审核结果使用 coverage 文件名落盘。"""
    monkeypatch.setattr(pipeline, "EDIT_RESULTS_DIR", tmp_path / "edit")

    pipeline._write_edit_validation_result("EC_001", {"passed": True})

    assert (tmp_path / "edit/EC_001/edit_coverage_validation.json").exists()


def test_finalize_edit_story_case_writes_coverage_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证已完成调整后会补做覆盖评估并落盘。"""
    monkeypatch.setattr(pipeline, "ASSETS_DIR", tmp_path / "assets")
    monkeypatch.setattr(pipeline, "EDIT_RESULTS_DIR", tmp_path / "edit")
    monkeypatch.setattr(pipeline, "EDIT_COVERAGE_PROMPT_FILE", _write_prompt(tmp_path))
    _write_text(tmp_path / "assets/SM_001/session-1/generate_final_image/index.html", "old html")
    html_path = tmp_path / "assets/EDG_001_T01/session-1/adjustment/index.html"
    _write_text(html_path, "new html")
    monkeypatch.setattr(
        pipeline,
        "call_llm_text",
        lambda _config, _prompt: "Score: 9\nPass: true\nReason: ok\nEvidence: html changed",
    )
    edit_case = _edit_case(["html"])
    edit_case.update(
        {
            "case_id": "EDG_001_T01",
            "ref_clinical_case_id": "SM_001",
            "message": "调整 html",
        }
    )
    adjustment_result = {
        "success": True,
        "downloaded_assets": [{"type": "html", "local_path": str(html_path)}],
    }

    result = pipeline.finalize_edit_story_case(
        FakeLlmConfig(),
        edit_case,
        "session-1",
        "task-1",
        adjustment_result,
    )

    assert result["edit_coverage_validation"]["passed"] is True
    output_path = tmp_path / "edit/EDG_001_T01/edit_coverage_validation.json"
    assert output_path.exists()


def test_build_content_diff_marks_before_and_after() -> None:
    """验证修改差异会明确标记删除和新增内容。"""
    result = pipeline.build_content_diff("原文A\n保留", "原文B\n保留")

    assert "--- before" in result
    assert "+++ after" in result
    assert "-原文A" in result
    assert "+原文B" in result


def _edit_case(required_nodes: list[str]) -> dict[str, Any]:
    """构建编辑用例测试数据。"""
    return {
        "case_id": "EC_001",
        "ref_clinical_case_id": "SM_001",
        "message": "增加声明",
        "evaluation_focus": "应增加声明",
        "involved_agent": {"required": required_nodes},
    }


def _write_prompt(tmp_path: Path) -> Path:
    """写入测试提示词模板。"""
    prompt_path = tmp_path / "prompt.md"
    _write_text(
        prompt_path,
        "{{message}}\n{{evaluation_focus}}\n{{image_input}}",
    )
    return prompt_path


def _write_text(path: Path, content: str) -> None:
    """写入测试文本文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
