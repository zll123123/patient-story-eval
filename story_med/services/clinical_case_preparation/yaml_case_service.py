"""YAML 测试数据读取服务。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from story_med.config.settings import (
    DATA_DIR,
    DEFAULT_CLINICAL_CASE_FILE,
    DEFAULT_EDIT_DIALOGUE_CASE_FILE,
    DEFAULT_HARD_RULE_FIELD_FILE,
)
from story_med.models.case_model import StoryCaseConfig
from story_med.utils.yaml_loader import load_yaml_file

DEFAULT_INTEND_CASE_FILE = DATA_DIR / "intend_cases.yaml"


def load_clinical_case_config(config_file: Path = DEFAULT_CLINICAL_CASE_FILE) -> Dict[str, Any]:
    """读取临床病例配置文件。"""
    if not config_file.exists():
        return {}
    data = load_yaml_file(config_file)
    return data if isinstance(data, dict) else {}


def load_hard_rule_fields(config_file: Path = DEFAULT_HARD_RULE_FIELD_FILE) -> Dict[str, Any]:
    """读取硬规则字段 schema。"""
    data = load_yaml_file(config_file)
    hard_rule_fields = data.get("hard_rule_fields")
    return hard_rule_fields if isinstance(hard_rule_fields, dict) else {}


def load_clinical_cases(config_file: Path = DEFAULT_CLINICAL_CASE_FILE) -> List[Dict[str, Any]]:
    """读取病例测试配置列表。"""
    config_data = load_clinical_case_config(config_file)
    raw_cases = config_data.get("clinical_cases") or []
    if isinstance(raw_cases, dict):
        return [dict(case_id=case_id, **value) for case_id, value in raw_cases.items() if isinstance(value, dict)]
    if isinstance(raw_cases, list):
        return [item for item in raw_cases if isinstance(item, dict)]
    return []


def get_clinical_case(case_id: str, config_file: Path = DEFAULT_CLINICAL_CASE_FILE) -> Dict[str, Any]:
    """按 case_id 获取病例配置。"""
    for case in load_clinical_cases(config_file):
        if str(case.get("case_id") or "") == case_id:
            return case
    raise FileNotFoundError(f"未找到病例配置: {case_id}")


def load_story_cases(case_file: Path | None = None) -> List[StoryCaseConfig]:
    """加载患者故事用例列表。"""
    config_file = case_file or DEFAULT_CLINICAL_CASE_FILE
    return [StoryCaseConfig.from_dict(_normalize_story_case(raw_case)) for raw_case in load_clinical_cases(config_file)]


def get_story_case(case_id: str, config_file: Path = DEFAULT_CLINICAL_CASE_FILE) -> StoryCaseConfig:
    """按 case_id 获取单条患者故事用例。"""
    return StoryCaseConfig.from_dict(_normalize_story_case(get_clinical_case(case_id, config_file)))


def load_edit_dialogue_cases(config_file: Path = DEFAULT_EDIT_DIALOGUE_CASE_FILE) -> List[Dict[str, Any]]:
    """加载多轮编辑对话测试用例。"""
    data = load_yaml_file(config_file)
    raw_cases = data.get("edit_dialogue_cases") or []
    if not isinstance(raw_cases, list):
        raise ValueError(f"edit_dialogue_cases 必须是列表: {config_file}")
    return [_normalize_dialogue_case(item) for item in raw_cases if isinstance(item, dict)]


def get_edit_dialogue_case(case_id: str, config_file: Path = DEFAULT_EDIT_DIALOGUE_CASE_FILE) -> Dict[str, Any]:
    """按 case_id 获取多轮编辑对话测试用例。"""
    for dialogue_case in load_edit_dialogue_cases(config_file):
        if dialogue_case["case_id"] == case_id:
            return dialogue_case
    raise KeyError(f"未找到多轮编辑对话测试用例: {case_id}")


def load_intent_schema(config_file: Path = DEFAULT_INTEND_CASE_FILE) -> Dict[str, Any]:
    """读取修改意图 schema。"""
    data = load_yaml_file(config_file)
    schema = data.get("intent_schema")
    return schema if isinstance(schema, dict) else {}


def _normalize_story_case(raw_case: Dict[str, Any]) -> Dict[str, Any]:
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


def _normalize_dialogue_case(raw_case: Dict[str, Any]) -> Dict[str, Any]:
    """标准化多轮编辑对话测试用例。"""
    turns = raw_case.get("turns") if isinstance(raw_case.get("turns"), list) else []
    normalized_turns = [_normalize_turn(item) for item in turns if isinstance(item, dict)]
    evaluation_mode = str(raw_case.get("evaluation_mode") or "per_turn").strip() or "per_turn"
    return {
        "case_id": str(raw_case.get("case_id") or "").strip(),
        "ref_clinical_case_id": str(raw_case.get("ref_clinical_case_id") or "").strip(),
        "summary": str(raw_case.get("summary") or "").strip(),
        "evaluation_mode": evaluation_mode,
        "turn_count": int(raw_case.get("turn_count") or len(normalized_turns)),
        "turns": normalized_turns,
        "coverage": raw_case.get("coverage") if isinstance(raw_case.get("coverage"), dict) else {},
    }


def _normalize_turn(raw_turn: Dict[str, Any]) -> Dict[str, Any]:
    """标准化单轮编辑对话数据。"""
    intent = raw_turn.get("intent") if isinstance(raw_turn.get("intent"), dict) else {}
    targets = intent.get("targets") if isinstance(intent.get("targets"), list) else []
    agents = raw_turn.get("involved_agents") if isinstance(raw_turn.get("involved_agents"), list) else []
    evaluation_focus = _normalize_evaluation_focus(raw_turn.get("evaluation_focus"), int(raw_turn.get("turn_id") or 0))
    return {
        "turn_id": int(raw_turn.get("turn_id") or 0),
        "message": str(raw_turn.get("message") or "").strip(),
        "intent": {
            "type": str(intent.get("type") or "").strip(),
            "targets": [str(target).strip() for target in targets if str(target).strip()],
        },
        "involved_agents": [str(agent).strip() for agent in agents if str(agent).strip()],
        "evaluation_focus": evaluation_focus,
    }


def _normalize_evaluation_focus(raw_focus: Any, turn_id: int) -> List[Dict[str, str]]:
    """标准化单轮评估点。"""
    if isinstance(raw_focus, list):
        items = [_normalize_focus_item(item, turn_id, index) for index, item in enumerate(raw_focus, start=1)]
        return [item for item in items if item]
    if isinstance(raw_focus, dict):
        item = _normalize_focus_item(raw_focus, turn_id, 1)
        return [item] if item else []
    text = str(raw_focus or "").strip()
    if not text:
        return []
    return [{"id": f"T{turn_id}", "description": text}]


def _normalize_focus_item(raw_item: Any, turn_id: int, index: int) -> Dict[str, str]:
    """标准化单个评估点。"""
    if isinstance(raw_item, dict):
        description = str(raw_item.get("description") or "").strip()
        if not description:
            return {}
        focus_id = str(raw_item.get("id") or f"T{turn_id}_{index}").strip()
        return {"id": focus_id, "description": description}
    description = str(raw_item or "").strip()
    if not description:
        return {}
    return {"id": f"T{turn_id}_{index}", "description": description}
