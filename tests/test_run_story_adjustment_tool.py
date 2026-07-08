"""患者故事编辑命令行入口单元测试。"""

from __future__ import annotations

import pytest

from story_med.tools import run_story_adjustment as tool


class _Args:
    """模拟命令行参数。"""

    def __init__(self, case_id: str, session_id: str, task_id: str, message: str, agent_type: str = "patient-case") -> None:
        self.case_id = case_id
        self.session_id = session_id
        self.task_id = task_id
        self.message = message
        self.agent_type = agent_type


class _Parser:
    """模拟参数解析器。"""

    def __init__(self, args: _Args) -> None:
        self._args = args

    def parse_args(self) -> _Args:
        return self._args


def test_main_requires_registered_edit_case(monkeypatch) -> None:
    """验证入口只支持 edit_story.yaml 中注册的编辑测试用例。"""
    monkeypatch.setattr(
        tool,
        "build_parser",
        lambda: _Parser(_Args("SM_001", "session-1", "task-1", "调整 html")),
    )
    monkeypatch.setattr(tool, "get_edit_case", lambda case_id: (_ for _ in ()).throw(KeyError(case_id)))

    with pytest.raises(KeyError):
        tool.main()


def test_main_uses_finalize_pipeline_for_registered_edit_case(monkeypatch) -> None:
    """验证编辑入口会固定执行调整+覆盖评估。"""
    monkeypatch.setattr(
        tool,
        "get_edit_case",
        lambda case_id: {
            "case_id": case_id,
            "ref_clinical_case_id": "SM_001",
            "message": "old",
        },
    )
    monkeypatch.setattr(
        tool,
        "build_parser",
        lambda: _Parser(_Args("EDG_001_T01", "session-1", "task-1", "new message")),
    )
    monkeypatch.setattr(tool, "load_app_config", lambda: "app-config")
    monkeypatch.setattr(tool, "load_llm_config", lambda: "llm-config")
    monkeypatch.setattr(tool, "run_story_adjustment", lambda **kwargs: {"success": True, "downloaded_assets": []})
    captured = {}

    def fake_finalize_edit_story_case(llm_config, edit_case, session_id, task_id, adjustment_result):
        captured["llm_config"] = llm_config
        captured["edit_case"] = edit_case
        captured["session_id"] = session_id
        captured["task_id"] = task_id
        captured["adjustment_result"] = adjustment_result
        return {"edit_coverage_validation": {"passed": True}}

    monkeypatch.setattr(tool, "finalize_edit_story_case", fake_finalize_edit_story_case)

    exit_code = tool.main()

    assert exit_code == 0
    assert captured["llm_config"] == "llm-config"
    assert captured["edit_case"]["message"] == "new message"
    assert captured["session_id"] == "session-1"
    assert captured["task_id"] == "task-1"
