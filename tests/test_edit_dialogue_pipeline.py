"""患者故事多轮编辑对话流程单元测试。"""

from __future__ import annotations

from typing import Any

import pytest

from story_med.services.story_edit_evaluation import edit_dialogue_pipeline as pipeline


class FakeConfig:
    """模拟配置对象。"""


def test_build_cumulative_evaluation_focus_uses_structured_items_only() -> None:
    """验证累计评估点只包含历史通过项与当前项。"""
    result = pipeline.build_cumulative_evaluation_focus(
        [{"turn_id": 1, "evaluation_focus": [{"id": "T1", "description": "应新增声明"}]}],
        [{"id": "T2", "description": "应修改背景颜色"}],
    )

    assert result == [
        {"id": "T1", "description": "应新增声明"},
        {"id": "T2", "description": "应修改背景颜色"},
    ]


def test_run_dialogue_turns_stops_after_execution_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证执行失败后停止后续 Agent 调用。"""
    dialogue_case = {
        "case_id": "EDG_TEST",
        "ref_clinical_case_id": "SM_001",
        "turns": [
            {
                "turn_id": 1,
                "message": "加声明",
                "evaluation_focus": [{"id": "T1", "description": "应新增声明"}],
                "involved_agents": ["html"],
                "intent": {"type": "add", "targets": ["company_statement"]},
            },
            {
                "turn_id": 2,
                "message": "改背景",
                "evaluation_focus": [{"id": "T2", "description": "应修改背景颜色"}],
                "involved_agents": ["html"],
                "intent": {"type": "modify", "targets": ["background_style"]},
            },
        ],
    }
    calls: list[str] = []

    def fake_run_story_adjustment(**_kwargs: Any) -> dict[str, Any]:
        calls.append(_kwargs["message"])
        return {"success": False, "error": "HTTP 409", "downloaded_assets": []}

    monkeypatch.setattr(pipeline, "run_story_adjustment", fake_run_story_adjustment)

    results = pipeline._run_dialogue_turns(
        app_config=FakeConfig(),
        llm_config=FakeConfig(),
        dialogue_case=dialogue_case,
        ref_context={"session_id": "session-1", "task_id": "task-1"},
        reference_session_id="session-1",
        input_content="input",
    )

    assert results[0]["execution_status"] == "failed"
    assert results[1]["execution_status"] == "not_run"
    assert calls == ["加声明"]


def test_run_dialogue_turns_final_turn_only_accumulates_successful_focuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证仅最终轮评估时，最终轮会累积前序执行成功轮次的评估点。"""
    dialogue_case = {
        "case_id": "EDG_TEST_FINAL",
        "ref_clinical_case_id": "SM_001",
        "turns": [
            {
                "turn_id": 1,
                "message": "加声明",
                "evaluation_focus": [{"id": "T1", "description": "应新增声明"}],
                "involved_agents": ["html"],
                "intent": {"type": "add", "targets": ["company_statement"]},
            },
            {
                "turn_id": 2,
                "message": "改背景",
                "evaluation_focus": [{"id": "T2", "description": "应修改背景颜色"}],
                "involved_agents": ["html"],
                "intent": {"type": "modify", "targets": ["background_style"]},
            },
        ],
    }
    prompts: list[list[dict[str, str]]] = []

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
        prompts.append(edit_case["evaluation_focus"])
        return {"passed": True, "score": 9}

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

    assert "audit_status" not in results[0]
    assert results[0]["execution_status"] == "success"
    assert results[1]["audit_status"] == "passed"
    assert results[1]["included_previous_turns"] == [1]
    assert prompts[0] == [
        {"id": "T1", "description": "应新增声明"},
        {"id": "T2", "description": "应修改背景颜色"},
    ]


def test_audit_missing_dialogue_result_writes_audit_result_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证缺少编辑执行结果时不覆盖 dialogue_result。"""
    dialogue_case = {
        "case_id": "EDG_MISSING",
        "ref_clinical_case_id": "SM_001",
        "turns": [],
    }
    written: dict[str, Any] = {}

    monkeypatch.setattr(pipeline, "get_edit_dialogue_case", lambda _case_id: dialogue_case)
    monkeypatch.setattr(
        pipeline,
        "_load_existing_dialogue_result",
        lambda _case_id: (_ for _ in ()).throw(FileNotFoundError("missing")),
    )
    monkeypatch.setattr(
        pipeline,
        "_write_audit_result",
        lambda case_id, result: written.update({"case_id": case_id, "result": result}),
    )

    result = pipeline.audit_edit_dialogue_case(FakeConfig(), FakeConfig(), "EDG_MISSING")

    assert result["error_type"] == "missing_dialogue_result"
    assert result["audit_status"] == "failed"
    assert written["case_id"] == "EDG_MISSING"
    assert "dialogue_result" not in written["result"]
