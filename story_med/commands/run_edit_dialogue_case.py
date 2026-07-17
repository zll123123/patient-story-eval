"""患者故事多轮编辑对话测试命令行入口。"""

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
from story_med.config.app_config import load_llm_config
from story_med.services.story_edit_evaluation.edit_dialogue_pipeline import (
    run_edit_dialogue_case,
    write_dialogue_failure_result,
)
from story_med.services.clinical_case_preparation.yaml_case_service import load_edit_dialogue_cases
from story_med.utils.artifact_cleaner import clear_edit_dialogue_cases_artifacts


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    Returns:
        命令行解析器。
    """
    parser = argparse.ArgumentParser(description="运行患者故事多轮编辑对话测试。")
    parser.add_argument("--case-id", default="", help="edit_dialogue_cases.yaml 中的单个对话用例 ID")
    parser.add_argument("--case-ids", default="", help="多个对话用例 ID，支持逗号、分号或竖线分隔")
    return parser


def main(argv: list[str] | None = None) -> int:
    """执行患者故事多轮编辑对话测试。

    Returns:
        进程退出码。
    """
    args = build_parser().parse_args(argv)
    case_ids = _resolve_case_ids(args.case_id, args.case_ids)
    clear_edit_dialogue_cases_artifacts(case_ids)
    app_config = load_app_config()
    llm_config = load_llm_config()
    results = [
        _run_one_case(app_config, llm_config, case_id) for case_id in case_ids
    ]
    sys.stdout.write(json.dumps(_compact_results(results), ensure_ascii=False, indent=2) + "\n")
    return 0 if results and all(result.get("overall_passed") is True for result in results) else 1


def _run_one_case(
    app_config: Any, llm_config: Any, case_id: str
) -> dict[str, Any]:
    """执行单个编辑 case，异常时记录并继续批量执行。"""
    try:
        return run_edit_dialogue_case(app_config, llm_config, case_id)
    except Exception as exc:
        return write_dialogue_failure_result(case_id, "execution_orchestration_failed", str(exc))


def _resolve_case_ids(case_id: str, case_ids: str) -> list[str]:
    """解析命令行传入的对话用例 ID。"""
    raw_value = case_ids.strip() or case_id.strip()
    if raw_value:
        return [item.strip() for item in re.split(r"[,;|]+", raw_value) if item.strip()]
    return [
        str(item.get("case_id") or "").strip()
        for item in load_edit_dialogue_cases()
        if str(item.get("case_id") or "").strip()
    ]


def _compact_results(results: list[dict]) -> list[dict]:
    """生成命令行摘要输出。"""
    return [
        {
            "case_id": result.get("case_id"),
            "ref_clinical_case_id": result.get("ref_clinical_case_id"),
            "session_id": result.get("session_id"),
            "task_id": result.get("task_id"),
            "overall_passed": result.get("overall_passed"),
            "turn_count": result.get("turn_count"),
            "turns": [
                {
                    "turn_id": turn.get("turn_id"),
                    "execution_status": turn.get("execution_status"),
                    "audit_status": turn.get("audit_status", "not_run"),
                    "score": turn.get("score") if turn.get("audit_status") else None,
                    "included_previous_turns": turn.get("included_previous_turns"),
                }
                for turn in result.get("turn_results", [])
            ],
            "error": result.get("error", ""),
        }
        for result in results
    ]


if __name__ == "__main__":
    sys.exit(main())
