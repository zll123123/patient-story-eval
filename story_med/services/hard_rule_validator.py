"""患者故事硬规则校验服务。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from story_med.models.case_model import StoryCaseConfig


@dataclass
class HardRuleCheckResult:
    """单个硬规则字段校验结果。"""

    field: str
    passed: bool
    expected: Any
    evidence: List[str]
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "field": self.field,
            "passed": self.passed,
            "expected": self.expected,
            "evidence": self.evidence,
            "reason": self.reason,
        }


def validate_hard_rules(case: StoryCaseConfig, outline_text: str, story_text: str) -> Dict[str, Any]:
    """分别校验大纲和正文是否满足硬规则。

    Args:
        case: 患者故事用例。
        outline_text: 大纲文本。
        story_text: 正文文本。

    Returns:
        Dict[str, Any]: 硬规则校验报告。
    """
    outline_results = _validate_text(case.hard_rules, outline_text)
    story_results = _validate_text(case.hard_rules, story_text)
    return {
        "case_id": case.case_id,
        "passed": _all_passed(outline_results) and _all_passed(story_results),
        "outline": {
            "passed": _all_passed(outline_results),
            "checks": [item.to_dict() for item in outline_results],
        },
        "story": {
            "passed": _all_passed(story_results),
            "checks": [item.to_dict() for item in story_results],
        },
    }


def write_hard_rule_report(report: Dict[str, Any], output_path: Path) -> None:
    """写入硬规则校验报告。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _validate_text(hard_rules: Dict[str, Any], text: str) -> List[HardRuleCheckResult]:
    """校验单份文本。"""
    checks = {
        "disease": _check_disease,
        "disease_subtype": _check_disease_subtype,
        "stage": _check_stage,
        "gender": _check_gender,
        "age_group": _check_age_group,
        "treatments": _check_treatments,
        "outcome": _check_outcome,
    }
    results: List[HardRuleCheckResult] = []
    for field, check_func in checks.items():
        rule = _normalize_rule(hard_rules.get(field))
        results.append(check_func(rule, text))
    return results


def _normalize_rule(rule: Any) -> Dict[str, Any]:
    """标准化单个硬规则字段。"""
    if not isinstance(rule, dict):
        return {}
    if isinstance(rule.get("field"), dict):
        return dict(rule["field"])
    return dict(rule)


def _all_passed(results: List[HardRuleCheckResult]) -> bool:
    """判断一组硬规则是否全部通过。"""
    return all(item.passed for item in results)


def _check_disease(rule: Dict[str, Any], text: str) -> HardRuleCheckResult:
    """校验核心疾病。"""
    expected = str(rule.get("expected") or "")
    consistent_terms = [expected, "左肺上叶占位", "左肺", "肺上叶腺癌", "肺癌", "腺癌"]
    conflict_terms = ["右肺上叶腺癌", "胃癌", "肝癌", "乳腺癌", "结直肠癌", "胰腺癌", "小细胞肺癌"]
    evidence = _find_terms(text, consistent_terms + conflict_terms)
    conflicts = _find_terms(text, conflict_terms)
    return _build_result("disease", expected, evidence, conflicts)


def _check_disease_subtype(rule: Dict[str, Any], text: str) -> HardRuleCheckResult:
    """校验疾病亚型。"""
    expected = dict(rule.get("expected") or {})
    pathology = str(expected.get("pathology") or "")
    molecular = str(expected.get("molecular") or "")
    consistent_terms = [pathology, molecular, "EGFR", "19号外显子缺失"]
    conflict_terms = ["鳞癌", "小细胞癌", "ALK阳性", "ROS1阳性", "KRAS突变", "L858R", "20号外显子插入"]
    evidence = _find_terms(text, consistent_terms + conflict_terms)
    conflicts = _find_terms(text, conflict_terms)
    return _build_result("disease_subtype", expected, evidence, conflicts)


def _check_stage(rule: Dict[str, Any], text: str) -> HardRuleCheckResult:
    """校验疾病阶段。"""
    expected = str(rule.get("expected") or "")
    consistent_terms = [expected, "IB期", "cT1cN0M0"]
    evidence = _find_terms(text, consistent_terms) + _find_stage_terms(text)
    conflicts = [term for term in _find_stage_terms(text) if term not in {"IB期", "ⅠB期", "1B期"}]
    conflicts.extend(_find_terms(text, ["cT2", "cT3", "cT4", "N1", "N2", "N3", "M1"]))
    return _build_result("stage", expected, _unique(evidence), _unique(conflicts))


def _check_gender(rule: Dict[str, Any], text: str) -> HardRuleCheckResult:
    """校验性别。"""
    expected = str(rule.get("expected") or "")
    female_terms = ["女性", "女，", "女，52岁", "女教师", "她"]
    male_conflicts = ["男性", "男，", "男老师", "他。", "他，"]
    evidence = _find_terms(text, female_terms + male_conflicts)
    conflicts = _find_terms(text, male_conflicts)
    return _build_result("gender", expected, evidence, conflicts)


def _check_age_group(rule: Dict[str, Any], text: str) -> HardRuleCheckResult:
    """校验年龄段。"""
    expected = str(rule.get("expected") or "")
    age_terms = _find_age_terms(text)
    consistent_terms = _find_terms(text, ["50-59岁", "五十", "50多岁"])
    evidence = _unique(age_terms + consistent_terms)
    conflicts = [term for term in age_terms if not _is_expected_age(term)]
    return _build_result("age_group", expected, evidence, conflicts)


def _check_treatments(rule: Dict[str, Any], text: str) -> HardRuleCheckResult:
    """校验核心治疗方式。"""
    expected = list(rule.get("expected") or [])
    consistent_terms = ["奥希替尼", "80mg", "QD", "一天一次", "1级皮疹", "1级甲沟炎", "对症处理"]
    conflict_terms = ["吉非替尼", "厄洛替尼", "阿美替尼", "伏美替尼", "化疗", "放疗", "免疫治疗", "手术切除"]
    evidence = _find_terms(text, consistent_terms + conflict_terms)
    conflicts = _find_treatment_conflicts(text, conflict_terms)
    return _build_result("treatments", expected, evidence, conflicts)


def _check_outcome(rule: Dict[str, Any], text: str) -> HardRuleCheckResult:
    """校验当前疾病状态。"""
    expected = str(rule.get("expected") or "")
    consistent_terms = ["用药14个月", "病情稳定", "恢复正常工作", "回到讲台", "部分缓解", "持续PR"]
    conflict_terms = ["治愈", "完全缓解", "CR", "根治", "疾病进展", "死亡"]
    evidence = _find_terms(text, consistent_terms + conflict_terms)
    conflicts = _find_terms(text, conflict_terms)
    return _build_result("outcome", expected, evidence, conflicts)


def _build_result(
    field: str,
    expected: Any,
    evidence: List[str],
    conflicts: List[str],
) -> HardRuleCheckResult:
    """构建硬规则结果。"""
    passed = not conflicts
    reason = _build_reason(evidence, conflicts)
    return HardRuleCheckResult(
        field=field,
        passed=passed,
        expected=expected,
        evidence=evidence,
        reason=reason,
    )


def _build_reason(evidence: List[str], conflicts: List[str]) -> str:
    """生成硬规则判定原因。"""
    if conflicts:
        return f"提及但不一致: {', '.join(conflicts)}"
    if evidence:
        return "提及且一致"
    return "未提及，按规则通过"


def _find_terms(text: str, terms: List[str]) -> List[str]:
    """返回文本中命中的关键词。"""
    return [term for term in terms if term and term in text]


def _find_treatment_conflicts(text: str, terms: List[str]) -> List[str]:
    """抽取真实治疗冲突，过滤否定、类比和泛化描述。"""
    conflicts: List[str] = []
    for term in terms:
        if term not in text:
            continue
        if _is_non_actual_treatment_context(text, term):
            continue
        conflicts.append(term)
    return conflicts


def _is_non_actual_treatment_context(text: str, term: str) -> bool:
    """判断治疗词是否处于非真实接受治疗语境。"""
    index = text.find(term)
    start = max(index - 8, 0)
    end = min(index + len(term) + 8, len(text))
    context = text[start:end]
    markers = ["比起", "相比", "不同于", "没有", "未接受", "无需", "不是", "而不是"]
    return any(marker in context for marker in markers)


def _find_stage_terms(text: str) -> List[str]:
    """抽取文本中的疾病分期表达。"""
    pattern = r"(?:Ⅰ|Ⅱ|Ⅲ|Ⅳ|I|II|III|IV|1|2|3|4)[ABC]?期"
    return re.findall(pattern, text)


def _find_age_terms(text: str) -> List[str]:
    """抽取文本中的年龄表达。"""
    return re.findall(r"\d{2}岁", text)


def _is_expected_age(age_term: str) -> bool:
    """判断年龄是否落在预期年龄段内。"""
    age = int(age_term.replace("岁", ""))
    return 50 <= age <= 59


def _unique(items: List[str]) -> List[str]:
    """按原始顺序去重。"""
    return list(dict.fromkeys(items))
