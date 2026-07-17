"""患者故事 DeepEval 执行编排服务。"""

from __future__ import annotations

import json
import os
import re
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Dict, List

from story_med.executors.patient_story_generation_executor import PatientStoryGenerationExecutor
from story_med.config.app_config import load_app_config
from story_med.config.app_config import load_llm_config
from story_med.config.settings import DEFAULT_CONFIG_FILE, RESULTS_DIR, STORY_AUDITS_DIR
from story_med.config.app_config import load_vision_config
from story_med.models.case_model import StoryCaseConfig
from story_med.services.story_generation_evaluation.audit_analysis_service import run_case_audit_attribution
from story_med.services.story_generation_evaluation.hard_rule_llm_pipeline import (
    run_existing_assets_compare_pipeline,
)
from story_med.services.story_generation_evaluation.image_audit_pipeline import run_case_latest_image_audit
from story_med.services.story_generation_evaluation.summary_pipeline import refresh_case_summary
from story_med.services.story_generation_evaluation.story_compliance_pipeline import run_story_compliance_validation
from story_med.services.story_generation_evaluation.story_generation_pipeline import (
    run_story_generation,
)
from story_med.services.clinical_case_preparation.yaml_case_service import load_story_cases


def run_selected_cases() -> List[Dict[str, Any]]:
    """按环境变量逐个执行 case，并在每个 case 落盘后立即审核。"""
    mode = _eval_mode()
    include_visual_steps = _include_visual_steps()
    run_attribution = _run_attribution()
    cases = _selected_cases(load_story_cases())
    llm_config = load_llm_config()
    vision_config = load_vision_config()
    app_config = load_app_config(DEFAULT_CONFIG_FILE)
    image_adapter = PatientStoryGenerationExecutor(app_config)
    results: List[Dict[str, Any]] = []

    for case in cases:
        result = run_single_case(
            image_adapter=image_adapter,
            llm_config=llm_config,
            vision_config=vision_config,
            case=case,
            mode=mode,
            include_visual_steps=include_visual_steps,
            run_attribution=run_attribution,
        )
        results.append(result)
    return results


def run_single_case(
    image_adapter: PatientStoryGenerationExecutor,
    llm_config: Any,
    vision_config: Any,
    case: StoryCaseConfig,
    mode: str,
    include_visual_steps: bool,
    run_attribution: bool,
) -> Dict[str, Any]:
    """执行单个 case 的生成、审核、归因和 DeepEval 评估。"""
    try:
        session_id = _run_generation_case(
            image_adapter=image_adapter,
            case=case,
            mode=mode,
        )
        _run_audit_case(
            llm_config=llm_config,
            vision_config=vision_config,
            case=case,
            session_id=session_id,
            run_attribution=run_attribution,
        )
        summary = refresh_case_summary(case.case_id)
        status = "success"
        error = ""
    except Exception as exc:
        status = "failed"
        error = str(exc)
        summary = _build_failed_pipeline_summary(case.case_id, error)
        _write_case_summary(case.case_id, summary)
    _write_case_output(case.case_id, {"mode": mode, "status": status, "error": error, "summary": summary})
    return {"case_id": case.case_id, "status": status, "summary": summary, "error": error}


def _run_generation_case(
    image_adapter: PatientStoryGenerationExecutor,
    case: StoryCaseConfig,
    mode: str,
) -> str:
    """执行单个 case 的生成流程。"""
    if mode == "image_case_pipeline":
        run_result = run_story_generation(image_adapter, case)
        return run_result.session_id
    else:
        return _existing_session_id(case)


def _run_audit_case(
    llm_config: Any,
    vision_config: Any,
    case: StoryCaseConfig,
    session_id: str,
    run_attribution: bool,
) -> None:
    """并发执行审核节点，全部完成后再执行归因。"""
    futures: Dict[str, Future[Any]] = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures["hard_rule_audit"] = executor.submit(
            run_existing_assets_compare_pipeline,
            llm_config,
            case,
            session_id,
        )
        futures["image_audit"] = executor.submit(
            run_case_latest_image_audit, vision_config, case, session_id
        )
        futures["story_compliance_audit"] = executor.submit(
            run_story_compliance_validation, llm_config, case, session_id
        )
        errors = _collect_audit_errors(futures)
    if errors:
        raise RuntimeError("审核节点执行失败: " + "; ".join(errors))
    refresh_case_summary(case.case_id)
    if run_attribution:
        run_case_audit_attribution(llm_config, case.case_id)


def _collect_audit_errors(futures: Dict[str, Future[Any]]) -> List[str]:
    """等待所有审核节点并收集异常，避免单个失败提前中断其他节点。"""
    errors: List[str] = []
    for stage_name, future in futures.items():
        try:
            future.result()
        except Exception as exc:
            errors.append(f"{stage_name}: {exc}")
    return errors


def _build_failed_pipeline_summary(case_id: str, error: str) -> Dict[str, Any]:
    """构建生成链路失败时的 summary，避免误读旧审核结果。"""
    overview_keys = [
        "outline_passed",
        "story_passed",
        "story_compliance_passed",
        "image_design_passed",
        "image_consistency_passed",
        "image_fact_passed",
        "final_image_layout_passed",
    ]
    return {
        "case_id": case_id,
        "pipeline_success": False,
        "pipeline_error": error,
        "session_id": "",
        "audit_overview": {key: False for key in overview_keys},
        "scorecard": {
            "total_score": 0.0,
            "gate_passed": False,
            "high_score_eligible": False,
            "breakdown": {
                "outline_fact_score": 0.0,
                "story_fact_score": 0.0,
                "story_compliance_score": 0.0,
                "image_design_score": 0.0,
                "image_consistency_score": 0.0,
                "image_fact_score": 0.0,
                "final_image_layout_score": 0.0,
            },
        },
        "failure_reason": "生成链路失败，未执行后续审核。",
    }


def _write_case_summary(case_id: str, summary: Dict[str, Any]) -> None:
    """写入单 case summary 文件。"""
    output_dir = STORY_AUDITS_DIR / case_id
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def _eval_mode() -> str:
    """读取 DeepEval 执行模式。"""
    mode = os.getenv("STORY_MED_DEEPEVAL_MODE", "audit_only").strip().lower()
    if mode not in {"audit_only", "image_case_pipeline"}:
        raise ValueError(f"不支持的 STORY_MED_DEEPEVAL_MODE: {mode}")
    return mode


def _include_visual_steps() -> bool:
    """读取是否重跑视觉步骤。"""
    raw_value = os.getenv("STORY_MED_PIPELINE_INCLUDE_VISUAL_STEPS", "true").strip().lower()
    return raw_value == "true"


def _run_attribution() -> bool:
    """读取是否执行归因步骤。"""
    raw_value = os.getenv("STORY_MED_RUN_AUDIT_ATTRIBUTION", "true").strip().lower()
    return raw_value == "true"


def _target_case_ids() -> List[str]:
    """读取目标 case 编号。"""
    raw_value = os.getenv("STORY_MED_CASE_IDS", "").strip()
    if not raw_value:
        return []
    return [item.strip() for item in re.split(r"[,;|]+", raw_value) if item.strip()]


def _selected_cases(cases: List[StoryCaseConfig]) -> List[StoryCaseConfig]:
    """按环境变量筛选 case。"""
    target_case_ids = _target_case_ids()
    if not target_case_ids:
        return cases
    return [case for case in cases if case.case_id in target_case_ids]


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
    """写入 DeepEval 统一汇总文件。"""
    output_path = STORY_AUDITS_DIR / "deepeval_patient_story_summary.json"
    output: Dict[str, Any] = {"results": {}}
    if output_path.exists():
        loaded = json.loads(output_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            output.update(loaded)
            if not isinstance(output.get("results"), dict):
                output["results"] = {}
    output["results"][case_id] = data
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
