"""患者故事多轮编辑归因流程单元测试。"""

from __future__ import annotations

from typing import Any

import pytest

from story_med.services.story_edit_evaluation import edit_dialogue_attribution_pipeline as pipeline


class FakeLlmConfig:
    """模拟 LLM 配置对象。"""


def test_run_edit_dialogue_analysis_assigns_failure_to_final_turn_when_previous_turn_recheck_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证上一轮重审通过时，失败归因于最终失败轮。"""
    dialogue_result = _dialogue_result()

    monkeypatch.setattr(pipeline, "read_reference_content", lambda *_args, **_kwargs: "before")
    monkeypatch.setattr(
        pipeline,
        "evaluate_edit_coverage",
        lambda _llm_config, edit_case, *_args, **_kwargs: {
            "passed": edit_case["case_id"].endswith("T02"),
            "score": 9,
            "reason": "ok",
        },
    )
    captured: dict[str, Any] = {}
    monkeypatch.setattr(pipeline, "_write_analysis", lambda case_id, analysis: captured.update({"case_id": case_id, "analysis": analysis}))

    analysis = pipeline.run_edit_dialogue_analysis(FakeLlmConfig(), dialogue_result)

    assert analysis is not None
    assert analysis["root_cause_turn"] == 3
    assert analysis["failed_final_turn"] == 3
    assert analysis["recheck_trace"][1]["turn_id"] == 2
    assert analysis["recheck_trace"][1]["recheck_passed"] is True
    assert captured["case_id"] == "EDG_001"


def test_run_edit_dialogue_analysis_assigns_failure_to_first_prior_failed_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证倒序重审命中 T2 失败、T1 通过时，归因于 T2。"""
    dialogue_result = _dialogue_result()

    monkeypatch.setattr(pipeline, "read_reference_content", lambda *_args, **_kwargs: "before")

    def fake_evaluate(_llm_config: Any, edit_case: dict[str, Any], *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "passed": edit_case["case_id"].endswith("T01"),
            "score": 9 if edit_case["case_id"].endswith("T01") else 0,
            "reason": "mock",
        }

    monkeypatch.setattr(pipeline, "evaluate_edit_coverage", fake_evaluate)
    monkeypatch.setattr(pipeline, "_write_analysis", lambda *_args, **_kwargs: None)

    analysis = pipeline.run_edit_dialogue_analysis(FakeLlmConfig(), dialogue_result)

    assert analysis is not None
    assert analysis["root_cause_turn"] == 2
    assert [item["turn_id"] for item in analysis["recheck_trace"]] == [3, 2, 1]
    assert analysis["recheck_trace"][1]["recheck_passed"] is False
    assert analysis["recheck_trace"][2]["recheck_passed"] is True


def test_run_edit_dialogue_analysis_captures_recheck_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证分析重审异常会单独记录，不向主流程抛出。"""
    dialogue_result = _dialogue_result()
    captured: dict[str, Any] = {}

    def raise_analysis_error(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise TimeoutError("LLM analysis timeout")

    monkeypatch.setattr(pipeline, "read_reference_content", lambda *_args, **_kwargs: "before")
    monkeypatch.setattr(pipeline, "evaluate_edit_coverage", raise_analysis_error)
    monkeypatch.setattr(
        pipeline,
        "_write_analysis",
        lambda case_id, analysis: captured.update({"case_id": case_id, "analysis": analysis}),
    )

    result = pipeline.run_edit_dialogue_analysis(FakeLlmConfig(), dialogue_result)

    assert result["analysis_status"] == "failed"
    assert result["error_type"] == "TimeoutError"
    assert captured["analysis"]["error"] == "LLM analysis timeout"


def _dialogue_result() -> dict[str, Any]:
    """构建多轮编辑失败结果。"""
    return {
        "case_id": "EDG_001",
        "ref_clinical_case_id": "SM_001",
        "reference_session_id": "session-1",
        "overall_passed": False,
        "turn_results": [
            _turn_result(1, True),
            _turn_result(2, False),
            _turn_result(3, False),
        ],
    }


def _turn_result(turn_id: int, passed: bool) -> dict[str, Any]:
    """构建单轮结果。"""
    return {
        "turn_id": turn_id,
        "case_id": f"EDG_001_T{turn_id:02d}",
        "message": f"message-{turn_id}",
        "intent": {"type": "modify", "targets": [f"target-{turn_id}"]},
        "involved_agents": ["html"],
        "effective_evaluation_focus": [{"id": f"T{turn_id}", "description": f"focus-{turn_id}"}],
        "execution_status": "success",
        "execution_passed": True,
        "audit_status": "passed" if passed else "failed",
        "passed": passed,
        "adjustment_result": {
            "success": True,
            "downloaded_assets": [{"local_path": f"/tmp/EDG_001_T{turn_id:02d}/index.html"}],
        },
    }
