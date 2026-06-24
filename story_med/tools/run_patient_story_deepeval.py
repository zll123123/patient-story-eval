"""患者故事 DeepEval 简化运行入口。"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from story_med.config.settings import DEFAULT_CONFIG_FILE
from story_med.utils.yaml_loader import load_yaml_file


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    Returns:
        命令行解析器。
    """
    parser = argparse.ArgumentParser(description="运行患者故事 DeepEval 评估。")
    parser.add_argument("--mode", choices=["full_pipeline", "audit_only"], default="")
    parser.add_argument("--case-ids", default="")
    parser.add_argument("--identifier", default="")
    parser.add_argument("--no-visual-steps", action="store_true")
    parser.add_argument("--no-attribution", action="store_true")
    return parser


def load_deepeval_defaults() -> dict:
    """读取 DeepEval 默认配置。

    Returns:
        DeepEval 默认配置字典。
    """
    config_data = load_yaml_file(DEFAULT_CONFIG_FILE)
    deepeval_config = config_data.get("deepeval") or {}
    if not isinstance(deepeval_config, dict):
        return {}
    return deepeval_config


def build_command(test_file: Path, identifier: str) -> list[str]:
    """构建 deepeval 执行命令。

    Args:
        test_file: 测试文件路径。
        identifier: 运行标识。

    Returns:
        子进程命令列表。
    """
    command = ["deepeval", "test", "run", str(test_file)]
    if identifier:
        command.extend(["--identifier", identifier])
    return command


def build_env(args: argparse.Namespace, defaults: dict) -> dict[str, str]:
    """构建子进程环境变量。

    Args:
        args: 命令行参数。
        defaults: 配置文件默认值。

    Returns:
        环境变量字典。
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT_DIR)
    env["STORY_MED_RUN_DEEPEVAL_PIPELINE"] = "true"
    env["STORY_MED_DEEPEVAL_MODE"] = args.mode or str(defaults.get("mode", "full_pipeline"))
    env["STORY_MED_PIPELINE_INCLUDE_VISUAL_STEPS"] = _resolve_bool_env(
        cli_disabled=args.no_visual_steps,
        default_value=bool(defaults.get("include_visual_steps", True)),
    )
    env["STORY_MED_RUN_AUDIT_ATTRIBUTION"] = _resolve_bool_env(
        cli_disabled=args.no_attribution,
        default_value=bool(defaults.get("run_attribution", True)),
    )
    if args.case_ids.strip():
        env["STORY_MED_CASE_IDS"] = args.case_ids.strip()
    else:
        env.pop("STORY_MED_CASE_IDS", None)
    env.pop("STORY_MED_LLM_ENV_FILE", None)
    return env


def _resolve_bool_env(cli_disabled: bool, default_value: bool) -> str:
    """将布尔配置转换为环境变量值。

    Args:
        cli_disabled: 命令行是否显式关闭。
        default_value: 默认配置值。

    Returns:
        true 或 false。
    """
    if cli_disabled:
        return "false"
    return "true" if default_value else "false"


def _resolve_test_file(defaults: dict) -> Path:
    """解析测试文件路径。

    Args:
        defaults: 配置文件默认值。

    Returns:
        绝对路径。
    """
    test_file = str(defaults.get("test_file", "tests/test_patient_story_deepeval_pipeline.py"))
    return (ROOT_DIR / test_file).resolve() if not Path(test_file).is_absolute() else Path(test_file).resolve()


def main() -> int:
    """执行患者故事 DeepEval。

    Returns:
        进程退出码。
    """
    args = build_parser().parse_args()
    defaults = load_deepeval_defaults()
    command = build_command(_resolve_test_file(defaults), args.identifier)
    env = build_env(args, defaults)
    completed = subprocess.run(command, cwd=ROOT_DIR, env=env, check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    sys.exit(main())
