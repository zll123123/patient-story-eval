"""多轮编辑对话批量命令行入口单元测试。"""

from __future__ import annotations

import pytest

from story_med.commands import run_edit_dialogue_case as tool


def test_resolve_case_ids_supports_multiple_delimiters() -> None:
    """验证支持逗号、分号和竖线分隔多个对话用例。"""
    result = tool._resolve_case_ids("", "EDG_001;EDG_003|EDG_005,EDG_007")

    assert result == ["EDG_001", "EDG_003", "EDG_005", "EDG_007"]


def test_resolve_case_ids_defaults_to_all_registered_cases(monkeypatch) -> None:
    """验证未传入参数时默认执行全部对话用例。"""
    monkeypatch.setattr(
        tool,
        "load_edit_dialogue_cases",
        lambda: [
            {"case_id": "EDG_001"},
            {"case_id": "EDG_003"},
        ],
    )

    result = tool._resolve_case_ids("", "")

    assert result == ["EDG_001", "EDG_003"]


def test_run_one_case_records_exception_and_returns_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证单个编排异常不会冒泡到批量入口。"""
    monkeypatch.setattr(
        tool,
        "run_edit_dialogue_case",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("case failed")),
    )
    monkeypatch.setattr(
        tool,
        "write_dialogue_failure_result",
        lambda case_id, error_type, error: {
            "case_id": case_id,
            "overall_passed": False,
            "error_type": error_type,
            "error": error,
        },
    )

    result = tool._run_one_case(object(), object(), "EDG_001")  # type: ignore[arg-type]

    assert result["overall_passed"] is False
    assert result["error_type"] == "execution_orchestration_failed"
