"""测试目录通用配置。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from story_med.utils.artifact_cleaner import (
    clear_case_evaluation_artifacts,
    clear_evaluation_artifacts,
    should_clear_evaluation_artifacts,
    target_case_ids_for_cleanup,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@pytest.fixture(scope="session", autouse=True)
def clean_deepeval_artifacts() -> None:
    """在 DeepEval 重跑开始前清理历史产物。"""
    if should_clear_evaluation_artifacts(os.environ):
        clear_evaluation_artifacts()
        return
    for case_id in target_case_ids_for_cleanup(os.environ):
        clear_case_evaluation_artifacts(case_id)
