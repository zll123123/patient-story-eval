"""患者故事编辑测试命令行入口。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from story_med.config.app_config import load_app_config
from story_med.config.llm_app_config import load_llm_config
from story_med.services.edit_story_config import load_edit_cases
from story_med.services.edit_story_pipeline import run_edit_story_case


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    Returns:
        命令行解析器。
    """
    parser = argparse.ArgumentParser(description="运行患者故事编辑覆盖测试。")
    parser.add_argument("--case-id", default="", help="edit_story.yaml 中的单个编辑用例 ID")
    parser.add_argument("--case-ids", default="", help="多个编辑用例 ID，支持逗号、分号或竖线分隔")
    return parser


def main() -> int:
    """执行患者故事编辑覆盖测试。

    Returns:
        进程退出码。
    """
    args = build_parser().parse_args()
    app_config = load_app_config()
    llm_config = load_llm_config()
    case_ids = _resolve_case_ids(args.case_id, args.case_ids)
    results = [run_edit_story_case(app_config, llm_config, case_id) for case_id in case_ids]
    sys.stdout.write(json.dumps(_compact_results(results), ensure_ascii=False, indent=2) + "\n")
    return 0 if results and all(_validation_result(result).get("passed") for result in results) else 1


def _resolve_case_ids(case_id: str, case_ids: str) -> list[str]:
    """解析待执行的编辑用例列表。"""
    raw_value = case_ids.strip() or case_id.strip()
    if raw_value:
        return [item.strip() for item in re.split(r"[,;|]+", raw_value) if item.strip()]
    return [str(item.get("case_id") or "").strip() for item in load_edit_cases() if str(item.get("case_id") or "").strip()]


def _compact_results(results: list[dict]) -> list[dict]:
    """生成批量命令行摘要输出。"""
    return [_compact_result(result) for result in results]


def _compact_result(result: dict) -> dict:
    """生成命令行摘要输出。"""
    validation = _validation_result(result)
    adjustment = result.get("adjustment_result") or {}
    return {
        "case_id": result.get("case_id"),
        "ref_clinical_case_id": result.get("ref_clinical_case_id"),
        "session_id": result.get("session_id"),
        "task_id": result.get("task_id"),
        "adjustment_success": adjustment.get("success"),
        "downloaded_assets": adjustment.get("downloaded_assets"),
        "score": validation.get("score"),
        "passed": validation.get("passed"),
        "reason": validation.get("reason"),
        "evidence": validation.get("evidence"),
    }


def _validation_result(result: dict) -> dict:
    """读取编辑覆盖审核结果。"""
    validation = result.get("edit_coverage_validation") or {}
    return validation if isinstance(validation, dict) else {}


if __name__ == "__main__":
    sys.exit(main())
