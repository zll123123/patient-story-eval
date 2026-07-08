"""运行已有产物的 Story 合规审核。"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from story_med.config.llm_app_config import load_llm_config
from story_med.services.story_compliance_pipeline import run_story_compliance_validation
from story_med.services.summary_pipeline import refresh_case_summary
from story_med.services.yaml_case_service import load_story_cases


def build_parser() -> argparse.ArgumentParser:
    """构建命令行解析器。"""
    parser = argparse.ArgumentParser(description="基于已有产物运行 Story 合规审核。")
    parser.add_argument("--case-ids", required=True, help="case id 列表，支持逗号、分号或竖线分隔。")
    return parser


def main() -> int:
    """执行 Story 合规审核并刷新 summary。"""
    args = build_parser().parse_args()
    target_ids = _split_case_ids(args.case_ids)
    cases = {case.case_id: case for case in load_story_cases()}
    missing_ids = [case_id for case_id in target_ids if case_id not in cases]
    if missing_ids:
        raise ValueError(f"未找到 case: {', '.join(missing_ids)}")

    llm_config = load_llm_config()
    for case_id in target_ids:
        case = cases[case_id]
        result = run_story_compliance_validation(llm_config, case)
        summary = refresh_case_summary(case_id)
        sys.stdout.write(
            f"{case_id}: story_compliance={result.get('status')} "
            f"passed={result.get('is_passed')} score={(summary.get('scorecard') or {}).get('total_score')}\n"
        )
    return 0


def _split_case_ids(raw_value: str) -> list[str]:
    """解析 case id 列表。"""
    return [item.strip() for item in re.split(r"[,;|]+", raw_value) if item.strip()]


if __name__ == "__main__":
    sys.exit(main())
