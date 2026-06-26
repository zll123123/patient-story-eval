"""患者故事用例加载服务。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

from story_med.models.case_model import StoryCaseConfig
from story_med.services.clinical_case_config import apply_clinical_case_overrides
from story_med.utils.yaml_loader import load_yaml_file


def load_story_cases(case_file: Path) -> List[StoryCaseConfig]:
    """加载患者故事用例列表。"""
    if case_file.suffix.lower() == ".md":
        return apply_clinical_case_overrides(_load_story_cases_from_markdown(case_file))
    data = load_yaml_file(case_file)
    raw_cases = data.get("cases", [])
    if not isinstance(raw_cases, list):
        raise ValueError(f"cases 必须是列表: {case_file}")
    cases: List[StoryCaseConfig] = []
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise ValueError(f"单条 case 必须是字典: {case_file}")
        cases.append(StoryCaseConfig.from_dict(raw_case))
    return apply_clinical_case_overrides(cases)


def _load_story_cases_from_markdown(case_file: Path) -> List[StoryCaseConfig]:
    """从 Markdown 文件加载故事 case。"""
    if not case_file.exists():
        raise FileNotFoundError(f"文件不存在: {case_file}")
    content = case_file.read_text(encoding="utf-8")
    blocks = re.split(r"^##\s+", content, flags=re.MULTILINE)
    cases: List[StoryCaseConfig] = []
    for block in blocks[1:]:
        raw_case = _parse_markdown_case_block(block.strip(), case_file)
        cases.append(StoryCaseConfig.from_dict(raw_case))
    return cases


def _parse_markdown_case_block(block: str, case_file: Path) -> Dict[str, object]:
    """解析单条 Markdown case。"""
    lines = block.splitlines()
    if not lines:
        raise ValueError(f"空的 case block: {case_file}")
    header = lines[0].strip()
    match = re.match(r"(?P<case_id>[^|]+)\|\s*(?P<description>.+)", header)
    if not match:
        raise ValueError(f"case 标题格式错误: {header}")
    case_id = match.group("case_id").strip()
    description = match.group("description").strip()
    body = "\n".join(lines[1:]).strip()
    sections = _split_markdown_sections(body)
    hard_rules = _parse_hard_rules_json(sections.get("hard_rules", ""), case_file, case_id)
    return {
        "case_id": case_id,
        "description": description,
        "creative_brief": sections.get("creative_brief", "").strip(),
        "case_facts": sections.get("case_facts", "").strip(),
        "hard_rules": hard_rules,
    }


def _split_markdown_sections(body: str) -> Dict[str, str]:
    """按三级标题拆分 Markdown 段落。"""
    parts = re.split(r"^###\s+", body, flags=re.MULTILINE)
    sections: Dict[str, str] = {}
    for part in parts[1:]:
        lines = part.splitlines()
        if not lines:
            continue
        name = lines[0].strip().lower()
        sections[name] = "\n".join(lines[1:]).strip()
    return sections


def _parse_hard_rules_json(section_text: str, case_file: Path, case_id: str) -> Dict[str, object]:
    """解析 hard_rules JSON 代码块。"""
    match = re.search(r"```json\s*(?P<json_body>.*?)\s*```", section_text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"hard_rules 缺少 json 代码块: {case_file} {case_id}")
    return json.loads(match.group("json_body"))
