"""患者故事调整节点单元测试。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

from story_med.clients.agent_task_client import build_adjustment_headers, build_adjustment_payload
from story_med.config.app_config import StoryMedConfig
from story_med.services import story_adjustment_pipeline as pipeline


class FakeResponse:
    """模拟 requests 响应。"""

    def __init__(self, body: Dict[str, Any] | None = None) -> None:
        """初始化响应体。"""
        self.status_code = 200
        self.text = ""
        self._body = body or {"success": True}

    def iter_content(self, chunk_size: int, decode_unicode: bool) -> list[str]:
        """返回模拟 SSE 分块。"""
        return [
            "data: {\"message_type\":\"TASK_RUNNING\"}\n\n",
            "data: {\"message_type\":\"TASK_COMPLETED\"}\n\n",
        ]

    def json(self) -> Dict[str, Any]:
        """返回模拟 JSON。"""
        return self._body


class FakeSession:
    """模拟 requests Session。"""

    def __init__(self) -> None:
        """初始化请求记录。"""
        self.request: Dict[str, Any] = {}

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        """记录 POST 请求并返回模拟响应。"""
        self.request = {"url": url, **kwargs}
        if url.endswith("/api/auth/login"):
            return FakeResponse(
                {
                    "success": True,
                    "data": {
                        "token_type": "Bearer",
                        "access_token": "new-token",
                    },
                }
            )
        return FakeResponse()


def build_config() -> StoryMedConfig:
    """构建单测配置。"""
    return StoryMedConfig(
        base_url="https://patient.example.com",
        timeout_seconds=1,
        verify_ssl=True,
        accept="application/json",
        user_agent="pytest",
        origin="",
        referer="",
        adjust_base_url="https://adjust.example.com",
        adjust_auth_token="token-1",
        adjust_origin="https://origin.example.com",
        adjust_referer="https://origin.example.com/",
        adjust_accept="text/event-stream;charset=UTF-8, text/event-stream",
        adjust_auth_username="admin",
        adjust_auth_password="password",
        active_env="dev",
        result_file="results/patient_story_run.json",
    )


def test_build_adjustment_payload() -> None:
    """验证调整接口请求体结构。"""
    payload = build_adjustment_payload("task-1", "patient-case", "session-1", "更写实")

    assert payload == {
        "task_id": "task-1",
        "agent_type": "patient-case",
        "form": {"session_id": "session-1", "message": "更写实"},
    }


def test_build_adjustment_payload_with_real_sample_values() -> None:
    """验证调整接口样例参数会原样传入。"""
    payload = build_adjustment_payload(
        "2071468448195149825",
        "patient-case",
        "5a11cf9e-2960-4801-aefc-dd8e0f7d952a",
        "增加一个底部说明文本：由零假设公司生产",
    )

    assert payload["task_id"] == "2071468448195149825"
    assert payload["agent_type"] == "patient-case"
    assert payload["form"] == {
        "session_id": "5a11cf9e-2960-4801-aefc-dd8e0f7d952a",
        "message": "增加一个底部说明文本：由零假设公司生产",
    }


def test_build_adjustment_headers_uses_config() -> None:
    """验证调整接口请求头读取配置。"""
    headers = build_adjustment_headers(build_config())

    assert headers["Accept"] == "text/event-stream;charset=UTF-8, text/event-stream"
    assert headers["Content-Type"] == "application/json;charset=UTF-8"
    assert headers["Authorization"] == "Bearer token-1"
    assert headers["Origin"] == "https://origin.example.com"
    assert headers["Referer"] == "https://origin.example.com/"


def test_run_story_adjustment_writes_stream_and_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证调整节点会保存 SSE 原始流和摘要结果。"""
    monkeypatch.setattr(pipeline, "EDIT_RESULTS_DIR", tmp_path / "edit")
    called = {}
    monkeypatch.setattr(pipeline, "clear_edit_case_artifacts", lambda case_id: called.setdefault("case_id", case_id))
    fake_session = FakeSession()

    result = pipeline.run_story_adjustment(
        config=build_config(),
        case_id="SM_001",
        session_id="session-1",
        task_id="task-1",
        message="图片风格调整的更写实一点",
        session=fake_session,
    )

    assert result["success"] is True
    assert result["has_task_completed"] is True
    assert result["response_body"]["event_count"] == 2
    assert fake_session.request["url"] == "https://adjust.example.com/api/agent/tasks/stream"
    assert fake_session.request["json"]["form"]["message"] == "图片风格调整的更写实一点"
    assert called["case_id"] == "SM_001"
    assert (tmp_path / "edit/SM_001/session-1_adjustment_stream.txt").exists()
    assert (tmp_path / "edit/SM_001/story_adjustment_result.json").exists()


def test_extract_adjustment_files_expands_oss_keys(tmp_path: Path) -> None:
    """验证调整流中的 oss_keys 会展开为多个可下载文件。"""
    stream_path = tmp_path / "stream.txt"
    stream_path.write_text(
        'data: {"payload":{"raw":{"data":{"files":[{"type":"image_list","oss_keys":["a.png","b.png"]}]}}}}\n',
        encoding="utf-8",
    )

    files = pipeline.extract_adjustment_files(stream_path)

    assert [item["oss_key"] for item in files] == ["a.png", "b.png"]
    assert [item["type"] for item in files] == ["image_list", "image_list"]


def test_extract_stream_errors_collects_outer_task_failed(tmp_path: Path) -> None:
    """验证内容中台外层 TASK_FAILED 会被识别为调整失败。"""
    stream_path = tmp_path / "stream.txt"
    stream_path.write_text(
        'data: {"message_type":"TASK_FAILED","content_text":"EOF reached while reading",'
        '"payload":{"error_message":"EOF reached while reading"}}\n',
        encoding="utf-8",
    )

    errors = pipeline.extract_stream_errors(stream_path)

    assert errors == ["EOF reached while reading"]


def test_detect_task_completed_returns_true_when_completed_event_exists(tmp_path: Path) -> None:
    """验证命中 TASK_COMPLETED 时返回 True。"""
    stream_path = tmp_path / "stream.txt"
    stream_path.write_text(
        'data: {"message_type":"TASK_RUNNING"}\n'
        'data: {"message_type":"TASK_COMPLETED"}\n',
        encoding="utf-8",
    )

    assert pipeline.detect_task_completed(stream_path) is True


def test_run_story_adjustment_fails_without_task_completed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证未命中 TASK_COMPLETED 时不应判定成功。"""
    monkeypatch.setattr(pipeline, "EDIT_RESULTS_DIR", tmp_path / "edit")
    monkeypatch.setattr(pipeline, "clear_edit_case_artifacts", lambda _case_id: None)

    class NoCompleteResponse(FakeResponse):
        def iter_content(self, chunk_size: int, decode_unicode: bool) -> list[str]:
            return ["data: {\"message_type\":\"TASK_RUNNING\"}\n\n"]

    class NoCompleteSession(FakeSession):
        def post(self, url: str, **kwargs: Any) -> FakeResponse:
            self.request = {"url": url, **kwargs}
            if url.endswith("/api/auth/login"):
                return FakeResponse(
                    {
                        "success": True,
                        "data": {
                            "token_type": "Bearer",
                            "access_token": "new-token",
                        },
                    }
                )
            return NoCompleteResponse()

    result = pipeline.run_story_adjustment(
        config=build_config(),
        case_id="SM_001",
        session_id="session-1",
        task_id="task-1",
        message="图片风格调整的更写实一点",
        session=NoCompleteSession(),
    )

    assert result["has_task_completed"] is False
    assert result["success"] is False
    assert result["downloaded_assets"] == []
