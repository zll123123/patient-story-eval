"""患者故事 Markdown 用例加载测试。"""

from __future__ import annotations

from pathlib import Path

from story_med.services.yaml_case_service import load_story_cases


def test_load_story_cases_prefers_case_parse(tmp_path: Path) -> None:
    """验证 clinical_case 中的 case_parse 会优先作为病例事实。"""
    case_file = tmp_path / "clinical_case.yaml"
    case_file.write_text(
        """clinical_cases:\n  - case_id: SM_TEST\n    title: 临床标题\n    creative_brief: brief\n    case_parse: parsed facts\n    hard_rules:\n      disease:\n        expected: 肺癌\n""",
        encoding="utf-8",
    )
    cases = load_story_cases(case_file)

    assert cases[0].case_facts == "parsed facts"
