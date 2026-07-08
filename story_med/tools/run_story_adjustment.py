"""患者故事生成结果调整命令行入口。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from story_med.clients.agent_task_client import DEFAULT_AGENT_TYPE
from story_med.config.app_config import load_app_config
from story_med.config.llm_app_config import load_llm_config
from story_med.services.edit_story_config import get_edit_case
from story_med.services.edit_story_pipeline import finalize_edit_story_case
from story_med.services.story_adjustment_pipeline import run_story_adjustment


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    Returns:
        命令行解析器。
    """
    parser = argparse.ArgumentParser(description="调整已生成的患者故事结果。")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--agent-type", default=DEFAULT_AGENT_TYPE)
    return parser


def main() -> int:
    """执行患者故事调整节点。

    Returns:
        进程退出码。
    """
    app_config = load_app_config()
    args = build_parser().parse_args()
    edit_case = get_edit_case(args.case_id)
    result = run_story_adjustment(
        config=app_config,
        case_id=args.case_id,
        session_id=args.session_id,
        task_id=args.task_id,
        message=args.message,
        agent_type=args.agent_type,
    )
    completed = finalize_edit_story_case(
        llm_config=load_llm_config(),
        edit_case={**edit_case, "message": args.message, "session_id": args.session_id, "task_id": args.task_id},
        session_id=args.session_id,
        task_id=args.task_id,
        adjustment_result=result,
    )
    sys.stdout.write(json.dumps(_compact_result(completed), ensure_ascii=False, indent=2) + "\n")
    validation = completed.get("edit_coverage_validation") or {}
    return 0 if bool(validation.get("passed")) else 1


def _compact_result(result: dict) -> dict:
    """生成编辑+覆盖评估模式下的摘要输出。"""
    validation = result.get("edit_coverage_validation") or {}
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


if __name__ == "__main__":
    sys.exit(main())
