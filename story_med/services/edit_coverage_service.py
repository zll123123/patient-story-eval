"""患者故事编辑覆盖共享服务。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

from story_med.clients.agent_task_client import find_agent_task_by_remote_task_id
from story_med.clients.llm_client import call_llm_text
from story_med.clients.story_client import create_session
from story_med.config.app_config import StoryMedConfig
from story_med.config.llm_app_config import StoryMedLlmConfig
from story_med.config.settings import ASSETS_DIR, EDIT_RESULTS_DIR, PROMPTS_DIR, RESULTS_DIR

EDIT_COVERAGE_PROMPT_FILE = PROMPTS_DIR / "edit_coverage_validate.md"


def resolve_reference_context(
    edit_case: Dict[str, Any],
    app_config: StoryMedConfig | None = None,
) -> Dict[str, str]:
    """解析编辑用例引用的历史会话上下文。

    Args:
        edit_case: 编辑测试用例。
        app_config: 接口运行配置，用于必要时反查内容中台任务。

    Returns:
        包含 session_id 与 task_id 的上下文。
    """
    session_id = str(edit_case.get("session_id") or "").strip()
    task_id = str(edit_case.get("task_id") or "").strip()
    ref_case_id = str(edit_case.get("ref_clinical_case_id") or "").strip()
    if session_id and task_id:
        return {"session_id": session_id, "task_id": task_id}
    previous_adjustment = _load_previous_adjustment(str(edit_case.get("case_id") or ""))
    session_id = session_id or str(previous_adjustment.get("session_id") or "").strip()
    task_id = task_id or str(previous_adjustment.get("task_id") or "").strip()
    if session_id and task_id:
        return {"session_id": session_id, "task_id": task_id}
    inferred_session_id = session_id or _infer_latest_complete_session_id(ref_case_id)
    task_id = _load_run_task_id(ref_case_id, inferred_session_id)
    if not task_id and app_config:
        task_id = _lookup_content_hub_task_id(app_config, inferred_session_id)
    if inferred_session_id and task_id:
        return {"session_id": inferred_session_id, "task_id": task_id}
    raise RuntimeError(
        f"编辑用例缺少 task_id，ref_clinical_case_id={ref_case_id}, inferred_session_id={inferred_session_id}"
    )


def resolve_reference_artifact_session_id(ref_case_id: str, fallback_session_id: str) -> str:
    """解析审核对比使用的原始病例最新产物会话 ID。"""
    if _is_complete_reference_session(ref_case_id, fallback_session_id):
        return fallback_session_id
    latest_session_id = _infer_latest_complete_session_id(ref_case_id)
    return latest_session_id or fallback_session_id


def read_reference_content(ref_case_id: str, session_id: str) -> str:
    """读取修改前基线内容。"""
    candidates = [
        ASSETS_DIR / ref_case_id / session_id / "adjustment" / "index.html",
        ASSETS_DIR / ref_case_id / session_id / "generate_final_image" / "index.html",
        ASSETS_DIR / ref_case_id / session_id / "generate_story" / "story.md",
    ]
    return _read_first_existing(candidates)


def read_adjusted_content(edit_case_id: str, session_id: str, adjustment_result: Dict[str, Any]) -> str:
    """读取修改后内容。"""
    for asset in adjustment_result.get("downloaded_assets") or []:
        local_path = Path(str(asset.get("local_path") or ""))
        if local_path.suffix.lower() == ".html" and local_path.exists():
            return local_path.read_text(encoding="utf-8")
    for asset in adjustment_result.get("downloaded_assets") or []:
        local_path = Path(str(asset.get("local_path") or ""))
        if local_path.suffix.lower() in {".md", ".json"} and local_path.exists():
            return local_path.read_text(encoding="utf-8")
    fallback = ASSETS_DIR / edit_case_id / session_id / "adjustment" / "index.html"
    return _read_first_existing([fallback], required=False)


def evaluate_edit_coverage(
    llm_config: StoryMedLlmConfig,
    edit_case: Dict[str, Any],
    session_id: str,
    adjustment_result: Dict[str, Any],
    fallback_input_content: str,
    fallback_output_content: str,
) -> Dict[str, Any]:
    """只基于最终长图审核编辑修改覆盖情况。"""
    output_content = _read_adjusted_long_image_content(edit_case["case_id"], session_id, adjustment_result)
    if not output_content.strip():
        return _missing_html_validation()
    parsed = _evaluate_edit_coverage_result(
        llm_config,
        edit_case,
        fallback_input_content,
        output_content or fallback_output_content,
    )
    node_result = {"node": "html", "artifact_present": True, **parsed}
    return {
        "metric_name": "修改覆盖",
        "score": parsed.get("score", 0),
        "passed": bool(parsed.get("passed")),
        "required_nodes": ["html"],
        "artifact_coverage": {"passed": True, "present_nodes": ["html"], "missing_nodes": []},
        "node_results": [node_result],
        "reason": parsed.get("reason", ""),
        "evidence": parsed.get("evidence", ""),
    }


def build_edit_coverage_prompt(
    edit_case: Dict[str, Any],
    input_content: str,
    output_content: str,
) -> str:
    """构建修改覆盖审核提示词。"""
    template = EDIT_COVERAGE_PROMPT_FILE.read_text(encoding="utf-8")
    replacements = {
        "{{message}}": str(edit_case.get("message") or ""),
        "{{evaluation_focus}}": _format_evaluation_focus(edit_case.get("evaluation_focus")),
        "{{image_input}}": _truncate(output_content, 12000),
        "{{content_diff}}": "",
        "{{input_content}}": _truncate(input_content, 12000),
        "{{output_content}}": _truncate(output_content, 12000),
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template


def parse_edit_coverage_result(raw_result: str) -> Dict[str, Any]:
    """解析修改覆盖审核返回文本。"""
    score_match = re.search(r"Score:\s*(\d+)", raw_result, re.IGNORECASE)
    pass_match = re.search(r"Pass:\s*(true|false)", raw_result, re.IGNORECASE)
    score = int(score_match.group(1)) if score_match else 0
    reason = _extract_line_value(raw_result, "Reason") or _extract_line_value(raw_result, "Overall_Reason")
    evidence = _extract_line_value(raw_result, "Evidence")
    return {
        "score": score,
        "passed": pass_match.group(1).lower() == "true" if pass_match else score >= 8,
        "reason": reason,
        "evidence": evidence,
    }


def write_edit_coverage_result(case_id: str, result: Dict[str, Any]) -> None:
    """写入编辑覆盖审核结果。"""
    output_path = EDIT_RESULTS_DIR / case_id / "edit_coverage_validation.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def _evaluate_edit_coverage_result(
    llm_config: StoryMedLlmConfig,
    edit_case: Dict[str, Any],
    input_content: str,
    output_content: str,
) -> Dict[str, Any]:
    """调用 LLM 判断修改覆盖是否满足测试预期。"""
    prompt = build_edit_coverage_prompt(edit_case, input_content, output_content)
    raw_result = call_llm_text(llm_config, prompt)
    parsed = parse_edit_coverage_result(raw_result)
    return {"raw_result": raw_result, **parsed}


def _read_adjusted_long_image_content(
    edit_case_id: str,
    session_id: str,
    adjustment_result: Dict[str, Any],
) -> str:
    """读取修改后的最终长图内容。"""
    for asset in adjustment_result.get("downloaded_assets") or []:
        local_path = Path(str(asset.get("local_path") or ""))
        if local_path.suffix.lower() == ".html" and local_path.exists():
            return local_path.read_text(encoding="utf-8")
    fallback = ASSETS_DIR / edit_case_id / session_id / "adjustment" / "index.html"
    return _read_first_existing([fallback], required=False)


def _missing_html_validation() -> Dict[str, Any]:
    """构建缺失最终长图时的固定审核结果。"""
    return {
        "metric_name": "修改覆盖",
        "score": 0,
        "passed": False,
        "required_nodes": ["html"],
        "artifact_coverage": {"passed": False, "present_nodes": [], "missing_nodes": ["html"]},
        "node_results": [
            {
                "node": "html",
                "artifact_present": False,
                "score": 0,
                "passed": False,
                "reason": "未找到最终长图产物，无法进行编辑覆盖审核。",
                "evidence": "",
            }
        ],
        "reason": "未找到最终长图产物，无法进行编辑覆盖审核。",
        "evidence": "",
    }


def _format_evaluation_focus(evaluation_focus: Any) -> str:
    """格式化评估点，供提示词消费。"""
    if isinstance(evaluation_focus, (list, dict)):
        return json.dumps(evaluation_focus, ensure_ascii=False, indent=2)
    return str(evaluation_focus or "")


def _load_previous_adjustment(case_id: str) -> Dict[str, Any]:
    """读取最近一次调整摘要。"""
    path = EDIT_RESULTS_DIR / case_id / "story_adjustment_result.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _load_run_task_id(ref_case_id: str, session_id: str) -> str:
    """从患者故事运行结果中读取已保存的内容中台 task_id。"""
    if not session_id:
        return ""
    path = RESULTS_DIR / "runs" / ref_case_id / f"{session_id}.json"
    if not path.exists():
        return ""
    data = json.loads(path.read_text(encoding="utf-8"))
    session_response = data.get("session_response") if isinstance(data, dict) else {}
    content_hub_task = session_response.get("content_hub_task") if isinstance(session_response, dict) else {}
    return str(content_hub_task.get("task_id") or "").strip() if isinstance(content_hub_task, dict) else ""


def _lookup_content_hub_task_id(app_config: StoryMedConfig, session_id: str) -> str:
    """通过内容中台任务列表实时反查 task_id。"""
    task = find_agent_task_by_remote_task_id(create_session(), app_config, session_id)
    return str(task.get("task_id") or "").strip()


def _infer_latest_complete_session_id(ref_case_id: str) -> str:
    """从 assets 目录推断引用病例最新完整会话 ID。"""
    case_dir = ASSETS_DIR / ref_case_id
    if not case_dir.exists():
        return ""
    sessions = [
        path
        for path in case_dir.iterdir()
        if path.is_dir() and _is_complete_reference_session(ref_case_id, path.name)
    ]
    if not sessions:
        return ""
    return max(sessions, key=lambda path: path.stat().st_mtime).name


def _is_complete_reference_session(ref_case_id: str, session_id: str) -> bool:
    """判断引用病例会话是否包含完整患者故事产物。"""
    if not ref_case_id or not session_id:
        return False
    base_dir = ASSETS_DIR / ref_case_id / session_id
    required_files = [
        base_dir / "generate_story" / "story.md",
        base_dir / "generate_final_image" / "index.html",
    ]
    return all(path.exists() for path in required_files)


def _read_first_existing(candidates: list[Path], required: bool = True) -> str:
    """读取第一个存在的文本文件。"""
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
    if not required:
        return ""
    raise FileNotFoundError(f"未找到可用于编辑评估的输入内容: {[str(path) for path in candidates]}")


def _extract_line_value(text: str, key: str) -> str:
    """按行提取指定键的值。"""
    pattern = re.compile(rf"^{re.escape(key)}:\s*(.*)$", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _truncate(text: str, max_chars: int) -> str:
    """限制输入给模型的文本长度。"""
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}\n\n...[内容已截断]"
