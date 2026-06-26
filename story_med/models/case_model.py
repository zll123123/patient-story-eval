"""患者故事用例模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class StoryCaseConfig:
    """患者故事测试用例。"""

    case_id: str
    description: str
    creative_brief: str
    image_dir: str = ""
    case_facts: str = ""
    case_parse: str = ""
    hard_rules: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "case_id": self.case_id,
            "description": self.description,
            "creative_brief": self.creative_brief,
            "image_dir": self.image_dir,
            "case_facts": self.case_facts,
            "case_parse": self.case_parse,
            "hard_rules": self.hard_rules,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoryCaseConfig":
        """从字典构造模型。"""
        return cls(
            case_id=str(data.get("case_id") or ""),
            description=str(data.get("description") or ""),
            creative_brief=str(data.get("creative_brief") or ""),
            image_dir=str(data.get("image_dir") or ""),
            case_facts=str(data.get("case_facts") or ""),
            case_parse=str(data.get("case_parse") or ""),
            hard_rules=dict(data.get("hard_rules") or {}),
        )


@dataclass
class StoryStepResult:
    """单步接口调用结果。"""

    step_name: str
    endpoint: str
    request_payload: Dict[str, Any]
    status_code: int
    response_body: Dict[str, Any]
    response_data: Dict[str, Any]
    session_id: str = ""
    started_at: str = ""
    finished_at: str = ""
    duration_seconds: float = 0.0
    downloaded_assets: List[Dict[str, Any]] | None = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "step_name": self.step_name,
            "endpoint": self.endpoint,
            "request_payload": self.request_payload,
            "status_code": self.status_code,
            "response_body": self.response_body,
            "response_data": self.response_data,
            "session_id": self.session_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
            "downloaded_assets": self.downloaded_assets or [],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoryStepResult":
        """从字典构造模型。"""
        return cls(
            step_name=str(data.get("step_name") or ""),
            endpoint=str(data.get("endpoint") or ""),
            request_payload=dict(data.get("request_payload") or {}),
            status_code=int(data.get("status_code") or 0),
            response_body=dict(data.get("response_body") or {}),
            response_data=dict(data.get("response_data") or {}),
            session_id=str(data.get("session_id") or ""),
            started_at=str(data.get("started_at") or ""),
            finished_at=str(data.get("finished_at") or ""),
            duration_seconds=float(data.get("duration_seconds") or 0.0),
            downloaded_assets=list(data.get("downloaded_assets") or []),
        )


@dataclass
class StoryAgentRunResult:
    """患者故事 agent 完整执行结果。"""

    case_id: str
    description: str
    session_id: str
    success: bool
    steps: List[StoryStepResult]
    session_response: Dict[str, Any]
    outline_response: Dict[str, Any]
    story_response: Dict[str, Any]
    images_response: Dict[str, Any]
    final_image_response: Dict[str, Any]
    downloaded_assets: List[Dict[str, Any]]
    started_at: str = ""
    finished_at: str = ""
    total_duration_seconds: float = 0.0
    error: str = ""
    failed_step: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "case_id": self.case_id,
            "description": self.description,
            "session_id": self.session_id,
            "success": self.success,
            "steps": [item.to_dict() for item in self.steps],
            "session_response": self.session_response,
            "outline_response": self.outline_response,
            "story_response": self.story_response,
            "images_response": self.images_response,
            "final_image_response": self.final_image_response,
            "downloaded_assets": self.downloaded_assets,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total_duration_seconds": self.total_duration_seconds,
            "error": self.error,
            "failed_step": self.failed_step,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoryAgentRunResult":
        """从字典构造模型。"""
        return cls(
            case_id=str(data.get("case_id") or ""),
            description=str(data.get("description") or ""),
            session_id=str(data.get("session_id") or ""),
            success=bool(data.get("success", False)),
            steps=[StoryStepResult.from_dict(item) for item in data.get("steps") or []],
            session_response=dict(data.get("session_response") or {}),
            outline_response=dict(data.get("outline_response") or {}),
            story_response=dict(data.get("story_response") or {}),
            images_response=dict(data.get("images_response") or {}),
            final_image_response=dict(data.get("final_image_response") or {}),
            downloaded_assets=list(data.get("downloaded_assets") or []),
            started_at=str(data.get("started_at") or ""),
            finished_at=str(data.get("finished_at") or ""),
            total_duration_seconds=float(data.get("total_duration_seconds") or 0.0),
            error=str(data.get("error") or ""),
            failed_step=str(data.get("failed_step") or ""),
        )
