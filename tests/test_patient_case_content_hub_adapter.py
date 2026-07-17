"""内容中台患者故事链路执行单元测试。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest
import json

from story_med.executors.patient_story_generation_executor import PatientStoryGenerationExecutor
from story_med.executors.patient_story_generation_executor import (
    _case_generation_message,
)
from story_med.executors.content_hub_history import (
    content_hub_task_from_create_response,
    detect_content_hub_upstream_error,
    extract_stream_turn_id,
    iter_artifacts,
    is_adjustment_history_complete,
    is_generation_history_complete,
    normalize_content_hub_history,
    normalize_content_hub_stream,
)
from story_med.config.app_config import StoryMedConfig
from story_med.models.case_model import StoryCaseConfig


def test_content_hub_create_response_extracts_task_and_session() -> None:
    """验证创建任务响应能提取中台任务 ID 和患者故事 session_id。"""
    body = {
        "success": True,
        "data": {
            "task_id": "task-1",
            "remote_agent_task_id": "session-1",
            "stream_url": "/api/agent/tasks/stream",
        },
    }

    result = content_hub_task_from_create_response(body)

    assert result["task_id"] == "task-1"
    assert result["remote_agent_task_id"] == "session-1"
    assert result["source"] == "content_hub_create_agent_task"


def test_normalize_content_hub_history_maps_messages_and_artifacts() -> None:
    """验证中台 history 会转成旧审核链路使用的 messages/artifacts。"""
    body = _history_body(
        [
            _agent_frame(
                {
                    "status": "PROCESSING",
                    "data": {"type": "message", "content": "病例解析完成:\n# 病例"},
                }
            ),
            _agent_frame(
                {
                    "status": "PROCESSING",
                    "data": {
                        "type": "file",
                        "files": [
                            {
                                "type": "markdown",
                                "title": "故事大纲",
                                "oss_key": "story-med/patient_case/session-1/outline.md",
                            },
                            {
                                "type": "html",
                                "title": "最终长图",
                                "oss_key": "story-med/patient_case/session-1/index.html",
                            },
                        ],
                    },
                }
            ),
        ]
    )

    result = normalize_content_hub_history(body)

    assert "病例解析完成" in result["messages"][0]["content"]
    assert result["artifacts"]["outline"][0]["oss_key"].endswith("outline.md")
    assert result["artifacts"]["html"][0]["oss_key"].endswith("index.html")


def test_normalize_content_hub_stream_maps_files_to_history_structure(tmp_path: Path) -> None:
    """验证 SSE 文件事件与 history 使用同一 artifacts 结构。"""
    stream_path = tmp_path / "stream.txt"
    event = {
        "payload": {
            "raw": {
                "data": {
                    "type": "file",
                    "files": [
                        {
                            "type": "html",
                            "title": "最终页面",
                            "oss_key": "story-med/patient_case/session-1/index.html",
                        },
                        {
                            "type": "png",
                            "title": "页面截图",
                            "oss_key": "story-med/patient_case/session-1/index.png",
                        },
                    ],
                }
            }
        }
    }
    stream_path.write_text(f"data:{json.dumps(event, ensure_ascii=False)}\n", encoding="utf-8")

    result = normalize_content_hub_stream(stream_path)

    assert result["artifacts"]["html"][0]["oss_key"].endswith("index.html")
    assert [item["file_key"] for item in iter_artifacts(result)] == [
        "story-med/patient_case/session-1/index.html",
        "story-med/patient_case/session-1/index.png",
    ]


def test_extract_stream_turn_id_reads_user_request_turn_id(tmp_path: Path) -> None:
    """验证从 SSE USER_REQUEST 读取内容中台远程 turn_id。"""
    stream_path = tmp_path / "stream.txt"
    event = {"message_type": "USER_REQUEST", "turn_id": "remote-turn-2"}
    stream_path.write_text(
        f"data:{json.dumps(event, ensure_ascii=False)}\n", encoding="utf-8"
    )

    assert extract_stream_turn_id(stream_path) == "remote-turn-2"


def test_detect_content_hub_upstream_error_when_raw_status_error() -> None:
    """验证上游 raw ERROR 会被识别为执行失败。"""
    body = _history_body(
        [
            _agent_frame({"status": "START", "title": "生成故事正文", "step_id": "story-node"}),
            _agent_frame(
                {
                    "status": "ERROR",
                    "step_id": "child-node",
                    "parent_step_id": "story-node",
                    "data": {"error": "InternalError.Algo.InvalidParameter"},
                }
            ),
        ]
    )

    result = detect_content_hub_upstream_error(body)

    assert result["failed_step"] == "generate_story"
    assert "InternalError.Algo.InvalidParameter" in result["message"]


def test_upload_presign_body_uses_filename_key(tmp_path: Path, monkeypatch: Any) -> None:
    """验证上传预签名接口使用中台要求的 filename 字段。"""
    from story_med.clients.agent_api.agent_task_client import create_story_med_upload_url
    from story_med.config.app_config import StoryMedConfig

    captured: Dict[str, Any] = {}

    class FakeResponse:
        """模拟 requests 响应。"""

        status_code = 200
        text = ""

        def json(self) -> Dict[str, Any]:
            """返回预签名响应。"""
            return {"success": True, "data": {"upload_url": "https://upload", "file_key": "key"}}

    class FakeSession:
        """模拟 HTTP 会话。"""

        def post(self, url: str, **kwargs: Any) -> FakeResponse:
            """捕获 POST 请求。"""
            captured["url"] = url
            captured["json"] = kwargs.get("json")
            return FakeResponse()

    config = StoryMedConfig(
        base_url="https://old.example",
        timeout_seconds=60,
        verify_ssl=True,
        accept="application/json",
        origin="",
        referer="",
        adjust_base_url="https://hub.example",
        adjust_auth_token="token",
        adjust_origin="",
        adjust_referer="",
        adjust_accept="text/event-stream",
        adjust_auth_username="admin",
        adjust_auth_password="password",
        active_env="test",
        result_file=str(tmp_path / "result.json"),
    )

    result = create_story_med_upload_url(FakeSession(), config, "病例基础信息.png")  # type: ignore[arg-type]

    assert captured["json"] == {"filename": "病例基础信息.png"}
    assert result["file_key"] == "key"


def test_login_content_hub_updates_runtime_token(tmp_path: Path) -> None:
    """验证中台登录会刷新运行期 Authorization token。"""
    from story_med.clients.agent_api.agent_task_client import login_content_hub
    from story_med.config.app_config import StoryMedConfig

    captured: Dict[str, Any] = {}

    class FakeResponse:
        """模拟登录响应。"""

        status_code = 200
        text = ""

        def json(self) -> Dict[str, Any]:
            """返回 token 响应。"""
            return {"success": True, "data": {"token_type": "Bearer", "access_token": "token-new"}}

    class FakeSession:
        """模拟 HTTP 会话。"""

        def post(self, url: str, **kwargs: Any) -> FakeResponse:
            """捕获登录请求。"""
            captured["url"] = url
            captured["json"] = kwargs.get("json")
            return FakeResponse()

    config = StoryMedConfig(
        base_url="https://old.example",
        timeout_seconds=60,
        verify_ssl=True,
        accept="application/json",
        origin="",
        referer="",
        adjust_base_url="https://hub.example",
        adjust_auth_token="expired",
        adjust_origin="",
        adjust_referer="",
        adjust_accept="text/event-stream",
        adjust_auth_username="admin",
        adjust_auth_password="password",
        active_env="test",
        result_file=str(tmp_path / "result.json"),
    )

    login_content_hub(FakeSession(), config)  # type: ignore[arg-type]

    assert captured["url"] == "https://hub.example/api/auth/login"
    assert captured["json"] == {"username": "admin", "password": "password"}
    assert config.adjust_auth_token == "Bearer token-new"


def test_case_generation_message_uses_creative_brief() -> None:
    """验证初始生成 message 读取 clinical_case.yaml 中的 creative_brief。"""
    case = StoryCaseConfig(
        case_id="SM_TEST",
        description="单测",
        creative_brief="  温暖克制，保留病例事实  ",
    )

    assert _case_generation_message(case) == "温暖克制，保留病例事实"


def test_is_history_complete_returns_true_when_core_artifacts_all_exist() -> None:
    """验证 history 包含核心产物时判定为完整。"""
    history = {
        "artifacts": {
            "outline": [{"oss_key": "outline.md"}],
            "story": [{"oss_key": "story.md"}],
            "image": [{"oss_key": "image_design.json"}],
            "html": [{"oss_key": "index.html"}],
        }
    }

    assert is_generation_history_complete(history) is True


def test_is_history_complete_returns_false_when_html_missing() -> None:
    """验证 history 缺少最终长图产物时不判定完整。"""
    history = {
        "artifacts": {
            "outline": [{"oss_key": "outline.md"}],
            "story": [{"oss_key": "story.md"}],
            "image": [{"oss_key": "image_design.json"}],
            "html": [],
        }
    }

    assert is_generation_history_complete(history) is False


def test_adjustment_history_ignores_previous_turn_html_when_current_turn_running() -> None:
    """验证旧 turn 的 HTML 不能把当前 RUNNING turn 判定为完成。"""
    history = {
        "raw_history": {
            "data": {
                "turns": [
                    {
                        "payload": {"message": "第一次修改"},
                        "status": "COMPLETED",
                        "frames": [_html_frame("old/index.html")],
                    },
                    {
                        "payload": {"message": "第二次修改"},
                        "status": "RUNNING",
                        "frames": [],
                    },
                ]
            }
        },
        "artifacts": {"html": [{"oss_key": "old/index.html"}]},
    }

    history["raw_history"]["data"]["turns"][1]["turn_id"] = "remote-turn-2"

    assert is_adjustment_history_complete(history, "remote-turn-2") is False


def test_adjustment_history_uses_current_turn_status_and_artifacts() -> None:
    """验证只有当前远程 turn 完成且自身有 HTML 才算完成。"""
    history = {
        "raw_history": {
            "data": {
                "turns": [
                    {
                        "turn_id": "remote-turn-1",
                        "status": "COMPLETED",
                        "frames": [_html_frame("old/index.html")],
                    },
                    {
                        "turn_id": "remote-turn-2",
                        "status": "COMPLETED",
                        "frames": [_html_frame("current/index.html")],
                    },
                ]
            }
        }
    }

    assert is_adjustment_history_complete(history, "remote-turn-2") is True


def test_history_error_ignores_previous_turn() -> None:
    """验证旧 turn 的失败事件不会污染当前 turn。"""
    body = {
        "data": {
            "turns": [
                {
                    "turn_id": "remote-turn-1",
                    "status": "FAILED",
                    "frames": [_agent_frame({"status": "ERROR", "data": {"error": "old"}})],
                },
                {
                    "turn_id": "remote-turn-2",
                    "status": "RUNNING",
                    "frames": [],
                },
            ]
        }
    }

    assert detect_content_hub_upstream_error(body, "remote-turn-2") == {}


def test_history_error_detects_current_turn() -> None:
    """验证当前 turn 的失败事件能被识别。"""
    body = {
        "data": {
            "turns": [
                {
                    "turn_id": "remote-turn-2",
                    "status": "FAILED",
                    "frames": [
                        _agent_frame(
                            {"status": "ERROR", "data": {"error": "current"}}
                        )
                    ],
                }
            ]
        }
    }

    assert detect_content_hub_upstream_error(body, "remote-turn-2")["message"]


def _html_frame(oss_key: str) -> Dict[str, Any]:
    """构造包含 HTML 文件的 history frame。"""
    return {
        "payload": {
            "raw": {
                "data": {
                    "files": [{"type": "html", "oss_key": oss_key}]
                }
            }
        }
    }


def test_wait_for_terminal_history_retries_until_complete(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """验证 stream 断开后会轮询 history 直到产物完整。"""
    adapter = PatientStoryGenerationExecutor(_build_config(tmp_path), session=object())
    pending_body = _history_body(
        [
            _agent_frame(
                {
                    "status": "PROCESSING",
                    "data": {
                        "type": "file",
                        "files": [{"type": "markdown", "title": "故事大纲", "oss_key": "story-med/patient_case/session-1/outline.md"}],
                    },
                }
            )
        ]
    )
    complete_body = _history_body(
        [
            _agent_frame(
                {
                    "status": "PROCESSING",
                    "data": {
                        "type": "file",
                        "files": [
                            {"type": "markdown", "title": "故事大纲", "oss_key": "story-med/patient_case/session-1/outline.md"},
                            {"type": "markdown", "title": "故事正文", "oss_key": "story-med/patient_case/session-1/story.md"},
                            {"type": "json", "title": "配图设计", "oss_key": "story-med/patient_case/session-1/image_design.json"},
                            {"type": "html", "title": "最终页面", "oss_key": "story-med/patient_case/session-1/index.html"},
                        ],
                    },
                }
            )
        ]
    )
    responses = [_fake_story_response(pending_body), _fake_story_response(complete_body)]
    calls: list[str] = []

    monkeypatch.setattr(
        "story_med.executors.content_hub_runtime.get_agent_task_history",
        lambda session, config, task_id: calls.append(task_id) or responses.pop(0),
    )
    monkeypatch.setattr("story_med.executors.content_hub_runtime.sleep", lambda _seconds: None)

    result = adapter._wait_for_terminal_history("task-1")

    assert result.body == complete_body
    assert calls == ["task-1", "task-1"]


def _history_body(frames: list[Dict[str, Any]]) -> Dict[str, Any]:
    """构建中台 history 响应体。"""
    return {"success": True, "data": {"turns": [{"frames": frames}]}}


def _agent_frame(raw: Dict[str, Any]) -> Dict[str, Any]:
    """构建中台 AGENT_EVENT frame。"""
    return {"message_type": "AGENT_EVENT", "payload": {"raw": raw}}


def _build_config(tmp_path: Path) -> StoryMedConfig:
    """构建适配器单测配置。"""
    return StoryMedConfig(
        base_url="https://old.example",
        timeout_seconds=1,
        verify_ssl=True,
        accept="application/json",
        origin="",
        referer="",
        adjust_base_url="https://hub.example",
        adjust_auth_token="token",
        adjust_origin="",
        adjust_referer="",
        adjust_accept="text/event-stream",
        adjust_auth_username="admin",
        adjust_auth_password="password",
        active_env="test",
        result_file=str(tmp_path / "result.json"),
    )


def _fake_story_response(body: Dict[str, Any]) -> Any:
    """构建最小化 StoryApiResponse 替身。"""
    class _Resp:
        status_code = 200

        def __init__(self, payload: Dict[str, Any]) -> None:
            self.body = payload
            self.data = payload

    return _Resp(body)
