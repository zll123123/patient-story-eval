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
            "agent_total_duration_seconds": 12.5,
            "agent_step_timings": {
                "generate_outline": {
                    "label": "获取大纲",
                    "duration_seconds": 1.1,
                },
                "generate_story": {
                    "label": "获取故事",
                    "duration_seconds": 2.2,
                },
            },
        },
    )
    _write_json(
        case_dir / "outline_hard_rule_compare.json",
        {
            "overall_passed": False,
            "field_results": {
                "outcome": {"passed": False},
                "timeline": {"passed": True},
            },
        },
    )
    _write_json(
        case_dir / "story_hard_rule_compare.json",
        {
            "overall_passed": True,
            "field_results": {
                "outcome": {"passed": True},
                "timeline": {"passed": True},
            },
        },
    )
    _write_json(case_dir / "image_design_validation.json", {"is_passed": True, "summary": "ok", "issues": []})
    _write_json(
        case_dir / "story_compliance_validation.json",
        {
            "status": "success",
            "is_passed": False,
            "summary": "存在隐私泄露风险",
            "issues": [{"issue_id": "privacy_leak"}],
        },
    )
    _write_json(case_dir / "image_consistency_validation.json", {"is_passed": False, "summary": "bad", "issues": [{"issue_id": "1"}]})
    _write_json(
        case_dir / "image_fact_validation.json",
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
            "issues": [
                {
                    "issue_id": "redundant_sections_check",
                    "issue_description": "发现多余的专家点评板块",
                    "reason": "专家点评",
                    "evidence_used": ["专家点评"],
                }
            ],
        },
    )
    generate_images_dir = tmp_path / "assets" / "SM_TEST" / "session-1" / "generate_images"
    generate_images_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        generate_images_dir / "generate_images_6_image_design.json",
        {
            "illustrations": [
                {"id": 1},
                {"id": 2},
            ]
        },
    )

    pipeline.TMP_DIR = case_dir.parent  # type: ignore[assignment]
    pipeline.RESULTS_DIR = tmp_path  # type: ignore[assignment]
    result = pipeline.refresh_case_summary("SM_TEST")

    assert result["audit_overview"] == {
        "outline_passed": False,
        "story_passed": True,
        "story_compliance_passed": False,
        "image_design_passed": True,
        "image_consistency_passed": False,
        "image_fact_passed": False,
        "final_image_layout_passed": False,
    }
    assert result["all_passed"] is False
    assert result["story_compliance"]["passed"] is False
    assert result["story_compliance"]["issue_count"] == 1
    assert result["image_design"]["passed"] is True
    assert result["image_design"]["total_count"] == 2
    assert result["image_consistency"]["issue_count"] == 1
    assert result["image_fact"]["failed_illustration_ids"] == [1]
    assert result["final_image_layout"]["issue_count"] == 1
    assert result["scorecard"]["gate_passed"] is False
    assert result["scorecard"]["high_score_eligible"] is False
    assert result["scorecard"]["max_score"] == 100
    assert result["scorecard"]["breakdown"] == {
        "outline_fact_score": 10.0,
        "story_fact_score": 20.0,
        "story_compliance_score": 5.0,
        "image_design_score": 10.0,
        "image_consistency_score": 0.0,
        "image_fact_score": 5.0,
        "final_image_layout_score": 15.0,
    }
    assert result["scorecard"]["total_score"] == 65.0
    assert result["agent_total_duration_seconds"] == 12.5
    assert result["agent_step_timings"]["generate_outline"]["duration_seconds"] == 1.1
    assert result["agent_step_timings"]["generate_story"]["duration_seconds"] == 2.2
    assert "outline_passed" not in result
    assert "story_passed" not in result


def test_refresh_case_summary_scores_image_design_from_design_total_when_image_fact_blocked(tmp_path: Path) -> None:
    """验证图片设计得分不再依赖 image_fact 成功返回。"""
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
    _write_json(case_dir / "outline_hard_rule_compare.json", {"overall_passed": True, "field_results": {"a": {"passed": True}}})
    _write_json(case_dir / "story_hard_rule_compare.json", {"overall_passed": True, "field_results": {"a": {"passed": True}}})
    _write_json(
        case_dir / "image_design_validation.json",
        {
            "is_passed": False,
            "summary": "bad",
            "issues": [
                {"issue_id": "图2、图3、图4、图5（对应id:2,3,4,5）"},
            ],
        },
    )
    _write_json(
        case_dir / "image_fact_validation.json",
        {
            "status": "blocked",
            "overall_passed": False,
            "illustrations": [],
            "final_image": {},
        },
    )
    generate_images_dir = tmp_path / "assets" / "SM_TEST" / "session-1" / "generate_images"
    generate_images_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        generate_images_dir / "generate_images_6_image_design.json",
        {
            "illustrations": [
                {"id": 1},
                {"id": 2},
                {"id": 3},
                {"id": 4},
                {"id": 5},
            ]
        },
    )

    pipeline.TMP_DIR = case_dir.parent  # type: ignore[assignment]
    pipeline.RESULTS_DIR = tmp_path  # type: ignore[assignment]
    result = pipeline.refresh_case_summary("SM_TEST")

    assert result["image_design"]["total_count"] == 5
    assert result["scorecard"]["breakdown"]["image_design_score"] == 2.0


def _write_json(path: Path, data: dict) -> None:
    """写入 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
