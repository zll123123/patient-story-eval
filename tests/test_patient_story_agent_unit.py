"""患者故事 agent 适配器单元测试。"""

from __future__ import annotations

from story_med.adapters.patient_story_agent import PatientStoryAgentAdapter
from story_med.clients.story_client import StoryApiResponse, extract_session_id
from story_med.config.app_config import StoryMedConfig
from story_med.models.case_model import StoryCaseConfig
from story_med.services.asset_downloader import extract_urls


def build_config() -> StoryMedConfig:
    """构建单测配置。"""
    return StoryMedConfig(
        base_url="https://example.com",
        timeout_seconds=1,
        verify_ssl=True,
        accept="application/json",
        user_agent="pytest",
        origin="",
        referer="",
        adjust_base_url="https://adjust.example.com",
        adjust_auth_token="",
        adjust_origin="",
        adjust_referer="",
        adjust_accept="text/event-stream",
        adjust_auth_username="admin",
        adjust_auth_password="password",
        active_env="dev",
        result_file="results/patient_story_run.json",
    )


def build_case() -> StoryCaseConfig:
    """构建单测用例。"""
    return StoryCaseConfig(
        case_id="SM_TEST",
        description="单测",
        creative_brief="brief",
        case_facts="facts",
        hard_rules={},
    )


def test_extract_session_id_supports_nested_data() -> None:
    """验证 session_id 提取逻辑兼容多种响应结构。"""
    assert extract_session_id({"session_id": "abc"}) == "abc"
    assert extract_session_id({"id": "def"}) == "def"
    assert extract_session_id({"data": {"session_id": "ghi"}}) == "ghi"
    assert extract_session_id({"data": {"id": "jkl"}}) == "jkl"


def test_run_case_collects_every_step() -> None:
    """验证适配器会收集完整 5 步输出。"""
    adapter = PatientStoryAgentAdapter(build_config())
    case = build_case()

    monkey_responses = [
        StoryApiResponse(
            status_code=200,
            body={"session_id": "session-1", "top_status": "processing"},
            data={"session_id": "session-1", "top_status": "processing"},
        ),
        StoryApiResponse(
            status_code=200,
            body={"outline": {"sections": ["a", "b"]}},
            data={"outline": {"sections": ["a", "b"]}},
        ),
        StoryApiResponse(
            status_code=200,
            body={"story": {"text": "story"}},
            data={"story": {"text": "story"}},
        ),
        StoryApiResponse(status_code=200, body={"images": []}, data={"images": []}),
        StoryApiResponse(status_code=200, body={"final_image": {}}, data={"final_image": {}}),
    ]

    adapter._create_session_step = lambda case: monkey_responses[0]  # type: ignore[method-assign]
    adapter._generate_outline_step = lambda case, session_id: monkey_responses[1]  # type: ignore[method-assign]
    adapter._generate_story_step = lambda case, session_id: monkey_responses[2]  # type: ignore[method-assign]
    adapter._generate_images_step = lambda session_id: monkey_responses[3]  # type: ignore[method-assign]
    adapter._generate_final_image_step = lambda session_id: monkey_responses[4]  # type: ignore[method-assign]
    adapter._download_step_assets = lambda case, session_id, step_name, response_body: []  # type: ignore[method-assign]

    result = adapter.run_case(case)

    assert result.success is True
    assert result.session_id == "session-1"
    assert len(result.steps) == 5
    assert result.session_response["session_id"] == "session-1"
    assert result.outline_response["outline"]["sections"] == ["a", "b"]
    assert result.story_response["story"]["text"] == "story"
    assert result.images_response["images"] == []
    assert result.final_image_response["final_image"] == {}
    assert result.started_at
    assert result.finished_at
    assert result.total_duration_seconds >= 0
    assert all(step.started_at for step in result.steps)
    assert all(step.finished_at for step in result.steps)
    assert all(step.duration_seconds >= 0 for step in result.steps)


def test_story_step_payload_uses_creative_brief_and_case_facts() -> None:
    """验证文章生成接口按服务端要求传入完整病例上下文。"""
    payload = PatientStoryAgentAdapter._build_story_payload(build_case())

    assert payload == {"creative_brief": "brief", "case_facts": "facts"}


def test_extract_urls_from_nested_response() -> None:
    """验证能从嵌套响应中提取 OSS 链接。"""
    payload = {
        "images": [
            {"url": "https://example.oss-cn-shanghai.aliyuncs.com/a.png"},
            "文本 https://example.oss-cn-shanghai.aliyuncs.com/b.jpg",
        ],
        "final": {"asset": "https://example.oss-cn-shanghai.aliyuncs.com/c.pdf"},
    }

    assert extract_urls(payload) == [
        "https://example.oss-cn-shanghai.aliyuncs.com/a.png",
        "https://example.oss-cn-shanghai.aliyuncs.com/b.jpg",
        "https://example.oss-cn-shanghai.aliyuncs.com/c.pdf",
    ]


def test_story_agent_run_result_to_dict_includes_timing_fields() -> None:
    """验证结果序列化包含耗时字段。"""
    adapter = PatientStoryAgentAdapter(build_config())
    adapter._create_session_step = lambda case: StoryApiResponse(  # type: ignore[method-assign]
        status_code=200,
        body={"session_id": "session-1"},
        data={"session_id": "session-1"},
    )
    adapter._generate_outline_step = lambda case, session_id: StoryApiResponse(  # type: ignore[method-assign]
        status_code=200,
        body={"outline": "ok"},
        data={"outline": "ok"},
    )
    adapter._generate_story_step = lambda case, session_id: StoryApiResponse(  # type: ignore[method-assign]
        status_code=200,
        body={"story": "ok"},
        data={"story": "ok"},
    )
    adapter._download_step_assets = lambda case, session_id, step_name, response_body: []  # type: ignore[method-assign]

    result = adapter.run_case_until_story(build_case()).to_dict()

    assert "started_at" in result
    assert "finished_at" in result
    assert "total_duration_seconds" in result
    assert len(result["steps"]) == 3
    assert all("duration_seconds" in step for step in result["steps"])
