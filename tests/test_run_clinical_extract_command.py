"""病例提取命令行入口测试。"""

from __future__ import annotations

from pathlib import Path

from story_med.commands import run_clinical_extract as command


def test_resolve_image_dirs_defaults_to_all_directories(monkeypatch, tmp_path: Path) -> None:
    """验证未传参数时默认扫描全部病例目录。"""
    (tmp_path / "A").mkdir()
    (tmp_path / "B").mkdir()
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(command, "CASE_IMAGE_DIR", tmp_path)

    result = command._resolve_image_dirs("", "")

    assert result == ["A", "B"]


def test_main_runs_batch_extract(monkeypatch) -> None:
    """验证命令入口会批量调用病例提取。"""
    captured: list[str] = []
    monkeypatch.setattr(command, "_resolve_image_dirs", lambda image_dir, image_dirs: ["A", "B"])
    monkeypatch.setattr(command, "load_vision_config", lambda: object())
    monkeypatch.setattr(command, "run_clinical_extract", lambda image_dir, config: captured.append(image_dir) or {"image_dir": image_dir})

    exit_code = command.main([])

    assert exit_code == 0
    assert captured == ["A", "B"]
