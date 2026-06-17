"""多模态模型配置加载测试。"""

from __future__ import annotations

from pathlib import Path

from story_med.config.vision_app_config import load_vision_config


def test_load_vision_config_prefers_dashscope_api_key(monkeypatch, tmp_path: Path) -> None:
    """验证视觉配置会优先读取本地百炼 API Key。"""
    monkeypatch.setenv("STORY_MED_ACTIVE_ENV", "test")
    monkeypatch.delenv("STORY_MED_VISION_API_KEY", raising=False)
    monkeypatch.delenv("STORY_MED_LLM_API_KEY", raising=False)
    monkeypatch.delenv("CSL_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-demo-key")

    config_file = tmp_path / "vision_config.yaml"
    config_file.write_text(
        "\n".join(
            [
                "vision_enabled: true",
                "vision_provider: openai_compatible",
                "vision_base_url: https://dashscope.aliyuncs.com/compatible-mode/v1",
                "vision_model: qwen3.7-plus",
                "vision_timeout_seconds: 120",
                "vision_max_image_side: 1280",
                "vision_jpeg_quality: 85",
                'vision_nhtai_service_name: ""',
                'vision_nhtai_model_version: "latest"',
                'vision_nhtai_host_header: ""',
            ]
        ),
        encoding="utf-8",
    )

    config = load_vision_config(config_file)

    assert config.api_key == "dashscope-demo-key"
    assert config.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert config.model == "qwen3.7-plus"
