"""患者故事编辑覆盖测试流程。"""

from __future__ import annotations

import json
import re
from difflib import unified_diff
from pathlib import Path
from typing import Any, Dict, List

from story_med.clients.agent_task_client import find_agent_task_by_remote_task_id
from story_med.clients.llm_client import call_llm_text
from story_med.clients.story_client import create_session
from story_med.config.app_config import StoryMedConfig
from story_med.config.llm_app_config import StoryMedLlmConfig
from story_med.config.settings import ASSETS_DIR, EDIT_RESULTS_DIR, PROMPTS_DIR, RESULTS_DIR
from story_med.services.edit_story_config import get_edit_case
from story_med.services.story_adjustment_pipeline import run_story_adjustment

EDIT_COVERAGE_PROMPT_FILE = PROMPTS_DIR / "stoty_edit_complete.md"
EDIT_COVERAGE_RESULT_FILE = "edit_coverage_validation.json"


def run_edit_story_case(
    app_config: StoryMedConfig,
    llm_config: StoryMedLlmConfig,
    edit_case_id: str,
) -> Dict[str, Any]:
    """执行单条患者故事编辑测试。

    Args:
        app_config: 接口运行配置。
        llm_config: LLM 运行配置。
        edit_case_id: 编辑测试用例 ID。

    Returns:
        编辑测试结果。
    """
    edit_case = get_edit_case(edit_case_id)
    try:
        ref_context = resolve_reference_context(edit_case, app_config)
        reference_session_id = resolve_reference_artifact_session_id(
            edit_case["ref_clinical_case_id"],
            ref_context["session_id"],
        )
        input_content = read_reference_content(edit_case["ref_clinical_case_id"], reference_session_id)
    except Exception as exc:
        result = _build_preflight_failed_edit_result(edit_case, str(exc))
        _write_edit_validation_result(edit_case["case_id"], result)
        return result
    adjustment_result = run_story_adjustment(
        config=app_config,
        case_id=edit_case["case_id"],
        session_id=ref_context["session_id"],
        task_id=ref_context["task_id"],
        message=edit_case["message"],
    )
    if not adjustment_result.get("success"):
        result = _build_failed_edit_result(edit_case, ref_context, reference_session_id, adjustment_result)
        _write_edit_validation_result(edit_case["case_id"], result)
        return result
    output_content = read_adjusted_content(edit_case["case_id"], ref_context["session_id"], adjustment_result)
    validation = evaluate_edit_coverage(
        llm_config,
        edit_case,
        reference_session_id,
        adjustment_result,
        input_content,
        output_content,
    )
    result = {
        "case_id": edit_case["case_id"],
        "ref_clinical_case_id": edit_case["ref_clinical_case_id"],
        "session_id": ref_context["session_id"],
        "reference_session_id": reference_session_id,
        "task_id": ref_context["task_id"],
        "message": edit_case["message"],
        "adjustment_result": adjustment_result,
        "edit_coverage_validation": validation,
    }
    _write_edit_validation_result(edit_case["case_id"], result)
    return result


def resolve_reference_context(edit_case: Dict[str, Any], app_config: StoryMedConfig | None = None) -> Dict[str, str]:
    """解析编辑用例引用的历史会话上下文。

    Args:
        edit_case: 编辑测试用例。
        app_config: 接口运行配置，用于实时反查内容中台任务。

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
    """解析审核对比使用的原始病例最新产物会话 ID。

    Args:
        ref_case_id: 原始患者故事 case ID。
        fallback_session_id: 找不到本地产物时使用的编辑会话 ID。

    Returns:
        用于读取修改前产物的 session ID。
    """
    if _is_complete_reference_session(ref_case_id, fallback_session_id):
        return fallback_session_id
    latest_session_id = _infer_latest_complete_session_id(ref_case_id)
    return latest_session_id or fallback_session_id


def read_reference_content(ref_case_id: str, session_id: str) -> str:
    """读取修改前内容。

    Args:
        ref_case_id: 被引用的临床病例 ID。
        session_id: 历史会话 ID。

    Returns:
        修改前 HTML 或故事内容。
    """
    candidates = [
        ASSETS_DIR / ref_case_id / session_id / "adjustment" / "index.html",
        ASSETS_DIR / ref_case_id / session_id / "generate_final_image" / "index.html",
        ASSETS_DIR / ref_case_id / session_id / "generate_story" / "story.md",
    ]
    return _read_first_existing(candidates)


def read_adjusted_content(edit_case_id: str, session_id: str, adjustment_result: Dict[str, Any]) -> str:
    """读取修改后内容。

    Args:
        edit_case_id: 编辑测试用例 ID。
        session_id: 历史会话 ID。
        adjustment_result: 调整节点结果。

    Returns:
        修改后的 HTML 或文件内容。
    """
    for asset in adjustment_result.get("downloaded_assets") or []:
        local_path = Path(str(asset.get("local_path") or ""))
        if local_path.suffix.lower() in {".html", ".md", ".json"} and local_path.exists():
            return local_path.read_text(encoding="utf-8")
    return _read_first_existing([ASSETS_DIR / edit_case_id / session_id / "adjustment" / "index.html"], required=False)


def evaluate_edit_coverage_result(
    llm_config: StoryMedLlmConfig,
    edit_case: Dict[str, Any],
    input_content: str,
    output_content: str,
) -> Dict[str, Any]:
    """调用 LLM 判断修改覆盖是否满足测试预期。

    Args:
        llm_config: LLM 运行配置。
        edit_case: 编辑测试用例。
        input_content: 修改前内容。
        output_content: 修改后内容。

    Returns:
        修改覆盖审核结果。
    """
    content_diff = build_content_diff(input_content, output_content)
    prompt = build_edit_coverage_prompt(edit_case, input_content, output_content, content_diff)
    raw_result = call_llm_text(llm_config, prompt)
    parsed = parse_edit_coverage_result(raw_result)
    return {"raw_result": raw_result, "content_diff": content_diff, **parsed}


def evaluate_edit_coverage(
    llm_config: StoryMedLlmConfig,
    edit_case: Dict[str, Any],
    session_id: str,
    adjustment_result: Dict[str, Any],
    fallback_input_content: str,
    fallback_output_content: str,
) -> Dict[str, Any]:
    """按涉及节点审核编辑修改覆盖情况。

    Args:
        llm_config: LLM 运行配置。
        edit_case: 编辑测试用例。
        session_id: 历史会话 ID。
        adjustment_result: 调整接口执行结果。
        fallback_input_content: 兜底修改前内容。
        fallback_output_content: 兜底修改后内容。

    Returns:
        修改覆盖聚合审核结果。
    """
    required_nodes = _required_edit_nodes(edit_case)
    node_results = [
        evaluate_edit_node_coverage(
            llm_config,
            edit_case,
            node,
            session_id,
            adjustment_result,
            fallback_input_content,
            fallback_output_content,
        )
        for node in required_nodes
    ]
    artifact_coverage = build_artifact_coverage(node_results)
    passed = artifact_coverage["passed"] and all(item.get("passed") is True for item in node_results)
    score = round(sum(int(item.get("score") or 0) for item in node_results) / max(len(node_results), 1), 2)
    return {
        "metric_name": "修改覆盖",
        "score": score,
        "passed": passed,
        "required_nodes": required_nodes,
        "artifact_coverage": artifact_coverage,
        "node_results": node_results,
        "reason": _join_node_field(node_results, "reason"),
        "evidence": _join_node_field(node_results, "evidence"),
    }


def evaluate_edit_node_coverage(
    llm_config: StoryMedLlmConfig,
    edit_case: Dict[str, Any],
    node: str,
    session_id: str,
    adjustment_result: Dict[str, Any],
    fallback_input_content: str,
    fallback_output_content: str,
) -> Dict[str, Any]:
    """审核单个涉及节点的编辑完成情况。"""
    node_input = read_reference_node_content(edit_case["ref_clinical_case_id"], session_id, node)
    node_output = read_adjusted_node_content(edit_case["case_id"], session_id, adjustment_result, node)
    changed = bool(node_input.strip()) and node_input.strip() != node_output.strip()
    if not node_output.strip():
        return {
            "node": node,
            "artifact_present": False,
            "changed": False,
            "score": 0,
            "passed": False,
            "reason": f"未找到 {node} 节点的修改后产物，无法证明修改已覆盖。",
            "evidence": "",
        }
    if node_input.strip() and not changed:
        return {
            "node": node,
            "artifact_present": True,
            "changed": False,
            "score": 0,
            "passed": False,
            "reason": f"{node} 节点产物存在，但修改前后内容完全一致，未发生可验证的修改。",
            "evidence": "",
        }
    content_diff = build_content_diff(
        node_input or fallback_input_content,
        node_output or fallback_output_content,
    )
    prompt = build_edit_coverage_prompt(
        edit_case,
        node_input or fallback_input_content,
        node_output or fallback_output_content,
        content_diff,
    )
    raw_result = call_llm_text(llm_config, prompt)
    parsed = parse_edit_coverage_result(raw_result)
    return {
        "node": node,
        "artifact_present": True,
        "changed": changed,
        "content_diff": content_diff,
        "raw_result": raw_result,
        **parsed,
    }


def build_artifact_coverage(node_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """构建 involved_agent 对应产物覆盖结果。

    Args:
        node_results: 节点级审核结果列表。

    Returns:
        产物覆盖校验结果。
    """
    present_nodes = [str(item.get("node")) for item in node_results if item.get("artifact_present") is True]
    missing_nodes = [str(item.get("node")) for item in node_results if item.get("artifact_present") is not True]
    return {
        "passed": not missing_nodes,
        "present_nodes": present_nodes,
        "missing_nodes": missing_nodes,
    }


def read_reference_node_content(ref_case_id: str, session_id: str, node: str) -> str:
    """读取指定节点的修改前产物内容。"""
    return _read_first_existing(_reference_node_candidates(ref_case_id, session_id, node), required=False)


def read_adjusted_node_content(
    edit_case_id: str,
    session_id: str,
    adjustment_result: Dict[str, Any],
    node: str,
) -> str:
    """读取指定节点的修改后产物内容。"""
    downloaded = _read_downloaded_node_asset(adjustment_result, node)
    if downloaded:
        return downloaded
    return _read_first_existing(_adjusted_node_candidates(edit_case_id, session_id, node), required=False)


def build_edit_coverage_prompt(
    edit_case: Dict[str, Any],
    input_content: str,
    output_content: str,
    content_diff: str | None = None,
) -> str:
    """构建修改覆盖审核提示词。"""
    template = EDIT_COVERAGE_PROMPT_FILE.read_text(encoding="utf-8")
    replacements = {
        "{{message}}": str(edit_case.get("message") or ""),
        "{{evaluation_focus}}": str(edit_case.get("evaluation_focus") or ""),
        "{{content_diff}}": _truncate(content_diff or build_content_diff(input_content, output_content), 12000),
        "{{input_content}}": _truncate(input_content, 12000),
        "{{output_content}}": _truncate(output_content, 12000),
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template


def build_content_diff(input_content: str, output_content: str, max_chars: int = 12000) -> str:
    """生成修改前后内容差异，用于修改覆盖审核。

    Args:
        input_content: 修改前内容。
        output_content: 修改后内容。
        max_chars: 最大保留字符数。

    Returns:
        unified diff 文本。
    """
    if not input_content.strip():
        return _truncate(f"[修改前为空]\n\n{output_content}", max_chars)
    diff_lines = unified_diff(
        input_content.splitlines(),
        output_content.splitlines(),
        fromfile="before",
        tofile="after",
        lineterm="",
    )
    diff_text = "\n".join(diff_lines)
    return _truncate(diff_text or "[无文本差异]", max_chars)


def parse_edit_coverage_result(raw_result: str) -> Dict[str, Any]:
    """解析修改覆盖审核返回文本。"""
    score_match = re.search(r"Score:\s*(\d+)", raw_result, re.IGNORECASE)
    pass_match = re.search(r"Pass:\s*(true|false)", raw_result, re.IGNORECASE)
    score = int(score_match.group(1)) if score_match else 0
    return {
        "score": score,
        "passed": pass_match.group(1).lower() == "true" if pass_match else score >= 8,
        "reason": _extract_line_value(raw_result, "Reason"),
        "evidence": _extract_line_value(raw_result, "Evidence"),
    }


def evaluate_edit_effect(
    llm_config: StoryMedLlmConfig,
    edit_case: Dict[str, Any],
    input_content: str,
    output_content: str,
) -> Dict[str, Any]:
    """兼容旧调用：改用修改覆盖审核。"""
    return evaluate_edit_coverage_result(llm_config, edit_case, input_content, output_content)


def build_edit_effect_prompt(
    edit_case: Dict[str, Any],
    input_content: str,
    output_content: str,
    content_diff: str | None = None,
) -> str:
    """兼容旧调用：改用修改覆盖提示词。"""
    return build_edit_coverage_prompt(edit_case, input_content, output_content, content_diff)


def parse_edit_effect_result(raw_result: str) -> Dict[str, Any]:
    """兼容旧调用：改用修改覆盖结果解析。"""
    return parse_edit_coverage_result(raw_result)


def _required_edit_nodes(edit_case: Dict[str, Any]) -> List[str]:
    """读取需要验证修改覆盖的节点列表。"""
    involved_agent = edit_case.get("involved_agent") if isinstance(edit_case.get("involved_agent"), dict) else {}
    raw_nodes = involved_agent.get("required") if isinstance(involved_agent, dict) else []
    nodes = [str(node).strip() for node in raw_nodes if str(node).strip()]
    return nodes or ["html"]


def _reference_node_candidates(ref_case_id: str, session_id: str, node: str) -> List[Path]:
    """生成指定节点修改前产物候选路径。"""
    base_dir = ASSETS_DIR / ref_case_id / session_id
    candidates = {
        "story": [base_dir / "adjustment" / "story.md", base_dir / "generate_story" / "story.md"],
        "html": [base_dir / "adjustment" / "index.html", base_dir / "generate_final_image" / "index.html"],
        "image": [base_dir / "adjustment" / "image_design.json", base_dir / "generate_images" / "image_design.json"],
        "outline": [base_dir / "adjustment" / "outline.md", base_dir / "generate_outline" / "outline.md"],
    }
    return candidates.get(node, [base_dir / "adjustment" / f"{node}.md", base_dir / "adjustment" / f"{node}.json"])


def _adjusted_node_candidates(edit_case_id: str, session_id: str, node: str) -> List[Path]:
    """生成指定节点修改后产物候选路径。"""
    base_dir = ASSETS_DIR / edit_case_id / session_id / "adjustment"
    candidates = {
        "story": [base_dir / "story.md"],
        "html": [base_dir / "index.html"],
        "image": [base_dir / "image_design.json"],
        "outline": [base_dir / "outline.md"],
    }
    return candidates.get(node, [base_dir / f"{node}.md", base_dir / f"{node}.json"])


def _read_downloaded_node_asset(adjustment_result: Dict[str, Any], node: str) -> str:
    """从已下载产物中读取指定节点文本内容。"""
    matched_assets: List[Dict[str, Any]] = []
    for asset in adjustment_result.get("downloaded_assets") or []:
        local_path = Path(str(asset.get("local_path") or ""))
        if not _asset_matches_node(local_path, asset, node):
            continue
        matched_assets.append(asset)
        if local_path.suffix.lower() in {".html", ".md", ".json", ".txt"} and local_path.exists():
            return local_path.read_text(encoding="utf-8")
    if matched_assets:
        return json.dumps({"downloaded_assets": matched_assets}, ensure_ascii=False, indent=2)
    return ""


def _asset_matches_node(local_path: Path, asset: Dict[str, Any], node: str) -> bool:
    """判断下载产物是否属于指定编辑节点。"""
    asset_type = str(asset.get("type") or "").lower()
    name = local_path.name.lower()
    if node == "story":
        return asset_type == "markdown" or name == "story.md"
    if node == "html":
        return asset_type == "html" or name == "index.html"
    if node == "image":
        return asset_type in {"json", "image", "image_list", "png", "jpg", "jpeg"} or name == "image_design.json"
    if node == "outline":
        return name == "outline.md"
    return node in name


def _join_node_field(node_results: List[Dict[str, Any]], field: str) -> str:
    """拼接节点审核说明。"""
    values = [f"{item.get('node')}: {item.get(field)}" for item in node_results if item.get(field)]
    return "；".join(values)


def _build_failed_edit_result(
    edit_case: Dict[str, Any],
    ref_context: Dict[str, str],
    reference_session_id: str,
    adjustment_result: Dict[str, Any],
) -> Dict[str, Any]:
    """构建调整失败时的编辑测试结果。"""
    evidence_parts = [str(item) for item in adjustment_result.get("stream_errors") or [] if str(item)]
    if adjustment_result.get("error"):
        evidence_parts.append(str(adjustment_result["error"]))
    result = {
        "case_id": edit_case["case_id"],
        "ref_clinical_case_id": edit_case["ref_clinical_case_id"],
        "session_id": ref_context["session_id"],
        "reference_session_id": reference_session_id,
        "task_id": ref_context["task_id"],
        "message": edit_case["message"],
        "adjustment_result": adjustment_result,
        "edit_coverage_validation": {
            "metric_name": "修改覆盖",
            "score": 0,
            "passed": False,
            "required_nodes": _required_edit_nodes(edit_case),
            "artifact_coverage": {
                "passed": False,
                "present_nodes": [],
                "missing_nodes": _required_edit_nodes(edit_case),
            },
            "node_results": [],
            "reason": "调整接口未成功产出修改后内容，跳过编辑效果审核。",
            "evidence": "; ".join(evidence_parts),
        },
    }
    return result


def _build_preflight_failed_edit_result(edit_case: Dict[str, Any], error: str) -> Dict[str, Any]:
    """构建编辑接口调用前置失败结果。

    Args:
        edit_case: 编辑测试用例。
        error: 前置校验失败原因。

    Returns:
        编辑失败结果。
    """
    required_nodes = _required_edit_nodes(edit_case)
    result = {
        "case_id": edit_case["case_id"],
        "ref_clinical_case_id": edit_case["ref_clinical_case_id"],
        "session_id": "",
        "reference_session_id": resolve_reference_artifact_session_id(edit_case["ref_clinical_case_id"], ""),
        "task_id": "",
        "message": edit_case["message"],
        "adjustment_result": {
            "success": False,
            "error": error,
        },
        "edit_coverage_validation": {
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
            "reason": f"编辑接口前置条件不满足：{error}",
            "evidence": "",
        },
    }
    return result


def _load_previous_adjustment(ref_case_id: str) -> Dict[str, Any]:
    """读取编辑用例最近一次调整摘要。"""
    path = EDIT_RESULTS_DIR / ref_case_id / "story_adjustment_result.json"
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


def _infer_latest_session_id(ref_case_id: str) -> str:
    """从 assets 目录推断引用病例最新会话 ID。"""
    case_dir = ASSETS_DIR / ref_case_id
    if not case_dir.exists():
        return ""
    sessions = [path for path in case_dir.iterdir() if path.is_dir()]
    if not sessions:
        return ""
    return max(sessions, key=lambda path: path.stat().st_mtime).name


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
    """判断引用病例会话是否包含可作为编辑基线的完整患者故事产物。"""
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


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    """写入 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_edit_validation_result(case_id: str, result: Dict[str, Any]) -> None:
    """写入编辑覆盖审核结果。"""
    _write_json(EDIT_RESULTS_DIR / case_id / EDIT_COVERAGE_RESULT_FILE, result)
