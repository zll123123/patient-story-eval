"""病例图片输入发现服务。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from story_med.config.settings import CASE_IMAGE_DIR

SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def resolve_case_image_root() -> Path:
    """解析病例图片根目录。

    Returns:
        病例图片根目录。
    """
    raw_value = os.getenv("STORY_MED_CASE_IMAGE_DIR", "").strip()
    if raw_value:
        return Path(raw_value).expanduser().resolve()
    return CASE_IMAGE_DIR


def list_case_images(case_id: str, image_root: Path | None = None) -> List[Path]:
    """读取指定 case 的病例图片列表。

    Args:
        case_id: 测试用例编号。
        image_root: 图片根目录，默认读取配置目录。

    Returns:
        按文件名排序后的病例图片路径。

    Raises:
        FileNotFoundError: case 图片目录不存在。
        RuntimeError: 图片目录下没有支持的图片文件。
    """
    root = image_root or resolve_case_image_root()
    case_dir = root / case_id
    if not case_dir.exists():
        raise FileNotFoundError(f"病例图片目录不存在: {case_dir}")
    images = sorted(
        [
            path
            for path in case_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
        ],
        key=lambda path: path.name,
    )
    if not images:
        raise RuntimeError(f"病例图片目录没有可上传图片: {case_dir}")
    return images


def list_case_images_by_path(image_dir: Path) -> List[Path]:
    """读取指定图片目录下的病例图片列表。"""
    if not image_dir.exists():
        raise FileNotFoundError(f"病例图片目录不存在: {image_dir}")
    images = sorted(
        [
            path
            for path in image_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
        ],
        key=lambda path: path.name,
    )
    if not images:
        raise RuntimeError(f"病例图片目录没有可上传图片: {image_dir}")
    return images
