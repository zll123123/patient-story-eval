"""患者故事多轮编辑对话测试数据加载。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from story_med.config.settings import DEFAULT_EDIT_DIALOGUE_CASE_FILE
from story_med.utils.yaml_loader import load_yaml_file


def load_edit_dialogue_cases(config_file: Path = DEFAULT_EDIT_DIALOGUE_CASE_FILE) -> List[Dict[str, Any]]:
    """加载多轮编辑对话测试用例。

    Args:
        config_file: 多轮编辑对话测试数据文件。

    Returns:
        标准化后的多轮编辑对话测试用例列表。
    """
    data = load_yaml_file(config_file)
    raw_cases = data.get("edit_dialogue_cases") or []
    if not isinstance(raw_cases, list):
        raise ValueError(f"edit_dialogue_cases 必须是列表: {config_file}")
    return [_normalize_dialogue_case(item) for item in raw_cases if isinstance(item, dict)]


def get_edit_dialogue_case(case_id: str, config_file: Path = DEFAULT_EDIT_DIALOGUE_CASE_FILE) -> Dict[str, Any]:
    """按 case_id 获取多轮编辑对话测试用例。

    Args:
        case_id: 多轮编辑对话测试用例 ID。
        config_file: 多轮编辑对话测试数据文件。

    Returns:
        多轮编辑对话测试用例。
    """
    for dialogue_case in load_edit_dialogue_cases(config_file):
        if dialogue_case["case_id"] == case_id:
            return dialogue_case
    raise KeyError(f"未找到多轮编辑对话测试用例: {case_id}")


def _normalize_dialogue_case(raw_case: Dict[str, Any]) -> Dict[str, Any]:
    """标准化多轮编辑对话测试用例。"""
    turns = raw_case.get("turns") if isinstance(raw_case.get("turns"), list) else []
    normalized_turns = [_normalize_turn(item) for item in turns if isinstance(item, dict)]
    return {
        "case_id": str(raw_case.get("case_id") or "").strip(),
        "ref_clinical_case_id": str(raw_case.get("ref_clinical_case_id") or "").strip(),
        "summary": str(raw_case.get("summary") or "").strip(),
        "turn_count": int(raw_case.get("turn_count") or len(normalized_turns)),
        "turns": normalized_turns,
        "coverage": raw_case.get("coverage") if isinstance(raw_case.get("coverage"), dict) else {},
    }


def _normalize_turn(raw_turn: Dict[str, Any]) -> Dict[str, Any]:
    """标准化单轮编辑对话数据。"""
    intent = raw_turn.get("intent") if isinstance(raw_turn.get("intent"), dict) else {}
    targets = intent.get("targets") if isinstance(intent.get("targets"), list) else []
    agents = raw_turn.get("involved_agents") if isinstance(raw_turn.get("involved_agents"), list) else []
    return {
        "turn_id": int(raw_turn.get("turn_id") or 0),
        "message": str(raw_turn.get("message") or "").strip(),
        "intent": {
            "type": str(intent.get("type") or "").strip(),
            "targets": [str(target).strip() for target in targets if str(target).strip()],
        },
        "involved_agents": [str(agent).strip() for agent in agents if str(agent).strip()],
        "evaluation_focus": str(raw_turn.get("evaluation_focus") or "").strip(),
    }
