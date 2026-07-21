"""患者故事生成-only 命令行入口。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from story_med.config.app_config import load_app_config
from story_med.config.settings import DEFAULT_CONFIG_FILE
from story_med.executors.patient_story_generation_executor import (
    PatientStoryGenerationExecutor,
)
from story_med.services.clinical_case_preparation.yaml_case_service import load_story_cases
from story_med.services.story_generation_evaluation.story_generation_pipeline import (
    run_story_generation,
)
from story_med.utils.artifact_cleaner import clear_case_evaluation_artifacts


def build_parser() -> argparse.ArgumentParser:
    """构建患者故事生成-only 参数解析器。"""
    parser = argparse.ArgumentParser(description="只执行患者故事生成和产物落盘。")
    parser.add_argument("--case-id", default="", help="单个患者故事 case ID")
    parser.add_argument("--case-ids", default="", help="多个 case ID，支持逗号、分号或竖线分隔")
    return parser


def main(argv: list[str] | None = None) -> int:
    """执行指定 case 的患者故事生成，不执行审核。"""
    args = build_parser().parse_args(argv)
    case_ids = _resolve_case_ids(args.case_id, args.case_ids)
    cases = {case.case_id: case for case in load_story_cases()}
    config = load_app_config(DEFAULT_CONFIG_FILE)
    executor = PatientStoryGenerationExecutor(config)
    results = [_run_case(executor, cases, case_id) for case_id in case_ids]
    sys.stdout.write(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    return 0 if results and all(item["success"] for item in results) else 1


def _run_case(
    executor: PatientStoryGenerationExecutor,
    cases: dict[str, Any],
    case_id: str,
) -> dict[str, Any]:
    """清理并执行单个患者故事生成 case。"""
    if case_id not in cases:
        return {"case_id": case_id, "success": False, "error": "case 不存在"}
    clear_case_evaluation_artifacts(case_id)
    try:
        result = run_story_generation(executor, cases[case_id])
        return {
            "case_id": case_id,
            "success": True,
            "task_id": result.task_id,
            "session_id": result.session_id,
        }
    except Exception as exc:
        return {"case_id": case_id, "success": False, "error": str(exc)}


def _resolve_case_ids(case_id: str, case_ids: str) -> list[str]:
    """解析患者故事 case ID，未指定时返回全部 case。"""
    raw_value = case_ids.strip() or case_id.strip()
    if raw_value:
        return [item.strip() for item in re.split(r"[,;|]+", raw_value) if item.strip()]
    return [case.case_id for case in load_story_cases()]


if __name__ == "__main__":
    sys.exit(main())
