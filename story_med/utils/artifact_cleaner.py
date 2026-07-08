"""患者故事评估产物清理工具。"""

from __future__ import annotations

import shutil
import re
from collections.abc import Mapping
from pathlib import Path

from story_med.config.settings import ASSETS_DIR, EDIT_DIALOGUE_RESULTS_DIR, EDIT_RESULTS_DIR, RESULTS_DIR, TMP_DIR


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


def target_case_ids_for_cleanup(env: Mapping[str, str]) -> list[str]:
    """解析需要清理产物的指定 case 列表。

    Args:
        env: 环境变量映射。

    Returns:
        目标 case 列表。仅当本次为指定 case 的 deepeval 运行时返回非空。
    """
    if env.get("STORY_MED_RUN_DEEPEVAL_PIPELINE", "").lower() != "true":
        return []
    raw_value = env.get("STORY_MED_CASE_IDS", "").strip()
    if not raw_value:
        return []
    return [item.strip() for item in re.split(r"[,;|]+", raw_value) if item.strip()]


def clear_evaluation_artifacts() -> None:
    """清空评估运行生成的临时和结果目录。"""
    for path in _target_directories():
        _reset_directory(path)


def clear_case_evaluation_artifacts(case_id: str) -> None:
    """清理单个原始病例的历史产物。

    Args:
        case_id: 原始病例 ID。
    """
    for path in _case_target_directories(case_id):
        if path.exists():
            shutil.rmtree(path)


def clear_edit_case_artifacts(case_id: str) -> None:
    """清理单个编辑测试用例的历史产物。

    Args:
        case_id: 编辑测试用例 ID。
    """
    for path in [EDIT_RESULTS_DIR / case_id, ASSETS_DIR / case_id]:
        if path.exists():
            shutil.rmtree(path)


def _target_directories() -> list[Path]:
    """返回需要清理的目录列表。"""
    return [TMP_DIR, ASSETS_DIR, RESULTS_DIR / "runs"]


def _case_target_directories(case_id: str) -> list[Path]:
    """返回单个病例需要清理的目录列表。"""
    return [
        TMP_DIR / case_id,
        ASSETS_DIR / case_id,
        RESULTS_DIR / "runs" / case_id,
        EDIT_RESULTS_DIR / case_id,
        EDIT_DIALOGUE_RESULTS_DIR / case_id,
    ]


def _reset_directory(path: Path) -> None:
    """删除并重建单个目录。"""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
