"""Story 合规审核流水线。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from story_med.clients.llm_client import call_llm_json
from story_med.config.llm_app_config import StoryMedLlmConfig
from story_med.config.settings import PROMPTS_DIR, RESULTS_DIR, TMP_DIR
from story_med.models.case_model import StoryCaseConfig
from story_med.services.clinical_baseline import load_clinical_baseline

STORY_COMPLIANCE_PROMPT_FILE = PROMPTS_DIR / "story_compliance_validate.md"


def run_story_compliance_validation(
    llm_config: StoryMedLlmConfig,
    case: StoryCaseConfig,
) -> Dict[str, Any]:
    """对最近一次 Story 文本执行合规审核。

    Args:
        llm_config: 文本模型配置。
        case: 当前测试病例。

    Returns:
        Story 合规审核结果。
    """
    output_dir = TMP_DIR / case.case_id
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = _build_validation_result(llm_config, case)
    except Exception as exc:
        result = _blocked_result(case, str(exc))
    _write_json(result, output_dir / "story_compliance_validation.json")
    return result


def _build_validation_result(
    llm_config: StoryMedLlmConfig,
    case: StoryCaseConfig,
) -> Dict[str, Any]:
    """构建并执行 Story 合规审核。"""
    if not STORY_COMPLIANCE_PROMPT_FILE.exists():
        return _pending_prompt_result(case)
    session_id = _latest_asset_session_id(case)
    asset_dir = RESULTS_DIR / "assets" / case.case_id / session_id
    story_text = _read_asset_text(asset_dir, "generate_story")
    payload = {
        "case_id": case.case_id,
        "creative_brief": case.creative_brief,
        "clinical_extract": load_clinical_baseline(case),
        "story_text": story_text,
    }
    model_result = call_llm_json(llm_config, _build_prompt(payload))
    return {
        "case_id": case.case_id,
        "session_id": session_id,
        "status": "success",
        **model_result,
    }


def _build_prompt(payload: Dict[str, Any]) -> str:
    """拼接 Story 合规审核 prompt 和输入。"""
    template = STORY_COMPLIANCE_PROMPT_FILE.read_text(encoding="utf-8")
    return f"{template}\n\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"


def _latest_asset_session_id(case: StoryCaseConfig) -> str:
    """读取指定 case 最近一次成功产物 session_id。"""
    case_asset_dir = RESULTS_DIR / "assets" / case.case_id
    sessions = sorted(
        [path for path in case_asset_dir.iterdir() if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not sessions:
        raise FileNotFoundError(f"缺少 Story 合规审核产物目录: {case_asset_dir}")
    return sessions[0].name


def _read_asset_text(asset_dir: Path, step_name: str) -> str:
    """读取指定步骤的唯一文本产物。"""
    step_dir = asset_dir / step_name
    text_files = _dedupe_text_paths(step_dir.glob("*"))
    if len(text_files) != 1:
        raise RuntimeError(f"{step_name} 文本文件数量异常: {text_files}")
    return text_files[0].read_text(encoding="utf-8")


def _dedupe_text_paths(paths: Any) -> list[Path]:
    """按最终落盘路径去重文本文件列表。"""
    unique: dict[str, Path] = {}
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists() or path.suffix.lower() not in {".md", ".txt"}:
            continue
        unique[str(path.resolve())] = path
    return list(unique.values())


def _pending_prompt_result(case: StoryCaseConfig) -> Dict[str, Any]:
    """构建提示词缺失结果。"""
    return {
        "case_id": case.case_id,
        "session_id": "",
        "status": "pending_prompt",
        "is_passed": False,
        "summary": f"缺少提示词文件: {STORY_COMPLIANCE_PROMPT_FILE.name}",
        "issues": [],
    }


def _blocked_result(case: StoryCaseConfig, error: str) -> Dict[str, Any]:
    """构建审核阻塞结果。"""
    return {
        "case_id": case.case_id,
        "session_id": "",
        "status": "blocked",
        "is_passed": False,
        "summary": "Story 合规审核执行失败",
        "error": error,
        "issues": [],
    }


def _write_json(data: Dict[str, Any], output_path: Path) -> None:
    """写入 JSON 文件。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
