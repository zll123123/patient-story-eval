"""患者故事汇总结果整理服务。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from story_med.config.settings import TMP_DIR


def refresh_case_summary(case_id: str) -> Dict[str, Any]:
    """基于当前 case 产物重建精简版 summary。"""
    case_dir = TMP_DIR / case_id
    base_summary = _read_json(case_dir / "summary.json")
    outline_compare = _read_json(case_dir / "outline_hard_rule_compare.json")
    story_compare = _read_json(case_dir / "story_hard_rule_compare.json")

    audit_overview: Dict[str, bool] = {
        "outline_passed": bool(outline_compare.get("overall_passed")),
        "story_passed": bool(story_compare.get("overall_passed")),
    }
    summary: Dict[str, Any] = {
        "case_id": base_summary.get("case_id", case_id),
        "description": base_summary.get("description", ""),
        "session_id": base_summary.get("session_id", ""),
        "source_mode": base_summary.get("source_mode", ""),
        "success": bool(base_summary.get("success", True)),
        "outline_failed_fields": _failed_fields(outline_compare),
        "story_failed_fields": _failed_fields(story_compare),
    }

    _merge_image_summary(case_dir, summary, audit_overview)
    summary["audit_overview"] = audit_overview
    summary["all_passed"] = all(audit_overview.values())
    _write_json(summary, case_dir / "summary.json")
    return summary


def _merge_image_summary(case_dir: Path, summary: Dict[str, Any], audit_overview: Dict[str, bool]) -> None:
    """合并图片审核汇总。"""
    image_design_path = case_dir / "image_design_validation.json"
    if image_design_path.exists():
        image_design = _read_json(image_design_path)
        audit_overview["image_design_passed"] = bool(image_design.get("is_passed"))
        summary["image_design"] = {
            "passed": bool(image_design.get("is_passed")),
            "issue_count": len(image_design.get("issues") or []),
            "summary": image_design.get("summary", ""),
        }

    image_consistant_path = case_dir / "image_consistant_validation.json"
    if image_consistant_path.exists():
        image_consistant = _read_json(image_consistant_path)
        audit_overview["image_consistant_passed"] = bool(image_consistant.get("is_passed"))
        summary["image_consistant"] = {
            "passed": bool(image_consistant.get("is_passed")),
            "issue_count": len(image_consistant.get("issues") or []),
            "summary": image_consistant.get("summary", ""),
        }

    image_compare_path = case_dir / "image_compare_result.json"
    if image_compare_path.exists():
        image_compare = _read_json(image_compare_path)
        final_result = (image_compare.get("final_image") or {}).get("result") or {}
        failed_illustration_ids = [
            item.get("image_id")
            for item in image_compare.get("illustrations") or []
            if not bool((item.get("result") or {}).get("overall_passed"))
        ]
        audit_overview["image_compare_passed"] = bool(image_compare.get("overall_passed"))
        summary["image_compare"] = {
            "status": image_compare.get("status", ""),
            "passed": bool(image_compare.get("overall_passed")),
            "failed_illustration_ids": failed_illustration_ids,
            "final_passed": bool(final_result.get("overall_passed", True)),
        }

    final_image_layout_path = case_dir / "final_image_layout_validation.json"
    if final_image_layout_path.exists():
        final_image_layout = _read_json(final_image_layout_path)
        audit_overview["final_image_layout_passed"] = bool(final_image_layout.get("is_passed"))
        summary["final_image_layout"] = {
            "status": final_image_layout.get("status", ""),
            "passed": bool(final_image_layout.get("is_passed")),
            "issue_count": len(final_image_layout.get("issues") or []),
            "summary": final_image_layout.get("summary", ""),
        }


def _failed_fields(compare_result: Dict[str, Any]) -> List[str]:
    """提取对比失败字段。"""
    field_results = compare_result.get("field_results")
    if not isinstance(field_results, dict):
        return []
    return [field for field, result in field_results.items() if isinstance(result, dict) and not result.get("passed")]


def _read_json(path: Path) -> Dict[str, Any]:
    """读取 JSON 文件。"""
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(data: Dict[str, Any], output_path: Path) -> None:
    """写入 JSON 文件。"""
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
