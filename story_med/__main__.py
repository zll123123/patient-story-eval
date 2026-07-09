"""患者故事评测统一运行入口。"""

from __future__ import annotations

import argparse
import sys
from typing import Callable

from story_med.commands import run_clinical_extract
from story_med.commands import run_edit_dialogue_audit
from story_med.commands import run_edit_dialogue_case
from story_med.commands import run_patient_story_audit
from story_med.commands import run_patient_story_deepeval

CommandHandler = Callable[[list[str] | None], int]


def build_parser() -> argparse.ArgumentParser:
    """构建统一命令行解析器。"""
    parser = argparse.ArgumentParser(
        description="患者故事评测统一入口。",
        usage=(
            "python3 -m story_med <command> [args]\n\n"
            "commands:\n"
            "  patient-story-full  运行患者故事生成+全链路审核+归因+上报\n"
            "  patient-story-audit 只对已有生成产物重跑全链路审核+归因\n"
            "  clinical-extract   批量提取病例图片结构化基线\n"
            "  patient-story-edit-full  运行多轮编辑执行+审核+归因\n"
            "  patient-story-edit-audit 只对已有编辑产物重跑审核+归因"
        ),
    )
    parser.add_argument("command", nargs="?", help="要执行的子命令")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="子命令参数")
    return parser


def command_registry() -> dict[str, CommandHandler]:
    """返回子命令与处理函数映射。"""
    return {
        "patient-story-full": run_patient_story_deepeval.main,
        "patient-story-audit": run_patient_story_audit.main,
        "clinical-extract": run_clinical_extract.main,
        "patient-story-edit-full": run_edit_dialogue_case.main,
        "patient-story-edit-audit": run_edit_dialogue_audit.main,
    }


def main(argv: list[str] | None = None) -> int:
    """执行统一命令分发。"""
    args = build_parser().parse_args(argv)
    command = str(args.command or "").strip()
    registry = command_registry()
    if not command:
        build_parser().print_help()
        return 1
    handler = registry.get(command)
    if handler is None:
        raise ValueError(f"不支持的命令: {command}")
    subcommand_args = list(args.args)
    if subcommand_args and subcommand_args[0] == "--":
        subcommand_args = subcommand_args[1:]
    return handler(subcommand_args)


if __name__ == "__main__":
    sys.exit(main())
