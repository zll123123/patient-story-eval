"""患者故事多轮编辑对话流程单元测试。"""

from __future__ import annotations

from typing import Any

import pytest

from story_med.services import edit_dialogue_pipeline as pipeline


class FakeConfig:
    """模拟配置对象。"""


def test_build_cumulative_evaluation_focus_uses_passed_turns_only() -> None:
    """验证累计评估点只包含历史已通过轮次和当前轮。"""
    result = pipeline.build_cumulative_evaluation_focus(
        [{"turn_id": 1, "evaluation_focus": "应新增声明"}],
        "应修改背景颜色",
    )

    assert "1. 应新增声明" in result
    assert "2. 应修改背景颜色" in result


def test_run_dialogue_turns_continues_after_failed_turn_without_accumulating_focus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证失败轮次不进入后续累计预期，但后续轮次继续执行。"""
    dialogue_case = {
        "case_id": "EDG_TEST",
        "ref_clinical_case_id": "SM_001",
        "turns": [
            {
                "turn_id": 1,
                "message": "加声明",
                "evaluation_focus": "应新增声明",
                "involved_agents": ["html"],
                "intent": {"type": "add", "targets": ["company_statement"]},
            },
            {
                "turn_id": 2,
                "message": "改背景",
                "evaluation_focus": "应修改背景颜色",
                "involved_agents": ["html"],
                "intent": {"type": "modify", "targets": ["background_style"]},
            },
        ],
    }
    prompts: list[str] = []

    def fake_run_story_adjustment(**_kwargs: Any) -> dict[str, Any]:
        return {"success": True, "downloaded_assets": []}

    def fake_read_adjusted_content(*_args: Any, **_kwargs: Any) -> str:
        return "output"

    def fake_evaluate_edit_coverage(
        _llm_config: Any,
        edit_case: dict[str, Any],
        *_args: Any,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        prompts.append(str(edit_case["evaluation_focus"]))
        passed = edit_case["case_id"].endswith("T02")
        return {"passed": passed, "score": 9 if passed else 0}

    monkeypatch.setattr(pipeline, "run_story_adjustment", fake_run_story_adjustment)
    monkeypatch.setattr(pipeline, "read_adjusted_content", fake_read_adjusted_content)
    monkeypatch.setattr(pipeline, "evaluate_edit_coverage", fake_evaluate_edit_coverage)
    monkeypatch.setattr(pipeline, "_write_turn_result", lambda *_args, **_kwargs: None)

    results = pipeline._run_dialogue_turns(
        app_config=FakeConfig(),
        llm_config=FakeConfig(),
        dialogue_case=dialogue_case,
        ref_context={"session_id": "session-1", "task_id": "task-1"},
        reference_session_id="session-1",
        input_content="input",
    )

    assert results[0]["passed"] is False
    assert results[1]["passed"] is True
    assert results[1]["included_previous_turns"] == []
    assert results[1]["excluded_failed_turns"] == [1]
    assert "应新增声明" not in prompts[1]
    assert "应修改背景颜色" in prompts[1]
