# 患者故事评测代码结构

## 顶层分层

```text
story_med/
├── executors/     # 外部患者故事任务执行层
├── clients/       # 外部接口 / 模型客户端
├── commands/      # 运行入口
├── config/        # YAML / ENV 配置
├── data/          # 测试 case 与硬规则模板
├── docs/          # 指标与覆盖说明
├── evals/         # DeepEval 指标定义
├── img/           # 病例原始图片
├── models/        # 数据模型
├── baselines/     # clinical_extract 基线输出
├── prompts/       # 审核与生成提示词
├── results/       # 运行产物、审核结果、报告
├── services/      # 核心业务服务
├── tools/         # 辅助脚本（非主入口）
└── utils/         # 通用工具
```

## 关键目录说明

### `clients/`

- `base/http_client.py`
  - 通用 HTTP 会话、统一响应对象、基础请求封装
- `llm/llm_client.py`
  - 文本模型调用封装
- `llm/multimodal_llm_client.py`
  - 多模态模型调用封装
- `agent_api/agent_task_client.py`
  - 中台任务接口客户端

### `executors/`

- `patient_story_generation_executor.py`
  - 患者故事生成执行器
- `patient_story_edit_executor.py`
  - 患者故事编辑执行器
- `content_hub_runtime.py`
  - stream/history 轮询与耗时记录公共能力
- `content_hub_history.py`
  - 内容中台 history 归一化与产物解析

### `commands/`

- `run_clinical_extract.py`
  - 运行病例图片解析，生成 `clinical_extract.md/json`
- `run_patient_story_deepeval.py`
  - 运行患者故事生成 / 审核 / 归因 / 打分 / DeepEval 上报
- `run_story_compliance_audit.py`
  - 单独执行 story 合规审核
- `run_edit_dialogue_case.py`
  - 运行多轮编辑及编辑评估

### `config/`

- `settings.py`
  - 全局路径与默认配置入口
- `app_config.py`
  - 应用配置、文本模型配置、多模态模型配置统一装配入口
- `config.yaml`
  - 稳定配置源，主要保存 `active_env`、结果路径、DeepEval 配置和少量非环境参数

### `envs/`

- `dev.env`
  - 本地环境配置，保存模型地址、开关、超时、中台地址、账号和密钥

### `data/`

- `clinical_case.yaml`
  - 患者故事生成评测 case
- `edit_dialogue_cases.yaml`
  - 多轮编辑 case
- `hard_rule_fields.yaml`
  - 硬规则字段模板
- `intend_cases.yaml`
  - 编辑意图模板

### `evals/`

- `patient_story_deepeval_metrics.py`
  - DeepEval 指标与分数聚合逻辑

### `prompts/`

- `clinical_extract.md`
  - 病例图片结构化提取
- `hard_rule_field_extraction.md`
  - 从大纲 / Story 抽取审核字段
- `hard_rule_semantic_compare.md`
  - 硬规则语义对比
- `image_design_validate.md`
  - 图片设计审核
- `image_consistency_validate.md`
  - 图片间 / 设计间一致性审核
- `image_fact_consistency_validate.md`
  - 图片与病例事实一致性审核
- `final_image_layout_validate.md`
  - 长图结构审核
- `story_compliance_validate.md`
  - Story 合规审核
- `audit_analysis.md`
  - 生成链路问题归因
- `edit_coverage_validate.md`
  - 编辑覆盖评估
- `edit_dialogue_generator.md`
  - 多轮编辑对话生成

### `utils/`

- `yaml_loader.py`
  - YAML 统一加载
- `artifact_cleaner.py`
  - 清理 `results/` 产物

## `services/` 分组

### `services/clinical_case_preparation/`

- `yaml_case_service.py`
  - 读取 `clinical_case.yaml` / `edit_dialogue_cases.yaml`
- `case_image_input.py`
  - 读取病例图片目录
- `case_parse_service.py`
  - 处理病例解析文本
- `clinical_extract_baseline_service.py`
  - 读取 `baselines/{image_dir}/clinical_extract.md`
- `clinical_extract_pipeline.py`
  - 执行病例图片解析并落盘

### `services/story_generation_evaluation/`

- `patient_story_deepeval_pipeline.py`
  - 生成链路主编排
- `hard_rule_llm_pipeline.py`
  - 大纲 / Story 硬规则抽取与对比
- `story_compliance_pipeline.py`
  - Story 合规审核
- `image_audit_pipeline.py`
  - 图片设计、一致性、事实一致性、长图 layout 审核汇总
- `final_image_layout_audit_service.py`
  - 长图结构审核实现
- `summary_pipeline.py`
  - 汇总 case 审核结果与分数
- `audit_analysis_service.py`
  - 生成链路问题归因

### `services/story_edit_evaluation/`

- `story_adjustment_pipeline.py`
  - 单轮编辑执行
- `edit_coverage_service.py`
  - 编辑结果覆盖评估
- `edit_dialogue_pipeline.py`
  - 多轮编辑编排
- `edit_dialogue_analysis_pipeline.py`
  - 多轮编辑失败归因

## 当前主链路

### 生成评测

```text
clinical_case.yaml
  -> clinical_case_preparation
  -> executors/patient_story_generation_executor.py
  -> story_generation_evaluation/patient_story_deepeval_pipeline.py
  -> results/assets + results/story_audits
```

### 编辑评测

```text
edit_dialogue_cases.yaml
  -> story_edit_evaluation/edit_dialogue_pipeline.py
  -> story_adjustment_pipeline.py
  -> edit_coverage_service.py
  -> edit_dialogue_analysis_pipeline.py
```

## 当前保留但非主入口

- `tools/generate_patient_story_audit_report.py`
  - 报告生成辅助脚本
  - 不是日常执行主入口
