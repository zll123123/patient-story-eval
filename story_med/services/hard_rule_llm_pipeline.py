"""硬规则 LLM 抽取与对比流水线。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from story_med.adapters.patient_story_agent import PatientStoryAgentAdapter
from story_med.clients.llm_client import call_llm_json
from story_med.config.llm_app_config import StoryMedLlmConfig
from story_med.config.settings import PROMPTS_DIR, RESULTS_DIR, TMP_DIR
from story_med.models.case_model import StoryAgentRunResult, StoryCaseConfig
from story_med.services.clinical_baseline import load_clinical_baseline
from story_med.services.clinical_case_config import load_hard_rule_fields
from story_med.utils.yaml_loader import load_yaml_file


def run_case_compare_pipeline(
    adapter: PatientStoryAgentAdapter,
    llm_config: StoryMedLlmConfig,
    case: StoryCaseConfig,
    include_visual_steps: bool = False,
) -> Dict[str, Any]:
    """执行单条 case 到硬规则对比结果阶段。"""
    output_dir = TMP_DIR / case.case_id
    output_dir.mkdir(parents=True, exist_ok=True)
    run_result = adapter.run_case(case) if include_visual_steps else adapter.run_case_until_story(case)
    _write_agent_run_result(run_result)
    if not run_result.success:
        raise RuntimeError(f"真实链路执行失败: {case.case_id} {run_result.error}")

    hard_rule_fields = load_hard_rule_fields()
    expected_fields = build_expected_fields(case)
    outline_text = _read_step_text(run_result, "generate_outline")
    story_text = _read_step_text(run_result, "generate_story")
    outline_result = _extract_and_compare(llm_config, "outline", outline_text, hard_rule_fields, expected_fields)
    story_result = _extract_and_compare(llm_config, "story", story_text, hard_rule_fields, expected_fields)
    _write_compare_artifacts(case, run_result.session_id, output_dir, outline_result, story_result)
    summary = _build_summary(case, run_result, outline_result["compare"], story_result["compare"])
    _write_json(summary, output_dir / "summary.json")
    return summary


def run_case_facts_compare_pipeline(llm_config: StoryMedLlmConfig, case: StoryCaseConfig) -> Dict[str, Any]:
    """使用 clinical_extract.md 执行抽取和对比，适合外部 agent 不可用时验证规则链路。"""
    output_dir = TMP_DIR / case.case_id
    output_dir.mkdir(parents=True, exist_ok=True)
    hard_rule_fields = load_hard_rule_fields()
    expected_fields = build_expected_fields(case)
    baseline_text = load_clinical_baseline(case)
    outline_result = _extract_and_compare(llm_config, "outline", baseline_text, hard_rule_fields, expected_fields)
    story_result = _extract_and_compare(llm_config, "story", baseline_text, hard_rule_fields, expected_fields)
    _write_compare_artifacts(case, "", output_dir, outline_result, story_result)
    summary = _build_case_facts_summary(case, outline_result["compare"], story_result["compare"])
    _write_json(summary, output_dir / "summary.json")
    return summary


def run_existing_assets_compare_pipeline(
    llm_config: StoryMedLlmConfig,
    case: StoryCaseConfig,
    session_id: str,
) -> Dict[str, Any]:
    """基于 results/assets 下已有接口产物执行大纲和文章对比。"""
    output_dir = TMP_DIR / case.case_id
    output_dir.mkdir(parents=True, exist_ok=True)
    asset_dir = RESULTS_DIR / "assets" / case.case_id / session_id
    hard_rule_fields = load_hard_rule_fields()
    expected_fields = build_expected_fields(case)
    outline_text = _read_asset_text(asset_dir, "generate_outline")
    story_text = _read_asset_text(asset_dir, "generate_story")
    outline_result = _extract_and_compare(llm_config, "outline", outline_text, hard_rule_fields, expected_fields)
    story_result = _extract_and_compare(llm_config, "story", story_text, hard_rule_fields, expected_fields)
    _write_compare_artifacts(case, session_id, output_dir, outline_result, story_result)
    summary = _build_existing_assets_summary(case, session_id, outline_result["compare"], story_result["compare"])
    _write_json(summary, output_dir / "summary.json")
    return summary


def build_expected_fields(case: StoryCaseConfig) -> Dict[str, Any]:
    """从 case.hard_rules.expected.value 提取预期值。"""
    expected_fields: Dict[str, Any] = {}
    for field_name, rule in case.hard_rules.items():
        if isinstance(rule, dict):
            expected = rule.get("expected") if isinstance(rule.get("expected"), dict) else {}
            expected_fields[field_name] = expected.get("value")
    return expected_fields


def _extract_and_compare(
    llm_config: StoryMedLlmConfig,
    source_type: str,
    source_text: str,
    hard_rule_fields: Dict[str, Any],
    expected_fields: Dict[str, Any],
) -> Dict[str, Any]:
    """执行抽取和结构对比。"""
    extracted = call_llm_json(
        llm_config,
        _build_extraction_prompt(source_type, source_text, hard_rule_fields),
    )
    compare = call_llm_json(
        llm_config,
        _build_compare_prompt(hard_rule_fields, expected_fields, extracted.get("extracted_fields", {})),
    )
    return {"extracted": extracted, "compare": compare}


def _build_extraction_prompt(source_type: str, source_text: str, hard_rule_fields: Dict[str, Any]) -> str:
    """构建字段抽取提示词。"""
    template = (PROMPTS_DIR / "hard_rule_field_extraction.md").read_text(encoding="utf-8")
    payload = {
        "source_type": source_type,
        "hard_rule_fields": hard_rule_fields,
        "source_text": source_text,
    }
    return f"{template}\n\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"


def _build_compare_prompt(
    hard_rule_fields: Dict[str, Any],
    expected_fields: Dict[str, Any],
    extracted_fields: Dict[str, Any],
) -> str:
    """构建字段对比提示词。"""
    template = (PROMPTS_DIR / "hard_rule_semantic_compare.md").read_text(encoding="utf-8")
    payload = {
        "hard_rule_fields": hard_rule_fields,
        "expected_fields": expected_fields,
        "extracted_fields": extracted_fields,
    }
    return f"{template}\n\n## Input\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"


def _read_step_text(run_result: StoryAgentRunResult, step_name: str) -> str:
    """读取指定步骤下载的 Markdown 文本。"""
    files = [
        Path(item["local_path"])
        for item in run_result.downloaded_assets
        if item.get("step_name") == step_name and item.get("local_path")
    ]
    text_files = [path for path in files if path.exists() and path.suffix.lower() in {".md", ".txt"}]
    if len(text_files) != 1:
        raise RuntimeError(f"{run_result.case_id} {step_name} 文本文件数量异常: {text_files}")
    return text_files[0].read_text(encoding="utf-8")


def _read_asset_text(asset_dir: Path, step_name: str) -> str:
    """读取 results/assets 下指定步骤的 Markdown 文本。"""
    step_dir = asset_dir / step_name
    text_files = [path for path in step_dir.glob("*") if path.suffix.lower() in {".md", ".txt"}]
    if len(text_files) != 1:
        raise RuntimeError(f"{step_name} 文本文件数量异常: {text_files}")
    return text_files[0].read_text(encoding="utf-8")


def _build_summary(
    case: StoryCaseConfig,
    run_result: StoryAgentRunResult,
    outline_compare: Dict[str, Any],
    story_compare: Dict[str, Any],
) -> Dict[str, Any]:
    """构建单 case 汇总结果。"""
    return {
        "case_id": case.case_id,
        "description": case.description,
        "session_id": run_result.session_id,
        "source_mode": "agent",
        "success": run_result.success,
        "agent_total_duration_seconds": run_result.total_duration_seconds,
        "agent_step_timings": _build_step_timings(run_result),
        "outline_failed_fields": _failed_fields(outline_compare),
        "story_failed_fields": _failed_fields(story_compare),
    }


def _build_existing_assets_summary(
    case: StoryCaseConfig,
    session_id: str,
    outline_compare: Dict[str, Any],
    story_compare: Dict[str, Any],
) -> Dict[str, Any]:
    """构建基于 results/assets 的汇总结果。"""
    return {
        "case_id": case.case_id,
        "description": case.description,
        "session_id": session_id,
        "source_mode": "results_assets",
        "success": True,
        "agent_step_timings": _load_existing_step_timings(case.case_id, session_id),
        "outline_failed_fields": _failed_fields(outline_compare),
        "story_failed_fields": _failed_fields(story_compare),
    }


def _build_case_facts_summary(
    case: StoryCaseConfig,
    outline_compare: Dict[str, Any],
    story_compare: Dict[str, Any],
) -> Dict[str, Any]:
    """构建基于 clinical_extract.md 的汇总结果。"""
    return {
        "case_id": case.case_id,
        "description": case.description,
        "session_id": "",
        "source_mode": "clinical_extract",
        "success": True,
        "agent_step_timings": {},
        "outline_failed_fields": _failed_fields(outline_compare),
        "story_failed_fields": _failed_fields(story_compare),
    }


def _build_step_timings(run_result: StoryAgentRunResult) -> Dict[str, Any]:
    """提取核心生成步骤耗时。"""
    target_steps = {
        "generate_outline": "获取大纲",
        "generate_story": "获取故事",
        "generate_images": "生成图片",
        "generate_final_image": "获取最终长图",
    }
    timings: Dict[str, Any] = {}
    for step in run_result.steps:
        if step.step_name not in target_steps:
            continue
        timings[step.step_name] = {
            "label": target_steps[step.step_name],
            "endpoint": step.endpoint,
            "started_at": step.started_at,
            "finished_at": step.finished_at,
            "duration_seconds": step.duration_seconds,
        }
    return timings


def _load_existing_step_timings(case_id: str, session_id: str) -> Dict[str, Any]:
    """从已有 run 结果中读取核心步骤耗时。"""
    run_path = RESULTS_DIR / "runs" / case_id / f"{session_id}.json"
    if not run_path.exists():
        return {}
    run_result = StoryAgentRunResult.from_dict(json.loads(run_path.read_text(encoding="utf-8")))
    return _build_step_timings(run_result)


def _failed_fields(compare_result: Dict[str, Any]) -> List[str]:
    """提取对比失败字段。"""
    field_results = compare_result.get("field_results")
    if not isinstance(field_results, dict):
        return []
    return [field for field, result in field_results.items() if isinstance(result, dict) and not result.get("passed")]


def _write_compare_artifacts(
    case: StoryCaseConfig,
    session_id: str,
    output_dir: Path,
    outline_result: Dict[str, Any],
    story_result: Dict[str, Any],
) -> None:
    """统一写入大纲和文章抽取、对比结果。"""
    _write_json(
        _attach_artifact_metadata(case, session_id, "outline", outline_result["extracted"]),
        output_dir / "outline_extracted_fields.json",
    )
    _write_json(
        _attach_artifact_metadata(case, session_id, "story", story_result["extracted"]),
        output_dir / "story_extracted_fields.json",
    )
    _write_json(
        _attach_artifact_metadata(case, session_id, "outline", outline_result["compare"]),
        output_dir / "outline_hard_rule_compare.json",
    )
    _write_json(
        _attach_artifact_metadata(case, session_id, "story", story_result["compare"]),
        output_dir / "story_hard_rule_compare.json",
    )


def _attach_artifact_metadata(
    case: StoryCaseConfig,
    session_id: str,
    source_type: str,
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """为抽取和对比结果补充 case 元信息。"""
    return {
        "case_id": case.case_id,
        "description": case.description,
        "session_id": session_id,
        "source_type": source_type,
        **result,
    }


def _write_agent_run_result(run_result: StoryAgentRunResult) -> None:
    """将真实接口链路结果写入 results，便于追溯接口产物。"""
    session_id = run_result.session_id or "failed"
    output_path = RESULTS_DIR / "runs" / run_result.case_id / f"{session_id}.json"
    _write_json(run_result.to_dict(), output_path)
    _write_json(run_result.to_dict(), RESULTS_DIR / "patient_story_run.json")


def _write_json(data: Dict[str, Any], output_path: Path) -> None:
    """写入 JSON 文件。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
