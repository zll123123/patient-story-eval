# 患者故事 Agent 评测

## 业务流程
这个流程对应 Bruno 里的 5 个接口：
1. `POST /api/session`
2. `POST /api/{session_id}/outline`，请求体包含 `creative_brief` 和 `case_facts`
3. `POST /api/{session_id}/story`，请求体包含 `creative_brief` 和 `case_facts`
4. `POST /api/{session_id}/images`
5. `POST /api/{session_id}/generate`

适配层会把每一步的原始响应、归一化响应和 `session_id` 一起保存。`outline`、`story`、`images` 和 `generate` 返回的 OSS 链接会被下载到本地，方便后续评测直接读取文件。

## 目录说明
- `config/`：运行配置与环境变量
- `data/`：YAML 测试数据
- `clients/`：HTTP 请求封装
- `adapters/`：患者故事 agent 适配层
- `models/`：测试用例与结果模型
- `services/`：用例加载与结果落盘
- `evals/`：pytest / DeepEval 执行入口
- `docs/`：指标说明

## 用例数据
硬规则字段模板放在 `story_med/data/hard_rule_fields.yaml`，用于统一管理需要抽取和对比的字段、中文含义和值类型。

预置 case 放在 `story_med/data/story_cases.yaml`，其中：
- `creative_brief`：生成风格与内容要求
- `case_facts`：患者原始事实
- `hard_rules`：每条 case 对应的硬规则预期值

当前已内置的硬规则字段包括：
- `disease`
- `disease_subtype`
- `stage`
- `gender`
- `age_group`
- `treatments`
- `outcome`

## 运行方式
首次运行先安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

只验证适配器封装，不请求远程接口：

```bash
PYTHONPATH=. python3 -m pytest story_med/evals/test_patient_story_agent_unit.py -q
```

在仓库根目录执行单条真实链路：

```bash
PYTHONPATH=. python3 -m pytest story_med/evals/test_patient_story_agent.py -q
```

如果你要用 DeepEval CLI：

```bash
PYTHONPATH=. deepeval test run story_med/evals/test_patient_story_agent.py
```

如果你要用统一的 Deepeval 双模式评估入口：

说明：
- 同一个测试入口文件，但每个 case 会作为一个独立 pytest item 上报到 Deepeval / Confident AI
- `STORY_MED_CASE_IDS` 支持用 `,`、`;`、`|` 分隔多个 case id

```bash
STORY_MED_RUN_DEEPEVAL_PIPELINE=true \
STORY_MED_DEEPEVAL_MODE=full_pipeline \
STORY_MED_LLM_ENV_FILE=/path/to/dev.env \
PYTHONPATH=. deepeval test run story_med/evals/test_patient_story_deepeval_pipeline.py
```

2. 只基于已有 `results/assets` 重跑审核和打分

```bash
STORY_MED_RUN_DEEPEVAL_PIPELINE=true \
STORY_MED_DEEPEVAL_MODE=audit_only \
STORY_MED_LLM_ENV_FILE=/path/to/dev.env \
PYTHONPATH=. deepeval test run story_med/evals/test_patient_story_deepeval_pipeline.py
```

常用可选参数：

- `STORY_MED_CASE_IDS=SM_001,SM_002`
  只跑指定 case
- `STORY_MED_CASE_IDS=SM_001;SM_002|SM_003`
  同样有效，可混用多种分隔符
- `STORY_MED_PIPELINE_INCLUDE_VISUAL_STEPS=true|false`
  仅在 `full_pipeline` 模式下生效，控制是否重跑图片生成接口
- `STORY_MED_RUN_AUDIT_ATTRIBUTION=true`
  在审核和打分后追加归因步骤

统一汇总会输出到：

```text
story_med/tmp/deepeval_patient_story_summary.json
```

批量跑种子 case 到硬规则抽取/对比阶段：

```bash
STORY_MED_RUN_HARD_RULE_PIPELINE=true \
STORY_MED_LLM_ENV_FILE=/path/to/dev.env \
PYTHONPATH=. python3 -m pytest story_med/evals/test_patient_story_hard_rule_pipeline.py -q
```

默认会调用真实患者故事 agent，执行到 `outline` 和 `story` 后再调用 LLM prompt 做字段抽取和对比。若外部 agent 暂不可用，只想验证 case、prompt 和对比链路，可以显式使用 `case_facts` 源模式：

```bash
STORY_MED_RUN_HARD_RULE_PIPELINE=true \
STORY_MED_PIPELINE_SOURCE_MODE=case_facts \
STORY_MED_LLM_ENV_FILE=/path/to/dev.env \
PYTHONPATH=. python3 -m pytest story_med/evals/test_patient_story_hard_rule_pipeline.py -q
```

只跑指定 case：

```bash
STORY_MED_RUN_HARD_RULE_PIPELINE=true \
STORY_MED_CASE_IDS=SM_002,SM_003 \
STORY_MED_LLM_ENV_FILE=/path/to/dev.env \
PYTHONPATH=. python3 -m pytest story_med/evals/test_patient_story_hard_rule_pipeline.py -q
```

评估最近一次真实链路生成的图片：

```bash
STORY_MED_RUN_IMAGE_COMPARE=true \
STORY_MED_VISION_API_KEY=<dashscope_api_key> \
PYTHONPATH=. python3 -m pytest story_med/evals/test_patient_story_image_compare.py -q
```

默认视觉模型配置已切到阿里云百炼 OpenAI 兼容接口：

- `vision_base_url=https://dashscope.aliyuncs.com/compatible-mode/v1`
- `vision_model=qwen3.7-plus`
- `api_key` 会按以下优先级读取：`STORY_MED_VISION_API_KEY` > `DASHSCOPE_API_KEY` > `STORY_MED_LLM_API_KEY` > `CSL_LLM_API_KEY` > `OPENAI_API_KEY`

如果直接复用本地百炼 Key，可这样执行：

```bash
STORY_MED_RUN_IMAGE_COMPARE=true \
DASHSCOPE_API_KEY=<dashscope_api_key> \
PYTHONPATH=. python3 -m pytest story_med/evals/test_patient_story_image_compare.py -q
```

如果使用本地 NHTAI 多模态网关：

```bash
STORY_MED_RUN_IMAGE_COMPARE=true \
STORY_MED_VISION_PROVIDER=nhtai \
STORY_MED_VISION_ENV_FILE=/path/to/.env \
STORY_MED_VISION_MODEL=qwen2.5-vl-72b-instruct \
PYTHONPATH=. python3 -m pytest story_med/evals/test_patient_story_image_compare.py -q
```

## 输出
运行结果会写入：

```text
story_med/results/patient_story_run.json
```

里面包含：
- `session_response`
- `outline_response`
- `story_response`
- `images_response`
- `final_image_response`
- `downloaded_assets`
- 每一步的原始请求与响应

如果接口超时或失败，结果文件仍会写入已完成步骤，并通过 `failed_step` 标记失败位置。

OSS 资源会保存到：

```text
story_med/results/assets/{case_id}/{session_id}/{step_name}/
```

硬规则抽取和对比中间结果会保存到：

```text
story_med/tmp/{case_id}/
```

图片评估结果会保存到：

```text
story_med/tmp/{case_id}/image_compare_result.json
```
