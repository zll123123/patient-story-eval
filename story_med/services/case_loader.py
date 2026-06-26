"""患者故事用例加载服务。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from story_med.models.case_model import StoryCaseConfig
from story_med.services.clinical_case_config import get_clinical_case, load_clinical_cases


def load_story_cases(case_file: Path | None = None) -> List[StoryCaseConfig]:
    """加载患者故事用例列表。

    Args:
        case_file: 已废弃，仅保留兼容签名。

    Returns:
        临床病例配置中的用例列表。
    """
    del case_file
    cases: List[StoryCaseConfig] = []
    for raw_case in load_clinical_cases():
        cases.append(StoryCaseConfig.from_dict(_normalize_case(raw_case)))
    return cases


def get_story_case(case_id: str) -> StoryCaseConfig:
    """按 case_id 获取单条病例配置。"""
    return StoryCaseConfig.from_dict(_normalize_case(get_clinical_case(case_id)))


def _normalize_case(raw_case: Dict[str, Any]) -> Dict[str, Any]:
    """标准化 clinical_case.yaml 中的 case 定义。"""
    case_id = str(raw_case.get("case_id") or "").strip()
    title = str(raw_case.get("title") or raw_case.get("description") or "").strip()
    creative_brief = str(raw_case.get("creative_brief") or "").strip()
    hard_rules = raw_case.get("hard_rules") or {}
    case_parse = str(raw_case.get("case_parse") or "").strip()
    normalized_hard_rules = _normalize_hard_rules(hard_rules)
    return {
        "case_id": case_id,
        "description": title,
        "creative_brief": creative_brief,
        "image_dir": str(raw_case.get("image_dir") or "").strip(),
        "case_facts": case_parse or str(raw_case.get("case_facts") or "").strip(),
        "case_parse": case_parse,
        "hard_rules": normalized_hard_rules,
    }


def _normalize_hard_rules(hard_rules: Any) -> Dict[str, Any]:
    """标准化 hard_rules.expected.value 结构。"""
    if not isinstance(hard_rules, dict):
        return {}
    normalized: Dict[str, Any] = {}
    for field_name, field_rule in hard_rules.items():
        if not isinstance(field_rule, dict):
            continue
        expected = field_rule.get("expected")
        if not isinstance(expected, dict) or "value" not in expected:
            expected = {"value": expected}
        normalized[field_name] = {"expected": expected}
    return normalized
