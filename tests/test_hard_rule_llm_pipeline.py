"""硬规则 LLM 流水线单元测试。"""

from __future__ import annotations

from story_med.models.case_model import StoryAgentRunResult, StoryCaseConfig, StoryStepResult
from story_med.services import hard_rule_llm_pipeline as pipeline


def test_build_summary_includes_agent_step_timings() -> None:
    """验证 summary 会记录核心生成步骤耗时。"""
    case = StoryCaseConfig(
        case_id="SM_TEST",
        description="耗时测试",
        creative_brief="brief",
        case_facts="facts",
        hard_rules={},
    )
    run_result = StoryAgentRunResult(
        case_id=case.case_id,
        description=case.description,
        session_id="session-1",
        success=True,
        steps=[
            _step("generate_outline", "/outline", 1.1),
            _step("generate_story", "/story", 2.2),
            _step("generate_images", "/images", 3.3),
            _step("generate_final_image", "/generate", 4.4),
        ],
        session_response={},
        outline_response={},
        story_response={},
        images_response={},
        final_image_response={},
        downloaded_assets=[],
        total_duration_seconds=11.0,
    )

    summary = pipeline._build_summary(  # type: ignore[attr-defined]
        case=case,
        run_result=run_result,
        outline_compare={"field_results": {}},
        story_compare={"field_results": {}},
    )

    timings = summary["agent_step_timings"]
    assert summary["agent_total_duration_seconds"] == 11.0
    assert timings["generate_outline"]["label"] == "获取大纲"
    assert timings["generate_outline"]["duration_seconds"] == 1.1
    assert timings["generate_story"]["label"] == "获取故事"
    assert timings["generate_story"]["duration_seconds"] == 2.2
    assert timings["generate_images"]["label"] == "生成图片"
    assert timings["generate_images"]["duration_seconds"] == 3.3
    assert timings["generate_final_image"]["label"] == "获取最终长图"
    assert timings["generate_final_image"]["duration_seconds"] == 4.4


def _step(step_name: str, endpoint: str, duration_seconds: float) -> StoryStepResult:
    """构建测试步骤结果。"""
    return StoryStepResult(
        step_name=step_name,
        endpoint=endpoint,
        request_payload={},
        status_code=200,
        response_body={},
        response_data={},
        started_at="2026-06-25T00:00:00Z",
        finished_at="2026-06-25T00:00:01Z",
        duration_seconds=duration_seconds,
    )
