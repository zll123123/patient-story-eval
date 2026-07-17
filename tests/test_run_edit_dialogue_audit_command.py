"""编辑审核命令入口测试。"""

from __future__ import annotations

from typing import Any

import pytest

from story_med.commands import run_edit_dialogue_audit as command


def test_resolve_case_ids_defaults_to_all_registered_cases(monkeypatch) -> None:
    """验证未传参数时默认执行全部编辑对话用例。"""
    monkeypatch.setattr(
        command,
        "load_edit_dialogue_cases",
        lambda: [{"case_id": "EDG_001"}, {"case_id": "EDG_002"}],
    )

    result = command._resolve_case_ids("", "")

    assert result == ["EDG_001", "EDG_002"]


def test_audit_one_case_records_error_without_blocking_next_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证单个 case 异常不会阻断后续 case。"""
    calls: list[str] = []

    def fake_audit(_app_config: Any, _llm_config: Any, case_id: str) -> dict[str, Any]:
        calls.append(case_id)
        if case_id == "EDG_001":
            raise FileNotFoundError("dialogue_result.json")
        return {"case_id": case_id, "overall_passed": True}

    monkeypatch.setattr(command, "audit_edit_dialogue_case", fake_audit)
    monkeypatch.setattr(
        command,
        "write_audit_failure_result",
        lambda case_id, error_type, error: {
            "case_id": case_id,
            "overall_passed": False,
            "error_type": error_type,
            "error": error,
        },
    )

    first = command._audit_one_case(object(), object(), "EDG_001")  # type: ignore[arg-type]
    second = command._audit_one_case(object(), object(), "EDG_002")  # type: ignore[arg-type]

    assert first["error_type"] == "audit_execution_failed"
    assert second["overall_passed"] is True
    assert calls == ["EDG_001", "EDG_002"]
