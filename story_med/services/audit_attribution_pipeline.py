"""患者故事审核结果归因流水线。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from story_med.clients.llm_client import call_llm_json
from story_med.config.llm_app_config import StoryMedLlmConfig
from story_med.config.settings import DEFAULT_CASE_FILE, RESULTS_DIR, PROMPTS_DIR, TMP_DIR
from story_med.services.case_loader import load_story_cases

ATTRIBUTION_PROMPT_FILE = PROMPTS_DIR / "audit_analysis.md"


def run_case_audit_attribution(llm_config: StoryMedLlmConfig, case_id: str) -> Dict[str, Any]:
    """按 case 执行审核归因，仅在存在失败审核项时触发。"""
    case_dir = TMP_DIR / case_id
    summary = _read_json(case_dir / "summary.json")
    failed_audits = _failed_audit_keys(summary.get("audit_overview"))
    if not failed_audits:
        result = _skip_result(case_id)
        _write_json(result, case_dir / "audit_analysis.json")
        return result

    if not ATTRIBUTION_PROMPT_FILE.exists():
        result = _pending_result(case_id, failed_audits)
        _write_json(result, case_dir / "audit_analysis.json")
        return result

    payload = _build_payload(case_dir, summary, failed_audits)
    result = call_llm_json(llm_config, _build_prompt(payload))
    output = {
        "case_id": case_id,
        "status": "success",
        "failed_audits": failed_audits,
        "attribution": result,
    }
    _write_json(output, case_dir / "audit_analysis.json")
    return output


def _failed_audit_keys(audit_overview: Any) -> List[str]:
    """提取 audit_overview 中失败的审核项。"""
    if not isinstance(audit_overview, dict):
        return []
    return [key for key, value in audit_overview.items() if value is False]


def _build_payload(case_dir: Path, summary: Dict[str, Any], failed_audits: List[str]) -> Dict[str, Any]:
    """构建归因提示词输入。"""
    case_id = str(summary.get("case_id") or "")
    case = _load_case(case_id)
    payload: Dict[str, Any] = {
        "case_facts": case.case_facts,
        "creative_brief": case.creative_brief,
        "summary": summary,
        "failed_audits": failed_audits,
        "intermediate_outputs": _load_intermediate_outputs(case_id, str(summary.get("session_id") or "")),
    }
    artifact_mapping = {
        "outline_passed": "outline_hard_rule_compare.json",
        "story_passed": "story_hard_rule_compare.json",
        "image_design_passed": "image_design_validation.json",
        "image_consistant_passed": "image_consistant_validation.json",
        "image_fact_passed": "image_fact_validation.json",
        "final_image_layout_passed": "final_image_layout_validation.json",
    }
    artifacts: Dict[str, Any] = {}
    for audit_key in failed_audits:
        file_name = artifact_mapping.get(audit_key)
        if not file_name:
            continue
        file_path = case_dir / file_name
        if file_path.exists():
            artifacts[audit_key] = _read_json(file_path)
    payload["artifacts"] = artifacts
    return payload


def _build_prompt(payload: Dict[str, Any]) -> str:
    """拼接审核归因 prompt 与输入。"""
    template = ATTRIBUTION_PROMPT_FILE.read_text(encoding="utf-8")
    return f"{template}\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"


def _load_case(case_id: str):
    """加载指定 case 配置。"""
    for case in load_story_cases(DEFAULT_CASE_FILE):
        if case.case_id == case_id:
            return case
    raise FileNotFoundError(f"未找到 case: {case_id}")


def _load_intermediate_outputs(case_id: str, session_id: str) -> Dict[str, Any]:
    """读取链路中间产物。"""
    if not session_id:
        return {}
    asset_dir = RESULTS_DIR / "assets" / case_id / session_id
    output: Dict[str, Any] = {}
    outline_path = asset_dir / "generate_outline" / "generate_outline_1_outline.md"
    story_path = asset_dir / "generate_story" / "generate_story_1_story.md"
    image_design_path = asset_dir / "generate_images" / "generate_images_6_image_design.json"
    if outline_path.exists():
        output["outline"] = outline_path.read_text(encoding="utf-8")
    if story_path.exists():
        output["story_text"] = story_path.read_text(encoding="utf-8")
    if image_design_path.exists():
        output["image_design"] = _read_json(image_design_path)
    return output


def _skip_result(case_id: str) -> Dict[str, Any]:
    """构建无需归因结果。"""
    return {
        "case_id": case_id,
        "status": "skipped",
        "reason": "audit_overview 中不存在 false，无需归因",
        "failed_audits": [],
    }


def _pending_result(case_id: str, failed_audits: List[str]) -> Dict[str, Any]:
    """构建待归因结果。"""
    return {
        "case_id": case_id,
        "status": "pending_prompt",
        "reason": f"缺少归因提示词文件: {ATTRIBUTION_PROMPT_FILE.name}",
        "failed_audits": failed_audits,
    }


def _read_json(path: Path) -> Dict[str, Any]:
    """读取 JSON 文件。"""
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(data: Dict[str, Any], output_path: Path) -> None:
    """写入 JSON 文件。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
