"""患者故事图片审核编排服务。"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

from story_med.clients.llm.llm_client import call_llm_json
from story_med.clients.llm.multimodal_llm_client import call_multimodal_json
from story_med.config.app_config import load_llm_config
from story_med.config.settings import PROMPTS_DIR, RESULTS_DIR, STORY_AUDITS_DIR
from story_med.config.app_config import StoryMedVisionConfig
from story_med.models.case_model import StoryCaseConfig
from story_med.services.clinical_case_preparation.clinical_extract_baseline_service import (
    load_clinical_baseline,
)
from story_med.services.story_generation_evaluation.final_image_layout_audit_service import (
    validate_final_image_layout,
)
from story_med.utils.timing import TimingCollector, write_stage_snapshots


def run_latest_image_audit(
    config: StoryMedVisionConfig, case: StoryCaseConfig
) -> Dict[str, Any]:
    """对最近一次真实链路生成的图片执行多模态评估。"""
    result_data = _read_latest_run_result()
    case_id = str(result_data.get("case_id") or "")
    session_id = str(result_data.get("session_id") or "")
    if case_id != case.case_id:
        raise RuntimeError(f"最近运行结果不是当前 case: {case.case_id} != {case_id}")
    output_dir = STORY_AUDITS_DIR / case.case_id
    output_dir.mkdir(parents=True, exist_ok=True)
    timings = TimingCollector(
        on_change=lambda stages: _write_image_audit_progress(
            case, session_id, stages, output_dir
        )
    )
    _write_image_audit_progress(case, session_id, [], output_dir)
    try:
        report = _build_success_report(config, case, session_id, timings)
    except Exception as exc:
        report = _build_blocked_report(case, session_id, str(exc), timings.to_list())
    _write_json(report, output_dir / "image_fact_validation.json")
    return report


def run_case_latest_image_audit(
    config: StoryMedVisionConfig, case: StoryCaseConfig, session_id: str
) -> Dict[str, Any]:
    """对指定 session 的成功产物执行多模态评估。"""
    output_dir = STORY_AUDITS_DIR / case.case_id
    output_dir.mkdir(parents=True, exist_ok=True)
    timings = TimingCollector(
        on_change=lambda stages: _write_image_audit_progress(
            case, session_id, stages, output_dir
        )
    )
    _write_image_audit_progress(case, session_id, [], output_dir)
    try:
        report = _build_success_report(config, case, session_id, timings)
    except Exception as exc:
        report = _build_blocked_report(case, session_id, str(exc), timings.to_list())
    _write_json(report, output_dir / "image_fact_validation.json")
    return report


def _build_success_report(
    config: StoryMedVisionConfig,
    case: StoryCaseConfig,
    session_id: str,
    timings: TimingCollector,
) -> Dict[str, Any]:
    """构建图片评估成功报告。"""
    asset_dir = RESULTS_DIR / "assets" / case.case_id / session_id
    image_design = _read_image_design(asset_dir)
    design_validation = _validate_image_design(case, asset_dir, image_design, timings)
    _write_json(
        design_validation,
        STORY_AUDITS_DIR / case.case_id / "image_design_validation.json",
    )
    with ThreadPoolExecutor(max_workers=4) as executor:
        consistency_future = executor.submit(
            _audit_image_consistency, config, asset_dir, image_design, timings
        )
        layout_future = executor.submit(
            validate_final_image_layout,
            config,
            case,
            asset_dir,
            image_design,
            timings,
        )
        illustrations_future = executor.submit(
            _compare_illustrations, config, case, asset_dir, image_design, timings
        )
        final_image_future = executor.submit(
            _compare_final_image, config, case, asset_dir, image_design, timings
        )
        consistency_validation = consistency_future.result()
        final_image_layout_validation = layout_future.result()
        illustration_results = illustrations_future.result()
        final_result = final_image_future.result()
    _write_json(
        consistency_validation,
        STORY_AUDITS_DIR / case.case_id / "image_consistency_validation.json",
    )
    _write_json(
        final_image_layout_validation,
        STORY_AUDITS_DIR / case.case_id / "final_image_layout_validation.json",
    )
    passed = all(
        bool(item["result"].get("overall_passed")) for item in illustration_results
    ) and bool(final_result["result"].get("overall_passed"))
    return {
        "case_id": case.case_id,
        "session_id": session_id,
        "status": "success",
        "overall_passed": bool(passed),
        "execution_stages": timings.to_list(),
        "illustrations": illustration_results,
        "final_image": final_result,
    }


def _compare_illustrations(
    config: StoryMedVisionConfig,
    case: StoryCaseConfig,
    asset_dir: Path,
    image_design: Dict[str, Any],
    timings: TimingCollector,
) -> List[Dict[str, Any]]:
    """并发评估分镜图片，并按设计顺序返回结果。"""
    illustrations = image_design.get("illustrations") or []
    if not illustrations:
        return []
    worker_count = min(_vision_audit_workers(), len(illustrations))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [
            executor.submit(
                _compare_single_illustration,
                config,
                case,
                asset_dir,
                illustration,
                timings,
            )
            for illustration in illustrations
        ]
        return [future.result() for future in futures]


def _compare_single_illustration(
    config: StoryMedVisionConfig,
    case: StoryCaseConfig,
    asset_dir: Path,
    illustration: Dict[str, Any],
    timings: TimingCollector,
) -> Dict[str, Any]:
    """执行单张图片事实审核并即时落盘。"""
    image_id = illustration.get("id")
    stage_name = f"image_fact_audit_{image_id or 'unknown'}"
    node_path = STORY_AUDITS_DIR / case.case_id / f"{stage_name}.json"
    image_path: Path | None = None
    prompt = _build_image_prompt(case, illustration)
    try:
        with timings.stage(stage_name, "audit", metadata={"image_id": image_id}):
            _write_image_node_result(
                node_path, stage_name, image_id, "running", image_path=""
            )
            image_path = _find_generated_image(
                asset_dir / "generate_images",
                str(illustration.get("image_url") or ""),
            )
            result = call_multimodal_json(config, prompt, [image_path])
        node = _build_image_node_result(
            stage_name,
            image_id,
            "success",
            result=result,
            image_path=str(image_path),
        )
    except Exception as exc:
        node = _build_image_node_result(
            stage_name,
            image_id,
            "failed",
            result={"overall_passed": False},
            image_path=str(image_path or ""),
            error=str(exc),
            error_type=type(exc).__name__,
        )
    _write_json(node, node_path)
    return {
        "image_id": image_id,
        "image_path": str(image_path or ""),
        "source_text": illustration.get("source_text"),
        "result": node["result"],
    }


def _vision_audit_workers() -> int:
    """读取视觉审核并发数，非法配置回退到保守值。"""
    raw_value = os.getenv("STORY_MED_VISION_AUDIT_CONCURRENCY", "3")
    try:
        return max(1, min(int(raw_value), 5))
    except ValueError:
        return 3


def _build_image_node_result(
    stage_name: str,
    image_id: Any,
    status: str,
    *,
    result: Dict[str, Any],
    image_path: str,
    error: str = "",
    error_type: str = "",
) -> Dict[str, Any]:
    """构建单张图片审核节点结果。"""
    return {
        "stage": stage_name,
        "image_id": image_id,
        "status": status,
        "image_path": image_path,
        "result": result,
        "error": error,
        "error_type": error_type,
    }


def _write_image_node_result(
    output_path: Path,
    stage_name: str,
    image_id: Any,
    status: str,
    *,
    image_path: str,
    error: str = "",
    error_type: str = "",
) -> None:
    """即时写入单张图片审核节点状态。"""
    _write_json(
        _build_image_node_result(
            stage_name,
            image_id,
            status,
            result={},
            image_path=image_path,
            error=error,
            error_type=error_type,
        ),
        output_path,
    )


def _compare_final_image(
    config: StoryMedVisionConfig,
    case: StoryCaseConfig,
    asset_dir: Path,
    image_design: Dict[str, Any],
    timings: TimingCollector,
) -> Dict[str, Any]:
    """评估最终长图。"""
    del image_design
    final_image = _find_single_image(asset_dir / "generate_final_image")
    payload = {
        "patient_case": _patient_case_baseline(case, asset_dir),
        "images": [{"image_id": final_image.name, "image_type": "final_composite"}],
    }
    with timings.stage(
        "final_image_fact_audit", "audit", metadata={"image_path": str(final_image)}
    ):
        result = call_multimodal_json(
            config, _prompt_with_payload(payload), [final_image]
        )
    return {"image_path": str(final_image), "result": result}


def _build_image_prompt(case: StoryCaseConfig, illustration: Dict[str, Any]) -> str:
    """构建单张图片评估提示词。"""
    payload = {
        "patient_case": _patient_case_baseline(case),
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
    template = (PROMPTS_DIR / "image_fact_consistency_validate.md").read_text(
        encoding="utf-8"
    )
    return (
        f"{template}\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
    )


def _validate_image_design(
    case: StoryCaseConfig,
    asset_dir: Path,
    image_design: Dict[str, Any],
    timings: TimingCollector,
) -> Dict[str, Any]:
    """审核图片设计大纲的医学和常识合理性。"""
    llm_config = load_llm_config()
    payload = {
        "patient_case": _patient_case_baseline(case, asset_dir),
        "image_design": image_design,
    }
    with timings.stage("image_design_audit", "audit"):
        return call_llm_json(llm_config, _image_design_validation_prompt(payload))


def _image_design_validation_prompt(payload: Dict[str, Any]) -> str:
    """拼接图片设计审核 prompt 和输入 JSON。"""
    template = (PROMPTS_DIR / "image_design_validate.md").read_text(encoding="utf-8")
    return (
        f"{template}\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
    )


def _audit_image_consistency(
    config: StoryMedVisionConfig,
    asset_dir: Path,
    image_design: Dict[str, Any],
    timings: TimingCollector,
) -> Dict[str, Any]:
    """审核图片与大纲的一致性以及多图全局一致性。"""
    payload = {
        "image_design": image_design,
        "images": _build_consistency_images_payload(asset_dir, image_design),
    }
    prompt = _image_consistency_prompt(payload)
    image_paths = [
        Path(item["local_path"]) for item in payload["images"] if item.get("local_path")
    ]
    with timings.stage("image_consistency_audit", "audit"):
        return call_multimodal_json(config, prompt, image_paths)


def _build_consistency_images_payload(
    asset_dir: Path, image_design: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """构建一致性审核输入，包含设计图与实际图片映射。"""
    payload: List[Dict[str, Any]] = []
    for illustration in image_design.get("illustrations") or []:
        image_path = _find_generated_image(
            asset_dir / "generate_images", str(illustration.get("image_url") or "")
        )
        payload.append(
            {
                "image_id": illustration.get("id"),
                "image_path": str(illustration.get("image_path") or ""),
                "composition": illustration.get("composition"),
                "local_path": str(image_path),
            }
        )
    return payload


def _image_consistency_prompt(payload: Dict[str, Any]) -> str:
    """拼接图片与大纲一致性审核 prompt。"""
    template = (PROMPTS_DIR / "image_consistency_validate.md").read_text(
        encoding="utf-8"
    )
    return (
        f"{template}\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
    )


def _read_case_parse(asset_dir: Path) -> str:
    """读取图片解析后的病例文本。"""
    case_parse_path = asset_dir / "case_parse" / "case_parse.md"
    if case_parse_path.exists():
        return case_parse_path.read_text(encoding="utf-8")
    return ""


def _patient_case_baseline(case: StoryCaseConfig, asset_dir: Path | None = None) -> str:
    """读取图片审核使用的病例基准文本。"""
    del asset_dir
    return load_clinical_baseline(case)


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


def _find_generated_image(directory: Path, source_image_url: str) -> Path:
    """根据设计文件 image_url 查找本地下载图片。"""
    source_name = Path(urlparse(source_image_url).path).name
    if not source_name:
        raise RuntimeError(f"图片 URL 缺少文件名: {source_image_url}")
    source_stem = Path(source_name).stem
    matches = [
        path
        for path in directory.glob("*.png")
        if path.name == source_name
        or path.stem.startswith(f"{source_stem}_")
    ]
    if len(matches) != 1:
        raise RuntimeError(f"生成图片匹配异常: {source_name}, {matches}")
    return matches[0]


def _find_single_image(directory: Path) -> Path:
    """读取目录下唯一 PNG 图片。"""
    files = list(directory.glob("*.png"))
    if len(files) != 1:
        raise RuntimeError(f"图片文件数量异常: {directory}")
    return files[0]


def _build_blocked_report(
    case: StoryCaseConfig,
    session_id: str,
    error: str,
    execution_stages: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """构建阻塞报告。"""
    return {
        "case_id": case.case_id,
        "session_id": session_id,
        "status": "blocked",
        "overall_passed": False,
        "error": error,
        "execution_stages": execution_stages,
        "illustrations": [],
        "final_image": {},
    }


def _write_image_audit_progress(
    case: StoryCaseConfig,
    session_id: str,
    execution_stages: List[Dict[str, Any]],
    output_dir: Path,
) -> None:
    """实时写入图片审核节点进度。"""
    write_stage_snapshots(output_dir, execution_stages)
    _write_json(
        {
            "case_id": case.case_id,
            "session_id": session_id,
            "status": "running",
            "overall_passed": False,
            "execution_stages": execution_stages,
            "illustrations": [],
            "final_image": {},
        },
        output_dir / "image_fact_validation.json",
    )


def _write_json(data: Dict[str, Any], output_path: Path) -> None:
    """写入 JSON 文件。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
