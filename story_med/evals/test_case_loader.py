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
