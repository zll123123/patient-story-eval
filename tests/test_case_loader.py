"""患者故事 Markdown 用例加载测试。"""

from __future__ import annotations

from pathlib import Path

from story_med.services.case_loader import load_story_cases


def test_load_story_cases_from_markdown(tmp_path: Path) -> None:
    """验证可从 Markdown 文件加载 case。"""
    case_file = tmp_path / "story_cases.md"
    case_file.write_text(
        """# Story Cases

## SM_TEST | Markdown 用例

### creative_brief

brief text

### case_facts

facts text

### hard_rules

```json
{
  "disease": {
    "expected": "肺癌"
  }
}
```
""",
        encoding="utf-8",
    )

    cases = load_story_cases(case_file)

    assert len(cases) == 1
    assert cases[0].case_id == "SM_TEST"
    assert cases[0].description == "Markdown 用例"
    assert cases[0].creative_brief == "brief text"
    assert cases[0].case_facts == "facts text"
    assert cases[0].hard_rules["disease"]["expected"] == "肺癌"


def test_load_story_cases_prefers_case_parse(tmp_path: Path) -> None:
    """验证 clinical_case 中的 case_parse 会优先作为病例事实。"""
    case_file = tmp_path / "clinical_case.yaml"
    case_file.write_text(
        """clinical_cases:\n  - case_id: SM_TEST\n    title: 临床标题\n    creative_brief: brief\n    case_parse: parsed facts\n    hard_rules:\n      disease:\n        expected: 肺癌\n""",
        encoding="utf-8",
    )
    from story_med.services import clinical_case_config as clinical_case_service

    clinical_case_service.DEFAULT_CLINICAL_CASE_FILE = case_file  # type: ignore[assignment]

    cases = load_story_cases()

    assert cases[0].case_facts == "parsed facts"
