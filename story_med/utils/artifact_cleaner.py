"""患者故事评估产物清理工具。"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path

from story_med.config.settings import ASSETS_DIR, RESULTS_DIR, TMP_DIR


def should_clear_evaluation_artifacts(env: Mapping[str, str]) -> bool:
    """判断本次 DeepEval 运行是否需要清空历史产物。

    Args:
        env: 环境变量映射。

    Returns:
        仅全量非 audit_only 运行返回 True。
    """
    if env.get("STORY_MED_RUN_DEEPEVAL_PIPELINE", "").lower() != "true":
        return False
    if env.get("STORY_MED_DEEPEVAL_MODE", "").lower() == "audit_only":
        return False
    return not env.get("STORY_MED_CASE_IDS", "").strip()


def clear_evaluation_artifacts() -> None:
    """清空评估运行生成的临时和结果目录。"""
    for path in _target_directories():
        _reset_directory(path)


def _target_directories() -> list[Path]:
    """返回需要清理的目录列表。"""
    return [TMP_DIR, ASSETS_DIR, RESULTS_DIR / "runs"]


def _reset_directory(path: Path) -> None:
    """删除并重建单个目录。"""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
