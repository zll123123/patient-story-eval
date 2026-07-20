"""患者故事调整节点单元测试。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

from story_med.clients.agent_api.agent_task_client import build_adjustment_headers, build_adjustment_payload
from story_med.config.app_config import StoryMedConfig
from story_med.executors.content_hub_history import iter_artifacts, normalize_content_hub_stream
from story_med.executors.patient_story_edit_executor import detect_task_completed, extract_stream_errors
from story_med.services.story_edit_evaluation import story_adjustment_pipeline as pipeline


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
            'data: {"message_type":"USER_REQUEST","turn_id":"turn-1"}\n\n',
            "data: {\"message_type\":\"TASK_RUNNING\"}\n\n",
            'data: {"payload":{"raw":{"data":{"files":[{"type":"html","oss_key":"story-med/adjustment/index_test.html"}]}}}}\n\n',
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
    monkeypatch.setattr(pipeline, "EDIT_RUNS_DIR", tmp_path / "edit")
    monkeypatch.setattr(
        "story_med.executors.patient_story_edit_executor.create_story_med_download_url",
        lambda *_args, **_kwargs: {"download_url": "https://download.example"},
    )

    def fake_download(_url: str, output_path: Path, _config: Any) -> dict[str, Any]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("<html></html>", encoding="utf-8")
        return {"local_path": str(output_path)}

    monkeypatch.setattr(
        "story_med.executors.patient_story_edit_executor.download_story_med_file",
        fake_download,
    )
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
    assert result["response_body"]["event_count"] == 4
    assert fake_session.request["url"] == "https://adjust.example.com/api/agent/tasks/stream"
    assert fake_session.request["json"]["form"]["message"] == "图片风格调整的更写实一点"
    assert (tmp_path / "edit/SM_001/session-1_adjustment_stream.txt").exists()
    assert (tmp_path / "edit/SM_001/story_adjustment_result.json").exists()


def test_normalize_adjustment_stream_uses_history_artifact_structure(tmp_path: Path) -> None:
    """验证调整 SSE 产物使用与 history 相同的结构。"""
    stream_path = tmp_path / "stream.txt"
    stream_path.write_text(
        'data: {"payload":{"raw":{"data":{"files":['
        '{"type":"html","title":"最终页面","oss_key":"index.html"},'
        '{"type":"png","title":"页面截图","oss_key":"index.png"}'
        ']}}}}\n',
        encoding="utf-8",
    )

    history = normalize_content_hub_stream(stream_path)
    files = iter_artifacts(history)

    assert [item["file_key"] for item in files] == ["index.html", "index.png"]
    assert [item["artifact"]["type"] for item in files] == ["html", "png"]


def test_extract_stream_errors_collects_outer_task_failed(tmp_path: Path) -> None:
    """验证内容中台外层 TASK_FAILED 会被识别为调整失败。"""
    stream_path = tmp_path / "stream.txt"
    stream_path.write_text(
        'data: {"message_type":"TASK_FAILED","content_text":"EOF reached while reading",'
        '"payload":{"error_message":"EOF reached while reading"}}\n',
        encoding="utf-8",
    )

    errors = extract_stream_errors(stream_path)

    assert errors == ["EOF reached while reading"]


def test_detect_task_completed_returns_true_when_completed_event_exists(tmp_path: Path) -> None:
    """验证命中 TASK_COMPLETED 时返回 True。"""
    stream_path = tmp_path / "stream.txt"
    stream_path.write_text(
        'data: {"message_type":"TASK_RUNNING"}\n'
        'data: {"message_type":"TASK_COMPLETED"}\n',
        encoding="utf-8",
    )

    assert detect_task_completed(stream_path) is True


def test_run_story_adjustment_fails_without_task_completed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """验证未命中 TASK_COMPLETED 时不应判定成功。"""
    monkeypatch.setattr(pipeline, "EDIT_RUNS_DIR", tmp_path / "edit")
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
