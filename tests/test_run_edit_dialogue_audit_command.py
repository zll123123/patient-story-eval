"""编辑审核命令入口测试。"""

from __future__ import annotations

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
