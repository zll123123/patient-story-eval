"""统一记录患者故事生成、编辑和审核节点耗时。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from threading import RLock
from typing import Any, Callable, Dict, List, Optional, Type

from loguru import logger


def now_iso() -> str:
    """返回当前 UTC ISO 时间。"""
    return datetime.now(UTC).isoformat()


def write_stage_snapshots(output_dir: "Path", stages: List[Dict[str, Any]]) -> None:
    """将每个执行节点的最新状态独立落盘。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    for stage in stages:
        raw_name = str(stage.get("stage") or "unknown")
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw_name)
        output_path = output_dir / f"execution_stage_{safe_name}.json"
        temp_path = output_path.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(stage, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temp_path.replace(output_path)


@dataclass
class ExecutionStage:
    """单个执行节点的耗时和状态。"""

    stage: str
    category: str
    status: str = "running"
    started_at: str = ""
    finished_at: str = ""
    duration_seconds: float = 0.0
    task_id: str = ""
    session_id: str = ""
    error: str = ""
    error_type: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为可序列化字典。"""
        return {
            "stage": self.stage,
            "category": self.category,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "error": self.error,
            "error_type": self.error_type,
            "metadata": self.metadata,
        }


class StageTimer:
    """记录一个执行节点，并在退出时写入采集器。"""

    def __init__(self, collector: "TimingCollector", stage: ExecutionStage) -> None:
        """初始化节点计时器。"""
        self._collector = collector
        self.stage = stage
        self._started_perf = 0.0

    def __enter__(self) -> "StageTimer":
        """开始记录节点。"""
        self.stage.started_at = now_iso()
        self._started_perf = perf_counter()
        self._collector.start(self.stage)
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Any,
    ) -> bool:
        """结束节点并记录异常，不吞掉异常。"""
        self.stage.finished_at = now_iso()
        self.stage.duration_seconds = round(perf_counter() - self._started_perf, 3)
        if exc_value is None:
            self.stage.status = "success"
        else:
            self.stage.status = "failed"
            self.stage.error = str(exc_value)
            self.stage.error_type = type(exc_value).__name__
        self._collector.changed()
        logger.info(
            "执行节点结束: stage={}, category={}, status={}, duration_seconds={}, error={}",
            self.stage.stage,
            self.stage.category,
            self.stage.status,
            self.stage.duration_seconds,
            self.stage.error,
        )
        return False

    def update(self, **values: Any) -> None:
        """更新当前节点的任务标识或元数据。"""
        for key, value in values.items():
            if hasattr(self.stage, key):
                setattr(self.stage, key, value)


class TimingCollector:
    """收集一条执行链路中的所有节点耗时。"""

    def __init__(
        self,
        on_change: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    ) -> None:
        """初始化空采集器。"""
        self._stages: List[ExecutionStage] = []
        self._on_change = on_change
        self._lock = RLock()

    @property
    def stages(self) -> List[ExecutionStage]:
        """返回已记录节点。"""
        with self._lock:
            return list(self._stages)

    def stage(
        self,
        name: str,
        category: str,
        *,
        task_id: str = "",
        session_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StageTimer:
        """创建一个可用 with 包裹的节点计时器。"""
        record = ExecutionStage(
            stage=name,
            category=category,
            task_id=task_id,
            session_id=session_id,
            metadata=dict(metadata or {}),
        )
        return StageTimer(self, record)

    def add(self, stage: ExecutionStage) -> None:
        """追加已经由上游事件计算完成的节点。"""
        with self._lock:
            self._stages.append(stage)
            self.changed()

    def start(self, stage: ExecutionStage) -> None:
        """记录节点开始状态并立即通知持久化回调。"""
        with self._lock:
            self._stages.append(stage)
            logger.info(
                "执行节点开始: stage={}, category={}, task_id={}, session_id={}",
                stage.stage,
                stage.category,
                stage.task_id,
                stage.session_id,
            )
            self.changed()

    def changed(self) -> None:
        """通知外部持久化当前节点快照。"""
        if self._on_change is None:
            return
        try:
            with self._lock:
                self._on_change(self.to_list())
        except Exception as exc:
            logger.warning("执行节点进度持久化失败: error={}", exc)

    def add_agent_nodes(
        self,
        nodes: List[Dict[str, Any]],
        *,
        task_id: str = "",
        session_id: str = "",
    ) -> None:
        """将内容中台返回的内部 agent 节点转成统一结构。"""
        for node in nodes:
            self.add(
                ExecutionStage(
                    stage=str(node.get("stage") or node.get("title") or "agent_node"),
                    category="agent_node",
                    status=_normalize_status(node.get("status")),
                    started_at=str(node.get("started_at") or ""),
                    finished_at=str(node.get("finished_at") or ""),
                    duration_seconds=float(node.get("duration_seconds") or 0.0),
                    task_id=task_id,
                    session_id=session_id,
                    error=str(node.get("error") or ""),
                    error_type=str(node.get("error_type") or ""),
                    metadata={
                        key: value
                        for key, value in node.items()
                        if key
                        not in {
                            "stage",
                            "title",
                            "status",
                            "started_at",
                            "finished_at",
                            "duration_seconds",
                            "error",
                            "error_type",
                        }
                    },
                )
            )

    def to_list(self) -> List[Dict[str, Any]]:
        """返回统一的执行节点列表。"""
        with self._lock:
            return [stage.to_dict() for stage in self._stages]


def _normalize_status(status: Any) -> str:
    """将上游节点状态归一化为结果状态。"""
    value = str(status or "").lower()
    if value in {"done", "end", "success", "completed"}:
        return "success"
    if value in {"error", "failed", "failure"}:
        return "failed"
    if value in {"running", "processing", "start"}:
        return "incomplete"
    return value or "incomplete"
