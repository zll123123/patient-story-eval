"""内容中台 history 解析工具。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def iter_artifacts(history: Dict[str, Any]) -> List[Dict[str, Any]]:
    """展开 history artifacts 中的 OSS key。"""
    artifacts = history.get("artifacts") or {}
    results: List[Dict[str, Any]] = []
    if not isinstance(artifacts, dict):
        return results
    for group, items in artifacts.items():
        if not isinstance(items, list):
            continue
        for artifact in items:
            if isinstance(artifact, dict):
                results.extend(_artifact_keys(str(group), artifact))
    return results


def artifact_step_name(group: str, artifact: Dict[str, Any]) -> str:
    """将解析版 artifact 映射到本地审核目录。"""
    artifact_type = str(artifact.get("type") or "")
    if group == "case_parse":
        return "case_parse"
    if group == "outline":
        return "generate_outline"
    if group == "story":
        return "generate_story"
    if group == "image" or artifact_type in {"json", "image_list"}:
        return "generate_images"
    return "generate_final_image"


def artifacts_by_group(history: Dict[str, Any], group: str) -> Dict[str, Any]:
    """读取指定 artifact 分组。"""
    artifacts = history.get("artifacts") or {}
    if not isinstance(artifacts, dict):
        return {}
    value = artifacts.get(group)
    return {"artifacts": value} if value else {}


def is_generation_history_complete(history: Dict[str, Any]) -> bool:
    """判断生成 history 是否包含审核所需核心产物。"""
    artifacts = history.get("artifacts") or {}
    if not isinstance(artifacts, dict):
        return False
    required_groups = ("outline", "story", "image", "html")
    return all(isinstance(artifacts.get(group), list) and bool(artifacts.get(group)) for group in required_groups)


def is_adjustment_history_complete(
    history: Dict[str, Any], expected_message: str
) -> bool:
    """判断当前编辑 turn 是否完成并产出最终长图。

    Args:
        history: 标准化后的 history。
        expected_message: 当前编辑 turn 的用户修改要求。

    Returns:
        只有当前 turn 为 COMPLETED 且该 turn 自己包含 HTML 文件时才返回 True。
    """
    turn = _latest_turn_by_message(history, expected_message)
    if not turn or str(turn.get("status") or "").upper() != "COMPLETED":
        return False
    return _turn_contains_html(turn)


def _latest_turn_by_message(
    history: Dict[str, Any], expected_message: str
) -> Dict[str, Any]:
    """从 history 中找到当前修改消息对应的最新 turn。"""
    raw_history = history.get("raw_history")
    data = raw_history.get("data") if isinstance(raw_history, dict) else {}
    turns = data.get("turns") if isinstance(data, dict) else []
    if not isinstance(turns, list):
        return {}
    matches: List[Dict[str, Any]] = []
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        payload = turn.get("payload")
        message = payload.get("message") if isinstance(payload, dict) else ""
        if str(message or "") == expected_message:
            matches.append(turn)
    return matches[-1] if matches else {}


def _turn_contains_html(turn: Dict[str, Any]) -> bool:
    """判断单个 turn 的文件事件是否包含 HTML。"""
    for frame in turn.get("frames") or []:
        raw = frame_raw(frame) if isinstance(frame, dict) else {}
        data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
        files = data.get("files") if isinstance(data, dict) else []
        for file_item in files if isinstance(files, list) else []:
            if not isinstance(file_item, dict):
                continue
            file_type = str(file_item.get("type") or "").lower()
            file_key = str(file_item.get("oss_key") or "").lower()
            if file_type == "html" or file_key.endswith(".html"):
                return True
    return False


def normalize_content_hub_history(body: Dict[str, Any]) -> Dict[str, Any]:
    """将内容中台 history 转成评测链路使用的统一结构。"""
    messages: List[Dict[str, str]] = []
    artifacts: Dict[str, List[Dict[str, Any]]] = {}
    for frame in content_hub_frames(body):
        raw = frame_raw(frame)
        data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
        content = str(data.get("content") or "").strip() if isinstance(data, dict) else ""
        if content:
            messages.append({"role": "ai", "content": content})
        files = data.get("files") if isinstance(data, dict) else []
        if isinstance(files, list):
            _append_history_files(artifacts, files)
    return {"messages": messages, "artifacts": artifacts, "raw_history": body}


def normalize_content_hub_stream(stream_path: Path) -> Dict[str, Any]:
    """将 SSE 文件事件转成与 history 一致的产物结构。

    Args:
        stream_path: SSE 原始事件文件路径。

    Returns:
        与 ``normalize_content_hub_history`` 相同的结构。
    """
    messages: List[Dict[str, str]] = []
    artifacts: Dict[str, List[Dict[str, Any]]] = {}
    if not stream_path.exists():
        return {"messages": messages, "artifacts": artifacts, "raw_stream": {}}
    for line in stream_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("data:"):
            continue
        event = _parse_stream_event(line[5:].strip())
        raw_payload = _stream_raw_payload(event)
        data = raw_payload.get("data")
        if not isinstance(data, dict):
            continue
        content = str(data.get("content") or "").strip()
        if content:
            messages.append({"role": "ai", "content": content})
        files = data.get("files")
        if isinstance(files, list):
            _append_history_files(artifacts, files)
    return {
        "messages": messages,
        "artifacts": artifacts,
        "raw_stream": {"stream_path": str(stream_path)},
    }


def _parse_stream_event(text: str) -> Dict[str, Any]:
    """解析单条 SSE JSON 数据。"""
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _stream_raw_payload(event: Dict[str, Any]) -> Dict[str, Any]:
    """提取 SSE 事件中的上游 raw payload。"""
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return {}
    raw = payload.get("raw")
    return raw if isinstance(raw, dict) else {}


def detect_content_hub_upstream_error(body: Dict[str, Any]) -> Dict[str, str]:
    """识别内容中台外层完成但上游 Agent 内层失败的情况。"""
    for frame in content_hub_frames(body):
        message_type = str(frame.get("message_type") or "")
        payload = frame.get("payload") if isinstance(frame.get("payload"), dict) else {}
        raw = frame_raw(frame)
        raw_text = json.dumps(raw or payload or frame, ensure_ascii=False)
        if message_type == "TASK_FAILED" or str(raw.get("status") or "") == "ERROR" or "graph stream error" in raw_text:
            return {
                "message": _upstream_error_message(frame, raw_text),
                "failed_step": _content_hub_failed_step(body),
            }
    return {}


def content_hub_task_from_create_response(body: Dict[str, Any]) -> Dict[str, Any]:
    """从创建任务响应中提取内容中台 task 上下文。"""
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    task_id = _first_non_empty(body.get("task_id"), body.get("taskId"), data.get("task_id"), data.get("taskId"))
    session_id = _first_non_empty(
        body.get("remote_agent_task_id"),
        body.get("session_id"),
        data.get("remote_agent_task_id"),
        data.get("session_id"),
    )
    if not task_id:
        return {}
    return {
        "task_id": task_id,
        "remote_agent_task_id": session_id,
        "source": "content_hub_create_agent_task",
    }


def content_hub_frames(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    """展开内容中台 history 中的 frames。"""
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    turns = data.get("turns") if isinstance(data.get("turns"), list) else []
    frames: List[Dict[str, Any]] = []
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        for frame in turn.get("frames") or []:
            if isinstance(frame, dict):
                frames.append(frame)
    return frames


def frame_raw(frame: Dict[str, Any]) -> Dict[str, Any]:
    """提取 frame 中的上游 raw payload。"""
    payload = frame.get("payload") if isinstance(frame.get("payload"), dict) else {}
    raw = payload.get("raw") if isinstance(payload.get("raw"), dict) else {}
    return raw if isinstance(raw, dict) else {}


def _artifact_keys(group: str, artifact: Dict[str, Any]) -> List[Dict[str, Any]]:
    """提取单个 artifact 的 OSS key。"""
    keys: List[str] = []
    if artifact.get("oss_key"):
        keys.append(str(artifact["oss_key"]))
    keys.extend([str(item) for item in artifact.get("oss_keys") or []])
    return [{"group": group, "artifact": artifact, "file_key": key} for key in keys]


def _append_history_files(artifacts: Dict[str, List[Dict[str, Any]]], files: List[Any]) -> None:
    """把中台文件事件追加到 artifacts 分组。"""
    for file_item in files:
        if not isinstance(file_item, dict):
            continue
        file_key = _first_non_empty(file_item.get("oss_key"), file_item.get("file_key"))
        oss_keys = [str(item) for item in file_item.get("oss_keys") or [] if str(item).strip()]
        if not file_key and not oss_keys:
            continue
        group = _content_hub_file_group(file_item, file_key or (oss_keys[0] if oss_keys else ""))
        artifact = {**file_item}
        if file_key:
            artifact["oss_key"] = file_key
        if oss_keys:
            artifact["oss_keys"] = oss_keys
        artifacts.setdefault(group, []).append(artifact)


def _content_hub_file_group(file_item: Dict[str, Any], file_key: str) -> str:
    """按文件元信息判断产物所属节点。"""
    title = str(file_item.get("title") or "").lower()
    file_type = str(file_item.get("type") or "").lower()
    key = file_key.lower()
    if "病例" in title or "case_parse" in key:
        return "case_parse"
    if "大纲" in title or key.endswith("outline.md"):
        return "outline"
    if "正文" in title or key.endswith("story.md"):
        return "story"
    if file_type in {"json", "image_list"} or "/images/" in key or "image" in title or "图片" in title:
        return "image"
    if file_type in {"html", "png"} or key.endswith(".html") or key.endswith(".png"):
        return "html"
    return "html"


def _content_hub_failed_step(body: Dict[str, Any]) -> str:
    """根据已开始但未正常结束的节点推断失败步骤。"""
    step_titles: Dict[str, str] = {}
    latest_started = ""
    for frame in content_hub_frames(body):
        raw = frame_raw(frame)
        status = str(raw.get("status") or "")
        step_id = str(raw.get("step_id") or "")
        parent_step_id = str(raw.get("parent_step_id") or "")
        title = str(raw.get("title") or "")
        if status == "START" and step_id:
            latest_started = step_id
            step_titles[step_id] = title
        if status == "ERROR":
            return _agent_title_to_step(step_titles.get(parent_step_id) or title)
    return _agent_title_to_step(step_titles.get(latest_started, ""))


def _upstream_error_message(frame: Dict[str, Any], raw_text: str) -> str:
    """生成上游错误摘要。"""
    raw = frame_raw(frame)
    data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    error = data.get("error") if isinstance(data, dict) else ""
    title = str(raw.get("title") or "")
    step_id = str(raw.get("parent_step_id") or raw.get("step_id") or "")
    detail = str(error or raw_text[:1000])
    prefix = f"{title or step_id}: " if title or step_id else ""
    return f"内容中台上游 Agent 执行失败: {prefix}{detail}"


def _agent_title_to_step(title: str) -> str:
    """将 Agent 节点标题映射为本地失败步骤名。"""
    if "解析" in title:
        return "case_parse"
    if "大纲" in title:
        return "generate_outline"
    if "故事" in title or "正文" in title:
        return "generate_story"
    if "图片" in title or "成图" in title:
        return "generate_images"
    if "长图" in title or "html" in title.lower():
        return "generate_final_image"
    return title or "stream_agent_task"


def _first_non_empty(*values: Any) -> str:
    """返回第一个非空字符串值。"""
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""
