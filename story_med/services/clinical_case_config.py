"""临床病例配置加载服务。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from story_med.config.settings import DEFAULT_CLINICAL_CASE_FILE, DEFAULT_HARD_RULE_FIELD_FILE, RESULTS_DIR
from story_med.utils.yaml_loader import load_yaml_file


def load_clinical_case_config(config_file: Path = DEFAULT_CLINICAL_CASE_FILE) -> Dict[str, Any]:
    """读取临床病例配置文件。"""
    if not config_file.exists():
        return {}
    data = load_yaml_file(config_file)
    return data if isinstance(data, dict) else {}


def load_hard_rule_fields() -> Dict[str, Any]:
    """读取硬规则字段 schema。"""
    legacy_data = load_yaml_file(DEFAULT_HARD_RULE_FIELD_FILE)
    legacy_fields = legacy_data.get("hard_rule_fields")
    return legacy_fields if isinstance(legacy_fields, dict) else {}


def load_clinical_cases() -> List[Dict[str, Any]]:
    """读取病例测试配置列表。

    Returns:
        标准化后的病例配置列表。
    """
    config_data = load_clinical_case_config()
    raw_cases = config_data.get("clinical_cases") or []
    if isinstance(raw_cases, dict):
        return [dict(case_id=case_id, **value) for case_id, value in raw_cases.items() if isinstance(value, dict)]
    if isinstance(raw_cases, list):
        return [item for item in raw_cases if isinstance(item, dict)]
    return []


def get_clinical_case(case_id: str) -> Dict[str, Any]:
    """按 case_id 获取病例配置。"""
    for case in load_clinical_cases():
        if str(case.get("case_id") or "") == case_id:
            return case
    raise FileNotFoundError(f"未找到病例配置: {case_id}")


def normalize_case_parse_text(case_id: str, history: Dict[str, Any]) -> str:
    """将病例解析 history 转成可复用的病例事实文本。"""
    messages = history.get("messages") or []
    lines: List[str] = [f"# {case_id} 病例解析", ""]
    for item in messages:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if "病例解析完成" in content:
            lines.append(content)
            break
    return "\n".join(lines).strip() + "\n"


def load_case_parse_text(case_id: str, session_id: str) -> str:
    """读取指定病例最近产出的解析文本。"""
    case_parse_path = RESULTS_DIR / "assets" / case_id / session_id / "case_parse" / "case_parse.md"
    if case_parse_path.exists():
        return case_parse_path.read_text(encoding="utf-8")
    return ""
