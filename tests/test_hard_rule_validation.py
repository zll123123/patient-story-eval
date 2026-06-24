"""患者故事硬规则校验测试。"""

from __future__ import annotations

import json
from pathlib import Path

from story_med.config.settings import BASE_DIR, DEFAULT_CASE_FILE, RESULTS_DIR
from story_med.services.case_loader import load_story_cases
from story_med.services.hard_rule_validator import validate_hard_rules, write_hard_rule_report


def test_latest_story_outputs_pass_hard_rules() -> None:
    """校验最近一次患者故事输出是否通过硬规则。"""
    result_path = RESULTS_DIR / "patient_story_run.json"
    assert result_path.exists(), "缺少真实链路运行结果，请先执行 patient story smoke 测试"

    result_data = json.loads(result_path.read_text(encoding="utf-8"))
    session_id = str(result_data.get("session_id") or "")
    case_id = str(result_data.get("case_id") or "")
    assert session_id
    assert case_id

    outline_path = _find_single_file(BASE_DIR / "results" / "assets" / case_id / session_id / "generate_outline")
    story_path = _find_single_file(BASE_DIR / "results" / "assets" / case_id / session_id / "generate_story")
    case = load_story_cases(DEFAULT_CASE_FILE)[0]
    report = validate_hard_rules(
        case=case,
        outline_text=outline_path.read_text(encoding="utf-8"),
        story_text=story_path.read_text(encoding="utf-8"),
    )
    write_hard_rule_report(report, RESULTS_DIR / "hard_rule_validation.json")

    assert report["passed"], report


def _find_single_file(directory: Path) -> Path:
    """查找目录中的唯一文件。"""
    files = [item for item in directory.iterdir() if item.is_file()]
    assert len(files) == 1, f"目录文件数量不符合预期: {directory}"
    return files[0]
