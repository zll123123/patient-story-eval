"""病例图片信息提取流水线。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from story_med.clients.multimodal_llm_client import call_multimodal_text
from story_med.config.settings import CASE_IMAGE_DIR, PROMPTS_DIR, RESULTS_DIR
from story_med.config.vision_app_config import StoryMedVisionConfig
from story_med.services.case_image_input import list_case_images_by_path


def run_clinical_extract(image_dir: str, config: StoryMedVisionConfig) -> Dict[str, Any]:
    """提取指定图片目录下的病例信息。

    Args:
        image_dir: `img` 目录下的病例文件夹名称，或绝对路径。
        config: 多模态模型配置。

    Returns:
        提取结果字典。
    """
    image_root = _resolve_image_dir(image_dir)
    image_paths = list_case_images_by_path(image_root)
    prompt = (PROMPTS_DIR / "clinical_extract.md").read_text(encoding="utf-8")
    content = call_multimodal_text(
        config,
        f"{prompt}\n\n请务必以 JSON 格式输出结果。",
        image_paths,
        use_thumbnail=False,
    )
    result = _parse_result(content, image_root, image_paths)
    _write_output(image_root.name, result, content, image_paths)
    return result


def _resolve_image_dir(image_dir: str) -> Path:
    """解析图片目录。"""
    path = Path(image_dir).expanduser()
    if not path.is_absolute():
        path = CASE_IMAGE_DIR / path
    return path.resolve()


def _parse_result(content: str, image_root: Path, image_paths: List[Path]) -> Dict[str, Any]:
    """解析模型输出并补充元信息。"""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = {"raw_output": content}
    return {
        "image_dir": image_root.name,
        "image_root": str(image_root),
        "image_count": len(image_paths),
        "result": data,
    }


def _write_output(image_dir_name: str, result: Dict[str, Any], raw_output: str, image_paths: List[Path]) -> None:
    """写入提取结果到 output 目录。"""
    output_dir = RESULTS_DIR.parent / "output" / image_dir_name
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        **result,
        "source_images": [str(path) for path in image_paths],
        "raw_output": raw_output,
    }
    (output_dir / "clinical_extract.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "clinical_extract.md").write_text(raw_output, encoding="utf-8")
