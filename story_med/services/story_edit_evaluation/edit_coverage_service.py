"""患者故事编辑覆盖共享服务。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

from story_med.clients.agent_api.agent_task_client import (
    find_agent_task_by_remote_task_id,
)
from story_med.clients.llm.llm_client import call_llm_text
from story_med.clients.llm.multimodal_llm_client import call_multimodal_text
from story_med.clients.base.http_client import create_session
from story_med.config.app_config import StoryMedConfig
from story_med.config.app_config import StoryMedLlmConfig
from story_med.config.app_config import StoryMedVisionConfig
from story_med.config.settings import (
    ASSETS_DIR,
    EDIT_RUNS_DIR,
    GENERATION_RUNS_DIR,
    PROMPTS_DIR,
)
from story_med.utils.timing import TimingCollector

EDIT_COVERAGE_PROMPT_FILE = PROMPTS_DIR / "edit_coverage_validate.md"
EDIT_IMAGE_COVERAGE_PROMPT_FILE = PROMPTS_DIR / "edit_image_coverage_validate.md"


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


def resolve_reference_artifact_session_id(
    ref_case_id: str, fallback_session_id: str
) -> str:
    """解析审核对比使用的原始病例最新产物会话 ID。"""
    if _is_complete_reference_session(ref_case_id, fallback_session_id):
        return fallback_session_id
    latest_session_id = _infer_latest_complete_session_id(ref_case_id)
    return latest_session_id or fallback_session_id


def read_reference_content(ref_case_id: str, session_id: str) -> str:
    """读取修改前基线内容。"""
    session_dir = ASSETS_DIR / ref_case_id / session_id
    generated_candidates = [
        *sorted((session_dir / "adjustment").glob("index_*.html")),
        *sorted((session_dir / "generate_final_image").glob("index_*.html")),
        *sorted((session_dir / "generate_story").glob("story_*.md")),
    ]
    return _read_first_existing(generated_candidates)


def read_adjusted_content(
    edit_case_id: str, session_id: str, adjustment_result: Dict[str, Any]
) -> str:
    """读取修改后内容。"""
    for asset in adjustment_result.get("downloaded_assets") or []:
        local_path = Path(str(asset.get("local_path") or ""))
        if local_path.suffix.lower() == ".html" and local_path.exists():
            return local_path.read_text(encoding="utf-8")
    for asset in adjustment_result.get("downloaded_assets") or []:
        local_path = Path(str(asset.get("local_path") or ""))
        if local_path.suffix.lower() in {".md", ".json"} and local_path.exists():
            return local_path.read_text(encoding="utf-8")
    candidates = sorted(
        (ASSETS_DIR / edit_case_id / session_id / "adjustment").glob("index_*.html")
    )
    return _read_first_existing(candidates, required=False)


def evaluate_edit_coverage(
    llm_config: StoryMedLlmConfig,
    edit_case: Dict[str, Any],
    session_id: str,
    adjustment_result: Dict[str, Any],
    fallback_input_content: str,
    fallback_output_content: str,
    vision_config: StoryMedVisionConfig | None = None,
) -> Dict[str, Any]:
    """只基于最终长图审核编辑修改覆盖情况。"""
    timings = TimingCollector()
    output_content = _read_adjusted_long_image_content(
        edit_case["case_id"], session_id, adjustment_result
    )
    if not output_content.strip():
        result = _missing_html_validation()
        result["execution_stages"] = timings.to_list()
        return result
    with timings.stage("edit_html_coverage_audit", "audit", session_id=session_id):
        html_result = _evaluate_edit_coverage_result(
            llm_config,
            edit_case,
            fallback_input_content,
            output_content or fallback_output_content,
        )
    final_result = _merge_html_and_image_results(
        vision_config=vision_config,
        edit_case=edit_case,
        html_result=html_result,
        image_path=_read_adjusted_image_path(edit_case["case_id"], session_id, adjustment_result),
        timings=timings,
    )
    return {
        "metric_name": "修改覆盖",
        "score": final_result["score"],
        "passed": final_result["passed"],
        "required_nodes": ["html"],
        "evaluated_nodes": final_result["evaluated_nodes"],
        "artifact_coverage": {
            "passed": True,
            "present_nodes": ["html"],
            "missing_nodes": [],
        },
        "node_results": final_result["node_results"],
        "reason": final_result["reason"],
        "evidence": final_result["evidence"],
        "html_validation": html_result,
        "image_validation": final_result["image_validation"],
        "execution_stages": timings.to_list(),
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
        "{{evaluation_focus}}": _format_evaluation_focus(
            edit_case.get("evaluation_focus")
        ),
        "{{image_input}}": output_content,
        "{{content_diff}}": "",
        "{{input_content}}": input_content,
        "{{output_content}}": output_content,
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template


def parse_edit_coverage_result(
    raw_result: str, evaluation_focus: Any = None
) -> Dict[str, Any]:
    """解析修改覆盖审核返回文本。"""
    json_result = _parse_json_coverage_result(raw_result)
    if json_result is not None:
        return json_result
    score_match = re.search(r"Score:\s*(\d+)", raw_result, re.IGNORECASE)
    pass_match = re.search(r"Pass:\s*(true|false)", raw_result, re.IGNORECASE)
    score = int(score_match.group(1)) if score_match else 0
    reason = _extract_line_value(raw_result, "Reason") or _extract_line_value(
        raw_result, "Overall_Reason"
    )
    evidence = _extract_line_value(raw_result, "Evidence")
    item_results = _parse_item_results(raw_result)
    if not item_results:
        item_results = _build_default_item_results(evaluation_focus, bool(pass_match and pass_match.group(1).lower() == "true"))
    return {
        "score": score,
        "passed": pass_match.group(1).lower() == "true" if pass_match else score >= 8,
        "reason": reason,
        "evidence": evidence,
        "item_results": item_results,
    }


def _parse_json_coverage_result(raw_result: str) -> Dict[str, Any] | None:
    """解析视觉模型返回的 JSON 结构。"""
    try:
        parsed = json.loads(raw_result)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    item_results = parsed.get("item_results") or parsed.get("Item_Results") or []
    if not isinstance(item_results, list):
        item_results = []
    normalized_items = [
        {
            "id": str(item.get("id") or ""),
            "passed": bool(item.get("passed")),
            "reason": str(item.get("reason") or ""),
            "evidence": str(item.get("evidence") or ""),
        }
        for item in item_results
        if isinstance(item, dict)
    ]
    passed = bool(parsed.get("passed", parsed.get("Pass", False)))
    return {
        "score": int(parsed.get("score", parsed.get("Score", 0)) or 0),
        "passed": passed,
        "reason": str(parsed.get("reason") or parsed.get("Overall_Reason") or ""),
        "evidence": str(parsed.get("evidence") or ""),
        "item_results": normalized_items,
    }


def _parse_item_results(raw_result: str) -> list[Dict[str, Any]]:
    """解析提示词返回的逐项 focus 结果。"""
    pattern = re.compile(
        r"-\s*id:\s*(?P<id>[^\n]+)\s*\n"
        r"\s*passed:\s*(?P<passed>true|false)\s*\n"
        r"\s*reason:\s*(?P<reason>.*?)\s*\n"
        r"\s*evidence:\s*(?P<evidence>.*?)(?=\n\s*-\s*id:|\n\s*Overall_Reason:|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    return [
        {
            "id": match.group("id").strip(),
            "passed": match.group("passed").lower() == "true",
            "reason": match.group("reason").strip(),
            "evidence": match.group("evidence").strip(),
        }
        for match in pattern.finditer(raw_result)
    ]


def _build_default_item_results(
    evaluation_focus: Any, passed: bool
) -> list[Dict[str, Any]]:
    """为未返回逐项结构的结果建立明确的整体项结果。"""
    if not isinstance(evaluation_focus, list):
        return []
    return [
        {
            "id": str(item.get("id") or ""),
            "passed": passed,
            "reason": "模型未返回逐项结果，沿用整体判断。",
            "evidence": "",
        }
        for item in evaluation_focus
        if isinstance(item, dict)
    ]


def write_edit_coverage_result(case_id: str, result: Dict[str, Any]) -> None:
    """写入编辑覆盖审核结果。"""
    output_path = EDIT_RUNS_DIR / case_id / "edit_coverage_validation.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _evaluate_edit_coverage_result(
    llm_config: StoryMedLlmConfig,
    edit_case: Dict[str, Any],
    input_content: str,
    output_content: str,
) -> Dict[str, Any]:
    """调用 LLM 判断修改覆盖是否满足测试预期。"""
    prompt = build_edit_coverage_prompt(edit_case, input_content, output_content)
    raw_result = call_llm_text(llm_config, prompt)
    parsed = parse_edit_coverage_result(raw_result, edit_case.get("evaluation_focus"))
    return {"raw_result": raw_result, **parsed}


def _merge_html_and_image_results(
    vision_config: StoryMedVisionConfig | None,
    edit_case: Dict[str, Any],
    html_result: Dict[str, Any],
    image_path: Path | None,
    timings: TimingCollector,
) -> Dict[str, Any]:
    """优先使用 HTML 结果，必要时用 PNG 复核失败 focus。"""
    html_items = html_result.get("item_results") or []
    failed_focus = [item for item in html_items if not item.get("passed")]
    image_result: Dict[str, Any] = {"status": "not_run", "item_results": []}
    if failed_focus and vision_config and image_path:
        with timings.stage("edit_image_coverage_audit", "audit"):
            image_result = _evaluate_image_coverage_result(
                vision_config, edit_case, failed_focus, image_path
            )
    final_items = _merge_item_results(html_items, image_result.get("item_results") or [])
    passed_count = sum(1 for item in final_items if item.get("passed"))
    total_count = len(final_items)
    passed = total_count > 0 and passed_count == total_count
    score = round(passed_count / total_count * 10) if total_count else 0
    return {
        "score": score,
        "passed": passed,
        "evaluated_nodes": ["html"] + (["image"] if image_result.get("status") == "success" else []),
        "node_results": [{"node": "html", "artifact_present": True, **html_result}]
        + ([{"node": "image", "artifact_present": True, **image_result}] if image_result.get("status") == "success" else []),
        "reason": _merge_reasons(final_items),
        "evidence": _merge_evidence(final_items),
        "image_validation": image_result,
    }


def _merge_item_results(
    html_items: list[Dict[str, Any]], image_items: list[Dict[str, Any]]
) -> list[Dict[str, Any]]:
    """按 focus ID 合并 HTML 和 PNG 的逐项结果。"""
    image_by_id = {str(item.get("id")): item for item in image_items}
    merged: list[Dict[str, Any]] = []
    for item in html_items:
        current = dict(item)
        image_item = image_by_id.get(str(item.get("id")))
        if not current.get("passed") and image_item:
            current = {**current, **image_item, "source": "image"}
        else:
            current["source"] = "html"
        merged.append(current)
    return merged


def _merge_reasons(items: list[Dict[str, Any]]) -> str:
    """拼接逐项审核结论。"""
    return "\n".join(
        f"{item.get('id')}: {item.get('reason') or '无判断理由'}"
        for item in items
    )


def _merge_evidence(items: list[Dict[str, Any]]) -> str:
    """拼接逐项审核证据。"""
    return "\n".join(
        f"{item.get('id')}: {item.get('evidence') or ''}" for item in items
    )


def _evaluate_image_coverage_result(
    vision_config: StoryMedVisionConfig,
    edit_case: Dict[str, Any],
    failed_focus: list[Dict[str, Any]],
    image_path: Path,
) -> Dict[str, Any]:
    """使用最终 PNG 复核 HTML 未通过的 focus。"""
    prompt = _build_image_coverage_prompt(edit_case, failed_focus)
    raw_result = call_multimodal_text(vision_config, prompt, [image_path])
    parsed = parse_edit_coverage_result(raw_result, failed_focus)
    return {"status": "success", "raw_result": raw_result, **parsed}


def _build_image_coverage_prompt(
    edit_case: Dict[str, Any], failed_focus: list[Dict[str, Any]]
) -> str:
    """构建视觉模型复核提示词。"""
    template = EDIT_IMAGE_COVERAGE_PROMPT_FILE.read_text(encoding="utf-8")
    replacements = {
        "{{message}}": str(edit_case.get("message") or ""),
        "{{evaluation_focus}}": _format_evaluation_focus(failed_focus),
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template


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
    candidates = sorted(
        (ASSETS_DIR / edit_case_id / session_id / "adjustment").glob("index_*.html")
    )
    return _read_first_existing(candidates, required=False)


def _read_adjusted_image_path(
    edit_case_id: str,
    session_id: str,
    adjustment_result: Dict[str, Any],
) -> Path | None:
    """读取最终轮 PNG 产物路径。"""
    for asset in adjustment_result.get("downloaded_assets") or []:
        local_path = Path(str(asset.get("local_path") or ""))
        if local_path.suffix.lower() == ".png" and local_path.exists():
            return local_path
    candidates = sorted(
        (ASSETS_DIR / edit_case_id / session_id / "adjustment").glob("index_*.png")
    )
    return candidates[0] if candidates else None


def _missing_html_validation() -> Dict[str, Any]:
    """构建缺失最终长图时的固定审核结果。"""
    return {
        "metric_name": "修改覆盖",
        "score": 0,
        "passed": False,
        "required_nodes": ["html"],
        "artifact_coverage": {
            "passed": False,
            "present_nodes": [],
            "missing_nodes": ["html"],
        },
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
    path = EDIT_RUNS_DIR / case_id / "story_adjustment_result.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _load_run_task_id(ref_case_id: str, session_id: str) -> str:
    """从患者故事运行结果中读取已保存的内容中台 task_id。"""
    if not session_id:
        return ""
    path = GENERATION_RUNS_DIR / ref_case_id / f"{session_id}.json"
    if not path.exists():
        return ""
    data = json.loads(path.read_text(encoding="utf-8"))
    session_response = data.get("session_response") if isinstance(data, dict) else {}
    content_hub_task = (
        session_response.get("content_hub_task")
        if isinstance(session_response, dict)
        else {}
    )
    return (
        str(content_hub_task.get("task_id") or "").strip()
        if isinstance(content_hub_task, dict)
        else ""
    )


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
    story_files = list((base_dir / "generate_story").glob("story_*.md"))
    html_files = list((base_dir / "generate_final_image").glob("index_*.html"))
    return bool(story_files and html_files)


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
