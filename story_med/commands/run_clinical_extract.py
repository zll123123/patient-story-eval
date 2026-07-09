"""病例图片信息提取运行入口。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from story_med.config.app_config import load_vision_config
from story_med.config.settings import CASE_IMAGE_DIR
from story_med.services.clinical_case_preparation.clinical_extract_pipeline import run_clinical_extract


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="提取病例图片中的关键信息。")
    parser.add_argument("--image-dir", default="", help="img 目录下的单个病例文件夹名称，或绝对路径")
    parser.add_argument("--image-dirs", default="", help="多个病例文件夹，支持逗号、分号或竖线分隔")
    return parser


def main(argv: list[str] | None = None) -> int:
    """执行病例信息提取。"""
    args = build_parser().parse_args(argv)
    config = load_vision_config()
    image_dirs = _resolve_image_dirs(args.image_dir, args.image_dirs)
    results = [run_clinical_extract(image_dir, config) for image_dir in image_dirs]
    sys.stdout.write(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    return 0


def _resolve_image_dirs(image_dir: str, image_dirs: str) -> list[str]:
    """解析待执行的病例图片目录列表。"""
    raw_value = image_dirs.strip() or image_dir.strip()
    if raw_value:
        import re

        return [item.strip() for item in re.split(r"[,;|]+", raw_value) if item.strip()]
    return sorted(path.name for path in CASE_IMAGE_DIR.iterdir() if path.is_dir())


if __name__ == "__main__":
    raise SystemExit(main())
