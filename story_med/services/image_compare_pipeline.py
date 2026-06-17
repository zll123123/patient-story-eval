"""患者故事图片多模态评估流水线。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from story_med.clients.multimodal_llm_client import call_multimodal_json
from story_med.config.settings import PROMPTS_DIR, RESULTS_DIR, TMP_DIR
from story_med.config.vision_app_config import StoryMedVisionConfig
from story_med.models.case_model import StoryCaseConfig


def run_latest_image_compare(config: StoryMedVisionConfig, case: StoryCaseConfig) -> Dict[str, Any]:
    """对最近一次真实链路生成的图片执行多模态评估。"""
    result_data = _read_latest_run_result()
    case_id = str(result_data.get("case_id") or "")
    session_id = str(result_data.get("session_id") or "")
    if case_id != case.case_id:
        raise RuntimeError(f"最近运行结果不是当前 case: {case.case_id} != {case_id}")

    output_dir = TMP_DIR / case.case_id
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        report = _build_success_report(config, case, session_id)
    except Exception as exc:
        report = _build_blocked_report(case, session_id, str(exc))
    _write_json(report, output_dir / "image_compare_result.json")
    return report


def run_case_latest_image_compare(config: StoryMedVisionConfig, case: StoryCaseConfig) -> Dict[str, Any]:
    """对指定 case 最近一次成功产物执行多模态评估。"""
    session_id = _latest_asset_session_id(case)
    output_dir = TMP_DIR / case.case_id
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        report = _build_success_report(config, case, session_id)
    except Exception as exc:
        report = _build_blocked_report(case, session_id, str(exc))
    _write_json(report, output_dir / "image_compare_result.json")
    return report


def _build_success_report(config: StoryMedVisionConfig, case: StoryCaseConfig, session_id: str) -> Dict[str, Any]:
    """构建图片评估成功报告。"""
    asset_dir = RESULTS_DIR / "assets" / case.case_id / session_id
    image_design = _read_image_design(asset_dir)
    illustration_results = _compare_illustrations(config, case, asset_dir, image_design)
    final_result = _compare_final_image(config, case, asset_dir, image_design)
    passed = all(bool(item["result"].get("overall_passed")) for item in illustration_results) and bool(
        final_result["result"].get("overall_passed")
    )
    return {
        "case_id": case.case_id,
        "session_id": session_id,
        "status": "success",
        "overall_passed": bool(passed),
        "illustrations": illustration_results,
        "final_image": final_result,
    }


def _compare_illustrations(
    config: StoryMedVisionConfig,
    case: StoryCaseConfig,
    asset_dir: Path,
    image_design: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """逐张评估分镜图片。"""
    results: List[Dict[str, Any]] = []
    for illustration in image_design.get("illustrations") or []:
        image_path = _find_generated_image(asset_dir / "generate_images", str(illustration.get("image_path") or ""))
        prompt = _build_image_prompt(case, "illustration", illustration)
        result = call_multimodal_json(config, prompt, [image_path])
        results.append(
            {
                "image_id": illustration.get("id"),
                "image_path": str(image_path),
                "source_text": illustration.get("source_text"),
                "result": result,
            }
        )
    return results


def _compare_final_image(
    config: StoryMedVisionConfig,
    case: StoryCaseConfig,
    asset_dir: Path,
    image_design: Dict[str, Any],
) -> Dict[str, Any]:
    """评估最终长图。"""
    final_image = _find_single_image(asset_dir / "generate_final_image")
    payload = {
        "image_type": "final_composite",
        "patient_case": case.case_facts,
        "image_design": image_design,
    }
    result = call_multimodal_json(config, _prompt_with_payload(payload), [final_image])
    return {"image_path": str(final_image), "result": result}


def _build_image_prompt(
    case: StoryCaseConfig,
    image_type: str,
    illustration: Dict[str, Any],
) -> str:
    """构建单张图片评估提示词。"""
    payload = {
        "image_type": image_type,
        "patient_case": case.case_facts,
        "expected_image": illustration,
    }
    return _prompt_with_payload(payload)


def _prompt_with_payload(payload: Dict[str, Any]) -> str:
    """拼接图片评估 prompt 和输入 JSON。"""
    template = (PROMPTS_DIR / "image_compare.md").read_text(encoding="utf-8")
    return f"{template}\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"


def _read_latest_run_result() -> Dict[str, Any]:
    """读取最近一次患者故事运行结果。"""
    result_path = RESULTS_DIR / "patient_story_run.json"
    if not result_path.exists():
        raise FileNotFoundError(f"缺少运行结果: {result_path}")
    return json.loads(result_path.read_text(encoding="utf-8"))


def _latest_asset_session_id(case: StoryCaseConfig) -> str:
    """读取指定 case 最近一次成功产物的 session_id。"""
    case_asset_dir = RESULTS_DIR / "assets" / case.case_id
    sessions = sorted(
        [path for path in case_asset_dir.iterdir() if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not sessions:
        raise FileNotFoundError(f"缺少图片审核产物目录: {case_asset_dir}")
    return sessions[0].name


def _read_image_design(asset_dir: Path) -> Dict[str, Any]:
    """读取图片设计 JSON。"""
    files = list((asset_dir / "generate_images").glob("*image_design.json"))
    if len(files) != 1:
        raise RuntimeError(f"image_design 文件数量异常: {files}")
    return json.loads(files[0].read_text(encoding="utf-8"))


def _find_generated_image(directory: Path, source_image_path: str) -> Path:
    """根据设计文件中的图片名查找本地图片。"""
    source_name = Path(source_image_path).name
    matches = [path for path in directory.glob("*.png") if path.name.endswith(source_name)]
    if len(matches) != 1:
        raise RuntimeError(f"生成图片匹配异常: {source_name}, {matches}")
    return matches[0]


def _find_single_image(directory: Path) -> Path:
    """读取目录下唯一 PNG 图片。"""
    files = list(directory.glob("*.png"))
    if len(files) != 1:
        raise RuntimeError(f"图片文件数量异常: {directory}")
    return files[0]


def _build_blocked_report(case: StoryCaseConfig, session_id: str, error: str) -> Dict[str, Any]:
    """构建阻塞报告。"""
    return {
        "case_id": case.case_id,
        "session_id": session_id,
        "status": "blocked",
        "overall_passed": False,
        "error": error,
        "illustrations": [],
        "final_image": {},
    }


def _write_json(data: Dict[str, Any], output_path: Path) -> None:
    """写入 JSON 文件。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
