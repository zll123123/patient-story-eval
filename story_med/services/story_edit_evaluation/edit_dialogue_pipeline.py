"""患者故事多轮编辑对话测试流程。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from story_med.config.app_config import StoryMedConfig
from story_med.config.app_config import StoryMedLlmConfig
from story_med.config.settings import EDIT_AUDITS_DIR
from story_med.services.story_edit_evaluation.edit_dialogue_attribution_pipeline import run_edit_dialogue_attribution
from story_med.services.story_edit_evaluation.edit_coverage_service import (
    evaluate_edit_coverage,
    read_adjusted_content,
    read_reference_content,
    resolve_reference_artifact_session_id,
    resolve_reference_context,
)
from story_med.services.story_edit_evaluation.story_adjustment_pipeline import run_story_adjustment
from story_med.services.clinical_case_preparation.yaml_case_service import get_edit_dialogue_case


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
        "evaluation_mode": "final_only",
        "session_id": ref_context["session_id"],
        "reference_session_id": reference_session_id,
        "task_id": ref_context["task_id"],
        "turn_count": len(dialogue_case["turns"]),
        "overall_passed": _build_overall_passed(turn_results),
        "turn_results": turn_results,
    }
    _write_dialogue_result(dialogue_case["case_id"], result)
    run_edit_dialogue_attribution(llm_config, result)
    return result


def audit_edit_dialogue_case(
    app_config: StoryMedConfig,
    llm_config: StoryMedLlmConfig,
    dialogue_case_id: str,
) -> Dict[str, Any]:
    """基于已有编辑产物重跑覆盖审核与归因。"""
    dialogue_case = get_edit_dialogue_case(dialogue_case_id)
    existing_result = _load_existing_dialogue_result(dialogue_case_id)
    try:
        ref_context = resolve_reference_context(_reference_edit_case(dialogue_case), app_config)
        reference_session_id = resolve_reference_artifact_session_id(
            dialogue_case["ref_clinical_case_id"],
            str(existing_result.get("reference_session_id") or ref_context["session_id"]),
        )
        input_content = read_reference_content(dialogue_case["ref_clinical_case_id"], reference_session_id)
    except Exception as exc:
        result = _build_preflight_failed_dialogue_result(dialogue_case, str(exc))
        _write_dialogue_result(dialogue_case["case_id"], result)
        return result

    turn_results = _audit_existing_turns(
        llm_config=llm_config,
        dialogue_case=dialogue_case,
        existing_result=existing_result,
        ref_context=ref_context,
        reference_session_id=reference_session_id,
        input_content=input_content,
    )
    result = {
        "case_id": dialogue_case["case_id"],
        "ref_clinical_case_id": dialogue_case["ref_clinical_case_id"],
        "summary": dialogue_case.get("summary", ""),
        "evaluation_mode": "final_only",
        "session_id": ref_context["session_id"],
        "reference_session_id": reference_session_id,
        "task_id": ref_context["task_id"],
        "turn_count": len(dialogue_case["turns"]),
        "overall_passed": _build_overall_passed(turn_results),
        "turn_results": turn_results,
    }
    _write_dialogue_result(dialogue_case["case_id"], result)
    run_edit_dialogue_attribution(llm_config, result)
    return result


def build_cumulative_evaluation_focus(
    passed_focuses: List[Dict[str, Any]],
    current_focus: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    """构建当前轮有效累计评估点。

    Args:
        passed_focuses: 历史已通过轮次的评估点。
        current_focus: 当前轮原子评估点列表。

    Returns:
        当前轮用于审核的累计评估点。
    """
    focus_items: List[Dict[str, str]] = []
    for item in passed_focuses:
        focus_items.extend(_normalize_focus_items(item.get("evaluation_focus")))
    focus_items.extend(_normalize_focus_items(current_focus))
    return focus_items


def _run_dialogue_turns(
    app_config: StoryMedConfig,
    llm_config: StoryMedLlmConfig,
    dialogue_case: Dict[str, Any],
    ref_context: Dict[str, str],
    reference_session_id: str,
    input_content: str,
) -> List[Dict[str, Any]]:
    """串行执行多轮编辑，全部成功后仅审核最终轮。"""
    passed_focuses: List[Dict[str, Any]] = []
    turn_results: List[Dict[str, Any]] = []
    execution_failed = False
    for turn in dialogue_case["turns"]:
        if execution_failed:
            turn_result = _not_run_turn(
                dialogue_case, turn, passed_focuses, "前一轮编辑执行失败"
            )
        else:
            turn_result = _execute_single_turn(
                app_config=app_config,
                dialogue_case=dialogue_case,
                turn=turn,
                ref_context=ref_context,
                passed_focuses=passed_focuses,
            )
        turn_results.append(turn_result)
        if turn_result.get("execution_status") == "success":
            passed_focuses.append(
                {
                    "turn_id": turn["turn_id"],
                    "evaluation_focus": turn["evaluation_focus"],
                    "involved_agents": turn.get("involved_agents", []),
                }
            )
        else:
            execution_failed = True
    if turn_results and not execution_failed:
        _audit_final_turn(
            llm_config,
            dialogue_case,
            turn_results[-1],
            reference_session_id,
            input_content,
        )
    return turn_results


def _audit_existing_turns(
    llm_config: StoryMedLlmConfig,
    dialogue_case: Dict[str, Any],
    existing_result: Dict[str, Any],
    ref_context: Dict[str, str],
    reference_session_id: str,
    input_content: str,
) -> List[Dict[str, Any]]:
    """基于已有编辑产物仅重跑最终轮审核。"""
    existing_turns = {
        int(item.get("turn_id") or 0): item
        for item in existing_result.get("turn_results", [])
        if isinstance(item, dict)
    }
    turn_results: List[Dict[str, Any]] = []
    execution_failed = False
    passed_focuses: List[Dict[str, Any]] = []
    for turn in dialogue_case["turns"]:
        existing_turn = existing_turns.get(int(turn["turn_id"]) or 0, {})
        turn_result = _execution_record_from_existing(dialogue_case, turn, existing_turn)
        turn_results.append(turn_result)
        if execution_failed:
            continue
        if turn_result.get("execution_status") == "success":
            passed_focuses.append({"turn_id": turn["turn_id"], "evaluation_focus": turn["evaluation_focus"], "involved_agents": turn.get("involved_agents", [])})
        else:
            execution_failed = True
    if turn_results and not execution_failed:
        _audit_final_turn(
            llm_config,
            dialogue_case,
            turn_results[-1],
            reference_session_id,
            input_content,
        )
    return turn_results


def _execute_single_turn(
    app_config: StoryMedConfig,
    dialogue_case: Dict[str, Any],
    turn: Dict[str, Any],
    ref_context: Dict[str, str],
    passed_focuses: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """只执行单轮编辑，不执行审核。"""
    turn_case_id = _turn_case_id(dialogue_case["case_id"], int(turn["turn_id"]))
    atomic_focus = _normalize_focus_items(turn["evaluation_focus"])
    effective_focus = build_cumulative_evaluation_focus(passed_focuses, atomic_focus)
    adjustment_result = run_story_adjustment(
        config=app_config,
        case_id=turn_case_id,
        session_id=ref_context["session_id"],
        task_id=ref_context["task_id"],
        message=turn["message"],
    )
    result = {
        "turn_id": turn["turn_id"],
        "case_id": turn_case_id,
        "message": turn["message"],
        "intent": turn.get("intent", {}),
        "involved_agents": turn.get("involved_agents", []),
        "atomic_evaluation_focus": atomic_focus,
        "effective_evaluation_focus": effective_focus,
        "included_previous_turns": [item["turn_id"] for item in passed_focuses],
        "execution_status": "success" if adjustment_result.get("success") else "failed",
        "execution_passed": bool(adjustment_result.get("success")),
        "adjustment_result": adjustment_result,
    }
    return result


def _not_run_turn(
    dialogue_case: Dict[str, Any],
    turn: Dict[str, Any],
    passed_focuses: List[Dict[str, Any]],
    reason: str,
) -> Dict[str, Any]:
    """记录未执行的后续轮次。"""
    return {
        "turn_id": turn["turn_id"],
        "case_id": _turn_case_id(dialogue_case["case_id"], int(turn["turn_id"])),
        "message": turn["message"],
        "intent": turn.get("intent", {}),
        "involved_agents": turn.get("involved_agents", []),
        "atomic_evaluation_focus": _normalize_focus_items(turn["evaluation_focus"]),
        "effective_evaluation_focus": build_cumulative_evaluation_focus(
            passed_focuses, _normalize_focus_items(turn["evaluation_focus"])
        ),
        "included_previous_turns": [item["turn_id"] for item in passed_focuses],
        "execution_status": "not_run",
        "execution_passed": False,
        "execution_error": reason,
    }


def _execution_record_from_existing(
    dialogue_case: Dict[str, Any],
    turn: Dict[str, Any],
    existing_turn: Dict[str, Any],
) -> Dict[str, Any]:
    """读取已有轮次的执行结果，不重建逐轮审核结果。"""
    adjustment_result = existing_turn.get("adjustment_result") if isinstance(existing_turn.get("adjustment_result"), dict) else {}
    success = bool(adjustment_result.get("success"))
    return {
        "turn_id": turn["turn_id"],
        "case_id": _turn_case_id(dialogue_case["case_id"], int(turn["turn_id"])),
        "message": turn["message"],
        "intent": turn.get("intent", {}),
        "involved_agents": turn.get("involved_agents", []),
        "atomic_evaluation_focus": _normalize_focus_items(turn["evaluation_focus"]),
        "effective_evaluation_focus": existing_turn.get("effective_evaluation_focus") or [],
        "execution_status": "success" if success else "failed",
        "execution_passed": success,
        "adjustment_result": adjustment_result,
    }


def _audit_final_turn(
    llm_config: StoryMedLlmConfig,
    dialogue_case: Dict[str, Any],
    turn_result: Dict[str, Any],
    session_id: str,
    input_content: str,
)-> None:
    """仅审核最终轮并写入最终轮审核结果。"""
    turn_case = _runtime_edit_case(
        dialogue_case,
        turn_result,
        str(turn_result["case_id"]),
        turn_result.get("effective_evaluation_focus") or [],
    )
    validation = _validate_turn_result(
        llm_config,
        turn_case,
        session_id,
        turn_result.get("adjustment_result") or {},
        input_content,
    )
    turn_result["audit_status"] = "passed" if validation.get("passed") else "failed"
    turn_result["edit_coverage_validation"] = validation
    turn_result["passed"] = bool(validation.get("passed"))
    turn_result["score"] = validation.get("score", 0)
    _write_turn_result(dialogue_case["case_id"], int(turn_result["turn_id"]), turn_result)


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


def _runtime_edit_case(
    dialogue_case: Dict[str, Any],
    turn: Dict[str, Any],
    turn_case_id: str,
    effective_focus: List[Dict[str, str]],
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
        "case_id": "",
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
        "evaluation_mode": "final_only",
        "session_id": "",
        "reference_session_id": "",
        "task_id": "",
        "turn_count": len(dialogue_case.get("turns", [])),
        "overall_passed": False,
        "turn_results": [],
        "error": f"多轮编辑接口前置条件不满足：{error}",
    }


def _turn_case_id(dialogue_case_id: str, turn_id: int) -> str:
    """生成单轮编辑用例 ID。"""
    return f"{dialogue_case_id}_T{turn_id:02d}"


def _write_dialogue_result(case_id: str, result: Dict[str, Any]) -> None:
    """写入多轮编辑对话总结果。"""
    _write_json(EDIT_AUDITS_DIR / case_id / "dialogue_result.json", result)


def _write_turn_result(case_id: str, turn_id: int, result: Dict[str, Any]) -> None:
    """写入单轮编辑对话结果。"""
    _write_json(EDIT_AUDITS_DIR / case_id / f"turn_{turn_id:02d}" / "edit_coverage_validation.json", result)


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    """写入 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_existing_dialogue_result(case_id: str) -> Dict[str, Any]:
    """读取已有多轮编辑结果。"""
    path = EDIT_AUDITS_DIR / case_id / "dialogue_result.json"
    if not path.exists():
        raise FileNotFoundError(f"未找到已有编辑结果: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _normalize_focus_items(raw_focus: Any) -> List[Dict[str, str]]:
    """归一化评估点结构。"""
    if isinstance(raw_focus, list):
        return [
            {
                "id": str(item.get("id") or "").strip(),
                "description": str(item.get("description") or "").strip(),
            }
            for item in raw_focus
            if isinstance(item, dict)
            and str(item.get("id") or "").strip()
            and str(item.get("description") or "").strip()
        ]
    return []


def _build_overall_passed(turn_results: List[Dict[str, Any]]) -> bool:
    """汇总多轮执行和最终轮审核状态。"""
    if not turn_results:
        return False
    if not all(item.get("execution_status") == "success" for item in turn_results):
        return False
    final_turn = max(turn_results, key=lambda item: int(item.get("turn_id") or 0))
    return final_turn.get("audit_status") == "passed"
