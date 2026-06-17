"""患者故事多模态模型配置加载。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from story_med.config.app_config import load_dotenv_file, load_env_files
from story_med.config.settings import DEFAULT_VISION_CONFIG_FILE
from story_med.utils.yaml_loader import load_yaml_file


@dataclass
class StoryMedVisionConfig:
    """患者故事视觉模型运行配置。"""

    enabled: bool
    provider: str
    base_url: str
    model: str
    api_key: str
    timeout_seconds: int
    max_image_side: int
    jpeg_quality: int
    nhtai_service_name: str
    nhtai_model_version: str
    nhtai_host_header: str


def load_vision_config(config_path: Path = DEFAULT_VISION_CONFIG_FILE) -> StoryMedVisionConfig:
    """加载多模态模型配置，支持 STORY_MED 和 CSL 环境变量覆盖。"""
    load_env_files()
    llm_env_file = os.getenv("STORY_MED_LLM_ENV_FILE", "").strip()
    if llm_env_file:
        load_dotenv_file(Path(llm_env_file))
    external_env_file = os.getenv("STORY_MED_VISION_ENV_FILE", "").strip()
    if external_env_file:
        load_dotenv_file(Path(external_env_file))
    config_data = load_yaml_file(config_path)
    return StoryMedVisionConfig(
        enabled=_env("STORY_MED_VISION_ENABLED", str(config_data.get("vision_enabled", False))).lower() == "true",
        provider=_env("STORY_MED_VISION_PROVIDER", str(config_data.get("vision_provider", "openai_compatible"))),
        base_url=_env(
            "STORY_MED_VISION_BASE_URL",
            _first_env("OPENAI_BASE_URL", "STORY_MED_LLM_BASE_URL", "CSL_LLM_BASE_URL")
            or str(config_data.get("vision_base_url", "")),
        ).rstrip("/"),
        model=_env("STORY_MED_VISION_MODEL", str(config_data.get("vision_model", ""))),
        api_key=_env(
            "STORY_MED_VISION_API_KEY",
            _first_env("DASHSCOPE_API_KEY", "STORY_MED_LLM_API_KEY", "CSL_LLM_API_KEY", "OPENAI_API_KEY"),
        ),
        timeout_seconds=int(_env("STORY_MED_VISION_TIMEOUT_SECONDS", str(config_data.get("vision_timeout_seconds", 30)))),
        max_image_side=int(_env("STORY_MED_VISION_MAX_IMAGE_SIDE", str(config_data.get("vision_max_image_side", 1280)))),
        jpeg_quality=int(_env("STORY_MED_VISION_JPEG_QUALITY", str(config_data.get("vision_jpeg_quality", 85)))),
        nhtai_service_name=_env(
            "STORY_MED_VISION_NHTAI_SERVICE_NAME",
            str(config_data.get("vision_nhtai_service_name", "")),
        ),
        nhtai_model_version=_env(
            "STORY_MED_VISION_NHTAI_MODEL_VERSION",
            str(config_data.get("vision_nhtai_model_version", "latest")),
        ),
        nhtai_host_header=_env(
            "STORY_MED_VISION_NHTAI_HOST_HEADER",
            os.getenv("OPENAI_HOST_HEADER", str(config_data.get("vision_nhtai_host_header", ""))),
        ),
    )


def _env(key: str, default: str) -> str:
    """读取环境变量。"""
    return os.getenv(key, default).strip()


def _first_env(*keys: str) -> str:
    """按顺序读取第一个非空环境变量。"""
    for key in keys:
        value = os.getenv(key, "").strip()
        if value:
            return value
    return ""
