"""患者故事审核命令入口测试。"""

from __future__ import annotations

from story_med.commands import run_patient_story_audit as command


def test_main_forwards_audit_only_mode(monkeypatch) -> None:
    """验证审核入口会固定转发 audit_only 模式。"""
    captured: dict[str, object] = {}

    def fake_main(argv=None):
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(command.run_patient_story_deepeval, "main", fake_main)

    exit_code = command.main(["--case-ids", "SM_001"])

    assert exit_code == 0
    assert captured["argv"] == ["--case-ids", "SM_001"]
