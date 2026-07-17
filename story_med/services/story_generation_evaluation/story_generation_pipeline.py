"""患者故事生成与产物落盘服务。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from story_med.config.settings import GENERATION_RUNS_DIR, RESULTS_DIR
from story_med.executors.patient_story_generation_executor import (
    PatientStoryGenerationExecutor,
)
from story_med.models.case_model import StoryAgentRunResult, StoryCaseConfig


def run_story_generation(
    adapter: PatientStoryGenerationExecutor,
    case: StoryCaseConfig,
) -> StoryAgentRunResult:
    """调用患者故事 Agent，并持久化本次生成结果。"""
    run_result = adapter.run_case(case)
    _write_generation_result(run_result)
    if not run_result.success:
        raise RuntimeError(f"真实链路执行失败: {case.case_id} {run_result.error}")
    return run_result


def _write_generation_result(run_result: StoryAgentRunResult) -> None:
    """写入生成运行结果和全局最近运行索引。"""
    session_id = run_result.session_id or "failed"
    output_path = GENERATION_RUNS_DIR / run_result.case_id / f"{session_id}.json"
    _write_json(run_result.to_dict(), output_path)
    _write_json(run_result.to_dict(), RESULTS_DIR / "patient_story_run.json")


def _write_json(data: Dict[str, Any], output_path: Path) -> None:
    """写入 JSON 文件。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
