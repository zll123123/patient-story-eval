"""患者故事汇总结果整理服务。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from story_med.config.settings import TMP_DIR

OUTLINE_FACT_MAX_SCORE = 20.0
STORY_FACT_MAX_SCORE = 20.0
IMAGE_DESIGN_MAX_SCORE = 10.0
IMAGE_CONSISTENCY_MAX_SCORE = 10.0
IMAGE_FACT_MAX_SCORE = 10.0
FINAL_IMAGE_LAYOUT_MAX_SCORE = 30.0

FINAL_IMAGE_LAYOUT_MISSING_DEDUCTION = 10.0
FINAL_IMAGE_LAYOUT_POSITION_DEDUCTION = 5.0
FINAL_IMAGE_LAYOUT_REDUNDANT_DEDUCTION = 5.0

KEY_COMPONENT_NAMES = [
    "主标题与副标题",
    "可视化时间轴",
    "医学数据展示区",
    "患者金句/引用块",
    "合规声明/免责声明",
]
POSITION_COMPONENT_NAMES = [
    "时间轴",
    "医学数据展示区",
    "患者金句",
    "引用块",
]


def refresh_case_summary(case_id: str) -> Dict[str, Any]:
    """基于当前 case 产物重建精简版 summary。

    Args:
        case_id: 病例编号。

    Returns:
        最新汇总结果。
    """
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
    summary["scorecard"] = _build_scorecard(
        outline_compare=outline_compare,
        story_compare=story_compare,
        summary=summary,
        audit_overview=audit_overview,
    )
    _write_json(summary, case_dir / "summary.json")
    return summary


def _merge_image_summary(case_dir: Path, summary: Dict[str, Any], audit_overview: Dict[str, bool]) -> None:
    """合并图片审核汇总。

    Args:
        case_dir: 当前 case 临时目录。
        summary: 汇总结果对象。
        audit_overview: 审核总览对象。
    """
    image_design_path = case_dir / "image_design_validation.json"
    if image_design_path.exists():
        image_design = _read_json(image_design_path)
        issue_ids = _collect_issue_ids(image_design)
        audit_overview["image_design_passed"] = bool(image_design.get("is_passed"))
        summary["image_design"] = {
            "passed": bool(image_design.get("is_passed")),
            "issue_count": len(image_design.get("issues") or []),
            "issue_ids": issue_ids,
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

    image_compare_path = case_dir / "image_fact_validation.json"
    if image_compare_path.exists():
        image_compare = _read_json(image_compare_path)
        illustrations = image_compare.get("illustrations") or []
        passed_count = sum(1 for item in illustrations if _image_result_passed(item.get("result")))
        total_count = len(illustrations)
        failed_illustration_ids = [
            item.get("image_id")
            for item in illustrations
            if not _image_result_passed(item.get("result"))
        ]
        image_fact_passed = total_count > 0 and passed_count == total_count
        audit_overview["image_fact_passed"] = image_fact_passed
        summary["image_fact"] = {
            "status": image_compare.get("status", ""),
            "passed": image_fact_passed,
            "failed_illustration_ids": failed_illustration_ids,
            "passed_count": passed_count,
            "total_count": total_count,
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
        summary["final_image_layout_detail"] = final_image_layout


def _build_scorecard(
    outline_compare: Dict[str, Any],
    story_compare: Dict[str, Any],
    summary: Dict[str, Any],
    audit_overview: Dict[str, bool],
) -> Dict[str, Any]:
    """构建两层制评分卡。

    Args:
        outline_compare: 大纲硬规则结果。
        story_compare: Story 硬规则结果。
        summary: 当前汇总对象。
        audit_overview: 审核总览。

    Returns:
        评分卡结果。
    """
    outline_score = _fact_ratio_score(outline_compare, OUTLINE_FACT_MAX_SCORE)
    story_score = _fact_ratio_score(story_compare, STORY_FACT_MAX_SCORE)
    image_design_score = _image_design_score(summary)
    image_consistency_score = _image_consistency_score(audit_overview)
    image_fact_score = _image_fact_score(summary)
    final_image_layout_score = _final_image_layout_score(summary)
    gate_passed = all(
        [
            audit_overview.get("outline_passed", False),
            audit_overview.get("story_passed", False),
            audit_overview.get("image_fact_passed", False),
        ]
    )
    total_score = round(
        outline_score
        + story_score
        + image_design_score
        + image_consistency_score
        + image_fact_score
        + final_image_layout_score,
        2,
    )
    return {
        "gate_passed": gate_passed,
        "high_score_eligible": gate_passed,
        "total_score": total_score,
        "max_score": 100,
        "breakdown": {
            "outline_fact_score": outline_score,
            "story_fact_score": story_score,
            "image_design_score": image_design_score,
            "image_consistency_score": image_consistency_score,
            "image_fact_score": image_fact_score,
            "final_image_layout_score": final_image_layout_score,
        },
    }


def _fact_ratio_score(compare_result: Dict[str, Any], max_score: float) -> float:
    """按字段通过比例计算事实类得分。

    Args:
        compare_result: 硬规则对比结果。
        max_score: 该维度满分。

    Returns:
        按比例折算后的得分。
    """
    passed_count, total_count = _count_passed_fields(compare_result)
    if total_count == 0:
        return 0.0
    return round(passed_count / total_count * max_score, 2)


def _count_passed_fields(compare_result: Dict[str, Any]) -> Tuple[int, int]:
    """统计字段通过数量。

    Args:
        compare_result: 硬规则对比结果。

    Returns:
        通过字段数和总字段数。
    """
    field_results = compare_result.get("field_results")
    if not isinstance(field_results, dict):
        return 0, 0
    total_count = 0
    passed_count = 0
    for result in field_results.values():
        if not isinstance(result, dict):
            continue
        total_count += 1
        if bool(result.get("passed")):
            passed_count += 1
    return passed_count, total_count


def _image_design_score(summary: Dict[str, Any]) -> float:
    """按图片通过比例计算图片设计得分。

    Args:
        summary: 当前汇总对象。

    Returns:
        图片设计得分。
    """
    image_fact = summary.get("image_fact") or {}
    total_count = int(image_fact.get("total_count") or 0)
    if total_count <= 0:
        return 0.0
    image_design = summary.get("image_design") or {}
    if bool(image_design.get("passed")):
        return IMAGE_DESIGN_MAX_SCORE
    failed_count = _failed_image_count_from_issue_ids(image_design.get("issue_ids") or [], total_count)
    passed_count = max(total_count - failed_count, 0)
    return round(passed_count / total_count * IMAGE_DESIGN_MAX_SCORE, 2)


def _image_consistency_score(audit_overview: Dict[str, bool]) -> float:
    """计算多图一致性得分。

    Args:
        audit_overview: 审核总览。

    Returns:
        一致性得分。
    """
    return IMAGE_CONSISTENCY_MAX_SCORE if audit_overview.get("image_consistant_passed", False) else 0.0


def _image_fact_score(summary: Dict[str, Any]) -> float:
    """按中间步骤图片事实一致性比例计算得分。

    Args:
        summary: 当前汇总对象。

    Returns:
        图片事实一致性得分。
    """
    image_fact = summary.get("image_fact") or {}
    total_count = int(image_fact.get("total_count") or 0)
    passed_count = int(image_fact.get("passed_count") or 0)
    if total_count <= 0:
        return 0.0
    return round(passed_count / total_count * IMAGE_FACT_MAX_SCORE, 2)


def _final_image_layout_score(summary: Dict[str, Any]) -> float:
    """按长图结构扣分规则计算得分。

    Args:
        summary: 当前汇总对象。

    Returns:
        长图结构得分。
    """
    detail = summary.get("final_image_layout_detail")
    if not isinstance(detail, dict):
        return 0.0
    issues = detail.get("issues") or []
    issue_mapping = {
        str(item.get("issue_id") or ""): item
        for item in issues
        if isinstance(item, dict)
    }
    missing_count = _missing_component_count(issue_mapping.get("key_components_check"))
    position_count = _position_error_count(issue_mapping.get("component_position_logic"))
    redundant_count = _redundant_count(issue_mapping.get("redundant_sections_check"))
    score = FINAL_IMAGE_LAYOUT_MAX_SCORE
    score -= missing_count * FINAL_IMAGE_LAYOUT_MISSING_DEDUCTION
    score -= position_count * FINAL_IMAGE_LAYOUT_POSITION_DEDUCTION
    score -= redundant_count * FINAL_IMAGE_LAYOUT_REDUNDANT_DEDUCTION
    return round(max(score, 0.0), 2)


def _missing_component_count(issue: Any) -> int:
    """估算缺失必要结构数量。

    Args:
        issue: 单个问题对象。

    Returns:
        缺失数量。
    """
    return _count_named_mentions(issue, KEY_COMPONENT_NAMES)


def _position_error_count(issue: Any) -> int:
    """估算位置错误数量。

    Args:
        issue: 单个问题对象。

    Returns:
        位置错误数量。
    """
    return _count_named_mentions(issue, POSITION_COMPONENT_NAMES)


def _redundant_count(issue: Any) -> int:
    """估算冗余内容数量。

    Args:
        issue: 单个问题对象。

    Returns:
        冗余数量。
    """
    if not isinstance(issue, dict):
        return 0
    evidence_used = issue.get("evidence_used")
    if isinstance(evidence_used, list) and evidence_used:
        return len(evidence_used)
    return 1


def _count_named_mentions(issue: Any, names: List[str]) -> int:
    """根据文本中出现的组件名称估算问题数量。

    Args:
        issue: 单个问题对象。
        names: 待匹配的组件名称列表。

    Returns:
        命中的组件数量。
    """
    if not isinstance(issue, dict):
        return 0
    text = " ".join(
        [
            str(issue.get("issue_description") or ""),
            str(issue.get("reason") or ""),
            " ".join(str(item) for item in (issue.get("evidence_used") or [])),
        ]
    )
    count = sum(1 for name in names if name in text)
    return count or 1


def _failed_image_count_from_issue_ids(issue_ids: List[Any], total_count: int) -> int:
    """从 issue_id 中提取失败图片数量。

    Args:
        issue_ids: 问题编号列表。
        total_count: 总图片数。

    Returns:
        失败图片数量。
    """
    image_ids = set()
    for issue_id in issue_ids:
        match = re.search(r"图\s*(\d+)", str(issue_id))
        if match:
            image_ids.add(match.group(1))
    if image_ids:
        return len(image_ids)
    return total_count


def _collect_issue_ids(result: Dict[str, Any]) -> List[str]:
    """收集问题编号列表。

    Args:
        result: 任一审核结果对象。

    Returns:
        问题编号列表。
    """
    issues = result.get("issues")
    if not isinstance(issues, list):
        return []
    output: List[str] = []
    for item in issues:
        if not isinstance(item, dict):
            continue
        issue_id = str(item.get("issue_id") or "").strip()
        if issue_id:
            output.append(issue_id)
    return output


def _image_result_passed(result: Any) -> bool:
    """统一判断图片事实审核结果是否通过。

    Args:
        result: 单张图片审核结果。

    Returns:
        是否通过。
    """
    return bool(isinstance(result, dict) and result.get("overall_passed"))


def _failed_fields(compare_result: Dict[str, Any]) -> List[str]:
    """提取对比失败字段。

    Args:
        compare_result: 硬规则对比结果。

    Returns:
        失败字段名列表。
    """
    field_results = compare_result.get("field_results")
    if not isinstance(field_results, dict):
        return []
    return [
        field
        for field, result in field_results.items()
        if isinstance(result, dict) and not result.get("passed")
    ]


def _read_json(path: Path) -> Dict[str, Any]:
    """读取 JSON 文件。

    Args:
        path: 文件路径。

    Returns:
        JSON 对象。
    """
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(data: Dict[str, Any], output_path: Path) -> None:
    """写入 JSON 文件。

    Args:
        data: 输出对象。
        output_path: 输出路径。
    """
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
