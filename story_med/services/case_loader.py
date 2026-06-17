"""患者故事用例加载服务。"""

from __future__ import annotations

from pathlib import Path
from typing import List

from story_med.models.case_model import StoryCaseConfig
from story_med.utils.yaml_loader import load_yaml_file


def load_story_cases(case_file: Path) -> List[StoryCaseConfig]:
    """加载患者故事用例列表。"""
    data = load_yaml_file(case_file)
    raw_cases = data.get("cases", [])
    if not isinstance(raw_cases, list):
        raise ValueError(f"cases 必须是列表: {case_file}")
    cases: List[StoryCaseConfig] = []
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise ValueError(f"单条 case 必须是字典: {case_file}")
        cases.append(StoryCaseConfig.from_dict(raw_case))
    return cases

