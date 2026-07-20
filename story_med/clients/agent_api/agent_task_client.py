"""内容中台 Agent 任务接口客户端。"""

from __future__ import annotations

import json
import requests
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, List

from requests import Response, Session

from story_med.clients.base.http_client import StoryApiResponse
from story_med.config.app_config import StoryMedConfig

AGENT_TASK_STREAM_PATH = "/api/agent/tasks/stream"
AGENT_TASKS_PATH = "/api/agent/tasks"
AGENT_TASK_HISTORY_PATH = "/api/agent/tasks/history"
AUTH_LOGIN_PATH = "/api/auth/login"
STORY_MED_PRESIGN_UPLOAD_PATH = "/api/agent/tasks/story-med/presign-upload"
STORY_MED_PRESIGN_DOWNLOAD_PATH = "/api/agent/tasks/story-med/presign-download"
DEFAULT_AGENT_TYPE = "patient-case"
STREAM_TASK_TIMEOUT_SECONDS = 1800


def login_content_hub(session: Session, config: StoryMedConfig) -> Dict[str, Any]:
    """使用用户名密码登录内容中台并保存运行期访问令牌。

    Args:
        session: HTTP 会话。
        config: 运行配置。

    Returns:
        登录响应 data。
    """
    username = config.adjust_auth_username.strip()
    password = config.adjust_auth_password.strip()
    if not username or not password:
        raise RuntimeError("内容中台登录缺少用户名或密码配置")
    response = session.post(
        f"{config.adjust_base_url}{AUTH_LOGIN_PATH}",
        json={"username": username, "password": password},
        headers=_login_headers(config),
        timeout=config.timeout_seconds,
        verify=config.verify_ssl,
    )
    body = _json_body(response, AUTH_LOGIN_PATH)
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    access_token = str(data.get("access_token") or "").strip()
    token_type = str(data.get("token_type") or "Bearer").strip() or "Bearer"
    if not access_token:
        raise RuntimeError(f"内容中台登录响应缺少 access_token: {_mask_login_body(body)}")
    config.adjust_auth_token = f"{token_type} {access_token}"
    return data


def ensure_content_hub_auth(session: Session, config: StoryMedConfig) -> None:
    """确保当前运行拥有可用的内容中台 token。"""
    login_content_hub(session, config)


def create_story_med_upload_url(
    session: Session, config: StoryMedConfig, filename: str
) -> Dict[str, Any]:
    """获取 story-med 文件上传预签名地址。

    Args:
        session: HTTP 会话。
        config: 运行配置。
        filename: 文件名。

    Returns:
        上传地址响应 data。
    """
    response = _post_json_with_retry(
        session,
        config,
        STORY_MED_PRESIGN_UPLOAD_PATH,
        {"filename": filename},
    )
    body = _json_body(response, STORY_MED_PRESIGN_UPLOAD_PATH)
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    if not data:
        raise RuntimeError(f"上传预签名响应缺少 data: {body}")
    return data


def upload_story_med_file(
    upload_url: str, file_path: Path, content_type: str, config: StoryMedConfig
) -> Dict[str, Any]:
    """上传文件到中台返回的 OSS 预签名地址。

    Args:
        upload_url: 上传预签名地址。
        file_path: 本地文件路径。
        content_type: 文件 MIME 类型。
        config: 运行配置。

    Returns:
        上传结果摘要。
    """
    with file_path.open("rb") as file_obj:
        response = requests.put(
            upload_url,
            data=file_obj,
            headers={"Content-Type": content_type},
            timeout=config.timeout_seconds,
            verify=config.verify_ssl,
        )
    if response.status_code >= 400:
        raise RuntimeError(
            f"OSS 上传失败: {file_path} {response.status_code} {response.text[:500]}"
        )
    return {"status_code": response.status_code, "size_bytes": file_path.stat().st_size}


def create_agent_task(
    session: Session,
    config: StoryMedConfig,
    agent_type: str,
    form: Dict[str, Any],
) -> StoryApiResponse:
    """创建内容中台 Agent 任务。

    Args:
        session: HTTP 会话。
        config: 运行配置。
        agent_type: Agent 类型。
        form: 业务表单。

    Returns:
        创建任务响应。
    """
    payload = {"agent_type": agent_type or DEFAULT_AGENT_TYPE, "form": form}
    response = _post_json_with_retry(session, config, AGENT_TASKS_PATH, payload)
    body = _json_body(response, AGENT_TASKS_PATH)
    return StoryApiResponse(status_code=response.status_code, body=body, data=body)


def stream_agent_task(
    session: Session,
    config: StoryMedConfig,
    payload: Dict[str, Any],
    output_path: Path,
    deadline: float,
) -> StoryApiResponse:
    """执行内容中台 Agent SSE 任务并保存原始流。

    Args:
        session: HTTP 会话。
        config: 运行配置。
        payload: SSE 请求体。
        output_path: 原始流保存路径。

    Returns:
        流式接口响应摘要。
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _raise_if_deadline_exceeded(deadline)
    response = _post_stream_with_retry(
        session,
        config,
        AGENT_TASK_STREAM_PATH,
        payload,
        deadline,
    )
    _raise_for_stream_error(response)
    event_count = write_stream_chunks(
        response.iter_content(chunk_size=1024, decode_unicode=True),
        output_path,
        deadline=deadline,
    )
    event_log_path = stream_event_log_path(output_path)
    events = _load_stream_events(event_log_path)
    agent_steps = _extract_step_timings(events)
    body = {
        "status_code": response.status_code,
        "stream_output_path": str(output_path),
        "stream_event_log_path": str(event_log_path),
        "event_count": event_count,
        "agent_node_timings": {
            "steps": agent_steps,
            "current_node": _current_node(agent_steps),
        },
    }
    return StoryApiResponse(status_code=response.status_code, body=body, data=body)


def get_agent_task_history(
    session: Session, config: StoryMedConfig, task_id: str
) -> StoryApiResponse:
    """查询内容中台 Agent 任务历史。

    Args:
        session: HTTP 会话。
        config: 运行配置。
        task_id: 内容中台任务 ID。

    Returns:
        任务历史响应。
    """
    response = _get_json_with_retry(
        session,
        config,
        AGENT_TASK_HISTORY_PATH,
        {"task_id": task_id},
    )
    body = _json_body(response, AGENT_TASK_HISTORY_PATH)
    return StoryApiResponse(status_code=response.status_code, body=body, data=body)


def create_story_med_download_url(
    session: Session, config: StoryMedConfig, file_key: str
) -> Dict[str, Any]:
    """获取 story-med 文件下载预签名地址。

    Args:
        session: HTTP 会话。
        config: 运行配置。
        file_key: OSS 文件 key。

    Returns:
        下载地址响应 data。
    """
    response = _post_json_with_retry(
        session,
        config,
        STORY_MED_PRESIGN_DOWNLOAD_PATH,
        {"file_key": file_key},
    )
    body = _json_body(response, STORY_MED_PRESIGN_DOWNLOAD_PATH)
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    if not data:
        raise RuntimeError(f"下载预签名响应缺少 data: {body}")
    return data


def download_story_med_file(
    download_url: str, output_path: Path, config: StoryMedConfig
) -> Dict[str, Any]:
    """下载 story-med 预签名文件。

    Args:
        download_url: 下载预签名地址。
        output_path: 本地保存路径。
        config: 运行配置。

    Returns:
        下载结果摘要。
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(
        download_url, timeout=config.timeout_seconds, verify=config.verify_ssl
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"OSS 下载失败: {output_path} {response.status_code} {response.text[:500]}"
        )
    output_path.write_bytes(response.content)
    return {
        "local_path": str(output_path),
        "content_type": response.headers.get("Content-Type", ""),
        "size_bytes": len(response.content),
    }


def stream_agent_adjustment_task(
    session: Session,
    config: StoryMedConfig,
    task_id: str,
    agent_type: str,
    session_id: str,
    message: str,
    output_path: Path,
    deadline: float,
) -> StoryApiResponse:
    """调用已生成患者故事调整 SSE 接口并保存原始流。

    Args:
        session: HTTP 会话。
        config: 运行配置。
        task_id: 服务端任务 ID。
        agent_type: Agent 类型。
        session_id: 已生成患者故事的会话 ID。
        message: 自然语言调整要求。
        output_path: SSE 原始流保存路径。

    Returns:
        接口响应摘要。
    """
    payload = build_adjustment_payload(task_id, agent_type, session_id, message)
    return stream_agent_task(session, config, payload, output_path, deadline)


def build_adjustment_payload(
    task_id: str, agent_type: str, session_id: str, message: str
) -> Dict[str, Any]:
    """构建调整接口请求体。

    Args:
        task_id: 服务端任务 ID。
        agent_type: Agent 类型。
        session_id: 已生成患者故事的会话 ID。
        message: 自然语言调整要求。

    Returns:
        JSON 请求体。
    """
    return {
        "task_id": task_id,
        "agent_type": agent_type or DEFAULT_AGENT_TYPE,
        "form": {
            "session_id": session_id,
            "message": message,
        },
    }


def build_adjustment_headers(config: StoryMedConfig) -> Dict[str, str]:
    """构建调整接口请求头。

    Args:
        config: 运行配置。

    Returns:
        HTTP 请求头。
    """
    headers = {
        "Accept": config.adjust_accept,
        "Content-Type": "application/json;charset=UTF-8",
    }
    if config.adjust_origin.strip():
        headers["Origin"] = config.adjust_origin.strip()
    if config.adjust_referer.strip():
        headers["Referer"] = config.adjust_referer.strip()
    auth_token = _normalize_auth_token(config.adjust_auth_token)
    if auth_token:
        headers["Authorization"] = auth_token
    return headers


def find_agent_task_by_remote_task_id(
    session: Session,
    config: StoryMedConfig,
    remote_agent_task_id: str,
) -> Dict[str, Any]:
    """按远端患者故事 session_id 反查内容中台任务。

    Args:
        session: HTTP 会话。
        config: 运行配置。
        remote_agent_task_id: 患者故事服务 session_id。

    Returns:
        匹配到的内容中台任务记录，未找到返回空字典。
    """
    target_id = remote_agent_task_id.strip()
    if not target_id:
        return {}
    response = _get_json_with_retry(session, config, AGENT_TASKS_PATH, {})
    if response.status_code >= 400:
        return {}
    body = _safe_json_body(response)
    for item in body.get("data") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("remote_agent_task_id") or "") == target_id:
            return item
    return {}


def _json_task_headers(config: StoryMedConfig) -> Dict[str, str]:
    """构建任务查询 JSON 请求头。"""
    headers = build_adjustment_headers(config)
    headers["Accept"] = "application/json"
    return headers


def _login_headers(config: StoryMedConfig) -> Dict[str, str]:
    """构建登录请求头。"""
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
    }
    if config.adjust_origin.strip():
        headers["Origin"] = config.adjust_origin.strip()
    if config.adjust_referer.strip():
        headers["Referer"] = config.adjust_referer.strip()
    return headers


def _post_json_with_retry(
    session: Session,
    config: StoryMedConfig,
    path: str,
    payload: Dict[str, Any],
) -> Response:
    """发送中台 JSON POST，未授权时重新登录并重试一次。"""
    response = session.post(
        f"{config.adjust_base_url}{path}",
        json=payload,
        headers=_json_task_headers(config),
        timeout=config.timeout_seconds,
        verify=config.verify_ssl,
    )
    if _is_unauthorized_response(response):
        login_content_hub(session, config)
        response = session.post(
            f"{config.adjust_base_url}{path}",
            json=payload,
            headers=_json_task_headers(config),
            timeout=config.timeout_seconds,
            verify=config.verify_ssl,
        )
    return response


def _post_stream_with_retry(
    session: Session,
    config: StoryMedConfig,
    path: str,
    payload: Dict[str, Any],
    deadline: float,
) -> Response:
    """发送中台 SSE POST，未授权时重新登录并重试一次。"""
    response = session.post(
        f"{config.adjust_base_url}{path}",
        json=payload,
        headers=build_adjustment_headers(config),
        stream=True,
        timeout=_stream_request_timeout(deadline),
        verify=config.verify_ssl,
    )
    if response.status_code == 401:
        response.close()
        login_content_hub(session, config)
        _raise_if_deadline_exceeded(deadline)
        response = session.post(
            f"{config.adjust_base_url}{path}",
            json=payload,
            headers=build_adjustment_headers(config),
            stream=True,
            timeout=_stream_request_timeout(deadline),
            verify=config.verify_ssl,
        )
    return response


def _stream_request_timeout(deadline: float) -> tuple[float, float]:
    """将任务截止时间转换为 requests 的连接和读取超时。"""
    remaining = deadline - perf_counter()
    if remaining <= 0:
        raise TimeoutError("Agent 任务超过 30 分钟总时限")
    return min(30.0, remaining), remaining


def _raise_if_deadline_exceeded(deadline: float) -> None:
    """在发起或继续中台请求前检查任务总截止时间。"""
    if deadline <= perf_counter():
        raise TimeoutError("Agent 任务超过 30 分钟总时限")


def _get_json_with_retry(
    session: Session,
    config: StoryMedConfig,
    path: str,
    params: Dict[str, Any],
) -> Response:
    """发送中台 JSON GET，未授权时重新登录并重试一次。"""
    response = session.get(
        f"{config.adjust_base_url}{path}",
        params=params,
        headers=_json_task_headers(config),
        timeout=config.timeout_seconds,
        verify=config.verify_ssl,
    )
    if _is_unauthorized_response(response):
        login_content_hub(session, config)
        response = session.get(
            f"{config.adjust_base_url}{path}",
            params=params,
            headers=_json_task_headers(config),
            timeout=config.timeout_seconds,
            verify=config.verify_ssl,
        )
    return response


def _is_unauthorized_response(response: Response) -> bool:
    """判断是否为 token 失效响应。"""
    if response.status_code == 401:
        return True
    body = _safe_json_body(response)
    return str(body.get("code") or "") in {"PCH-401-03", "PCH-401-01"}


def _mask_login_body(body: Dict[str, Any]) -> Dict[str, Any]:
    """屏蔽登录响应中的敏感字段。"""
    masked = dict(body)
    data = masked.get("data")
    if isinstance(data, dict):
        masked["data"] = {
            key: "***MASKED***" if "token" in key.lower() else value
            for key, value in data.items()
        }
    return masked


def _normalize_auth_token(raw_token: str) -> str:
    """标准化 Authorization 请求头值。"""
    token = raw_token.strip()
    if not token:
        return ""
    if token.lower().startswith("bearer "):
        return token
    return f"Bearer {token}"


def _safe_json_body(response: Response) -> Dict[str, Any]:
    """安全解析 JSON 响应体。"""
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _json_body(response: Response, path: str) -> Dict[str, Any]:
    """解析 JSON 响应并处理错误状态。"""
    body = _safe_json_body(response)
    if response.status_code >= 400:
        raise RuntimeError(
            f"{response.status_code} {path}: {body or response.text[:500]}"
        )
    if not body:
        raise RuntimeError(f"接口返回非 JSON 对象: {path}")
    return body


def write_stream_chunks(
    chunks: Iterable[str | bytes],
    output_path: Path,
    deadline: float,
) -> int:
    """写入 SSE 分块内容。

    Args:
        chunks: SSE 分块迭代器。
        output_path: 原始流输出路径。
        deadline: 当前任务的绝对截止时间。

    Returns:
        识别到的 data 事件数量。
    """
    event_count = 0
    event_log_path = stream_event_log_path(output_path)
    line_buffer = ""
    with output_path.open("w", encoding="utf-8") as file_obj, event_log_path.open(
        "w", encoding="utf-8"
    ) as event_obj:
        for chunk in chunks:
            if perf_counter() >= deadline:
                raise TimeoutError(
                    "Agent 任务超过 30 分钟总时限"
                )
            if not chunk:
                continue
            text = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
            event_count += text.count("data:")
            file_obj.write(text)
            file_obj.flush()
            line_buffer = _write_received_events(line_buffer + text, event_obj)
        if line_buffer.strip():
            _write_event_line(line_buffer.strip(), event_obj)
    return event_count


def stream_event_log_path(output_path: Path) -> Path:
    """构建带时间戳事件日志路径。"""
    return output_path.with_name(f"{output_path.stem}_events.jsonl")


def _write_received_events(buffer: str, event_obj: Any) -> str:
    """写入已完整接收的 SSE data 行。"""
    lines = buffer.splitlines(keepends=True)
    if lines and not lines[-1].endswith(("\n", "\r")):
        remainder = lines.pop()
    else:
        remainder = ""
    for raw_line in lines:
        _write_event_line(raw_line.strip(), event_obj)
    return remainder


def _write_event_line(line: str, event_obj: Any) -> None:
    """写入单条带接收时间的 SSE data 事件。"""
    if not line.startswith("data:"):
        return
    event_obj.write(
        json.dumps(
            {"received_at": _now_iso(), "payload": _safe_json(line[5:].strip())},
            ensure_ascii=False,
        )
        + "\n"
    )
    event_obj.flush()


def _load_stream_events(event_log_path: Path) -> List[Dict[str, Any]]:
    """读取 SSE 事件日志。"""
    events: List[Dict[str, Any]] = []
    if not event_log_path.exists():
        return events
    for line in event_log_path.read_text(encoding="utf-8").splitlines():
        data = _safe_json(line)
        if isinstance(data, dict):
            events.append(data)
    return events


def _extract_step_timings(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """从内容中台事件中提取上游 Agent 节点耗时。"""
    steps: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    last_time = ""
    for event in events:
        received_at = str(event.get("received_at") or "")
        last_time = received_at or last_time
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        raw = _raw_payload(payload)
        if not raw:
            continue
        status = str(raw.get("status") or "")
        step_id = str(raw.get("step_id") or "")
        parent_step_id = str(raw.get("parent_step_id") or "")
        title = str(raw.get("title") or "")
        if status == "START" and step_id:
            steps[step_id] = {
                "step_id": step_id,
                "title": title or step_id,
                "status": "running",
                "started_at": received_at,
                "finished_at": "",
                "duration_seconds": 0.0,
            }
            order.append(step_id)
        elif status == "END" and step_id:
            target_id = step_id if step_id in steps else parent_step_id
            if target_id in steps:
                steps[target_id]["status"] = "done"
                steps[target_id]["finished_at"] = received_at
        elif status == "ERROR" and parent_step_id in steps:
            steps[parent_step_id]["status"] = "error"
            steps[parent_step_id]["finished_at"] = received_at
            data = raw.get("data")
            steps[parent_step_id]["error"] = _format_agent_error(data)
            steps[parent_step_id]["error_type"] = "UpstreamAgentError"
    _finalize_step_durations(steps, last_time)
    return [steps[step_id] for step_id in order if step_id in steps]


def _raw_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """提取内容中台事件中的上游 raw payload。"""
    raw_payload = (
        payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    )
    raw = raw_payload.get("raw") if isinstance(raw_payload, dict) else {}
    return raw if isinstance(raw, dict) else {}


def _finalize_step_durations(
    steps: Dict[str, Dict[str, Any]], fallback_end: str
) -> None:
    """补齐节点耗时。"""
    for step in steps.values():
        started_at = str(step.get("started_at") or "")
        finished_at = str(step.get("finished_at") or "")
        end_at = finished_at or fallback_end
        step["duration_seconds"] = _duration_seconds(started_at, end_at)


def _current_node(steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """提取当前运行中的节点。"""
    for step in reversed(steps):
        if step.get("status") == "running":
            return step
    return {}


def _duration_seconds(started_at: str, finished_at: str) -> float:
    """计算两个 ISO 时间之间的秒数。"""
    if not started_at or not finished_at:
        return 0.0
    try:
        start = datetime.fromisoformat(started_at)
        end = datetime.fromisoformat(finished_at)
    except ValueError:
        return 0.0
    return round((end - start).total_seconds(), 3)


def _format_agent_error(data: Any) -> str:
    """提取中台 agent 节点返回的原始错误文本。"""
    if isinstance(data, dict):
        for key in ("error", "message", "detail"):
            value = data.get(key)
            if value:
                return str(value)
        return json.dumps(data, ensure_ascii=False)
    return str(data or "未知上游错误")


def _safe_json(text: str) -> Any:
    """安全解析 JSON 字符串。"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _now_iso() -> str:
    """返回当前 UTC ISO 时间。"""
    return datetime.now(UTC).isoformat()




def _raise_for_stream_error(response: Response) -> None:
    """处理 SSE 接口错误响应。"""
    if response.status_code < 400:
        return
    raise RuntimeError(
        f"{response.status_code} {AGENT_TASK_STREAM_PATH}: {response.text[:500]}"
    )
