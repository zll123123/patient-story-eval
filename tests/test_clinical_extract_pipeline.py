"""病例图片信息提取流水线测试。"""

from __future__ import annotations

import json
from pathlib import Path

from story_med.services import clinical_extract_pipeline as pipeline
from story_med.config.vision_app_config import StoryMedVisionConfig


def test_run_clinical_extract_writes_output_by_image_dir(monkeypatch, tmp_path: Path) -> None:
    """验证提取结果按图片目录名落到 output 目录。"""
    image_root = tmp_path / "img" / "安达唐-孙"
    image_root.mkdir(parents=True)
    (image_root / "a.png").write_bytes(b"a")
    (image_root / "b.jpg").write_bytes(b"b")

    monkeypatch.setattr(pipeline, "CASE_IMAGE_DIR", tmp_path / "img")
    monkeypatch.setattr(pipeline, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(pipeline, "PROMPTS_DIR", tmp_path)
    (tmp_path / "clinical_extract.md").write_text("prompt", encoding="utf-8")
    monkeypatch.setattr(pipeline, "list_case_images_by_path", lambda path: [image_root / "a.png", image_root / "b.jpg"])
    monkeypatch.setattr(pipeline, "call_multimodal_text", lambda config, prompt, image_paths, use_thumbnail=False: '{"ok":true}')
    config = StoryMedVisionConfig(
        enabled=True,
        provider="openai_compatible",
        base_url="https://example.com",
        model="qwen3.7-plus",
        api_key="key",
        timeout_seconds=30,
        max_image_side=1280,
        jpeg_quality=85,
        nhtai_service_name="",
        nhtai_model_version="latest",
        nhtai_host_header="",
    )

    result = pipeline.run_clinical_extract("安达唐-孙", config)

    output_json = tmp_path / "output" / "安达唐-孙" / "clinical_extract.json"
    output_md = tmp_path / "output" / "安达唐-孙" / "clinical_extract.md"
    assert output_json.exists()
    assert output_md.exists()
    data = json.loads(output_json.read_text(encoding="utf-8"))
    assert data["image_dir"] == "安达唐-孙"
    assert data["image_count"] == 2
    assert result["image_dir"] == "安达唐-孙"
