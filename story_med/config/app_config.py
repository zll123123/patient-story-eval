"""患者故事配置加载。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from story_med.config.settings import DEFAULT_CONFIG_FILE, ENVS_DIR
from story_med.utils.yaml_loader import load_yaml_file

DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_VERIFY_SSL = True
DEFAULT_ACCEPT = "application/json"
DEFAULT_ADJUST_ACCEPT = "text/event-stream;charset=UTF-8, text/event-stream"
DEFAULT_LLM_TIMEOUT_SECONDS = 30
DEFAULT_VISION_PROVIDER = "openai_compatible"
DEFAULT_VISION_TIMEOUT_SECONDS = 30
DEFAULT_VISION_MAX_IMAGE_SIDE = 1280
DEFAULT_VISION_JPEG_QUALITY = 85
DEFAULT_VISION_NHTAI_MODEL_VERSION = "latest"


@dataclass
class StoryMedConfig:
    """患者故事接口运行配置。"""

    base_url: str
    timeout_seconds: int
    verify_ssl: bool
    accept: str
    origin: str
    referer: str
    adjust_base_url: str
    adjust_origin: str
    adjust_referer: str
    adjust_accept: str
    adjust_auth_username: str
    adjust_auth_password: str
    active_env: str
    result_file: str


@dataclass
class StoryMedLlmConfig:
    """患者故事 LLM 运行配置。"""

    enabled: bool
    base_url: str
    model: str
    api_key: str
    timeout_seconds: int


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


def load_dotenv_file(env_path: Path) -> None:
    """从环境文件加载键值对。"""
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_env_files() -> None:
    """按优先级加载环境变量文件。"""
    active_env = os.getenv("STORY_MED_ACTIVE_ENV", "").strip().lower()
    if not active_env:
        config_data = load_yaml_file(DEFAULT_CONFIG_FILE)
        app_data = _read_section(config_data, "app")
        active_env = _read_str(app_data, "active_env", "dev").strip().lower()
    target_env_file = ENVS_DIR / f"{active_env}.env"
    load_dotenv_file(target_env_file)


def load_app_config(config_path: Path = DEFAULT_CONFIG_FILE) -> StoryMedConfig:
    """加载并构建患者故事运行配置。"""
    load_env_files()
    config_data = load_yaml_file(config_path)
    app_data = _read_section(config_data, "app")
    return StoryMedConfig(
        base_url=os.getenv("STORY_MED_BASE_URL", "").rstrip("/"),
        timeout_seconds=int(
            os.getenv(
                "STORY_MED_TIMEOUT_SECONDS",
                str(DEFAULT_TIMEOUT_SECONDS),
            )
        ),
        verify_ssl=os.getenv(
            "STORY_MED_VERIFY_SSL",
            str(DEFAULT_VERIFY_SSL),
        ).lower()
        == "true",
        accept=os.getenv("STORY_MED_ACCEPT", DEFAULT_ACCEPT),
        origin=os.getenv("STORY_MED_ORIGIN", ""),
        referer=os.getenv("STORY_MED_REFERER", ""),
        adjust_base_url=os.getenv(
            "STORY_MED_ADJUST_BASE_URL",
            "",
        ).rstrip("/"),
        adjust_origin=os.getenv(
            "STORY_MED_ADJUST_ORIGIN",
            "",
        ),
        adjust_referer=os.getenv(
            "STORY_MED_ADJUST_REFERER",
            "",
        ),
        adjust_accept=os.getenv(
            "STORY_MED_ADJUST_ACCEPT",
            DEFAULT_ADJUST_ACCEPT,
        ),
        adjust_auth_username=os.getenv(
            "STORY_MED_ADJUST_AUTH_USERNAME",
            "",
        ),
        adjust_auth_password=os.getenv(
            "STORY_MED_ADJUST_AUTH_PASSWORD",
            "",
        ),
        active_env=os.getenv("STORY_MED_ACTIVE_ENV", _read_str(app_data, "active_env", "dev")),
        result_file=os.getenv(
            "STORY_MED_RESULT_FILE",
            _read_str(app_data, "result_file", "results/patient_story_run.json"),
        ),
    )


def load_llm_config(config_path: Path = DEFAULT_CONFIG_FILE) -> StoryMedLlmConfig:
    """加载 LLM 配置，支持 STORY_MED 和 CSL 环境变量覆盖。"""
    load_env_files()
    external_env_file = os.getenv("STORY_MED_LLM_ENV_FILE", "").strip()
    if external_env_file:
        load_dotenv_file(Path(external_env_file))
    enabled = _get_env("STORY_MED_LLM_ENABLED", "CSL_LLM_ENABLED", "false")
    base_url = _get_env("STORY_MED_LLM_BASE_URL", "CSL_LLM_BASE_URL", "")
    model = _get_env("STORY_MED_LLM_MODEL", "CSL_LLM_MODEL", "")
    api_key = _get_env("STORY_MED_LLM_API_KEY", "CSL_LLM_API_KEY", "")
    timeout = _get_env(
        "STORY_MED_LLM_TIMEOUT_SECONDS",
        "CSL_LLM_TIMEOUT_SECONDS",
        str(DEFAULT_LLM_TIMEOUT_SECONDS),
    )
    return StoryMedLlmConfig(
        enabled=enabled.lower() == "true",
        base_url=base_url.rstrip("/"),
        model=model,
        api_key=api_key,
        timeout_seconds=int(timeout),
    )


def load_vision_config(config_path: Path = DEFAULT_CONFIG_FILE) -> StoryMedVisionConfig:
    """加载多模态模型配置，支持 STORY_MED 和 CSL 环境变量覆盖。"""
    load_env_files()
    llm_env_file = os.getenv("STORY_MED_LLM_ENV_FILE", "").strip()
    if llm_env_file:
        load_dotenv_file(Path(llm_env_file))
    external_env_file = os.getenv("STORY_MED_VISION_ENV_FILE", "").strip()
    if external_env_file:
        load_dotenv_file(Path(external_env_file))
    config_data = load_yaml_file(config_path)
    vision_data = _read_section(config_data, "vision")
    return StoryMedVisionConfig(
        enabled=_env("STORY_MED_VISION_ENABLED", "false").lower() == "true",
        provider=_env("STORY_MED_VISION_PROVIDER", DEFAULT_VISION_PROVIDER),
        base_url=_env(
            "STORY_MED_VISION_BASE_URL",
            _first_env("OPENAI_BASE_URL", "STORY_MED_LLM_BASE_URL", "CSL_LLM_BASE_URL"),
        ).rstrip("/"),
        model=_env("STORY_MED_VISION_MODEL", ""),
        api_key=_env(
            "STORY_MED_VISION_API_KEY",
            _first_env("DASHSCOPE_API_KEY", "STORY_MED_LLM_API_KEY", "CSL_LLM_API_KEY", "OPENAI_API_KEY"),
        ),
        timeout_seconds=int(_env("STORY_MED_VISION_TIMEOUT_SECONDS", str(DEFAULT_VISION_TIMEOUT_SECONDS))),
        max_image_side=int(_env("STORY_MED_VISION_MAX_IMAGE_SIDE", _read_str(vision_data, "max_image_side", str(DEFAULT_VISION_MAX_IMAGE_SIDE)))),
        jpeg_quality=int(_env("STORY_MED_VISION_JPEG_QUALITY", _read_str(vision_data, "jpeg_quality", str(DEFAULT_VISION_JPEG_QUALITY)))),
        nhtai_service_name=_env(
            "STORY_MED_VISION_NHTAI_SERVICE_NAME",
            "",
        ),
        nhtai_model_version=_env(
            "STORY_MED_VISION_NHTAI_MODEL_VERSION",
            DEFAULT_VISION_NHTAI_MODEL_VERSION,
        ),
        nhtai_host_header=_env(
            "STORY_MED_VISION_NHTAI_HOST_HEADER",
            os.getenv("OPENAI_HOST_HEADER", ""),
        ),
    )


def _get_env(primary_key: str, fallback_key: str, default: str) -> str:
    """按优先级读取环境变量。"""
    return os.getenv(primary_key, os.getenv(fallback_key, default)).strip()


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


def _read_section(config_data: dict[str, Any], key: str) -> dict[str, Any]:
    """读取指定配置分组。"""
    value = config_data.get(key, {})
    if isinstance(value, dict):
        return value
    return {}


def _read_scalar(section: dict[str, Any], key: str, default: Any) -> Any:
    """读取配置标量值。"""
    return section.get(key, default)


def _read_str(section: dict[str, Any], key: str, default: str = "") -> str:
    """读取字符串配置值。"""
    return str(_read_scalar(section, key, default))
