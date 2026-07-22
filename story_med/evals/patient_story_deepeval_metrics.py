"""患者故事 Deepeval 自定义指标。"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from deepeval.metrics.base_metric import BaseMetric
from deepeval.test_case.llm_test_case import LLMTestCase

from story_med.config.settings import STORY_AUDITS_DIR


# DeepEval/Confident AI 指标统一使用 0~1；本地 scorecard 仍保留业务分制。
OUTLINE_FACT_MAX_SCORE = 20.0
STORY_FACT_MAX_SCORE = 20.0
STORY_COMPLIANCE_MAX_SCORE = 10.0
IMAGE_DESIGN_MAX_SCORE = 10.0
IMAGE_CONSISTENCY_MAX_SCORE = 10.0
IMAGE_FACT_MAX_SCORE = 10.0
FINAL_IMAGE_LAYOUT_MAX_SCORE = 20.0
PATIENT_STORY_OVERALL_MAX_SCORE = 100.0


class _PatientStoryBaseMetric(BaseMetric):
    """患者故事业务指标基类。"""

    threshold = 1.0
    async_mode = False
    include_reason = True
    verbose_mode = False

    def __init__(self) -> None:
        self.score = 0.0
        self.reason = ""
        self.success = False
        self.score_breakdown: Dict[str, Any] = {}

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        """从 summary.json 读取审核结果并计算指标。"""
        summary = _load_summary(test_case.input)
        self.score = self._score(summary)
        self.success = self._success(summary)
        self.reason = self._reason(summary)
        self.score_breakdown = self._breakdown(summary)
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        """异步模式下复用同步实现。"""
        return self.measure(test_case, *args, **kwargs)

    def is_successful(self) -> bool:
        """返回是否通过。"""
        return bool(self.success)

    def _score(self, summary: Dict[str, Any]) -> float:
        raise NotImplementedError

    def _success(self, summary: Dict[str, Any]) -> bool:
        raise NotImplementedError

    def _reason(self, summary: Dict[str, Any]) -> str:
        raise NotImplementedError

    def _breakdown(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class OutlineFactMetric(_PatientStoryBaseMetric):
    """大纲事实一致性指标。"""

    @property
    def __name__(self) -> str:
        return "outline_fact_metric"

    def _score(self, summary: Dict[str, Any]) -> float:
        return _normalized_breakdown_score(
            summary, "outline_fact_score", OUTLINE_FACT_MAX_SCORE
        )

    def _success(self, summary: Dict[str, Any]) -> bool:
        return bool(_audit_value(summary, "outline_passed"))

    def _reason(self, summary: Dict[str, Any]) -> str:
        failed_fields = summary.get("outline_failed_fields") or []
        if self._success(summary):
            return f"大纲事实审核通过，得分 {self.score}。"
        return f"大纲事实审核未通过，失败字段: {', '.join(failed_fields) or '未知'}，得分 {self.score}。"

    def _breakdown(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "passed": _audit_value(summary, "outline_passed"),
            "failed_fields": summary.get("outline_failed_fields") or [],
        }


class StoryFactMetric(_PatientStoryBaseMetric):
    """Story 事实一致性指标。"""

    @property
    def __name__(self) -> str:
        return "story_fact_metric"

    def _score(self, summary: Dict[str, Any]) -> float:
        return _normalized_breakdown_score(
            summary, "story_fact_score", STORY_FACT_MAX_SCORE
        )

    def _success(self, summary: Dict[str, Any]) -> bool:
        return bool(_audit_value(summary, "story_passed"))

    def _reason(self, summary: Dict[str, Any]) -> str:
        failed_fields = summary.get("story_failed_fields") or []
        if self._success(summary):
            return f"Story 事实审核通过，得分 {self.score}。"
        return f"Story 事实审核未通过，失败字段: {', '.join(failed_fields) or '未知'}，得分 {self.score}。"

    def _breakdown(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "passed": _audit_value(summary, "story_passed"),
            "failed_fields": summary.get("story_failed_fields") or [],
        }


class ImageDesignMetric(_PatientStoryBaseMetric):
    """图片设计审核指标。"""

    @property
    def __name__(self) -> str:
        return "image_design_metric"

    def _score(self, summary: Dict[str, Any]) -> float:
        return _normalized_breakdown_score(
            summary, "image_design_score", IMAGE_DESIGN_MAX_SCORE
        )

    def _success(self, summary: Dict[str, Any]) -> bool:
        return bool(_audit_value(summary, "image_design_passed"))

    def _reason(self, summary: Dict[str, Any]) -> str:
        image_design = summary.get("image_design") or {}
        return f"{image_design.get('summary') or '图片设计审核无结果'}，得分 {self.score}。"

    def _breakdown(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        return summary.get("image_design") or {}


class StoryComplianceMetric(_PatientStoryBaseMetric):
    """Story 合规审核指标。"""

    @property
    def __name__(self) -> str:
        return "story_compliance_metric"

    def _score(self, summary: Dict[str, Any]) -> float:
        return _normalized_breakdown_score(
            summary, "story_compliance_score", STORY_COMPLIANCE_MAX_SCORE
        )

    def _success(self, summary: Dict[str, Any]) -> bool:
        return bool(_audit_value(summary, "story_compliance_passed"))

    def _reason(self, summary: Dict[str, Any]) -> str:
        story_compliance = summary.get("story_compliance") or {}
        return story_compliance.get("summary") or "Story 合规审核无结果。"

    def _breakdown(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        return summary.get("story_compliance") or {}


class ImageConsistencyMetric(_PatientStoryBaseMetric):
    """图片一致性审核指标。"""

    @property
    def __name__(self) -> str:
        return "image_consistency_metric"

    def _score(self, summary: Dict[str, Any]) -> float:
        return _normalized_breakdown_score(
            summary, "image_consistency_score", IMAGE_CONSISTENCY_MAX_SCORE
        )

    def _success(self, summary: Dict[str, Any]) -> bool:
        return bool(_audit_value(summary, "image_consistency_passed"))

    def _reason(self, summary: Dict[str, Any]) -> str:
        image_consistency = summary.get("image_consistency") or {}
        return f"{image_consistency.get('summary') or '图片一致性审核无结果'}，得分 {self.score}。"

    def _breakdown(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        return summary.get("image_consistency") or {}


class ImageFactMetric(_PatientStoryBaseMetric):
    """成图事实一致性审核指标。"""

    @property
    def __name__(self) -> str:
        return "image_fact_metric"

    def _score(self, summary: Dict[str, Any]) -> float:
        return _normalized_breakdown_score(
            summary, "image_fact_score", IMAGE_FACT_MAX_SCORE
        )

    def _success(self, summary: Dict[str, Any]) -> bool:
        return bool(_audit_value(summary, "image_fact_passed"))

    def _reason(self, summary: Dict[str, Any]) -> str:
        image_fact = summary.get("image_fact") or {}
        return (
            f"成图事实审核状态: {image_fact.get('status') or 'unknown'}，"
            f"通过数 {image_fact.get('passed_count', 0)}/{image_fact.get('total_count', 0)}，得分 {self.score}。"
        )

    def _breakdown(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        return summary.get("image_fact") or {}


class FinalImageLayoutMetric(_PatientStoryBaseMetric):
    """最终长图结构审核指标。"""

    @property
    def __name__(self) -> str:
        return "final_image_layout_metric"

    def _score(self, summary: Dict[str, Any]) -> float:
        return _normalized_breakdown_score(
            summary, "final_image_layout_score", FINAL_IMAGE_LAYOUT_MAX_SCORE
        )

    def _success(self, summary: Dict[str, Any]) -> bool:
        return bool(_audit_value(summary, "final_image_layout_passed"))

    def _reason(self, summary: Dict[str, Any]) -> str:
        layout = summary.get("final_image_layout") or {}
        return f"{layout.get('summary') or '长图结构审核无结果'}，得分 {self.score}。"

    def _breakdown(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        return summary.get("final_image_layout") or {}


class PatientStoryAuditMetric(_PatientStoryBaseMetric):
    """患者故事整体审核指标。"""

    @property
    def __name__(self) -> str:
        return "patient_story_overall_metric"

    def _score(self, summary: Dict[str, Any]) -> float:
        scorecard = summary.get("scorecard") or {}
        raw_score = float(scorecard.get("total_score") or 0.0)
        return _normalize_score(raw_score, PATIENT_STORY_OVERALL_MAX_SCORE)

    def _success(self, summary: Dict[str, Any]) -> bool:
        overview = summary.get("audit_overview") or {}
        return bool(overview) and all(value is True for value in overview.values())

    def _reason(self, summary: Dict[str, Any]) -> str:
        overview = summary.get("audit_overview") or {}
        failed_fields = [key for key, value in overview.items() if value is False]
        if not failed_fields:
            return f"整体审核通过，综合得分 {self.score}。"
        return f"整体审核未通过，失败项: {', '.join(failed_fields)}，综合得分 {self.score}。"

    def _breakdown(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        scorecard = summary.get("scorecard") or {}
        return {
            "audit_overview": summary.get("audit_overview") or {},
            "scorecard": scorecard.get("breakdown") or {},
            "gate_passed": scorecard.get("gate_passed"),
            "high_score_eligible": scorecard.get("high_score_eligible"),
        }


def build_patient_story_metrics() -> List[BaseMetric]:
    """构建患者故事 Deepeval 指标集合。"""
    return [
        OutlineFactMetric(),
        StoryFactMetric(),
        StoryComplianceMetric(),
        ImageDesignMetric(),
        ImageConsistencyMetric(),
        ImageFactMetric(),
        FinalImageLayoutMetric(),
        PatientStoryAuditMetric(),
    ]


def _load_summary(case_id: str) -> Dict[str, Any]:
    """加载指定 case 的 summary。"""
    summary_path = STORY_AUDITS_DIR / case_id / "summary.json"
    if not summary_path.exists():
        return {}
    try:
        return json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _audit_value(summary: Dict[str, Any], key: str) -> Optional[bool]:
    """读取 audit_overview 布尔值。"""
    overview = summary.get("audit_overview") or {}
    value = overview.get(key)
    return bool(value) if value is not None else None


def _breakdown_score(summary: Dict[str, Any], key: str) -> float:
    """读取 scorecard.breakdown 中的单项分数。"""
    scorecard = summary.get("scorecard") or {}
    breakdown = scorecard.get("breakdown") or {}
    return float(breakdown.get(key) or 0.0)


def _normalized_breakdown_score(
    summary: Dict[str, Any], key: str, max_score: float
) -> float:
    """读取本地分数并转换为 DeepEval 使用的 0~1 分数。"""
    return _normalize_score(_breakdown_score(summary, key), max_score)


def _normalize_score(score: float, max_score: float) -> float:
    """将业务分数归一化到 0~1，避免上报超出 DeepEval 分数范围。"""
    if max_score <= 0:
        raise ValueError("指标满分必须大于 0")
    return round(min(max(score / max_score, 0.0), 1.0), 4)
