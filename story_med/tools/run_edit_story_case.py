"""患者故事编辑测试命令行入口。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from story_med.config.app_config import load_app_config
from story_med.config.llm_app_config import load_llm_config
from story_med.services.edit_story_pipeline import run_edit_story_case


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    Returns:
        命令行解析器。
    """
    parser = argparse.ArgumentParser(description="运行患者故事编辑覆盖测试。")
    parser.add_argument("--case-id", required=True, help="edit_story.yaml 中的编辑用例 ID")
    return parser


def main() -> int:
    """执行患者故事编辑覆盖测试。

    Returns:
        进程退出码。
    """
    args = build_parser().parse_args()
    result = run_edit_story_case(load_app_config(), load_llm_config(), args.case_id)
    sys.stdout.write(json.dumps(_compact_result(result), ensure_ascii=False, indent=2) + "\n")
    return 0 if _validation_result(result).get("passed") else 1


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
