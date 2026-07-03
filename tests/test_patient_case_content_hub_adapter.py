"""内容中台患者故事链路适配单元测试。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from story_med.adapters.patient_case_image_agent import (
    _content_hub_task_from_create_response,
    _case_generation_message,
    detect_content_hub_upstream_error,
    normalize_content_hub_history,
)
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

    result = _content_hub_task_from_create_response(body)

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
    from story_med.clients.agent_task_client import create_story_med_upload_url
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
        user_agent="pytest",
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
    from story_med.clients.agent_task_client import login_content_hub
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
        user_agent="pytest",
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


def _history_body(frames: list[Dict[str, Any]]) -> Dict[str, Any]:
    """构建中台 history 响应体。"""
    return {"success": True, "data": {"turns": [{"frames": frames}]}}


def _agent_frame(raw: Dict[str, Any]) -> Dict[str, Any]:
    """构建中台 AGENT_EVENT frame。"""
    return {"message_type": "AGENT_EVENT", "payload": {"raw": raw}}
