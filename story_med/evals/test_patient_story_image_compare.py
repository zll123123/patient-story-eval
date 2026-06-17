"""患者故事图片多模态评估测试。"""

from __future__ import annotations

import os

import pytest

from story_med.config.settings import DEFAULT_CASE_FILE
from story_med.config.vision_app_config import load_vision_config
from story_med.services.case_loader import load_story_cases
from story_med.services.image_compare_pipeline import run_case_latest_image_compare, run_latest_image_compare


def test_latest_patient_story_images_compare() -> None:
    """评估最近一次真实链路生成的图片。"""
    if os.getenv("STORY_MED_RUN_IMAGE_COMPARE", "").lower() != "true":
        pytest.skip("需要设置 STORY_MED_RUN_IMAGE_COMPARE=true 才执行图片多模态评估")

    cases = load_story_cases(DEFAULT_CASE_FILE)
    case = next(item for item in cases if item.case_id == os.getenv("STORY_MED_IMAGE_CASE_ID", "SM_001"))
    report = run_latest_image_compare(load_vision_config(), case)

    assert report["status"] in {"success", "blocked"}


def test_seed_cases_latest_images_compare() -> None:
    """批量评估各 case 最近一次真实链路生成的图片。"""
    if os.getenv("STORY_MED_RUN_IMAGE_COMPARE_BATCH", "").lower() != "true":
        pytest.skip("需要设置 STORY_MED_RUN_IMAGE_COMPARE_BATCH=true 才执行批量图片多模态评估")

    target_case_ids = {
        item.strip()
        for item in os.getenv("STORY_MED_CASE_IDS", "").split(",")
        if item.strip()
    }
    cases = load_story_cases(DEFAULT_CASE_FILE)
    selected_cases = [case for case in cases if not target_case_ids or case.case_id in target_case_ids]
    assert selected_cases, "未找到需要执行图片评估的 case"

    config = load_vision_config()
    failures = []
    for case in selected_cases:
        report = run_case_latest_image_compare(config, case)
        if report["status"] not in {"success", "blocked"}:
            failures.append({"case_id": case.case_id, "status": report["status"]})

    assert not failures, failures
