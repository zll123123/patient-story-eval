"""统一运行入口单元测试。"""

from __future__ import annotations

import pytest

from story_med import __main__ as cli


def test_main_routes_patient_story_full_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证统一入口会分发到患者故事主链路命令。"""
    captured: dict[str, object] = {}

    def fake_main(argv: list[str] | None = None) -> int:
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(cli.run_patient_story_deepeval, "main", fake_main)

    exit_code = cli.main(["patient-story-full", "--mode", "audit_only", "--case-ids", "SM_001"])

    assert exit_code == 0
    assert captured["argv"] == ["--mode", "audit_only", "--case-ids", "SM_001"]


def test_main_routes_patient_story_audit_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证统一入口会分发到生成产物审核命令。"""
    captured: dict[str, object] = {}

    def fake_main(argv: list[str] | None = None) -> int:
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(cli.run_patient_story_audit, "main", fake_main)

    exit_code = cli.main(["patient-story-audit", "--case-ids", "SM_001"])

    assert exit_code == 0
    assert captured["argv"] == ["--case-ids", "SM_001"]


def test_main_routes_patient_story_edit_audit_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证统一入口会分发到编辑产物审核命令。"""
    captured: dict[str, object] = {}

    def fake_main(argv: list[str] | None = None) -> int:
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(cli.run_edit_dialogue_audit, "main", fake_main)

    exit_code = cli.main(["patient-story-edit-audit", "--case-ids", "EDG_001"])

    assert exit_code == 0
    assert captured["argv"] == ["--case-ids", "EDG_001"]


def test_main_returns_error_when_command_missing() -> None:
    """验证未提供子命令时返回非零退出码。"""
    assert cli.main([]) == 1


def test_main_rejects_unknown_command() -> None:
    """验证未知子命令会报错。"""
    with pytest.raises(ValueError):
        cli.main(["unknown-command"])
