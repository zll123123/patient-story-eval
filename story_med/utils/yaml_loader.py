"""YAML 读取工具。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


def load_yaml_file(file_path: Path) -> Dict[str, Any]:
    """读取 YAML 文件并解析为字典。

    Args:
        file_path: YAML 文件路径。

    Returns:
        Dict[str, Any]: 解析后的字典数据。

    Raises:
        FileNotFoundError: 当文件不存在时抛出。
        ValueError: 当 YAML 根节点不是字典时抛出。
    """
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    data = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML 根节点必须是字典: {file_path}")
    return data

