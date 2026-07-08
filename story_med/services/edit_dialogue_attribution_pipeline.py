"""患者故事多轮编辑失败归因流程。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from story_med.config.llm_app_config import StoryMedLlmConfig
from story_med.config.settings import EDIT_DIALOGUE_RESULTS_DIR
from story_med.services.edit_coverage_service import evaluate_edit_coverage, read_reference_content

EDIT_AUDIT_ANALYSIS_FILE = "edit_audit_analysis.json"


def run_edit_dialogue_attribution(
    llm_config: StoryMedLlmConfig,
    dialogue_result: Dict[str, Any],
) -> Dict[str, Any] | None:
    """对失败的多轮编辑结果执行独立归因。

    Args:
        llm_config: LLM 配置。
        dialogue_result: 多轮编辑执行结果。

    Returns:
        归因结果；若无需归因则返回 None。
    """
    if bool(dialogue_result.get("overall_passed")):
        return None
    turn_results = dialogue_result.get("turn_results")
    if not isinstance(turn_results, list) or not turn_results:
        return None
    failed_turn = _latest_failed_turn(turn_results)
    if not failed_turn:
        return None

    trace = [_trace_entry(failed_turn, recheck_passed=False, source="final_failed_turn")]
    current_root_turn = failed_turn
    for prior_turn in _previous_turns(turn_results, int(failed_turn["turn_id"])):
        recheck = _recheck_turn(llm_config, dialogue_result, prior_turn)
        trace.append(recheck)
        if recheck["recheck_passed"] is True:
            break
        current_root_turn = prior_turn

    analysis = _build_analysis(dialogue_result, failed_turn, current_root_turn, trace)
    _write_analysis(str(dialogue_result.get("case_id") or ""), analysis)
    return analysis


def _latest_failed_turn(turn_results: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    """读取最终失败轮次。"""
    failed = [item for item in turn_results if item.get("passed") is not True]
    if not failed:
        return None
    return max(failed, key=lambda item: int(item.get("turn_id") or 0))


def _previous_turns(turn_results: List[Dict[str, Any]], failed_turn_id: int) -> List[Dict[str, Any]]:
    """按倒序返回失败轮之前的轮次。"""
    candidates = [item for item in turn_results if int(item.get("turn_id") or 0) < failed_turn_id]
    return sorted(candidates, key=lambda item: int(item.get("turn_id") or 0), reverse=True)


def _recheck_turn(
    llm_config: StoryMedLlmConfig,
    dialogue_result: Dict[str, Any],
    turn_result: Dict[str, Any],
) -> Dict[str, Any]:
    """使用该轮产物和当轮累计预期重新审核。"""
    turn_case = _build_turn_runtime_case(dialogue_result, turn_result)
    adjustment_result = turn_result.get("adjustment_result") if isinstance(turn_result.get("adjustment_result"), dict) else {}
    if not adjustment_result.get("success"):
        return _trace_entry(
            turn_result,
            recheck_passed=False,
            source="recheck_failed",
            reason="该轮调整执行未成功，无法满足审核预期。",
            validation={"passed": False, "score": 0, "reason": "调整执行失败"},
        )

    reference_session_id = str(dialogue_result.get("reference_session_id") or "")
    input_content = read_reference_content(str(dialogue_result.get("ref_clinical_case_id") or ""), reference_session_id)
    validation = evaluate_edit_coverage(
        llm_config,
        turn_case,
        reference_session_id,
        adjustment_result,
        input_content,
        "",
    )
    return _trace_entry(
        turn_result,
        recheck_passed=bool(validation.get("passed")),
        source="recheck",
        reason=str(validation.get("reason") or ""),
        validation=validation,
    )


def _build_turn_runtime_case(dialogue_result: Dict[str, Any], turn_result: Dict[str, Any]) -> Dict[str, Any]:
    """构建重审所需的运行时编辑用例。"""
    return {
        "case_id": str(turn_result.get("case_id") or ""),
        "ref_clinical_case_id": str(dialogue_result.get("ref_clinical_case_id") or ""),
        "message": str(turn_result.get("message") or ""),
        "evaluation_focus": turn_result.get("effective_evaluation_focus") or [],
        "intent": turn_result.get("intent") or {},
        "involved_agent": {"required": turn_result.get("involved_agents") or []},
    }


def _trace_entry(
    turn_result: Dict[str, Any],
    recheck_passed: bool,
    source: str,
    reason: str = "",
    validation: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """构建单轮重审轨迹。"""
    return {
        "turn_id": int(turn_result.get("turn_id") or 0),
        "case_id": str(turn_result.get("case_id") or ""),
        "message": str(turn_result.get("message") or ""),
        "intent": turn_result.get("intent") or {},
        "configured_agents": list(turn_result.get("involved_agents") or []),
        "produced_agents": _produced_agents(turn_result),
        "effective_evaluation_focus": turn_result.get("effective_evaluation_focus") or [],
        "recheck_passed": recheck_passed,
        "source": source,
        "reason": reason,
        "validation": validation or {},
    }


def _build_analysis(
    dialogue_result: Dict[str, Any],
    failed_turn: Dict[str, Any],
    root_turn: Dict[str, Any],
    trace: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """构建最终编辑归因结果。"""
    suspected_agents = list(root_turn.get("involved_agents") or [])
    produced_agents = _produced_agents(root_turn)
    return {
        "case_id": str(dialogue_result.get("case_id") or ""),
        "is_passed": False,
        "failed_final_turn": int(failed_turn.get("turn_id") or 0),
        "root_cause_turn": int(root_turn.get("turn_id") or 0),
        "root_cause_turn_case_id": str(root_turn.get("case_id") or ""),
        "suspected_agents": suspected_agents,
        "produced_agents": produced_agents,
        "root_cause_agent_confidence": _agent_confidence(suspected_agents, produced_agents),
        "intent": root_turn.get("intent") or {},
        "message": str(root_turn.get("message") or ""),
        "effective_evaluation_focus": root_turn.get("effective_evaluation_focus") or [],
        "reason": _build_reason(failed_turn, root_turn, trace),
        "recheck_trace": trace,
    }


def _build_reason(
    failed_turn: Dict[str, Any],
    root_turn: Dict[str, Any],
    trace: List[Dict[str, Any]],
) -> str:
    """生成归因说明。"""
    failed_turn_id = int(failed_turn.get("turn_id") or 0)
    root_turn_id = int(root_turn.get("turn_id") or 0)
    if failed_turn_id == root_turn_id:
        return f"T{root_turn_id} 为最终失败轮，向前倒查未发现更早失败来源，归因于该轮修改覆盖未满足。"
    previous_trace = next((item for item in trace if int(item.get("turn_id") or 0) == root_turn_id + 1), None)
    if previous_trace and previous_trace.get("recheck_passed") is True:
        return f"T{root_turn_id} 重审失败，而其后续轮前一轮已通过，说明首次失败引入于 T{root_turn_id}。"
    return f"倒序重审后，T{root_turn_id} 是首次重新审核仍失败的轮次，归因于该轮。"


def _produced_agents(turn_result: Dict[str, Any]) -> List[str]:
    """从实际下载产物推断该轮涉及的 agent。"""
    adjustment = turn_result.get("adjustment_result") if isinstance(turn_result.get("adjustment_result"), dict) else {}
    assets = adjustment.get("downloaded_assets") if isinstance(adjustment.get("downloaded_assets"), list) else []
    produced: set[str] = set()
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        local_path = Path(str(asset.get("local_path") or ""))
        file_name = local_path.name.lower()
        suffix = local_path.suffix.lower()
        if suffix == ".html" or file_name == "index.html":
            produced.add("html")
        elif suffix == ".md" and "outline" in file_name:
            produced.add("outline")
        elif suffix == ".md" and "story" in file_name:
            produced.add("story")
        elif suffix in {".png", ".jpg", ".jpeg", ".webp"} or "image_design" in file_name or suffix == ".json":
            produced.add("image")
    return sorted(produced)


def _agent_confidence(configured_agents: List[str], produced_agents: List[str]) -> str:
    """判断 agent 归因置信度。"""
    if len(configured_agents) == 1:
        return "high"
    if len(produced_agents) == 1:
        return "medium"
    return "low"


def _write_analysis(case_id: str, analysis: Dict[str, Any]) -> None:
    """写入归因结果。"""
    path = EDIT_DIALOGUE_RESULTS_DIR / case_id / EDIT_AUDIT_ANALYSIS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
