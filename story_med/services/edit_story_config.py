"""患者故事编辑测试数据加载。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from story_med.config.settings import DEFAULT_EDIT_CASE_FILE
from story_med.utils.yaml_loader import load_yaml_file


def load_edit_cases(config_file: Path = DEFAULT_EDIT_CASE_FILE) -> List[Dict[str, Any]]:
    """加载患者故事编辑测试用例。

    Args:
        config_file: 编辑测试数据文件。

    Returns:
        编辑测试用例列表。
    """
    data = load_yaml_file(config_file)
    raw_cases = data.get("edit_cases") or []
    if not isinstance(raw_cases, list):
        raise ValueError(f"edit_cases 必须是列表: {config_file}")
    return [_normalize_edit_case(item) for item in raw_cases if isinstance(item, dict)]


def get_edit_case(case_id: str, config_file: Path = DEFAULT_EDIT_CASE_FILE) -> Dict[str, Any]:
    """按 case_id 获取编辑测试用例。

    Args:
        case_id: 编辑测试用例 ID。
        config_file: 编辑测试数据文件。

    Returns:
        编辑测试用例。
    """
    for edit_case in load_edit_cases(config_file):
        if edit_case["case_id"] == case_id:
            return edit_case
    raise KeyError(f"未找到编辑测试用例: {case_id}")


def _normalize_edit_case(raw_case: Dict[str, Any]) -> Dict[str, Any]:
    """标准化编辑测试用例。"""
    evaluation = raw_case.get("evaluation") if isinstance(raw_case.get("evaluation"), dict) else {}
    return {
        "case_id": str(raw_case.get("case_id") or "").strip(),
        "ref_clinical_case_id": str(raw_case.get("ref_clinical_case_id") or "").strip(),
        "description": str(raw_case.get("description") or "").strip(),
        "message": str(raw_case.get("message") or "").strip(),
        "task_id": str(raw_case.get("task_id") or "").strip(),
        "session_id": str(raw_case.get("session_id") or "").strip(),
        "evaluation_focus": str(evaluation.get("evaluation_focus") or "").strip(),
        "evaluation": evaluation,
        "intent": raw_case.get("intent") or {},
        "involved_agent": raw_case.get("involved_agent") or {},
        "case_fact_consistency": raw_case.get("case_fact_consistency") or {},
    }
