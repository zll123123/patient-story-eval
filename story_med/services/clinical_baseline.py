"""临床病例评估基准读取服务。"""

from __future__ import annotations

from pathlib import Path

from story_med.config.settings import RESULTS_DIR
from story_med.models.case_model import StoryCaseConfig


def load_clinical_baseline(case: StoryCaseConfig) -> str:
    """读取独立病例提取结果作为评估基准。

    Args:
        case: 测试用例配置。

    Returns:
        病例评估基准文本。
    """
    if not case.image_dir.strip():
        raise ValueError(f"case 未配置 image_dir，无法读取 clinical_extract.md: {case.case_id}")
    path = clinical_baseline_path(case)
    if not path.exists():
        raise FileNotFoundError(f"缺少病例基准提取文件: {path}")
    return path.read_text(encoding="utf-8")


def clinical_baseline_path(case: StoryCaseConfig) -> Path:
    """返回指定 case 的病例基准文件路径。"""
    return RESULTS_DIR.parent / "output" / case.image_dir.strip() / "clinical_extract.md"
