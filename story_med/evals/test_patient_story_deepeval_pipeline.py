"""患者故事 Deepeval 双模式评估入口。"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

import pytest

from story_med.adapters.patient_story_agent import PatientStoryAgentAdapter
from story_med.config.app_config import load_app_config
from story_med.config.llm_app_config import load_llm_config
from story_med.config.settings import DEFAULT_CASE_FILE, DEFAULT_CONFIG_FILE, RESULTS_DIR, TMP_DIR
from story_med.config.vision_app_config import load_vision_config
from story_med.models.case_model import StoryCaseConfig
from story_med.services.audit_attribution_pipeline import run_case_audit_attribution
from story_med.services.case_loader import load_story_cases
from story_med.services.hard_rule_llm_pipeline import (
    run_case_compare_pipeline,
    run_existing_assets_compare_pipeline,
)
from story_med.services.image_compare_pipeline import run_case_latest_image_compare
from story_med.services.summary_pipeline import refresh_case_summary


def _selected_case_ids() -> List[str]:
    """按环境变量选择需要执行的 case_id 列表。"""
    cases = load_story_cases(DEFAULT_CASE_FILE)
    selected_cases = _selected_cases(cases)
    return [case.case_id for case in selected_cases]


def _selected_cases(cases: List[StoryCaseConfig]) -> List[StoryCaseConfig]:
    """按环境变量选择需要执行的 case。"""
    target_case_ids = _target_case_ids()
    if not target_case_ids:
        return cases
    return [case for case in cases if case.case_id in target_case_ids]


def _target_case_ids() -> List[str]:
    """读取 case 过滤条件。"""
    raw_value = os.getenv("STORY_MED_CASE_IDS", "").strip()
    if not raw_value:
        return []
    return [item.strip() for item in re.split(r"[,;|]+", raw_value) if item.strip()]


def _eval_mode() -> str:
    """读取 Deepeval 执行模式。"""
    mode = os.getenv("STORY_MED_DEEPEVAL_MODE", "audit_only").strip().lower()
    if mode not in {"full_pipeline", "audit_only"}:
        raise ValueError(f"不支持的 STORY_MED_DEEPEVAL_MODE: {mode}")
    return mode


def _include_visual_steps() -> bool:
    """读取整链路模式下是否重跑图片生成接口。"""
    raw_value = os.getenv("STORY_MED_PIPELINE_INCLUDE_VISUAL_STEPS", "true").strip().lower()
    return raw_value == "true"


def _run_attribution() -> bool:
    """读取是否执行归因步骤。"""
    return os.getenv("STORY_MED_RUN_AUDIT_ATTRIBUTION", "").strip().lower() == "true"


def _existing_session_id(case: StoryCaseConfig) -> str:
    """读取指定 case 最近一次接口产物 session_id。"""
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


def _write_case_output(case_id: str, data: Dict[str, Any]) -> None:
    """写入 Deepeval 统一汇总文件中的单 case 结果。"""
    output_path = TMP_DIR / "deepeval_patient_story_summary.json"
    output: Dict[str, Any] = {"results": {}}
    if output_path.exists():
        loaded = json.loads(output_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            output.update(loaded)
            if not isinstance(output.get("results"), dict):
                output["results"] = {}
    output["results"][case_id] = data
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.mark.parametrize("case_id", _selected_case_ids(), ids=str)
def test_patient_story_deepeval_pipeline(case_id: str) -> None:
    """按模式执行单个患者故事评估并写入统一汇总。"""
    if os.getenv("STORY_MED_RUN_DEEPEVAL_PIPELINE", "").lower() != "true":
        pytest.skip("需要设置 STORY_MED_RUN_DEEPEVAL_PIPELINE=true 才执行 Deepeval 评估")

    mode = _eval_mode()
    cases = {case.case_id: case for case in load_story_cases(DEFAULT_CASE_FILE)}
    case = cases.get(case_id)
    assert case is not None, f"未找到需要执行的 case: {case_id}"

    llm_config = load_llm_config()
    vision_config = load_vision_config()
    app_config = load_app_config(DEFAULT_CONFIG_FILE)
    adapter = PatientStoryAgentAdapter(app_config)
    include_visual_steps = _include_visual_steps()
    run_attribution = _run_attribution()
    try:
        summary = _run_single_case(
            adapter=adapter,
            llm_config=llm_config,
            vision_config=vision_config,
            case=case,
            mode=mode,
            include_visual_steps=include_visual_steps,
            run_attribution=run_attribution,
        )
    except Exception as exc:
        _write_case_output(
            case_id=case_id,
            data={"mode": mode, "status": "failed", "error": str(exc)},
        )
        raise
    _write_case_output(
        case_id=case_id,
        data={"mode": mode, "status": "success", "summary": summary},
    )


def _run_single_case(
    adapter: PatientStoryAgentAdapter,
    llm_config,
    vision_config,
    case: StoryCaseConfig,
    mode: str,
    include_visual_steps: bool,
    run_attribution: bool,
) -> Dict[str, Any]:
    """执行单个 case 的评估流程。"""
    if mode == "full_pipeline":
        run_case_compare_pipeline(adapter, llm_config, case, include_visual_steps=include_visual_steps)
    else:
        run_existing_assets_compare_pipeline(llm_config, case, _existing_session_id(case))
    run_case_latest_image_compare(vision_config, case)
    summary = refresh_case_summary(case.case_id)
    if run_attribution:
        run_case_audit_attribution(llm_config, case.case_id)
    return summary
