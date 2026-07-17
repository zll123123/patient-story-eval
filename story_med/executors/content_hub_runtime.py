"""内容中台执行期公共能力。"""

from __future__ import annotations

from time import perf_counter, sleep
from typing import Any, Callable, Dict

from requests import Session

from story_med.clients.agent_api.agent_task_client import get_agent_task_history
from story_med.clients.base.http_client import StoryApiResponse
from story_med.config.app_config import StoryMedConfig

HISTORY_POLL_TIMEOUT_SECONDS = 600
HISTORY_POLL_INTERVAL_SECONDS = 10


def wait_for_terminal_history(
    session: Session,
    config: StoryMedConfig,
    task_id: str,
    is_complete: Callable[[Dict[str, Any]], bool],
    has_error: Callable[[Dict[str, Any]], bool],
    timeout_seconds: int = HISTORY_POLL_TIMEOUT_SECONDS,
    poll_interval_seconds: int = HISTORY_POLL_INTERVAL_SECONDS,
) -> StoryApiResponse:
    """轮询 history，直到任务完成、失败或超时。"""
    deadline = perf_counter() + timeout_seconds
    last_response: StoryApiResponse | None = None
    while perf_counter() < deadline:
        response = get_agent_task_history(session, config, task_id)
        last_response = response
        body = response.body if isinstance(response.body, dict) else {}
        if has_error(body) or is_complete(body):
            return response
        sleep(poll_interval_seconds)
    if last_response is not None:
        return last_response
    raise RuntimeError(f"内容中台 history 轮询超时且未返回有效响应: task_id={task_id}")
