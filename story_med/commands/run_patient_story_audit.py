"""患者故事已有产物全链路审核入口。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from story_med.commands import run_patient_story_deepeval


def main(argv: list[str] | None = None) -> int:
    """基于已有生成产物重跑全链路审核与归因。"""
    forwarded_args = list(argv or [])
    previous_mode = os.environ.get("STORY_MED_DEEPEVAL_MODE")
    os.environ["STORY_MED_DEEPEVAL_MODE"] = "audit_only"
    try:
        return run_patient_story_deepeval.main(forwarded_args)
    finally:
        if previous_mode is None:
            os.environ.pop("STORY_MED_DEEPEVAL_MODE", None)
        else:
            os.environ["STORY_MED_DEEPEVAL_MODE"] = previous_mode


if __name__ == "__main__":
    sys.exit(main())
