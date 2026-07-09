"""患者故事已有产物全链路审核入口。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from story_med.commands import run_patient_story_deepeval


def main(argv: list[str] | None = None) -> int:
    """基于已有生成产物重跑全链路审核与归因。"""
    forwarded_args = ["--mode", "audit_only", *(argv or [])]
    return run_patient_story_deepeval.main(forwarded_args)


if __name__ == "__main__":
    sys.exit(main())
