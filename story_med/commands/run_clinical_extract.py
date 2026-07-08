"""病例图片信息提取运行入口。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from story_med.config.vision_app_config import load_vision_config
from story_med.services.clinical_extract_pipeline import run_clinical_extract


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="提取病例图片中的关键信息。")
    parser.add_argument("--image-dir", required=True, help="img 目录下的病例文件夹名称，或绝对路径")
    return parser


def main() -> int:
    """执行病例信息提取。"""
    args = build_parser().parse_args()
    config = load_vision_config()
    run_clinical_extract(args.image_dir, config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
