"""解析版患者病例 SSE 节点耗时单元测试。"""

from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter, sleep

import pytest

from story_med.clients.agent_api import agent_task_client
from story_med.utils.timing import TimingCollector


def test_write_stream_chunks_generates_event_log_and_step_timings(
    tmp_path: Path,
) -> None:
    """验证 SSE 写入时会生成事件时间戳和节点耗时。"""
    output_path = tmp_path / "session_patient_case_stream.txt"
    chunks = [
        'data: {"payload":{"raw":{"step_id":"1","status":"START","title":"生成大纲"}}}\n\n',
        'data: {"payload":{"raw":{"step_id":"1","status":"END"}}}\n\n',
    ]

    event_count = agent_task_client.write_stream_chunks(
        chunks, output_path, deadline=perf_counter() + 10
    )
    event_log_path = output_path.with_name("session_patient_case_stream_events.jsonl")
    events = [
        json.loads(line)
        for line in event_log_path.read_text(encoding="utf-8").splitlines()
    ]
    timing = agent_task_client._extract_step_timings(events)  # type: ignore[attr-defined]
    assert event_count == 2
    assert timing[0]["title"] == "生成大纲"
    assert timing[0]["status"] == "done"
    assert "received_at" in event_log_path.read_text()


def test_write_stream_chunks_raises_when_total_timeout_reached(tmp_path: Path) -> None:
    """验证 SSE 总时长超限时抛出可转 history 的超时异常。"""
    output_path = tmp_path / "stream.txt"

    def chunks():
        yield 'data: {"message_type":"HEARTBEAT"}\n\n'
        sleep(0.02)
        yield 'data: {"message_type":"HEARTBEAT"}\n\n'

    with pytest.raises(TimeoutError, match="30 分钟总时限"):
        agent_task_client.write_stream_chunks(
            chunks(), output_path, deadline=perf_counter() + 0.01
        )
    assert output_path.exists()


def test_timing_collector_normalizes_agent_nodes() -> None:
    """验证中台节点可以进入统一 execution_stages 结构。"""
    collector = TimingCollector()
    collector.add_agent_nodes(
        [
            {
                "title": "生成故事正文",
                "status": "done",
                "started_at": "2026-07-02T00:00:00+00:00",
                "finished_at": "2026-07-02T00:00:03+00:00",
                "duration_seconds": 3.0,
            }
        ],
        task_id="task-1",
        session_id="session-1",
    )

    stage = collector.to_list()[0]
    assert stage["stage"] == "生成故事正文"
    assert stage["category"] == "agent_node"
    assert stage["status"] == "success"
    assert stage["duration_seconds"] == 3.0
