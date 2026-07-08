"""最终长图结构审核服务。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from story_med.clients.multimodal_llm_client import call_multimodal_json
from story_med.config.settings import PROMPTS_DIR
from story_med.config.vision_app_config import StoryMedVisionConfig
from story_med.models.case_model import StoryCaseConfig
from story_med.services.clinical_extract_baseline_service import load_clinical_baseline


def validate_final_image_layout(
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
        "patient_case": load_clinical_baseline(case),
        "image_design": image_design,
    }
    prompt = _final_image_layout_prompt(prompt_file, payload)
    result = call_multimodal_json(config, prompt, [final_image], use_thumbnail=False)
    return {
        "status": "success",
        "image_path": str(final_image),
        **result,
    }


def _final_image_layout_prompt(prompt_file: Path, payload: Dict[str, Any]) -> str:
    """拼接最终长图结构审核 prompt。"""
    template = prompt_file.read_text(encoding="utf-8")
    return f"{template}\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"


def _find_single_image(directory: Path) -> Path:
    """读取目录下唯一 PNG 图片。"""
    files = list(directory.glob("*.png"))
    if len(files) != 1:
        raise RuntimeError(f"图片文件数量异常: {directory}")
    return files[0]
