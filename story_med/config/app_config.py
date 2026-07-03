"""患者故事运行配置加载。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from story_med.config.settings import CONFIG_DIR, DEFAULT_CONFIG_FILE
from story_med.utils.yaml_loader import load_yaml_file

DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_VERIFY_SSL = True
DEFAULT_ACCEPT = "application/json"
DEFAULT_ADJUST_BASE_URL = "https://pharma-content-hub-java-dev.nullht.com"
DEFAULT_ADJUST_ACCEPT = "text/event-stream;charset=UTF-8, text/event-stream"
DEFAULT_ADJUST_AUTH_USERNAME = "admin"
DEFAULT_ADJUST_AUTH_PASSWORD = "Admin@123456"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
)


@dataclass
class StoryMedConfig:
    """患者故事接口运行配置。"""

    base_url: str
    timeout_seconds: int
    verify_ssl: bool
    accept: str
    user_agent: str
    origin: str
    referer: str
    adjust_base_url: str
    adjust_auth_token: str
    adjust_origin: str
    adjust_referer: str
    adjust_accept: str
    adjust_auth_username: str
    adjust_auth_password: str
    active_env: str
    result_file: str


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
        active_env = str(config_data.get("active_env", "dev")).strip().lower()
    target_env_file = CONFIG_DIR / f"{active_env}.env"
    load_dotenv_file(target_env_file)


def load_app_config(config_path: Path = DEFAULT_CONFIG_FILE) -> StoryMedConfig:
    """加载并构建患者故事运行配置。"""
    load_env_files()
    config_data = load_yaml_file(config_path)
    return StoryMedConfig(
        base_url=os.getenv("STORY_MED_BASE_URL", str(config_data.get("base_url", ""))).rstrip("/"),
        timeout_seconds=int(
            os.getenv(
                "STORY_MED_TIMEOUT_SECONDS",
                config_data.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS),
            )
        ),
        verify_ssl=os.getenv(
            "STORY_MED_VERIFY_SSL",
            str(config_data.get("verify_ssl", DEFAULT_VERIFY_SSL)),
        ).lower()
        == "true",
        accept=os.getenv("STORY_MED_ACCEPT", str(config_data.get("accept", DEFAULT_ACCEPT))),
        user_agent=os.getenv("STORY_MED_USER_AGENT", str(config_data.get("user_agent", DEFAULT_USER_AGENT))),
        origin=os.getenv("STORY_MED_ORIGIN", str(config_data.get("origin", ""))),
        referer=os.getenv("STORY_MED_REFERER", str(config_data.get("referer", ""))),
        adjust_base_url=os.getenv(
            "STORY_MED_ADJUST_BASE_URL",
            str(config_data.get("adjust_base_url", DEFAULT_ADJUST_BASE_URL)),
        ).rstrip("/"),
        adjust_auth_token=os.getenv(
            "STORY_MED_ADJUST_AUTH_TOKEN",
            os.getenv("authorization", str(config_data.get("adjust_auth_token", ""))),
        ),
        adjust_origin=os.getenv(
            "STORY_MED_ADJUST_ORIGIN",
            str(config_data.get("adjust_origin", config_data.get("origin", ""))),
        ),
        adjust_referer=os.getenv(
            "STORY_MED_ADJUST_REFERER",
            str(config_data.get("adjust_referer", config_data.get("referer", ""))),
        ),
        adjust_accept=os.getenv(
            "STORY_MED_ADJUST_ACCEPT",
            str(config_data.get("adjust_accept", DEFAULT_ADJUST_ACCEPT)),
        ),
        adjust_auth_username=os.getenv(
            "STORY_MED_ADJUST_AUTH_USERNAME",
            str(config_data.get("adjust_auth_username", DEFAULT_ADJUST_AUTH_USERNAME)),
        ),
        adjust_auth_password=os.getenv(
            "STORY_MED_ADJUST_AUTH_PASSWORD",
            str(config_data.get("adjust_auth_password", DEFAULT_ADJUST_AUTH_PASSWORD)),
        ),
        active_env=os.getenv("STORY_MED_ACTIVE_ENV", str(config_data.get("active_env", "dev"))),
        result_file=os.getenv(
            "STORY_MED_RESULT_FILE",
            str(config_data.get("result_file", "results/patient_story_run.json")),
        ),
    )
