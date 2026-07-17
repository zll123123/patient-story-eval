# 编辑链路重跑清理设计

## 1. 背景

当前编辑执行器只在每个轮次开始时清理当前轮目录，无法保证一次全量编辑重跑前已经删除该编辑用例的全部历史产物。历史审核结果和旧产物可能在本轮失败时继续存在，造成结果误读。

## 2. 目标

- 全量编辑重跑前，清理所有待执行编辑用例的历史编辑产物。
- 指定编辑用例重跑前，只清理指定用例的历史产物。
- 不删除原始患者故事生成产物和病例基线。
- 每次执行结束后，编辑结果目录只对应本次运行。
- `audit-only` 只审核已有产物，不触发清理。

## 3. 清理边界

### 3.1 需要清理

以编辑对话 case ID 为单位，例如 `EDG_001`：

```text
story_med/results/edit_runs/EDG_001/
story_med/results/assets/EDG_001/
story_med/results/edit_audits/EDG_001/
```

这三个目录分别保存编辑执行事件和结果、编辑生成的文件、逐轮审核和归因结果。

### 3.2 禁止清理

以下原始生成产物必须保留，作为编辑流程的输入：

```text
story_med/results/assets/SM_001/
story_med/results/generation_runs/SM_001/
story_med/results/story_audits/SM_001/
story_med/results/assets/*/generate_final_image/
```

清理函数必须只接收并校验 `EDG_` 开头的编辑 case ID，避免误删 `SM_*` 原始病例目录。

## 4. 执行策略

### 4.1 全量编辑

入口：`patient-story-edit-full`

执行顺序：

```text
读取 edit_dialogue_cases.yaml
    -> 解析全部 EDG case ID
    -> 清理每个 EDG case 的 edit_runs/assets/edit_audits
    -> 按 case 串行执行多轮编辑
    -> 每轮等待当前 turn 完成并落盘
    -> 执行覆盖审核
    -> 生成编辑归因
```

清理发生在第一个编辑 Agent 调用之前，且每个 `EDG_*` case 只清理一次。

### 4.2 指定编辑 case

入口支持：

```bash
uv run story-med patient-story-edit-full --case-ids "EDG_001,EDG_003"
```

只清理 `EDG_001` 和 `EDG_003`，其他编辑 case 的历史结果不受影响。

### 4.3 仅审核已有结果

入口：`patient-story-edit-audit`

不执行清理，直接读取已有：

```text
edit_runs/
assets/
edit_audits/
```

这样可以在不重跑上游编辑 Agent 的情况下重新执行覆盖审核和归因。

## 5. 代码职责调整

### 命令入口

`run_edit_dialogue_case.py` 负责：

- 解析全量或指定 case ID。
- 在编辑执行开始前调用批量清理函数。
- 继续调用现有多轮编辑编排。

### 清理工具

`artifact_cleaner.py` 提供：

```python
clear_edit_dialogue_case_artifacts(case_id: str) -> None
clear_edit_dialogue_cases_artifacts(case_ids: list[str]) -> None
```

清理函数必须：

- 校验 case ID 非空且符合 `EDG_` 格式。
- 只删除编辑目录。
- 删除失败时抛出异常并记录日志，禁止静默继续。

### 编辑执行器

`PatientStoryEditExecutor` 不再在每个 turn 开始时调用清理。执行器只负责调用 Agent、获取产物、落盘和记录执行结果，避免编排层和执行器重复承担清理职责。

## 6. 异常处理

- 清理目录不存在：视为已清理，不报错。
- 清理目录权限不足或删除失败：当前编辑 case 直接失败，不调用 Agent。
- 某个 case 清理失败：全量运行记录该 case 失败，并继续执行其他 case；是否终止全量由命令入口配置决定，默认继续并在最终摘要中标记失败。
- 单 case 清理失败：命令返回非 0，不调用 Agent。

## 7. 验收标准

1. 全量执行前，所有 `EDG_*` 的 `edit_runs/assets/edit_audits` 历史目录均被删除。
2. 原始 `SM_*` 生成产物保持不变。
3. 指定 case 执行只影响指定 `EDG_*` 目录。
4. `audit-only` 不删除任何产物。
5. 单个 case 的多轮执行过程中，不再重复清理目录。
6. 清理失败有明确日志、case ID 和原始异常。
7. 测试覆盖全量、指定 case、audit-only、非法 case ID 和删除异常场景。

