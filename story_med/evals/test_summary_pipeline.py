"""患者故事汇总结果整理服务单元测试。"""

from __future__ import annotations

import json
from pathlib import Path

from story_med.services import summary_pipeline as pipeline


def test_refresh_case_summary_compacts_pass_fields(tmp_path: Path) -> None:
    """验证 summary 会收敛为精简结构。"""
    case_dir = tmp_path / "tmp" / "SM_TEST"
    _write_json(
        case_dir / "summary.json",
        {
            "case_id": "SM_TEST",
            "description": "test",
            "session_id": "session-1",
            "source_mode": "results_assets",
            "success": True,
        },
    )
    _write_json(case_dir / "outline_hard_rule_compare.json", {"overall_passed": False, "field_results": {"outcome": {"passed": False}}})
    _write_json(case_dir / "story_hard_rule_compare.json", {"overall_passed": True, "field_results": {}})
    _write_json(case_dir / "image_design_validation.json", {"is_passed": True, "summary": "ok", "issues": []})
    _write_json(case_dir / "image_consistant_validation.json", {"is_passed": False, "summary": "bad", "issues": [{"issue_id": "1"}]})
    _write_json(
        case_dir / "image_compare_result.json",
        {
            "status": "success",
            "overall_passed": False,
            "illustrations": [
                {"image_id": 1, "result": {"overall_passed": False}},
                {"image_id": 2, "result": {"overall_passed": True}},
            ],
            "final_image": {"result": {"overall_passed": True}},
        },
    )
    _write_json(
        case_dir / "final_image_layout_validation.json",
        {
            "status": "success",
            "is_passed": False,
            "summary": "layout bad",
            "issues": [{"issue_id": "1"}],
        },
    )

    pipeline.TMP_DIR = case_dir.parent  # type: ignore[assignment]
    result = pipeline.refresh_case_summary("SM_TEST")

    assert result["audit_overview"] == {
        "outline_passed": False,
        "story_passed": True,
        "image_design_passed": True,
        "image_consistant_passed": False,
        "image_compare_passed": False,
        "final_image_layout_passed": False,
    }
    assert result["all_passed"] is False
    assert result["image_design"]["passed"] is True
    assert result["image_consistant"]["issue_count"] == 1
    assert result["image_compare"]["failed_illustration_ids"] == [1]
    assert result["final_image_layout"]["issue_count"] == 1
    assert "outline_passed" not in result
    assert "story_passed" not in result


def _write_json(path: Path, data: dict) -> None:
    """写入 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
