"""内容中台执行期公共能力。"""

from __future__ import annotations

from time import perf_counter, sleep
from typing import Any, Callable, Dict

from requests import Session

from story_med.clients.agent_api.agent_task_client import get_agent_task_history
from story_med.clients.base.http_client import StoryApiResponse
from story_med.config.app_config import StoryMedConfig

HISTORY_POLL_INTERVAL_SECONDS = 10


def wait_for_terminal_history(
    session: Session,
    config: StoryMedConfig,
    task_id: str,
    is_complete: Callable[[Dict[str, Any]], bool],
    has_error: Callable[[Dict[str, Any]], bool],
    deadline: float,
    poll_interval_seconds: int = HISTORY_POLL_INTERVAL_SECONDS,
) -> StoryApiResponse:
    """轮询 history，直到任务完成、失败或超时。"""
    last_response: StoryApiResponse | None = None
    while perf_counter() < deadline:
        response = get_agent_task_history(session, config, task_id)
        last_response = response
        body = response.body if isinstance(response.body, dict) else {}
        if has_error(body) or is_complete(body):
            return response
        remaining = deadline - perf_counter()
        if remaining <= 0:
            break
        sleep(min(poll_interval_seconds, remaining))
    raise TimeoutError(f"Agent 任务超过 30 分钟总时限: task_id={task_id}")
