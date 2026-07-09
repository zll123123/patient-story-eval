"""多模态模型配置加载测试。"""

from __future__ import annotations

from pathlib import Path

from story_med.config.app_config import load_vision_config


def test_load_vision_config_prefers_dashscope_api_key(monkeypatch, tmp_path: Path) -> None:
    """验证视觉配置会优先读取本地百炼 API Key。"""
    monkeypatch.setenv("STORY_MED_ACTIVE_ENV", "test")
    monkeypatch.setenv("STORY_MED_VISION_ENABLED", "true")
    monkeypatch.setenv("STORY_MED_VISION_PROVIDER", "openai_compatible")
    monkeypatch.setenv("STORY_MED_VISION_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    monkeypatch.setenv("STORY_MED_VISION_MODEL", "qwen3.7-plus")
    monkeypatch.setenv("STORY_MED_VISION_TIMEOUT_SECONDS", "120")
    monkeypatch.delenv("STORY_MED_VISION_API_KEY", raising=False)
    monkeypatch.delenv("STORY_MED_LLM_API_KEY", raising=False)
    monkeypatch.delenv("CSL_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-demo-key")

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "\n".join(
            [
                "vision:",
                "  max_image_side: 1280",
                "  jpeg_quality: 85",
            ]
        ),
        encoding="utf-8",
    )

    config = load_vision_config(config_file)

    assert config.api_key == "dashscope-demo-key"
    assert config.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert config.model == "qwen3.7-plus"
