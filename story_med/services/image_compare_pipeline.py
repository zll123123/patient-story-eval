"""患者故事图片多模态评估流水线。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from story_med.clients.llm_client import call_llm_json
from story_med.clients.multimodal_llm_client import call_multimodal_json
from story_med.config.llm_app_config import load_llm_config
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
    _write_json(report, output_dir / "image_fact_validation.json")
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
    _write_json(report, output_dir / "image_fact_validation.json")
    return report


def _build_success_report(config: StoryMedVisionConfig, case: StoryCaseConfig, session_id: str) -> Dict[str, Any]:
    """构建图片评估成功报告。"""
    asset_dir = RESULTS_DIR / "assets" / case.case_id / session_id
    image_design = _read_image_design(asset_dir)
    design_validation = _validate_image_design(case, asset_dir, image_design)
    _write_json(design_validation, TMP_DIR / case.case_id / "image_design_validation.json")
    consistant_validation = _validate_image_consistance(config, asset_dir, image_design)
    _write_json(consistant_validation, TMP_DIR / case.case_id / "image_consistant_validation.json")
    final_image_layout_validation = _validate_final_image_layout(config, case, asset_dir, image_design)
    _write_json(final_image_layout_validation, TMP_DIR / case.case_id / "final_image_layout_validation.json")
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
        prompt = _build_image_prompt(case, illustration)
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
    del image_design
    final_image = _find_single_image(asset_dir / "generate_final_image")
    payload = {
        "patient_case": _read_case_parse(asset_dir),
        "images": [
            {
                "image_id": final_image.name,
                "image_type": "final_composite",
            }
        ],
    }
    result = call_multimodal_json(config, _prompt_with_payload(payload), [final_image])
    return {"image_path": str(final_image), "result": result}


def _validate_final_image_layout(
    config: StoryMedVisionConfig,
    case: StoryCaseConfig,
    asset_dir: Path,
    image_design: Dict[str, Any],
) -> Dict[str, Any]:
    """审核最终长图是否满足一图读懂的结构与顺序要求。"""
    prompt_file = PROMPTS_DIR / "final_image_layout_validate.md"
    if not prompt_file.exists():
        return {
            "status": "pending_prompt",
            "is_passed": False,
            "summary": f"缺少提示词文件: {prompt_file.name}",
            "issues": [],
        }
    final_image = _find_single_image(asset_dir / "generate_final_image")
    payload = {
        "patient_case": _read_case_parse(asset_dir),
        "image_design": image_design,
    }
    prompt = _final_image_layout_prompt(prompt_file, payload)
    result = call_multimodal_json(config, prompt, [final_image], use_thumbnail=False)
    return {
        "status": "success",
        "image_path": str(final_image),
        **result,
    }


def _build_image_prompt(
    case: StoryCaseConfig,
    illustration: Dict[str, Any],
) -> str:
    """构建单张图片评估提示词。"""
    payload = {
        "patient_case": case.case_parse or case.case_facts,
        "images": [
            {
                "image_id": illustration.get("id"),
                "image_type": "illustration",
                "source_text": illustration.get("source_text"),
            }
        ],
    }
    return _prompt_with_payload(payload)


def _prompt_with_payload(payload: Dict[str, Any]) -> str:
    """拼接图片评估 prompt 和输入 JSON。"""
    template = (PROMPTS_DIR / "image_fact_consistency_validate.md").read_text(encoding="utf-8")
    return f"{template}\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"


def _validate_image_design(
    case: StoryCaseConfig,
    asset_dir: Path,
    image_design: Dict[str, Any],
) -> Dict[str, Any]:
    """审核图片设计大纲的医学和常识合理性。"""
    llm_config = load_llm_config()
    payload = {
        "patient_case": _read_case_parse(asset_dir) or case.case_parse or case.case_facts,
        "image_design": image_design,
    }
    return call_llm_json(llm_config, _image_design_validation_prompt(payload))


def _image_design_validation_prompt(payload: Dict[str, Any]) -> str:
    """拼接图片设计审核 prompt 和输入 JSON。"""
    template = (PROMPTS_DIR / "image_design_validate.md").read_text(encoding="utf-8")
    return f"{template}\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"


def _validate_image_consistance(
    config: StoryMedVisionConfig,
    asset_dir: Path,
    image_design: Dict[str, Any],
) -> Dict[str, Any]:
    """审核图片与大纲的一致性以及多图全局一致性。"""
    payload = {
        "image_design": image_design,
        "images": _build_consistance_images_payload(asset_dir, image_design),
    }
    prompt = _image_consistance_prompt(payload)
    image_paths = [Path(item["local_path"]) for item in payload["images"] if item.get("local_path")]
    return call_multimodal_json(config, prompt, image_paths)


def _build_consistance_images_payload(asset_dir: Path, image_design: Dict[str, Any]) -> List[Dict[str, Any]]:
    """构建一致性审核输入，包含设计图与实际图片映射。"""
    payload: List[Dict[str, Any]] = []
    for illustration in image_design.get("illustrations") or []:
        image_path = _find_generated_image(asset_dir / "generate_images", str(illustration.get("image_path") or ""))
        payload.append(
            {
                "image_id": illustration.get("id"),
                "image_path": str(illustration.get("image_path") or ""),
                "composition": illustration.get("composition"),
                "local_path": str(image_path),
            }
        )
    return payload


def _image_consistance_prompt(payload: Dict[str, Any]) -> str:
    """拼接图片与大纲一致性审核 prompt。"""
    template = (PROMPTS_DIR / "image_consistant_validate.md").read_text(encoding="utf-8")
    return f"{template}\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"


def _final_image_layout_prompt(prompt_file: Path, payload: Dict[str, Any]) -> str:
    """拼接最终长图结构审核 prompt。"""
    template = prompt_file.read_text(encoding="utf-8")
    return f"{template}\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"


def _read_case_parse(asset_dir: Path) -> str:
    """读取图片解析后的病例文本。"""
    case_parse_path = asset_dir / "case_parse" / "case_parse.md"
    if case_parse_path.exists():
        return case_parse_path.read_text(encoding="utf-8")
    return ""


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
