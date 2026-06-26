"""测试目录通用配置。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from story_med.utils.artifact_cleaner import clear_evaluation_artifacts


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@pytest.fixture(scope="session", autouse=True)
def clean_deepeval_artifacts() -> None:
    """在 DeepEval 重跑开始前清理历史产物。"""
    if os.getenv("STORY_MED_RUN_DEEPEVAL_PIPELINE", "").lower() != "true":
        return
    if os.getenv("STORY_MED_DEEPEVAL_MODE", "").lower() == "audit_only":
        return
    clear_evaluation_artifacts()
