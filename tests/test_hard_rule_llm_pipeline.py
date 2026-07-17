"""硬规则 LLM 流水线单元测试。"""

from __future__ import annotations

from story_med.models.case_model import StoryAgentRunResult, StoryCaseConfig
from story_med.services.story_generation_evaluation import (
    hard_rule_llm_pipeline as pipeline,
)


def test_build_summary_includes_execution_stages() -> None:
    """验证 summary 会记录统一执行节点耗时。"""
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
        steps=[],
        session_response={},
        outline_response={},
        story_response={},
        images_response={},
        final_image_response={},
        downloaded_assets=[],
        execution_stages=[
            {"stage": "generate_outline", "duration_seconds": 1.1},
            {"stage": "generate_story", "duration_seconds": 2.2},
            {"stage": "generate_images", "duration_seconds": 3.3},
            {"stage": "generate_final_image", "duration_seconds": 4.4},
        ],
    )

    summary = pipeline._build_summary(  # type: ignore[attr-defined]
        case=case,
        run_result=run_result,
        outline_compare={"field_results": {}},
        story_compare={"field_results": {}},
        execution_stages=[],
    )

    stages = summary["execution_stages"]
    assert [item["stage"] for item in stages] == [
        "generate_outline",
        "generate_story",
        "generate_images",
        "generate_final_image",
    ]
    assert stages[0]["duration_seconds"] == 1.1
    assert stages[-1]["duration_seconds"] == 4.4
