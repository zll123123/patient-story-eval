"""患者故事生成结果调整命令行入口。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from story_med.clients.agent_task_client import DEFAULT_AGENT_TYPE
from story_med.config.app_config import load_app_config
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
    args = build_parser().parse_args()
    result = run_story_adjustment(
        config=load_app_config(),
        case_id=args.case_id,
        session_id=args.session_id,
        task_id=args.task_id,
        message=args.message,
        agent_type=args.agent_type,
    )
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
