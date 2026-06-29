# 患者故事 Agent 评测

## 当前业务流程

当前评测链路以病例图片为输入，分两段执行：

1. 病例图片提取基准：`story_med/img/{image_dir}/` -> `story_med/output/{image_dir}/clinical_extract.md`
2. 患者故事生成和审核：调用图片病例版 Agent 生成大纲、Story、配图、长图，然后执行硬规则对比、图片审核、Layout 审核、归因、打分和 DeepEval / Confident AI 上报

`clinical_extract.md` 是测试侧病例事实基准。后续审核需要病例事实输入时，只读取：

```text
story_med/output/{image_dir}/clinical_extract.md
```

如果该文件不存在，审核直接失败，不会 fallback 到 `case_facts` 或病例解析服务输出。

## 关键输入

测试 case 统一维护在：

```text
story_med/data/clinical_case.yaml
```

每条 case 至少包含：

```yaml
clinical_cases:
  - case_id: SM_003
    title: 卢肺癌病例
    creative_brief: 生成风格要求
    image_dir: "卢-肺癌"
    hard_rules:
      demographics:
        expected:
          value:
            gender: "女"
            age: 71
```

病例图片目录由 `image_dir` 指定：

```text
story_med/img/卢-肺癌/入院检查-CT.jpg
story_med/img/卢-肺癌/病理检查.jpg
```

硬规则字段模板维护在：

```text
story_med/data/hard_rule_fields.yaml
```

当前 hardrule 只维护病例事实红线字段：

- `demographics`
- `primary_diagnosis`
- `visible_signs`
- `treatment_timeline`
- `key_metrics`
- `observed_outcomes`

## 第一步：提取病例基准

新增病例图片后，先运行 clinical extract。该步骤只生成病例事实基准，不调用患者故事 Agent。

```bash
PYTHONPATH=. python3 story_med/tools/run_clinical_extract.py \
  --image-dir 卢-肺癌
```

输出位置：

```text
story_med/output/卢-肺癌/clinical_extract.md
story_med/output/卢-肺癌/clinical_extract.json
```

说明：

- `clinical_extract.md`：后续审核实际使用的病例事实基准。
- `clinical_extract.json`：包含图片目录、图片列表、原始输出等元信息，便于程序追踪。
- 后续重跑完整审核时，不会自动重跑 clinical extract。

## 第二步：补测试数据

将新病例补到 `story_med/data/clinical_case.yaml`：

- `case_id`：如 `SM_003`
- `image_dir`：必须等于 `story_med/img/` 下的病例图片文件夹名
- `creative_brief`：生成风格要求
- `hard_rules.expected.value`：从 `clinical_extract.md` 中维护少量病例红线事实

原则：

- 只维护病例里明确写出的事实。
- 不维护广告法、合规禁用词等非病例事实。
- 不确定的字段不要硬填。

## 第三步：完整生成、审核、归因、打分并上报

以当前已有的 case2 和 case3 为例：

```bash
python3 story_med/tools/run_patient_story_deepeval.py \
  --mode image_case_pipeline \
  --case-ids "SM_002,SM_003" \
  --identifier patient-story-sm002-sm003-full-audit
```

这个命令会执行：

- 指定 `--case-ids` 时只运行这些病例，不清空历史结果目录
- 按 `clinical_case.yaml` 的 `image_dir` 读取病例图片
- 调用 `story_med/adapters/patient_case_image_agent.py` 生成大纲、Story、配图、最终长图
- 对大纲和 Story 先抽取 hardrule 结构，再和 `clinical_case.yaml` 的 expected 对比
- 使用 `clinical_extract.md` 执行图片设计审核、图片事实一致性审核、长图 Layout 审核
- 执行归因 `audit_analysis`
- 计算 summary 和 scorecard
- 通过 DeepEval 上报 Confident AI

执行前必须确认：

```text
story_med/output/卢胜-肝癌/clinical_extract.md
story_med/output/卢-肺癌/clinical_extract.md
```

如果要只跑单个 case：

```bash
python3 story_med/tools/run_patient_story_deepeval.py \
  --mode image_case_pipeline \
  --case-ids SM_003 \
  --identifier patient-story-sm003-full-audit
```

`--case-ids` 支持 `,`、`;`、`|` 分隔多个 case：

```bash
python3 story_med/tools/run_patient_story_deepeval.py \
  --mode image_case_pipeline \
  --case-ids "SM_001;SM_002|SM_003"
```

如果要全量重跑所有 case，省略 `--case-ids`：

```bash
python3 story_med/tools/run_patient_story_deepeval.py \
  --mode image_case_pipeline \
  --identifier patient-story-all-full-audit
```

只有这种全量重跑会在开始前清空：

- `story_med/results/temp`
- `story_med/results/assets`
- `story_med/results/runs`

## 只重跑审核和打分

如果已有 `story_med/results/assets/{case_id}/{session_id}/` 生成产物，只想重跑审核、归因、打分和上报：

```bash
python3 story_med/tools/run_patient_story_deepeval.py \
  --mode audit_only \
  --case-ids "SM_002,SM_003" \
  --identifier patient-story-sm002-sm003-audit-only
```

注意：

- `audit_only` 不会重跑 Agent 生成接口。
- `audit_only` 仍然要求对应 case 的 `clinical_extract.md` 已存在。
- `audit_only` 使用当前 `results/assets` 中最新 session。

## DeepEval / Confident AI

统一入口 `story_med/tools/run_patient_story_deepeval.py` 内部会调用：

```text
deepeval test run tests/test_patient_story_deepeval_pipeline.py
```

上报 Confident AI 前，需先完成登录：

```bash
deepeval login
```

本地每个 case 会作为独立 pytest item 上报。可通过 `--identifier` 标记本次运行。

## 输出目录

Agent 生成产物：

```text
story_med/results/assets/{case_id}/{session_id}/
```

包括：

- `case_parse/case_parse.md`：病例解析服务输出，仅用于链路归因，不作为评估基准
- `generate_outline/outline.md`
- `generate_story/story.md`
- `generate_images/image_design.json`
- `generate_images/*.png`
- `generate_final_image/index.html`
- `generate_final_image/index.png`

审核和汇总产物：

```text
story_med/results/temp/{case_id}/
```

包括：

- `outline_extracted_fields.json`
- `outline_hard_rule_compare.json`
- `story_extracted_fields.json`
- `story_hard_rule_compare.json`
- `image_design_validation.json`
- `image_consistant_validation.json`
- `image_fact_validation.json`
- `final_image_layout_validation.json`
- `audit_analysis.json`
- `summary.json`

统一 DeepEval 汇总：

```text
story_med/results/temp/deepeval_patient_story_summary.json
```

单次 Agent 运行原始记录：

```text
story_med/results/runs/{case_id}/{session_id}.json
story_med/results/patient_story_run.json
```

## 配置

普通配置：

```text
story_med/config/config.yaml
story_med/config/vision_config.yaml
story_med/config/llm_config.yaml
```

敏感信息：

```text
story_med/config/dev.env
```

视觉模型默认使用百炼 OpenAI 兼容接口：

- `vision_base_url=https://dashscope.aliyuncs.com/compatible-mode/v1`
- `vision_model=qwen3.7-plus`
- API Key 读取优先级：`STORY_MED_VISION_API_KEY` > `DASHSCOPE_API_KEY` > `STORY_MED_LLM_API_KEY` > `CSL_LLM_API_KEY` > `OPENAI_API_KEY`

## 常用检查命令

确认 case 能被加载：

```bash
PYTHONPATH=. python3 - <<'PY'
from story_med.services.case_loader import load_story_cases
print([(case.case_id, case.image_dir) for case in load_story_cases()])
PY
```

确认 clinical extract 已存在：

```bash
find story_med/output -maxdepth 2 -name clinical_extract.md | sort
```

跑核心单测：

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_clinical_extract_pipeline.py \
  tests/test_patient_story_image_compare.py \
  tests/test_audit_attribution_pipeline.py \
  tests/test_hard_rule_llm_pipeline.py \
  -q
```
