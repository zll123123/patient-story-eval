"""解析版患者病例 SSE 节点耗时单元测试。"""

from __future__ import annotations

import json
from pathlib import Path

from story_med.clients import agent_task_client
from story_med.models.case_model import StoryAgentRunResult, StoryStepResult
from story_med.services.hard_rule_llm_pipeline import _build_step_timings


def test_write_stream_chunks_generates_event_log_and_step_timings(tmp_path: Path) -> None:
    """验证 SSE 写入时会生成事件时间戳和节点耗时。"""
    output_path = tmp_path / "session_patient_case_stream.txt"
    chunks = [
        'data: {"payload":{"raw":{"step_id":"1","status":"START","title":"生成大纲"}}}\n\n',
        'data: {"payload":{"raw":{"step_id":"1","status":"END"}}}\n\n',
    ]

    event_count = agent_task_client.write_stream_chunks(chunks, output_path)
    timing_path = agent_task_client.write_stream_step_timings(
        output_path.with_name("session_patient_case_stream_events.jsonl"),
        output_path.with_name("session_patient_case_stream_step_timings.json"),
    )

    timing = json.loads(timing_path.read_text(encoding="utf-8"))
    assert event_count == 2
    assert output_path.exists()
    assert timing["steps"][0]["title"] == "生成大纲"
    assert timing["steps"][0]["status"] == "done"
    assert "received_at" in (output_path.with_name("session_patient_case_stream_events.jsonl").read_text())


def test_build_step_timings_uses_patient_case_internal_timings() -> None:
    """验证 summary 优先使用解析版 Agent 内部节点耗时。"""
    run_result = StoryAgentRunResult(
        case_id="SM_TEST",
        description="单测",
        session_id="session-1",
        success=True,
        steps=[
            StoryStepResult(
                step_name="stream_agent_task",
                endpoint="/api/agent/tasks/stream",
                request_payload={},
                status_code=200,
                response_body={
                    "agent_node_timings": {
                        "steps": [
                            {
                                "title": "生成故事正文",
                                "status": "done",
                                "started_at": "2026-07-02T00:00:00+00:00",
                                "finished_at": "2026-07-02T00:00:03+00:00",
                                "duration_seconds": 3.0,
                            }
                        ]
                    }
                },
                response_data={},
            )
        ],
        session_response={},
        outline_response={},
        story_response={},
        images_response={},
        final_image_response={},
        downloaded_assets=[],
    )

    timings = _build_step_timings(run_result)

    assert timings["generate_story"]["label"] == "获取故事"
    assert timings["generate_story"]["duration_seconds"] == 3.0
    assert timings["generate_story"]["agent_title"] == "生成故事正文"
