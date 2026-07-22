"""患者故事 DeepEval 指标分数归一化测试。"""

from __future__ import annotations

import pytest

from story_med.evals.patient_story_deepeval_metrics import (
    FinalImageLayoutMetric,
    ImageConsistencyMetric,
    ImageDesignMetric,
    ImageFactMetric,
    OutlineFactMetric,
    PatientStoryAuditMetric,
    StoryComplianceMetric,
    StoryFactMetric,
)


@pytest.mark.parametrize(
    ("metric_class", "score_key", "raw_score", "expected_score"),
    [
        (OutlineFactMetric, "outline_fact_score", 10.0, 0.5),
        (StoryFactMetric, "story_fact_score", 15.0, 0.75),
        (StoryComplianceMetric, "story_compliance_score", 5.0, 0.5),
        (ImageDesignMetric, "image_design_score", 8.0, 0.8),
        (ImageConsistencyMetric, "image_consistency_score", 10.0, 1.0),
        (ImageFactMetric, "image_fact_score", 7.5, 0.75),
        (FinalImageLayoutMetric, "final_image_layout_score", 15.0, 0.75),
    ],
)
def test_dimension_metrics_return_normalized_scores(
    metric_class: type, score_key: str, raw_score: float, expected_score: float
) -> None:
    """验证各维度指标将业务分数转换为 0~1。"""
    metric = metric_class()
    summary = {"scorecard": {"breakdown": {score_key: raw_score}}}

    assert metric._score(summary) == expected_score


def test_overall_metric_returns_normalized_score() -> None:
    """验证整体 100 分制指标转换为 0~1。"""
    metric = PatientStoryAuditMetric()
    summary = {"scorecard": {"total_score": 82.5}}

    assert metric._score(summary) == 0.825


def test_normalized_scores_are_clamped_to_zero_one() -> None:
    """验证异常业务分数不会突破 DeepEval 的 0~1 范围。"""
    metric = FinalImageLayoutMetric()

    assert metric._score({"scorecard": {"breakdown": {"final_image_layout_score": -5}}}) == 0.0
    assert metric._score({"scorecard": {"breakdown": {"final_image_layout_score": 25}}}) == 1.0
