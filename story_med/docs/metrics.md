# 患者故事 Agent 指标说明

## 评测对象
这个流程分 5 步：
1. 创建会话
2. 生成大纲
3. 生成故事正文
4. 生成图片
5. 生成最终成图

当前适合的评测方式不是先假设固定答案，而是先记录每一步的真实输出和下载后的本地文件，再按步骤分别打分。

## 指标定义

## 硬规则基准字段
硬规则字段放在 YAML 用例的 `hard_rules` 中。硬规则先于自定义指标执行，只有硬规则通过后，才进入生成质量、风格、叙事完整性等自定义指标评估。

| 字段 | 中文含义 | 评估目标 |
| --- | --- | --- |
| `disease` | 核心疾病 | 检查患者主要诊断疾病是否被写错 |
| `disease_subtype` | 疾病亚型 | 检查分子分型、病理分型等关键属性是否被篡改 |
| `stage` | 疾病阶段 | 检查肿瘤分期或疾病严重程度是否一致 |
| `gender` | 性别 | 检查患者身份一致性 |
| `age_group` | 年龄段 | 检查患者画像是否失真 |
| `treatments` | 核心治疗方式 | 检查是否编造或遗漏真实治疗 |
| `outcome` | 当前疾病状态 | 检查是否夸大疗效或改变当前状态 |

### 1. 会话创建成功率
- 中文含义：`/api/session` 是否成功创建会话。
- 计算方式：`session_id` 非空且 HTTP 状态码为 2xx 记为 1，否则记为 0。

### 2. 大纲生成成功率
- 中文含义：`/outline` 是否返回可用的大纲结果。
- 计算方式：`outline_response` 非空，且响应中的 OSS 大纲文件下载成功记为 1，否则记为 0。若接口超时或返回错误，记为 0，并保留失败步骤。

### 3. 故事生成成功率
- 中文含义：`/story` 是否返回可用的故事正文。
- 计算方式：`story_response` 非空，且响应中的 OSS 正文文件下载成功记为 1，否则记为 0。

### 4. 图片生成成功率
- 中文含义：`/images` 是否返回可用的图片生成结果。
- 计算方式：`images_response` 非空，且响应中能提取到有效内容记为 1，否则记为 0。若响应中包含 OSS 链接，还需要检查 `downloaded_assets` 中对应资源下载成功。

### 5. 最终成图成功率
- 中文含义：`/generate` 是否成功输出最终图片结果。
- 计算方式：`final_image_response` 非空，且响应中能提取到有效内容记为 1，否则记为 0。若响应中包含 OSS 链接，还需要检查最终成图文件已保存到本地。

### 6. 全流程完成率
- 中文含义：整条患者故事链路是否完整跑通。
- 计算方式：5 个步骤全部成功记为 1，否则记为 0。

### 7. 步骤失败定位
- 中文含义：当流程失败时，定位失败发生在哪一步。
- 计算方式：读取结果中的 `failed_step` 字段，例如 `generate_outline`、`generate_story`、`generate_images`、`generate_final_image`。

## 结果建议
- 若后续要做 DeepEval 细评，可以把每一步的 `response_body` 作为评测输入。
- 如果要看业务层质量，建议再补一层人工规则，例如：
  - 大纲是否覆盖关键事实
  - 故事是否完整保留病例信息
  - 叙事风格是否符合 creative brief
  - 图片结果是否可用

## 当前硬规则实现
当前硬规则校验会分别读取本地下载的大纲 Markdown 和正文 Markdown，对 `disease`、`disease_subtype`、`stage`、`gender`、`age_group`、`treatments`、`outcome` 逐项校验。

运行方式：

```bash
PYTHONPATH=. python3 -m pytest story_med/evals/test_hard_rule_validation.py -q
```

校验报告输出到：

```text
story_med/results/hard_rule_validation.json
```
