"""患者故事编辑批量命令行入口单元测试。"""

from __future__ import annotations

from story_med.tools import run_edit_story_case as tool


def test_resolve_case_ids_supports_multiple_delimiters() -> None:
    """验证支持逗号、分号和竖线分隔多个编辑用例。"""
    result = tool._resolve_case_ids("", "EDG_001_T01;EDG_001_T02|EDG_003_T01,EDG_003_T02")

    assert result == ["EDG_001_T01", "EDG_001_T02", "EDG_003_T01", "EDG_003_T02"]


def test_resolve_case_ids_defaults_to_all_registered_cases(monkeypatch) -> None:
    """验证未传入 case 参数时默认执行全部编辑用例。"""
    monkeypatch.setattr(
        tool,
        "load_edit_cases",
        lambda: [
            {"case_id": "EDG_001_T01"},
            {"case_id": "EDG_001_T02"},
        ],
    )

    result = tool._resolve_case_ids("", "")

    assert result == ["EDG_001_T01", "EDG_001_T02"]
