"""患者故事 LLM 配置加载。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from story_med.config.app_config import load_dotenv_file, load_env_files
from story_med.config.settings import DEFAULT_LLM_CONFIG_FILE
from story_med.utils.yaml_loader import load_yaml_file


@dataclass
class StoryMedLlmConfig:
    """患者故事 LLM 运行配置。"""

    enabled: bool
    base_url: str
    model: str
    api_key: str
    timeout_seconds: int


def load_llm_config(config_path: Path = DEFAULT_LLM_CONFIG_FILE) -> StoryMedLlmConfig:
    """加载 LLM 配置，支持 STORY_MED 和 CSL 环境变量覆盖。"""
    load_env_files()
    external_env_file = os.getenv("STORY_MED_LLM_ENV_FILE", "").strip()
    if external_env_file:
        load_dotenv_file(Path(external_env_file))
    config_data = load_yaml_file(config_path)
    enabled = _get_env("STORY_MED_LLM_ENABLED", "CSL_LLM_ENABLED", str(config_data.get("llm_enabled", False)))
    base_url = _get_env("STORY_MED_LLM_BASE_URL", "CSL_LLM_BASE_URL", str(config_data.get("llm_base_url", "")))
    model = _get_env("STORY_MED_LLM_MODEL", "CSL_LLM_MODEL", str(config_data.get("llm_model", "")))
    api_key = _get_env("STORY_MED_LLM_API_KEY", "CSL_LLM_API_KEY", "")
    timeout = _get_env(
        "STORY_MED_LLM_TIMEOUT_SECONDS",
        "CSL_LLM_TIMEOUT_SECONDS",
        str(config_data.get("llm_timeout_seconds", 30)),
    )
    return StoryMedLlmConfig(
        enabled=enabled.lower() == "true",
        base_url=base_url.rstrip("/"),
        model=model,
        api_key=api_key,
        timeout_seconds=int(timeout),
    )


def _get_env(primary_key: str, fallback_key: str, default: str) -> str:
    """按优先级读取环境变量。"""
    return os.getenv(primary_key, os.getenv(fallback_key, default)).strip()
