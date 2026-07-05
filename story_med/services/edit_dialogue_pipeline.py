"""患者故事多轮编辑对话测试流程。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from story_med.config.app_config import StoryMedConfig
from story_med.config.llm_app_config import StoryMedLlmConfig
from story_med.config.settings import EDIT_DIALOGUE_RESULTS_DIR
from story_med.services.edit_dialogue_config import get_edit_dialogue_case
from story_med.services.edit_story_pipeline import (
    evaluate_edit_coverage,
    read_adjusted_content,
    read_reference_content,
    resolve_reference_artifact_session_id,
    resolve_reference_context,
)
from story_med.services.story_adjustment_pipeline import run_story_adjustment


def run_edit_dialogue_case(
    app_config: StoryMedConfig,
    llm_config: StoryMedLlmConfig,
    dialogue_case_id: str,
) -> Dict[str, Any]:
    """执行单条多轮患者故事编辑对话测试。

    Args:
        app_config: 接口运行配置。
        llm_config: LLM 运行配置。
        dialogue_case_id: 多轮编辑对话测试用例 ID。

    Returns:
        多轮编辑对话测试结果。
    """
    dialogue_case = get_edit_dialogue_case(dialogue_case_id)
    try:
        ref_context = resolve_reference_context(_reference_edit_case(dialogue_case), app_config)
        reference_session_id = resolve_reference_artifact_session_id(
            dialogue_case["ref_clinical_case_id"],
            ref_context["session_id"],
        )
        input_content = read_reference_content(dialogue_case["ref_clinical_case_id"], reference_session_id)
    except Exception as exc:
        result = _build_preflight_failed_dialogue_result(dialogue_case, str(exc))
        _write_dialogue_result(dialogue_case["case_id"], result)
        return result

    turn_results = _run_dialogue_turns(
        app_config=app_config,
        llm_config=llm_config,
        dialogue_case=dialogue_case,
        ref_context=ref_context,
        reference_session_id=reference_session_id,
        input_content=input_content,
    )
    result = {
        "case_id": dialogue_case["case_id"],
        "ref_clinical_case_id": dialogue_case["ref_clinical_case_id"],
        "summary": dialogue_case.get("summary", ""),
        "session_id": ref_context["session_id"],
        "reference_session_id": reference_session_id,
        "task_id": ref_context["task_id"],
        "turn_count": len(dialogue_case["turns"]),
        "overall_passed": bool(turn_results) and all(item.get("passed") is True for item in turn_results),
        "turn_results": turn_results,
    }
    _write_dialogue_result(dialogue_case["case_id"], result)
    return result


def build_cumulative_evaluation_focus(passed_focuses: List[Dict[str, Any]], current_focus: str) -> str:
    """构建当前轮有效累计评估点。

    Args:
        passed_focuses: 历史已通过轮次的评估点。
        current_focus: 当前轮原子评估点。

    Returns:
        当前轮用于审核的累计评估点。
    """
    focuses = [str(item.get("evaluation_focus") or "").strip() for item in passed_focuses]
    if current_focus.strip():
        focuses.append(current_focus.strip())
    lines = ["截至当前轮，需要同时满足以下修改覆盖："]
    lines.extend(f"{index}. {focus}" for index, focus in enumerate(focuses, start=1) if focus)
    return "\n".join(lines)


def _run_dialogue_turns(
    app_config: StoryMedConfig,
    llm_config: StoryMedLlmConfig,
    dialogue_case: Dict[str, Any],
    ref_context: Dict[str, str],
    reference_session_id: str,
    input_content: str,
) -> List[Dict[str, Any]]:
    """串行执行多轮编辑并逐轮审核。"""
    passed_focuses: List[Dict[str, Any]] = []
    failed_turn_ids: List[int] = []
    turn_results: List[Dict[str, Any]] = []
    for turn in dialogue_case["turns"]:
        turn_result = _run_single_dialogue_turn(
            app_config=app_config,
            llm_config=llm_config,
            dialogue_case=dialogue_case,
            turn=turn,
            ref_context=ref_context,
            reference_session_id=reference_session_id,
            input_content=input_content,
            passed_focuses=passed_focuses,
            failed_turn_ids=failed_turn_ids,
        )
        turn_results.append(turn_result)
        if turn_result.get("passed") is True:
            passed_focuses.append(
                {
                    "turn_id": turn["turn_id"],
                    "evaluation_focus": turn["evaluation_focus"],
                    "involved_agents": turn.get("involved_agents", []),
                }
            )
        else:
            failed_turn_ids.append(int(turn["turn_id"]))
    return turn_results


def _run_single_dialogue_turn(
    app_config: StoryMedConfig,
    llm_config: StoryMedLlmConfig,
    dialogue_case: Dict[str, Any],
    turn: Dict[str, Any],
    ref_context: Dict[str, str],
    reference_session_id: str,
    input_content: str,
    passed_focuses: List[Dict[str, Any]],
    failed_turn_ids: List[int],
) -> Dict[str, Any]:
    """执行并审核单轮多轮编辑。"""
    turn_case_id = _turn_case_id(dialogue_case["case_id"], int(turn["turn_id"]))
    effective_focus = build_cumulative_evaluation_focus(passed_focuses, str(turn["evaluation_focus"]))
    runtime_edit_case = _runtime_edit_case(dialogue_case, turn, turn_case_id, effective_focus)
    adjustment_result = run_story_adjustment(
        config=app_config,
        case_id=turn_case_id,
        session_id=ref_context["session_id"],
        task_id=ref_context["task_id"],
        message=turn["message"],
    )
    validation = _validate_turn_result(
        llm_config=llm_config,
        runtime_edit_case=runtime_edit_case,
        session_id=ref_context["session_id"],
        adjustment_result=adjustment_result,
        input_content=input_content,
    )
    result = {
        "turn_id": turn["turn_id"],
        "case_id": turn_case_id,
        "message": turn["message"],
        "intent": turn.get("intent", {}),
        "involved_agents": turn.get("involved_agents", []),
        "atomic_evaluation_focus": turn["evaluation_focus"],
        "effective_evaluation_focus": effective_focus,
        "included_previous_turns": [item["turn_id"] for item in passed_focuses],
        "excluded_failed_turns": list(failed_turn_ids),
        "adjustment_result": adjustment_result,
        "edit_coverage_validation": validation,
        "passed": bool(validation.get("passed")),
        "score": validation.get("score", 0),
    }
    _write_turn_result(dialogue_case["case_id"], int(turn["turn_id"]), result)
    return result


def _validate_turn_result(
    llm_config: StoryMedLlmConfig,
    runtime_edit_case: Dict[str, Any],
    session_id: str,
    adjustment_result: Dict[str, Any],
    input_content: str,
) -> Dict[str, Any]:
    """审核单轮调整结果。"""
    if not adjustment_result.get("success"):
        return _failed_turn_validation(runtime_edit_case, adjustment_result)
    output_content = read_adjusted_content(runtime_edit_case["case_id"], session_id, adjustment_result)
    return evaluate_edit_coverage(
        llm_config,
        runtime_edit_case,
        session_id,
        adjustment_result,
        input_content,
        output_content,
    )


def _failed_turn_validation(runtime_edit_case: Dict[str, Any], adjustment_result: Dict[str, Any]) -> Dict[str, Any]:
    """构建单轮调整失败时的审核结果。"""
    evidence_parts = [str(item) for item in adjustment_result.get("stream_errors") or [] if str(item)]
    if adjustment_result.get("error"):
        evidence_parts.append(str(adjustment_result["error"]))
    required_nodes = _required_nodes(runtime_edit_case)
    return {
        "metric_name": "修改覆盖",
        "score": 0,
        "passed": False,
        "required_nodes": required_nodes,
        "artifact_coverage": {
            "passed": False,
            "present_nodes": [],
            "missing_nodes": required_nodes,
        },
        "node_results": [],
        "reason": "调整接口未成功产出修改后内容，跳过当前轮编辑覆盖审核。",
        "evidence": "; ".join(evidence_parts),
    }


def _runtime_edit_case(
    dialogue_case: Dict[str, Any],
    turn: Dict[str, Any],
    turn_case_id: str,
    effective_focus: str,
) -> Dict[str, Any]:
    """构建复用单轮编辑审核函数的运行时编辑用例。"""
    return {
        "case_id": turn_case_id,
        "ref_clinical_case_id": dialogue_case["ref_clinical_case_id"],
        "message": turn["message"],
        "evaluation_focus": effective_focus,
        "intent": turn.get("intent", {}),
        "involved_agent": {"required": turn.get("involved_agents", [])},
    }


def _reference_edit_case(dialogue_case: Dict[str, Any]) -> Dict[str, Any]:
    """构建解析原始患者故事上下文所需的最小编辑用例。"""
    return {
        "case_id": dialogue_case["case_id"],
        "ref_clinical_case_id": dialogue_case["ref_clinical_case_id"],
        "session_id": str(dialogue_case.get("session_id") or ""),
        "task_id": str(dialogue_case.get("task_id") or ""),
    }


def _build_preflight_failed_dialogue_result(dialogue_case: Dict[str, Any], error: str) -> Dict[str, Any]:
    """构建多轮编辑前置条件失败结果。"""
    return {
        "case_id": dialogue_case["case_id"],
        "ref_clinical_case_id": dialogue_case["ref_clinical_case_id"],
        "summary": dialogue_case.get("summary", ""),
        "session_id": "",
        "reference_session_id": "",
        "task_id": "",
        "turn_count": len(dialogue_case.get("turns", [])),
        "overall_passed": False,
        "turn_results": [],
        "error": f"多轮编辑接口前置条件不满足：{error}",
    }


def _required_nodes(edit_case: Dict[str, Any]) -> List[str]:
    """读取运行时编辑用例要求审核的节点。"""
    involved_agent = edit_case.get("involved_agent") if isinstance(edit_case.get("involved_agent"), dict) else {}
    raw_nodes = involved_agent.get("required") if isinstance(involved_agent, dict) else []
    nodes = [str(node).strip() for node in raw_nodes if str(node).strip()]
    return nodes or ["html"]


def _turn_case_id(dialogue_case_id: str, turn_id: int) -> str:
    """生成单轮编辑用例 ID。"""
    return f"{dialogue_case_id}_T{turn_id:02d}"


def _write_dialogue_result(case_id: str, result: Dict[str, Any]) -> None:
    """写入多轮编辑对话总结果。"""
    _write_json(EDIT_DIALOGUE_RESULTS_DIR / case_id / "dialogue_result.json", result)


def _write_turn_result(case_id: str, turn_id: int, result: Dict[str, Any]) -> None:
    """写入单轮编辑对话结果。"""
    _write_json(EDIT_DIALOGUE_RESULTS_DIR / case_id / f"turn_{turn_id:02d}" / "edit_coverage_validation.json", result)


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    """写入 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
