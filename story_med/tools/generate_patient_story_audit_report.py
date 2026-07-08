"""生成患者故事 Agent 审核问题说明文档。"""

from __future__ import annotations

import base64
import json
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ROOT_DIR = Path("/Users/layla.zhang/workspace/patient-story-eval")
CASE_FILE = ROOT_DIR / "story_med/data/story_cases.md"
TMP_DIR = ROOT_DIR / "story_med/results/temp"
REPORT_DIR = ROOT_DIR / "story_med/results/reports"
HTML_REPORT = REPORT_DIR / "patient_story_audit_report_2026-06-24.html"
DOCX_REPORT = REPORT_DIR / "patient_story_audit_report_2026-06-24.docx"
SUMMARY_HTML_REPORT = REPORT_DIR / "patient_story_audit_report_summary_2026-06-24.html"
SUMMARY_DOCX_REPORT = REPORT_DIR / "patient_story_audit_report_summary_2026-06-24.docx"


@dataclass(frozen=True)
class CategoryExample:
    """问题分类示例。"""

    title: str
    description: str
    case_ids: List[str]


def load_case_blocks(case_file: Path) -> Dict[str, str]:
    """按 case_id 提取 Markdown 原始块。

    Args:
        case_file: 测试数据文件。

    Returns:
        case_id 到原始 Markdown 内容的映射。
    """
    text = case_file.read_text(encoding="utf-8")
    matches = re.findall(r"(## (SM_\d{3}) \| .*?)(?=\n## SM_|\Z)", text, re.S)
    return {case_id: block.strip() for block, case_id in matches}


def load_json(path: Path) -> Dict[str, Any]:
    """读取 JSON 文件。

    Args:
        path: 文件路径。

    Returns:
        JSON 对象；若文件缺失则返回空字典。
    """
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def list_case_ids() -> List[str]:
    """列出已有 summary 的 case_id。"""
    return sorted(path.name for path in TMP_DIR.glob("SM_*") if path.is_dir())


def summarize_failures(case_ids: Iterable[str]) -> Dict[str, List[str]]:
    """按失败审核项聚合 case。"""
    grouped: Dict[str, List[str]] = defaultdict(list)
    for case_id in case_ids:
        summary = load_json(TMP_DIR / case_id / "summary.json")
        for key, value in (summary.get("audit_overview") or {}).items():
            if value is False:
                grouped[key].append(case_id)
    return dict(sorted(grouped.items()))


def score_table_rows(case_ids: Iterable[str]) -> List[Dict[str, Any]]:
    """构造全量分数表。"""
    rows: List[Dict[str, Any]] = []
    for case_id in case_ids:
        summary = load_json(TMP_DIR / case_id / "summary.json")
        rows.append(
            {
                "case_id": case_id,
                "description": summary.get("description", ""),
                "score": (summary.get("scorecard") or {}).get("total_score"),
                "failed": [
                    key
                    for key, value in (summary.get("audit_overview") or {}).items()
                    if value is False
                ],
            }
        )
    rows.sort(key=lambda item: (999 if item["score"] is None else float(item["score"]), item["case_id"]))
    return rows


def image_to_data_uri(image_path: str) -> str:
    """将图片转为内联 data URI。"""
    raw = Path(image_path).read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def render_metric_section() -> str:
    """渲染评判指标说明。"""
    return """
    <h2>一、当前评判指标</h2>
    <p>当前患者故事 Agent 采用“两层制”评估：</p>
    <ol>
      <li><b>硬门槛</b>：<code>outline_passed</code>、<code>story_passed</code>、<code>image_fact_passed</code> 任一为 false，则整案不具备高分资格。</li>
      <li><b>100 分加权评分</b>：
        <ul>
          <li>Outline 事实一致性：20 分</li>
          <li>Story 事实一致性：20 分</li>
          <li>图片设计合理性：10 分</li>
          <li>图片与设计/多图一致性：10 分</li>
          <li>成图事实一致性：10 分</li>
          <li>长图结构合规：30 分</li>
        </ul>
      </li>
    </ol>
    <p>当前审核链路对应的核心判断项为：<code>outline_passed</code>、<code>story_passed</code>、<code>image_design_passed</code>、<code>image_consistency_passed</code>、<code>image_fact_passed</code>、<code>final_image_layout_passed</code>。</p>
    """


def render_overview_table(rows: List[Dict[str, Any]]) -> str:
    """渲染全量 case 总览表。"""
    table_rows = []
    for row in rows:
        failed = "、".join(row["failed"]) if row["failed"] else "无"
        table_rows.append(
            "<tr>"
            f"<td>{escape(row['case_id'])}</td>"
            f"<td>{escape(row['description'])}</td>"
            f"<td>{escape(str(row['score']))}</td>"
            f"<td>{escape(failed)}</td>"
            "</tr>"
        )
    return (
        "<h2>二、全量 Case 审核总览</h2>"
        "<table><thead><tr><th>Case</th><th>标题</th><th>总分</th><th>失败项</th></tr></thead>"
        f"<tbody>{''.join(table_rows)}</tbody></table>"
    )


def render_failure_summary(grouped: Dict[str, List[str]]) -> str:
    """渲染失败项聚合。"""
    parts = ["<h2>三、主要问题分布</h2>", "<ul>"]
    for key, case_ids in grouped.items():
        parts.append(f"<li><b>{escape(key)}</b>：{escape('、'.join(case_ids))}</li>")
    parts.append("</ul>")
    return "".join(parts)


def render_case_excerpt(case_block: str) -> str:
    """渲染病例原文数据块。"""
    return f"<pre>{escape(case_block)}</pre>"


def render_issue_list(items: List[Dict[str, Any]]) -> str:
    """渲染问题列表。"""
    if not items:
        return "<p>无详细问题条目。</p>"
    parts = ["<ul>"]
    for item in items:
        parts.append(
            "<li>"
            f"<b>{escape(str(item.get('issue_id', '')))}</b>："
            f"{escape(str(item.get('issue_description', '')))}"
            f"<br><span class='reason'>说明：{escape(str(item.get('reason', item.get('root_cause_reason', ''))))}</span>"
            "</li>"
        )
    parts.append("</ul>")
    return "".join(parts)


def render_category_examples(case_blocks: Dict[str, str]) -> str:
    """渲染问题分类与案例。"""
    examples = [
        CategoryExample(
            title="1. 医学事实与合规问题",
            description="问题通常出现在故事大纲或 Story 归纳阶段，表现为医学常识错误、疗效夸大、遗漏关键限定词，或继承原始病例中的错误陈述。",
            case_ids=["SM_001", "SM_002", "SM_014"],
        ),
        CategoryExample(
            title="2. 图片设计与多图一致性问题",
            description="问题主要体现在图片设计 Prompt 没有固定角色年龄、发型、穿着、座椅/场景等视觉锚点，导致多张图之间角色漂移。",
            case_ids=["SM_001", "SM_020", "SM_021", "SM_022"],
        ),
        CategoryExample(
            title="3. 成图渲染偏差问题",
            description="上游文本与图片设计正确，但最终成图对动作、道具数量、站位、背景细节的渲染偏离 Prompt。",
            case_ids=["SM_001", "SM_014", "SM_020", "SM_022"],
        ),
        CategoryExample(
            title="4. 长图 Layout / 结构问题",
            description="最终一图读懂常见问题包括：缺失可视化时间轴、缺失患者金句/风险警示、叙事断层，以及多余的“专家点评”板块。",
            case_ids=["SM_008", "SM_014", "SM_020", "SM_021", "SM_022"],
        ),
    ]
    parts = ["<h2>四、按问题类型的详细说明</h2>"]
    for category in examples:
        parts.append(f"<h3>{escape(category.title)}</h3>")
        parts.append(f"<p>{escape(category.description)}</p>")
        for case_id in category.case_ids:
            summary = load_json(TMP_DIR / case_id / "summary.json")
            attribution = load_json(TMP_DIR / case_id / "audit_analysis.json")
            layout_detail = summary.get("final_image_layout_detail") or {}
            image_design = summary.get("image_design") or {}
            image_consistent = summary.get("image_consistency") or {}
            root_causes = ((attribution.get("attribution") or {}).get("root_causes") or [])
            parts.append(f"<h4>{escape(case_id)} | {escape(summary.get('description', ''))}</h4>")
            parts.append(
                "<p>"
                f"<b>总分：</b>{escape(str((summary.get('scorecard') or {}).get('total_score')))}"
                f"；<b>失败项：</b>{escape('、'.join([key for key, value in (summary.get('audit_overview') or {}).items() if value is False]))}"
                "</p>"
            )
            parts.append("<p><b>病例原文测试数据</b></p>")
            parts.append(render_case_excerpt(case_blocks.get(case_id, "未找到对应测试数据。")))
            parts.append("<p><b>最终错误结果摘要</b></p>")
            parts.append(
                "<ul>"
                f"<li>图片设计审核：{escape(str(image_design.get('summary', '')))}</li>"
                f"<li>图片一致性审核：{escape(str(image_consistent.get('summary', '')))}</li>"
                f"<li>长图 Layout 审核：{escape(str((summary.get('final_image_layout') or {}).get('summary', '')))}</li>"
                f"<li>归因总结：{escape(str((attribution.get('attribution') or {}).get('summary', '')))}</li>"
                "</ul>"
            )
            if root_causes:
                parts.append("<p><b>归因明细</b></p>")
                parts.append(render_issue_list(root_causes))
            layout_issues = layout_detail.get("issues") or []
            if layout_issues:
                parts.append("<p><b>长图结构错误详情</b></p>")
                parts.append(render_issue_list(layout_issues))
            image_path = layout_detail.get("image_path")
            if image_path and Path(image_path).exists():
                parts.append("<p><b>对应最终长图</b></p>")
                parts.append(
                    f"<img class='layout-image' src='{image_to_data_uri(image_path)}' alt='{escape(case_id)} layout image' />"
                )
    return "".join(parts)


def render_conclusion() -> str:
    """渲染结论。"""
    return """
    <h2>五、阶段性结论</h2>
    <ul>
      <li>当前最稳定的文本节点是 Outline / Story 的基础事实抽取，但仍会在特定案例中出现医学常识错误、遗漏限定词和合规表达失真。</li>
      <li>当前最不稳定的节点是图片相关链路，尤其是 <code>image_consistency_passed</code> 与 <code>image_fact_passed</code>，表现为角色锚点缺失和成图渲染偏差。</li>
      <li>长图生成存在系统性结构问题：一类是结构缺失（如 SM_008），另一类是反复出现多余“专家点评”板块（如 SM_014、SM_020、SM_021、SM_022）。</li>
      <li>从归因角度看，问题主要集中在故事大纲问题、图片设计问题、成图问题，以及一图读懂生成问题四类节点。</li>
    </ul>
    """


def render_summary_html(case_blocks: Dict[str, str]) -> str:
    """构造摘要版 HTML 报告。"""
    rows = score_table_rows(list_case_ids())
    low_score_rows = [row for row in rows if row["score"] is not None and float(row["score"]) <= 65]
    top_risks = [
        ("图片一致性", "22/22 case 失败，说明角色锚点、场景锚点和跨图一致性控制是当前最普遍的问题。"),
        ("成图事实审核", "大量 case 为 blocked 0/0，说明当前逐图事实核验链路还不稳定，既影响打分，也影响问题定位。"),
        ("长图结构", "12 个 case 出现 layout 失败，主要是缺失时间轴/核心组件，或反复出现多余“专家点评”板块。"),
        ("文本合规与医学常识", "少数 case 已出现医学常识错误、疗效夸大、限定词遗漏，说明上游文本层仍需加强防护。"),
    ]
    representative_cases = ["SM_008", "SM_014", "SM_020", "SM_021", "SM_022", "SM_002"]
    case_cards: List[str] = []
    for case_id in representative_cases:
        summary = load_json(TMP_DIR / case_id / "summary.json")
        attribution = load_json(TMP_DIR / case_id / "audit_analysis.json")
        layout_detail = summary.get("final_image_layout_detail") or {}
        card_parts = [
            f"<h3>{escape(case_id)} | {escape(summary.get('description', ''))}</h3>",
            "<ul>",
            f"<li><b>总分</b>：{escape(str((summary.get('scorecard') or {}).get('total_score')))}</li>",
            f"<li><b>失败项</b>：{escape('、'.join([k for k,v in (summary.get('audit_overview') or {}).items() if v is False]))}</li>",
            f"<li><b>摘要</b>：{escape(str((attribution.get('attribution') or {}).get('summary', '')))}</li>",
            "</ul>",
        ]
        issues = layout_detail.get("issues") or []
        if issues:
            card_parts.append("<p><b>长图结构错误示例</b></p>")
            card_parts.append(render_issue_list(issues[:3]))
        image_path = layout_detail.get("image_path")
        if image_path and Path(image_path).exists():
            card_parts.append(f"<img class='layout-image' src='{image_to_data_uri(image_path)}' alt='{escape(case_id)} layout image' />")
        case_cards.append("".join(card_parts))

    low_score_table_rows = []
    for row in low_score_rows:
        low_score_table_rows.append(
            "<tr>"
            f"<td>{escape(row['case_id'])}</td>"
            f"<td>{escape(row['description'])}</td>"
            f"<td>{escape(str(row['score']))}</td>"
            f"<td>{escape('、'.join(row['failed']))}</td>"
            "</tr>"
        )

    risk_items = "".join(
        f"<li><b>{escape(title)}</b>：{escape(desc)}</li>" for title, desc in top_risks
    )
    case_section = "".join(case_cards)
    low_score_table = (
        "<table><thead><tr><th>Case</th><th>标题</th><th>总分</th><th>失败项</th></tr></thead>"
        f"<tbody>{''.join(low_score_table_rows)}</tbody></table>"
    )
    return f"""
    <html>
    <head>
      <meta charset="utf-8" />
      <title>患者故事 Agent 审核问题摘要版</title>
      <style>
        body {{ font-family: "PingFang SC", "Microsoft YaHei", sans-serif; line-height: 1.6; margin: 36px; color: #222; }}
        h1, h2, h3 {{ color: #1f3a5f; }}
        table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px; }}
        th, td {{ border: 1px solid #cfd8e3; padding: 8px; vertical-align: top; }}
        th {{ background: #eef4fb; }}
        ul {{ margin-top: 8px; }}
        .layout-image {{ width: 700px; max-width: 100%; border: 1px solid #d0d7de; margin: 8px 0 20px; }}
      </style>
    </head>
    <body>
      <h1>患者故事 Agent 审核问题摘要版</h1>
      <p>生成日期：2026-06-24</p>
      <h2>一、摘要结论</h2>
      <ul>
        <li>当前 22 个 case 中，没有完全通过所有审核项的 case。</li>
        <li>最普遍的问题集中在图片一致性、成图事实审核和长图结构。</li>
        <li>文本层总体比图片层稳定，但仍存在医学常识、限定词遗漏和合规表达失真风险。</li>
        <li>如果按优先级修复，建议先修图片一致性与长图结构，再修成图事实审核链路，最后补强文本合规拦截。</li>
      </ul>
      <h2>二、当前评判指标</h2>
      <ul>
        <li>硬门槛：outline / story / image_fact</li>
        <li>加权评分：outline 20，story 20，image_design 10，image_consistency 10，image_fact 10，final_image_layout 30</li>
      </ul>
      <h2>三、最重要的 4 类风险</h2>
      <ul>{risk_items}</ul>
      <h2>四、低分 case 清单</h2>
      {low_score_table}
      <h2>五、代表性问题案例</h2>
      {case_section}
      <h2>六、建议的修复顺序</h2>
      <ol>
        <li>先修“专家点评”板块反复出现的问题，避免长图结构系统性失分。</li>
        <li>补图片设计 Prompt 的角色统一锚点，至少固定年龄、发型、服饰、核心道具与场景。</li>
        <li>补成图事实审核链路，解决 blocked 0/0，确保逐图审核结果可用于定位问题。</li>
        <li>在大纲/Story 生成前增加医学合规拦截，重点拦截早期肺癌直接一线靶向、治愈承诺、遗漏关键限定词等问题。</li>
      </ol>
    </body>
    </html>
    """


def build_html(case_blocks: Dict[str, str]) -> str:
    """构造 HTML 报告。"""
    case_ids = list_case_ids()
    rows = score_table_rows(case_ids)
    grouped = summarize_failures(case_ids)
    return f"""
    <html>
    <head>
      <meta charset="utf-8" />
      <title>患者故事 Agent 审核问题报告</title>
      <style>
        body {{ font-family: "PingFang SC", "Microsoft YaHei", sans-serif; line-height: 1.6; margin: 36px; color: #222; }}
        h1, h2, h3, h4 {{ color: #1f3a5f; }}
        table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px; }}
        th, td {{ border: 1px solid #cfd8e3; padding: 8px; vertical-align: top; }}
        th {{ background: #eef4fb; }}
        code {{ background: #f5f7fa; padding: 2px 4px; }}
        pre {{ white-space: pre-wrap; word-break: break-word; background: #f7f9fc; border: 1px solid #dbe4ef; padding: 12px; }}
        .layout-image {{ width: 700px; max-width: 100%; border: 1px solid #d0d7de; }}
        .reason {{ color: #555; }}
      </style>
    </head>
    <body>
      <h1>患者故事 Agent 当前问题、评判指标与归因报告</h1>
      <p>生成日期：2026-06-24</p>
      {render_metric_section()}
      {render_overview_table(rows)}
      {render_failure_summary(grouped)}
      {render_category_examples(case_blocks)}
      {render_conclusion()}
    </body>
    </html>
    """


def convert_html_to_docx(html_path: Path, docx_path: Path) -> None:
    """使用 textutil 转换为 docx。"""
    subprocess.run(
        [
            "/usr/bin/textutil",
            "-convert",
            "docx",
            str(html_path),
            "-output",
            str(docx_path),
        ],
        check=True,
    )


def main() -> None:
    """执行报告生成。"""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    case_blocks = load_case_blocks(CASE_FILE)
    html = build_html(case_blocks)
    HTML_REPORT.write_text(html, encoding="utf-8")
    convert_html_to_docx(HTML_REPORT, DOCX_REPORT)
    summary_html = render_summary_html(case_blocks)
    SUMMARY_HTML_REPORT.write_text(summary_html, encoding="utf-8")
    convert_html_to_docx(SUMMARY_HTML_REPORT, SUMMARY_DOCX_REPORT)
    print(HTML_REPORT)
    print(DOCX_REPORT)
    print(SUMMARY_HTML_REPORT)
    print(SUMMARY_DOCX_REPORT)


if __name__ == "__main__":
    main()
