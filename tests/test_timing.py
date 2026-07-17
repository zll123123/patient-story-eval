"""通用执行节点计时与并发快照单元测试。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from story_med.utils.timing import TimingCollector


def test_timing_collector_serializes_concurrent_progress_snapshots() -> None:
    """验证并发节点写进度时不会丢失阶段快照。"""
    snapshots: list[list[dict]] = []
    collector = TimingCollector(on_change=lambda stages: snapshots.append(stages))

    def run_stage(index: int) -> None:
        with collector.stage(f"stage_{index}", "audit"):
            pass

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(run_stage, range(8)))

    assert len(collector.to_list()) == 8
    assert snapshots
    assert max(len(snapshot) for snapshot in snapshots) == 8
