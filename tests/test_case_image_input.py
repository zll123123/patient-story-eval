"""病例图片输入服务单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from story_med.services.case_image_input import list_case_images, list_case_images_by_path


def test_list_case_images_returns_sorted_supported_files(tmp_path: Path) -> None:
    """验证按 case 目录读取多张病例图片并稳定排序。"""
    case_dir = tmp_path / "SM_001"
    case_dir.mkdir()
    (case_dir / "b.png").write_bytes(b"b")
    (case_dir / "a.jpg").write_bytes(b"a")
    (case_dir / "note.txt").write_text("ignore", encoding="utf-8")

    images = list_case_images("SM_001", tmp_path)

    assert [path.name for path in images] == ["a.jpg", "b.png"]


def test_list_case_images_rejects_missing_case_dir(tmp_path: Path) -> None:
    """验证病例图片目录缺失时抛出明确错误。"""
    with pytest.raises(FileNotFoundError):
        list_case_images("SM_MISSING", tmp_path)


def test_list_case_images_by_path_reads_direct_folder(tmp_path: Path) -> None:
    """验证可直接按图片文件夹读取病例图片。"""
    image_dir = tmp_path / "case-images"
    image_dir.mkdir()
    (image_dir / "c.png").write_bytes(b"c")
    (image_dir / "a.jpeg").write_bytes(b"a")

    images = list_case_images_by_path(image_dir)

    assert [path.name for path in images] == ["a.jpeg", "c.png"]
