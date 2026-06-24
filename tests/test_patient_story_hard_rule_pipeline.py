"""患者故事批量硬规则 LLM 对比测试。"""

from __future__ import annotations

import json
import os
from typing import List

import pytest

from story_med.adapters.patient_story_agent import PatientStoryAgentAdapter
from story_med.config.app_config import load_app_config
from story_med.config.llm_app_config import load_llm_config
from story_med.config.settings import DEFAULT_CASE_FILE, DEFAULT_CONFIG_FILE, RESULTS_DIR, TMP_DIR
from story_med.models.case_model import StoryCaseConfig
from story_med.services.case_loader import load_story_cases
from story_med.services.hard_rule_llm_pipeline import (
    run_case_compare_pipeline,
    run_case_facts_compare_pipeline,
    run_existing_assets_compare_pipeline,
)


def test_seed_cases_run_to_hard_rule_compare() -> None:
    """批量执行种子 case 到硬规则对比结果阶段。"""
    if os.getenv("STORY_MED_RUN_HARD_RULE_PIPELINE", "").lower() != "true":
        pytest.skip("需要设置 STORY_MED_RUN_HARD_RULE_PIPELINE=true 才执行外部链路")
    cases = _select_seed_cases(load_story_cases(DEFAULT_CASE_FILE))
    assert cases, "未找到需要执行的种子 case"

    llm_config = load_llm_config()
    source_mode = os.getenv("STORY_MED_PIPELINE_SOURCE_MODE", "agent").strip()
    app_config = load_app_config(DEFAULT_CONFIG_FILE)
    adapter = PatientStoryAgentAdapter(app_config)
    include_visual_steps = _include_visual_steps()
    summaries = []
    failures = []

    for case in cases:
        try:
            if source_mode == "case_facts":
                summaries.append(run_case_facts_compare_pipeline(llm_config, case))
            elif source_mode == "results_assets":
                summaries.append(run_existing_assets_compare_pipeline(llm_config, case, _existing_session_id(case)))
            else:
                summaries.append(run_case_compare_pipeline(adapter, llm_config, case, include_visual_steps))
        except Exception as exc:
            failures.append({"case_id": case.case_id, "error": str(exc)})

    output = {"summaries": summaries, "failures": failures}
    (TMP_DIR / "seed_case_compare_summary.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    assert not failures, failures


def _select_seed_cases(cases: List[StoryCaseConfig]) -> List[StoryCaseConfig]:
    """选择需要跑批的种子 case。"""
    target_case_ids = _target_case_ids()
    if target_case_ids:
        return [case for case in cases if case.case_id in target_case_ids]
    return [case for case in cases if case.case_id != "SM_001"]


def _target_case_ids() -> List[str]:
    """从环境变量读取指定 case 列表。"""
    raw_value = os.getenv("STORY_MED_CASE_IDS", "").strip()
    if not raw_value:
        return []
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _include_visual_steps() -> bool:
    """读取是否执行图片生成接口。"""
    return os.getenv("STORY_MED_PIPELINE_INCLUDE_VISUAL_STEPS", "").strip().lower() == "true"


def _existing_session_id(case: StoryCaseConfig) -> str:
    """读取或推断 results/assets 下已有产物的 session_id。"""
    session_id = os.getenv("STORY_MED_EXISTING_SESSION_ID", "").strip()
    if session_id:
        return session_id
    case_asset_dir = RESULTS_DIR / "assets" / case.case_id
    sessions = sorted(
        [path for path in case_asset_dir.iterdir() if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not sessions:
        raise RuntimeError(f"未找到已有接口产物目录: {case_asset_dir}")
    return sessions[0].name
