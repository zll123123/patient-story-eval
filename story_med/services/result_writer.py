"""患者故事结果写入服务。"""

from __future__ import annotations

import json
from pathlib import Path

from story_med.models.case_model import StoryAgentRunResult


def write_run_result(result: StoryAgentRunResult, output_path: Path) -> None:
    """将运行结果写入 JSON 文件。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

