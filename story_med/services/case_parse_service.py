"""病例解析产物处理服务。"""

from __future__ import annotations

from typing import Any, Dict, List

from story_med.config.settings import RESULTS_DIR


def normalize_case_parse_text(case_id: str, history: Dict[str, Any]) -> str:
    """将病例解析 history 转成可复用的病例事实文本。"""
    messages = history.get("messages") or []
    lines: List[str] = [f"# {case_id} 病例解析", ""]
    for item in messages:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if "病例解析完成" in content:
            lines.append(content)
            break
    return "\n".join(lines).strip() + "\n"


def load_case_parse_text(case_id: str, session_id: str) -> str:
    """读取指定病例最近产出的解析文本。"""
    case_parse_path = RESULTS_DIR / "assets" / case_id / session_id / "case_parse" / "case_parse.md"
    if case_parse_path.exists():
        return case_parse_path.read_text(encoding="utf-8")
    return ""
