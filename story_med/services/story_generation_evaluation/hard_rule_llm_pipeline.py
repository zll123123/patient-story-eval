"""硬规则 LLM 抽取与对比流水线。"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List

from story_med.clients.llm.llm_client import call_llm_json
from story_med.config.app_config import StoryMedLlmConfig
from story_med.config.settings import (
    PROMPTS_DIR,
    RESULTS_DIR,
    STORY_AUDITS_DIR,
)
from story_med.models.case_model import StoryAgentRunResult, StoryCaseConfig
from story_med.services.clinical_case_preparation.clinical_extract_baseline_service import (
    load_clinical_baseline,
)
from story_med.services.clinical_case_preparation.yaml_case_service import (
    load_hard_rule_fields,
)
from story_med.utils.timing import TimingCollector, write_stage_snapshots
from story_med.utils.yaml_loader import load_yaml_file


def run_case_facts_compare_pipeline(
    llm_config: StoryMedLlmConfig, case: StoryCaseConfig
) -> Dict[str, Any]:
    """使用 clinical_extract.md 执行抽取和对比，适合外部 agent 不可用时验证规则链路。"""
    output_dir = STORY_AUDITS_DIR / case.case_id
    output_dir.mkdir(parents=True, exist_ok=True)
    hard_rule_fields = load_hard_rule_fields()
    expected_fields = build_expected_fields(case)
    baseline_text = load_clinical_baseline(case)
    timings = TimingCollector(
        on_change=lambda stages: _write_audit_progress(
            case, output_dir / "summary.json", stages
        )
    )
    _write_audit_progress(case, output_dir / "summary.json", [])
    outline_result, story_result = _compare_outline_and_story(
        llm_config,
        baseline_text,
        baseline_text,
        hard_rule_fields,
        expected_fields,
        timings,
    )
    _write_compare_artifacts(case, "", output_dir, outline_result, story_result)
    summary = _build_case_facts_summary(
        case, outline_result["compare"], story_result["compare"], timings.to_list()
    )
    _write_json(summary, output_dir / "summary.json")
    return summary


def run_existing_assets_compare_pipeline(
    llm_config: StoryMedLlmConfig,
    case: StoryCaseConfig,
    session_id: str,
) -> Dict[str, Any]:
    """基于 results/assets 下已有接口产物执行大纲和文章对比。"""
    output_dir = STORY_AUDITS_DIR / case.case_id
    output_dir.mkdir(parents=True, exist_ok=True)
    asset_dir = RESULTS_DIR / "assets" / case.case_id / session_id
    hard_rule_fields = load_hard_rule_fields()
    expected_fields = build_expected_fields(case)
    outline_text = _read_asset_text(asset_dir, "generate_outline")
    story_text = _read_asset_text(asset_dir, "generate_story")
    timings = TimingCollector(
        on_change=lambda stages: _write_audit_progress(
            case, output_dir / "summary.json", stages
        )
    )
    _write_audit_progress(case, output_dir / "summary.json", [])
    outline_result, story_result = _compare_outline_and_story(
        llm_config,
        outline_text,
        story_text,
        hard_rule_fields,
        expected_fields,
        timings,
    )
    _write_compare_artifacts(case, session_id, output_dir, outline_result, story_result)
    summary = _build_existing_assets_summary(
        case,
        session_id,
        outline_result["compare"],
        story_result["compare"],
        timings.to_list(),
    )
    _write_json(summary, output_dir / "summary.json")
    return summary


def build_expected_fields(case: StoryCaseConfig) -> Dict[str, Any]:
    """从 case.hard_rules.expected.value 提取预期值。"""
    expected_fields: Dict[str, Any] = {}
    for field_name, rule in case.hard_rules.items():
        if isinstance(rule, dict):
            expected = (
                rule.get("expected") if isinstance(rule.get("expected"), dict) else {}
            )
            expected_fields[field_name] = expected.get("value")
    return expected_fields


def _extract_and_compare(
    llm_config: StoryMedLlmConfig,
    source_type: str,
    source_text: str,
    hard_rule_fields: Dict[str, Any],
    expected_fields: Dict[str, Any],
    timings: TimingCollector,
) -> Dict[str, Any]:
    """执行抽取和结构对比。"""
    with timings.stage(f"{source_type}_fact_extraction", "audit"):
        extracted = call_llm_json(
            llm_config,
            _build_extraction_prompt(source_type, source_text, hard_rule_fields),
        )
    with timings.stage(f"{source_type}_fact_compare", "audit"):
        compare = call_llm_json(
            llm_config,
            _build_compare_prompt(
                hard_rule_fields, expected_fields, extracted.get("extracted_fields", {})
            ),
        )
    return {"extracted": extracted, "compare": compare}


def _compare_outline_and_story(
    llm_config: StoryMedLlmConfig,
    outline_text: str,
    story_text: str,
    hard_rule_fields: Dict[str, Any],
    expected_fields: Dict[str, Any],
    timings: TimingCollector,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """并发执行大纲和 Story 两条独立事实审核链。"""
    with ThreadPoolExecutor(max_workers=2) as executor:
        outline_future = executor.submit(
            _extract_and_compare,
            llm_config,
            "outline",
            outline_text,
            hard_rule_fields,
            expected_fields,
            timings,
        )
        story_future = executor.submit(
            _extract_and_compare,
            llm_config,
            "story",
            story_text,
            hard_rule_fields,
            expected_fields,
            timings,
        )
        return outline_future.result(), story_future.result()


def _build_extraction_prompt(
    source_type: str, source_text: str, hard_rule_fields: Dict[str, Any]
) -> str:
    """构建字段抽取提示词。"""
    template = (PROMPTS_DIR / "hard_rule_field_extraction.md").read_text(
        encoding="utf-8"
    )
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
    template = (PROMPTS_DIR / "hard_rule_semantic_compare.md").read_text(
        encoding="utf-8"
    )
    payload = {
        "hard_rule_fields": hard_rule_fields,
        "expected_fields": expected_fields,
        "extracted_fields": extracted_fields,
    }
    return f"{template}\n\n## Input\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"


def _read_asset_text(asset_dir: Path, step_name: str) -> str:
    """读取 results/assets 下指定步骤的 Markdown 文本。"""
    step_dir = asset_dir / step_name
    text_files = _dedupe_text_paths(step_dir.glob("*"))
    if len(text_files) != 1:
        raise RuntimeError(f"{step_name} 文本文件数量异常: {text_files}")
    return text_files[0].read_text(encoding="utf-8")


def _dedupe_text_paths(paths: Any) -> List[Path]:
    """按最终落盘路径去重文本文件列表。

    上游 history 里同一个 OSS 文件可能在多个 frame 中重复上报，
    本地下载记录会出现多个相同 local_path。这里按规范化后的路径去重，
    只保留最终落盘文件本身。
    """
    unique: Dict[str, Path] = {}
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists() or path.suffix.lower() not in {".md", ".txt"}:
            continue
        unique[str(path.resolve())] = path
    return list(unique.values())


def _build_existing_assets_summary(
    case: StoryCaseConfig,
    session_id: str,
    outline_compare: Dict[str, Any],
    story_compare: Dict[str, Any],
    execution_stages: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """构建基于 results/assets 的汇总结果。"""
    return {
        "case_id": case.case_id,
        "description": case.description,
        "session_id": session_id,
        "source_mode": "results_assets",
        "success": True,
        "execution_stages": execution_stages,
        "outline_failed_fields": _failed_fields(outline_compare),
        "story_failed_fields": _failed_fields(story_compare),
    }


def _build_summary(
    case: StoryCaseConfig,
    run_result: StoryAgentRunResult,
    outline_compare: Dict[str, Any],
    story_compare: Dict[str, Any],
    execution_stages: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """构建包含生成和审核节点耗时的结果汇总。"""
    return {
        "case_id": case.case_id,
        "description": case.description,
        "session_id": run_result.session_id,
        "task_id": run_result.task_id,
        "source_mode": "agent",
        "success": run_result.success,
        "execution_stages": run_result.execution_stages + execution_stages,
        "outline_failed_fields": _failed_fields(outline_compare),
        "story_failed_fields": _failed_fields(story_compare),
    }


def _build_case_facts_summary(
    case: StoryCaseConfig,
    outline_compare: Dict[str, Any],
    story_compare: Dict[str, Any],
    execution_stages: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """构建基于 clinical_extract.md 的汇总结果。"""
    return {
        "case_id": case.case_id,
        "description": case.description,
        "session_id": "",
        "source_mode": "clinical_extract",
        "success": True,
        "execution_stages": execution_stages,
        "outline_failed_fields": _failed_fields(outline_compare),
        "story_failed_fields": _failed_fields(story_compare),
    }


def _failed_fields(compare_result: Dict[str, Any]) -> List[str]:
    """提取对比失败字段。"""
    field_results = compare_result.get("field_results")
    if not isinstance(field_results, dict):
        return []
    return [
        field
        for field, result in field_results.items()
        if isinstance(result, dict) and not result.get("passed")
    ]


def _write_audit_progress(
    case: StoryCaseConfig,
    output_path: Path,
    execution_stages: List[Dict[str, Any]],
) -> None:
    """实时写入审核进度，便于定位中断或超时节点。"""
    write_stage_snapshots(output_path.parent, execution_stages)
    _write_json(
        {
            "case_id": case.case_id,
            "description": case.description,
            "session_id": "",
            "source_mode": "existing_assets",
            "success": True,
            "audit_status": "running",
            "execution_stages": execution_stages,
        },
        output_path,
    )


def _write_compare_artifacts(
    case: StoryCaseConfig,
    session_id: str,
    output_dir: Path,
    outline_result: Dict[str, Any],
    story_result: Dict[str, Any],
) -> None:
    """统一写入大纲和文章抽取、对比结果。"""
    _write_json(
        _attach_artifact_metadata(
            case, session_id, "outline", outline_result["extracted"]
        ),
        output_dir / "outline_extracted_fields.json",
    )
    _write_json(
        _attach_artifact_metadata(case, session_id, "story", story_result["extracted"]),
        output_dir / "story_extracted_fields.json",
    )
    _write_json(
        _attach_artifact_metadata(
            case, session_id, "outline", outline_result["compare"]
        ),
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


def _write_json(data: Dict[str, Any], output_path: Path) -> None:
    """写入 JSON 文件。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
