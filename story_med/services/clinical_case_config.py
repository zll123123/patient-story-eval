"""临床病例预期配置加载服务。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from story_med.config.settings import DEFAULT_CLINICAL_CASE_FILE, DEFAULT_HARD_RULE_FIELD_FILE
from story_med.models.case_model import StoryCaseConfig
from story_med.utils.yaml_loader import load_yaml_file


def load_clinical_case_config(config_file: Path = DEFAULT_CLINICAL_CASE_FILE) -> Dict[str, Any]:
    """加载临床病例预期配置。

    Args:
        config_file: 临床病例配置文件路径。

    Returns:
        配置字典。文件不存在时返回空配置。
    """
    if not config_file.exists():
        return {}
    data = load_yaml_file(config_file)
    return data if isinstance(data, dict) else {}


def load_hard_rule_fields() -> Dict[str, Any]:
    """读取硬规则字段定义。

    Returns:
        硬规则字段 schema。优先读取 clinical_case.yaml，缺失时兼容旧文件。
    """
    config_data = load_clinical_case_config()
    hard_rule_fields = config_data.get("hard_rule_fields")
    if isinstance(hard_rule_fields, dict) and hard_rule_fields:
        return hard_rule_fields
    legacy_data = load_yaml_file(DEFAULT_HARD_RULE_FIELD_FILE)
    legacy_fields = legacy_data.get("hard_rule_fields")
    return legacy_fields if isinstance(legacy_fields, dict) else {}


def apply_clinical_case_overrides(cases: list[StoryCaseConfig]) -> list[StoryCaseConfig]:
    """将 clinical_case.yaml 中的标题和硬规则预期覆盖到 case。

    Args:
        cases: 从主测试数据加载出的 case 列表。

    Returns:
        覆盖后的 case 列表。
    """
    clinical_cases = _clinical_cases()
    if not clinical_cases:
        return cases
    return [_override_case(case, clinical_cases.get(case.case_id)) for case in cases]


def _clinical_cases() -> Dict[str, Any]:
    """读取按 case_id 索引的临床病例配置。"""
    config_data = load_clinical_case_config()
    raw_cases = config_data.get("clinical_cases") or config_data.get("cases") or {}
    if isinstance(raw_cases, list):
        return {
            str(item.get("case_id")): item
            for item in raw_cases
            if isinstance(item, dict) and item.get("case_id")
        }
    return raw_cases if isinstance(raw_cases, dict) else {}


def _override_case(case: StoryCaseConfig, raw_override: Any) -> StoryCaseConfig:
    """覆盖单条 case 配置。"""
    if not isinstance(raw_override, dict):
        return case
    title = str(raw_override.get("title") or raw_override.get("description") or "").strip()
    hard_rules = _normalize_hard_rules(raw_override)
    return StoryCaseConfig(
        case_id=case.case_id,
        description=title or case.description,
        creative_brief=case.creative_brief,
        case_facts=case.case_facts,
        hard_rules=hard_rules or case.hard_rules,
    )


def _normalize_hard_rules(raw_override: Dict[str, Any]) -> Dict[str, Any]:
    """归一化 clinical_case.yaml 中的硬规则预期。"""
    raw_rules = raw_override.get("hard_rules")
    if isinstance(raw_rules, dict) and raw_rules:
        return raw_rules
    expected_fields = raw_override.get("expected_fields")
    if not isinstance(expected_fields, dict):
        return {}
    return {field_name: {"expected": expected} for field_name, expected in expected_fields.items()}
