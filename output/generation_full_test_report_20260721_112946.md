# 患者故事生成与审核全链路测试报告

- 报告生成时间：2026-07-21 11:28:40 +0800
- 数据来源：`story_med/results/generation_runs/*/*.json`、`story_med/results/story_audits/*/summary.json`及审核阶段记录
- 统计范围：当前已有的 `SM_001` 至 `SM_010` 生成任务
- 总耗时口径：每个任务使用阶段最早开始到最后结束的墙钟时间；阶段表按节点名称汇总，避免并行节点重复累加

## 1. 任务汇总

- 总任务数：**10**
- 生成执行成功：**7**
- 生成执行失败：**3**
- 审核执行失败：**4**
- 业务审核失败：**3**
- 生成与审核全链路通过：**0**

### 失败类型汇总

| 类型 | Case | 含义 |
|---|---|---|
| 生成执行失败 | SM_001, SM_006, SM_008 | 任务未成功生成最终产物，因此未进入完整业务审核 |
| 审核执行失败 | SM_002, SM_003, SM_007, SM_009 | 产物已生成，但审核节点调用失败，不能据此判定业务不合格 |
| 业务审核失败 | SM_004, SM_005, SM_010 | 审核已返回业务判断，产物存在具体不满足项 |
| 全链路通过 | - | 生成成功且审核结果全部通过 |

## 2. Case 结果总览

| Case | 结论类型 | 生成状态 | 生成耗时 | 审核耗时 | Task ID | Session ID | 具体失败点 |
|---|---|---|---:|---:|---|---|---|
| SM_001 | 生成执行失败 | 失败 | 1801.978s (30.03min) | - | `2079125921692839937` | `3ec4367d-274b-4b8b-966c-942bc3e3bd96` | Agent 任务超过 30 分钟总时限: task_id=2079125921692839937 |
| SM_002 | 审核执行失败 | 成功 | 603.121s (10.05min) | 144.027s (2.40min) | `2079133526523834370` | `b1077769-9b97-4b13-97de-1f343386b583` | 429 Client Error: Too Many Requests for url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions |
| SM_003 | 审核执行失败 | 成功 | 589.178s (9.82min) | 140.491s (2.34min) | `2079136645605421057` | `ac3aa205-ccb3-4b79-bbe7-9aaf8e7ee281` | 生成图片匹配异常: story_66437873_0.png, []; 生成图片匹配异常: story_66437873_1.png, []; 生成图片匹配异常: story_66437873_2.png, []; 生成图片匹配异常: story_66437873_3.png, []; 生成图片匹配异常: story_66437873_4.png, []; 429 Client Error: Too Many Requests for url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions |
| SM_004 | 业务审核失败 | 成功 | 680.490s (11.34min) | 253.942s (4.23min) | `2079139707384426497` | `af879f0e-d948-4a50-b782-2f99c5e20a08` | 故事合规：实际使用的PD-1单药术后辅助治疗超适应症，且文本未标注探索性治疗；推荐联合方案描述存在医学常识错误。；图片设计：替雷利珠单抗作为注射剂，以口服药盒形式呈现，易误导观众认为其可口服。 |
| SM_005 | 业务审核失败 | 成功 | 879.133s (14.65min) | 218.863s (3.65min) | `2079143613980143617` | `b2222e17-0466-4fce-a014-b12c0daa3f2a` | 故事合规：度伐利尤单抗+贝伐珠单抗+吉西他滨+顺铂四药联合方案属于超适应症探索性治疗，但文本未明确标注，且缺少知情同意、风险获益说明及MDT记录。；图片设计：患者年龄与案例不符（52岁 vs 69岁），图1的prompt背景与composition描述矛盾。 |
| SM_006 | 生成执行失败 | 失败 | 1807.152s (30.12min) | - | `2079148230902214657` | `03f91f8f-cf6a-4121-a08a-9370e0bb7f85` | Agent 任务超过 30 分钟总时限: task_id=2079148230902214657 |
| SM_007 | 审核执行失败 | 成功 | 592.202s (9.87min) | 0.220s (0.00min) | `2079155824600793089` | `c496d77d-c175-4642-afab-efbf4bd9ed9b` | 429 Client Error: Too Many Requests for url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions |
| SM_008 | 生成执行失败 | 失败 | 214.760s (3.58min) | - | `2079158274619588610` | `5d6b9492-cc8a-43b5-818f-ede6c8b0c4ca` | 内容中台上游 Agent 执行失败: 696f26ac-34ce-4fdd-9fe0-ac25576de862: [Errno 2] No such file or directory: '/app/workspaces/5d6b9492-cc8a-43b5-818f-ede6c8b0c4ca/story.md' |
| SM_009 | 审核执行失败 | 成功 | 560.418s (9.34min) | 75.271s (1.25min) | `2079159205553750017` | `163f25aa-3ddc-4004-875f-464d8b05c874` | 生成图片匹配异常: story_4029188875_0.png, []; 生成图片匹配异常: story_4029188875_1.png, []; 生成图片匹配异常: story_4029188875_2.png, []; 生成图片匹配异常: story_4029188875_3.png, []; 生成图片匹配异常: story_4029188875_4.png, []; 429 Client Error: Too Many Requests for url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions |
| SM_010 | 业务审核失败 | 成功 | 540.310s (9.01min) | 189.185s (3.15min) | `2079161870396407809` | `6be09caf-6ef9-46cc-b6e7-6e7d2d7d430e` | 故事合规：仑伐替尼联合信迪利单抗用于肝内胆管癌属于超适应症，文本未明确标注，且缺少知情同意及风险获益说明。；图片设计：图2/第二幕存在年龄不一致。 |

## 3. 每个 Case 的节点运行时间

### SM_001

- 结论：**生成执行失败**
- 生成总耗时：**1801.978s (30.03min)**
- 审核总耗时：未执行或无阶段记录

#### 生成节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| ensure_content_hub_auth | content_hub_request | 1 | 0.267s (0.00min) | 0.267s (0.00min) | 成功 | - |
| presign_upload | content_hub_request | 4 | 0.251s (0.00min) | 0.063s (0.00min) | 成功 | - |
| upload_case_image | content_hub_request | 4 | 0.820s (0.01min) | 0.205s (0.00min) | 成功 | - |
| create_agent_task | content_hub_request | 1 | 0.249s (0.00min) | 0.249s (0.00min) | 成功 | - |
| stream_agent_task | content_hub_request | 1 | 1800.410s (30.01min) | 1800.410s (30.01min) | 成功 | - |
| 制定计划 | agent_node | 1 | 7.183s (0.12min) | 7.183s (0.12min) | 成功 | - |
| 解析病例文件 | agent_node | 1 | 21.848s (0.36min) | 21.848s (0.36min) | 成功 | - |
| 生成大纲 | agent_node | 1 | 1762.063s (29.37min) | 1762.063s (29.37min) | 失败 | - |
| history_polling | content_hub_request | 1 | 0.001s (0.00min) | 0.001s (0.00min) | 失败 | Agent 任务超过 30 分钟总时限: task_id=2079125921692839937 |

#### 审核节点

未执行审核：生成执行阶段已失败。
### SM_002

- 结论：**审核执行失败**
- 生成总耗时：**603.121s (10.05min)**
- 审核总耗时：**144.027s (2.40min)**

#### 生成节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| ensure_content_hub_auth | content_hub_request | 1 | 0.267s (0.00min) | 0.267s (0.00min) | 成功 | - |
| presign_upload | content_hub_request | 22 | 1.451s (0.02min) | 0.066s (0.00min) | 成功 | - |
| upload_case_image | content_hub_request | 22 | 10.214s (0.17min) | 0.464s (0.01min) | 成功 | - |
| create_agent_task | content_hub_request | 1 | 0.188s (0.00min) | 0.188s (0.00min) | 成功 | - |
| stream_agent_task | content_hub_request | 1 | 583.050s (9.72min) | 583.050s (9.72min) | 成功 | - |
| 制定计划 | agent_node | 1 | 6.780s (0.11min) | 6.780s (0.11min) | 成功 | - |
| 解析病例文件 | agent_node | 1 | 49.888s (0.83min) | 49.888s (0.83min) | 成功 | - |
| 生成大纲 | agent_node | 1 | 100.274s (1.67min) | 100.274s (1.67min) | 成功 | - |
| 生成故事正文 | agent_node | 1 | 62.229s (1.04min) | 62.229s (1.04min) | 成功 | - |
| 生成配图 | agent_node | 1 | 196.255s (3.27min) | 196.255s (3.27min) | 成功 | - |
| 生成html页面 | agent_node | 1 | 166.902s (2.78min) | 166.902s (2.78min) | 成功 | - |
| history_polling | content_hub_request | 1 | 0.186s (0.00min) | 0.186s (0.00min) | 成功 | - |
| write_case_parse | content_hub_request | 1 | 0.028s (0.00min) | 0.028s (0.00min) | 成功 | - |
| presign_download | content_hub_request | 10 | 1.097s (0.02min) | 0.110s (0.00min) | 成功 | - |
| download_artifact | content_hub_request | 10 | 6.681s (0.11min) | 0.668s (0.01min) | 成功 | - |

#### 审核节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| image_design_audit | audit | 1 | 8.522s (0.14min) | 8.522s (0.14min) | 失败 | 429 Client Error: Too Many Requests for url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions |
| outline_fact_compare | audit | 1 | 69.476s (1.16min) | 69.476s (1.16min) | 成功 | - |
| outline_fact_extraction | audit | 1 | 74.542s (1.24min) | 74.542s (1.24min) | 成功 | - |
| story_compliance_audit | audit | 1 | 8.432s (0.14min) | 8.432s (0.14min) | 失败 | 429 Client Error: Too Many Requests for url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions |
| story_fact_extraction | audit | 1 | 7.104s (0.12min) | 7.104s (0.12min) | 失败 | 429 Client Error: Too Many Requests for url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions |
### SM_003

- 结论：**审核执行失败**
- 生成总耗时：**589.178s (9.82min)**
- 审核总耗时：**140.491s (2.34min)**

#### 生成节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| ensure_content_hub_auth | content_hub_request | 1 | 0.235s (0.00min) | 0.235s (0.00min) | 成功 | - |
| presign_upload | content_hub_request | 12 | 1.346s (0.02min) | 0.112s (0.00min) | 成功 | - |
| upload_case_image | content_hub_request | 12 | 6.376s (0.11min) | 0.531s (0.01min) | 成功 | - |
| create_agent_task | content_hub_request | 1 | 0.200s (0.00min) | 0.200s (0.00min) | 成功 | - |
| stream_agent_task | content_hub_request | 1 | 577.133s (9.62min) | 577.133s (9.62min) | 成功 | - |
| 制定计划 | agent_node | 1 | 0.066s (0.00min) | 0.066s (0.00min) | 成功 | - |
| 解析病例文件 | agent_node | 1 | 29.660s (0.49min) | 29.660s (0.49min) | 成功 | - |
| 生成大纲 | agent_node | 1 | 77.415s (1.29min) | 77.415s (1.29min) | 成功 | - |
| 生成故事正文 | agent_node | 1 | 32.120s (0.54min) | 32.120s (0.54min) | 成功 | - |
| 生成配图 | agent_node | 1 | 251.992s (4.20min) | 251.992s (4.20min) | 成功 | - |
| 生成html页面 | agent_node | 1 | 185.152s (3.09min) | 185.152s (3.09min) | 成功 | - |
| history_polling | content_hub_request | 1 | 0.147s (0.00min) | 0.147s (0.00min) | 成功 | - |
| write_case_parse | content_hub_request | 1 | 0.008s (0.00min) | 0.008s (0.00min) | 成功 | - |
| presign_download | content_hub_request | 11 | 0.867s (0.01min) | 0.079s (0.00min) | 成功 | - |
| download_artifact | content_hub_request | 11 | 2.786s (0.05min) | 0.253s (0.00min) | 成功 | - |

#### 审核节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| final_image_fact_audit | audit | 1 | 108.854s (1.81min) | 108.854s (1.81min) | 成功 | - |
| final_image_layout_audit | audit | 1 | 111.116s (1.85min) | 111.116s (1.85min) | 成功 | - |
| image_design_audit | audit | 1 | 29.352s (0.49min) | 29.352s (0.49min) | 成功 | - |
| image_fact_audit_1 | audit | 1 | 0.011s (0.00min) | 0.011s (0.00min) | 失败 | 生成图片匹配异常: story_66437873_0.png, [] |
| image_fact_audit_2 | audit | 1 | 0.224s (0.00min) | 0.224s (0.00min) | 失败 | 生成图片匹配异常: story_66437873_1.png, [] |
| image_fact_audit_3 | audit | 1 | 0.286s (0.00min) | 0.286s (0.00min) | 失败 | 生成图片匹配异常: story_66437873_2.png, [] |
| image_fact_audit_4 | audit | 1 | 0.014s (0.00min) | 0.014s (0.00min) | 失败 | 生成图片匹配异常: story_66437873_3.png, [] |
| image_fact_audit_5 | audit | 1 | 0.025s (0.00min) | 0.025s (0.00min) | 失败 | 生成图片匹配异常: story_66437873_4.png, [] |
| outline_fact_extraction | audit | 1 | 5.311s (0.09min) | 5.311s (0.09min) | 失败 | 429 Client Error: Too Many Requests for url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions |
| story_compliance_audit | audit | 1 | 5.983s (0.10min) | 5.983s (0.10min) | 失败 | 429 Client Error: Too Many Requests for url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions |
| story_fact_extraction | audit | 1 | 5.904s (0.10min) | 5.904s (0.10min) | 失败 | 429 Client Error: Too Many Requests for url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions |
### SM_004

- 结论：**业务审核失败**
- 生成总耗时：**680.490s (11.34min)**
- 审核总耗时：**253.942s (4.23min)**

#### 生成节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| ensure_content_hub_auth | content_hub_request | 1 | 0.211s (0.00min) | 0.211s (0.00min) | 成功 | - |
| presign_upload | content_hub_request | 36 | 2.659s (0.04min) | 0.074s (0.00min) | 成功 | - |
| upload_case_image | content_hub_request | 36 | 5.185s (0.09min) | 0.144s (0.00min) | 成功 | - |
| create_agent_task | content_hub_request | 1 | 0.207s (0.00min) | 0.207s (0.00min) | 成功 | - |
| stream_agent_task | content_hub_request | 1 | 668.598s (11.14min) | 668.598s (11.14min) | 成功 | - |
| 制定计划 | agent_node | 1 | 6.942s (0.12min) | 6.942s (0.12min) | 成功 | - |
| 解析病例文件 | agent_node | 1 | 64.167s (1.07min) | 64.167s (1.07min) | 成功 | - |
| 生成大纲 | agent_node | 1 | 104.684s (1.74min) | 104.684s (1.74min) | 成功 | - |
| 生成故事正文 | agent_node | 1 | 55.643s (0.93min) | 55.643s (0.93min) | 成功 | - |
| 生成配图 | agent_node | 1 | 263.184s (4.39min) | 263.184s (4.39min) | 成功 | - |
| 生成html页面 | agent_node | 1 | 173.226s (2.89min) | 173.226s (2.89min) | 成功 | - |
| history_polling | content_hub_request | 1 | 0.162s (0.00min) | 0.162s (0.00min) | 成功 | - |
| write_case_parse | content_hub_request | 1 | 0.004s (0.00min) | 0.004s (0.00min) | 成功 | - |
| presign_download | content_hub_request | 11 | 0.905s (0.02min) | 0.082s (0.00min) | 成功 | - |
| download_artifact | content_hub_request | 11 | 2.483s (0.04min) | 0.226s (0.00min) | 成功 | - |

#### 审核节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| outline_fact_extraction | audit | 1 | 54.895s (0.91min) | 54.895s (0.91min) | 成功 | - |
| story_fact_extraction | audit | 1 | 88.434s (1.47min) | 88.434s (1.47min) | 成功 | - |
| outline_fact_compare | audit | 1 | 57.171s (0.95min) | 57.171s (0.95min) | 成功 | - |
| story_fact_compare | audit | 1 | 48.173s (0.80min) | 48.173s (0.80min) | 成功 | - |
| image_design_audit | audit | 1 | 30.164s (0.50min) | 30.164s (0.50min) | 成功 | - |
| final_image_fact_audit | audit | 1 | 68.752s (1.15min) | 68.752s (1.15min) | 成功 | - |
| final_image_layout_audit | audit | 1 | 157.666s (2.63min) | 157.666s (2.63min) | 成功 | - |
| image_fact_audit_3 | audit | 1 | 0.033s (0.00min) | 0.033s (0.00min) | 失败 | 生成图片匹配异常: story_605606809_2.png, [] |
| image_fact_audit_2 | audit | 1 | 0.042s (0.00min) | 0.042s (0.00min) | 失败 | 生成图片匹配异常: story_605606809_1.png, [] |
| image_fact_audit_1 | audit | 1 | 0.048s (0.00min) | 0.048s (0.00min) | 失败 | 生成图片匹配异常: story_605606809_0.png, [] |
| image_fact_audit_4 | audit | 1 | 0.021s (0.00min) | 0.021s (0.00min) | 失败 | 生成图片匹配异常: story_605606809_3.png, [] |
| image_fact_audit_5 | audit | 1 | 0.020s (0.00min) | 0.020s (0.00min) | 失败 | 生成图片匹配异常: story_605606809_4.png, [] |
| story_compliance_audit | audit | 1 | 68.993s (1.15min) | 68.993s (1.15min) | 成功 | - |
| audit_analysis | audit | 1 | 65.808s (1.10min) | 65.808s (1.10min) | 成功 | - |
### SM_005

- 结论：**业务审核失败**
- 生成总耗时：**879.133s (14.65min)**
- 审核总耗时：**218.863s (3.65min)**

#### 生成节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| ensure_content_hub_auth | content_hub_request | 1 | 1.334s (0.02min) | 1.334s (0.02min) | 成功 | - |
| presign_upload | content_hub_request | 13 | 1.077s (0.02min) | 0.083s (0.00min) | 成功 | - |
| upload_case_image | content_hub_request | 13 | 2.173s (0.04min) | 0.167s (0.00min) | 成功 | - |
| create_agent_task | content_hub_request | 1 | 0.242s (0.00min) | 0.242s (0.00min) | 成功 | - |
| stream_agent_task | content_hub_request | 1 | 870.381s (14.51min) | 870.381s (14.51min) | 成功 | - |
| 制定计划 | agent_node | 1 | 7.402s (0.12min) | 7.402s (0.12min) | 成功 | - |
| 解析病例文件 | agent_node | 1 | 37.108s (0.62min) | 37.108s (0.62min) | 成功 | - |
| 生成大纲 | agent_node | 1 | 62.525s (1.04min) | 62.525s (1.04min) | 成功 | - |
| 生成故事正文 | agent_node | 1 | 46.220s (0.77min) | 46.220s (0.77min) | 成功 | - |
| 生成配图 | agent_node | 1 | 200.901s (3.35min) | 200.901s (3.35min) | 成功 | - |
| 生成html页面 | agent_node | 1 | 194.057s (3.23min) | 194.057s (3.23min) | 成功 | - |
| history_polling | content_hub_request | 1 | 0.150s (0.00min) | 0.150s (0.00min) | 成功 | - |
| write_case_parse | content_hub_request | 1 | 0.006s (0.00min) | 0.006s (0.00min) | 成功 | - |
| presign_download | content_hub_request | 10 | 0.810s (0.01min) | 0.081s (0.00min) | 成功 | - |
| download_artifact | content_hub_request | 10 | 2.917s (0.05min) | 0.292s (0.00min) | 成功 | - |

#### 审核节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| outline_fact_extraction | audit | 1 | 91.900s (1.53min) | 91.900s (1.53min) | 成功 | - |
| story_fact_extraction | audit | 1 | 127.317s (2.12min) | 127.317s (2.12min) | 成功 | - |
| outline_fact_compare | audit | 1 | 40.336s (0.67min) | 40.336s (0.67min) | 成功 | - |
| story_fact_compare | audit | 1 | 37.805s (0.63min) | 37.805s (0.63min) | 成功 | - |
| image_design_audit | audit | 1 | 25.309s (0.42min) | 25.309s (0.42min) | 成功 | - |
| final_image_fact_audit | audit | 1 | 66.938s (1.12min) | 66.938s (1.12min) | 成功 | - |
| image_fact_audit_3 | audit | 1 | 0.014s (0.00min) | 0.014s (0.00min) | 失败 | 生成图片匹配异常: story_2724723846_2.png, [] |
| final_image_layout_audit | audit | 1 | 120.598s (2.01min) | 120.598s (2.01min) | 成功 | - |
| image_fact_audit_2 | audit | 1 | 0.023s (0.00min) | 0.023s (0.00min) | 失败 | 生成图片匹配异常: story_2724723846_1.png, [] |
| image_fact_audit_1 | audit | 1 | 0.025s (0.00min) | 0.025s (0.00min) | 失败 | 生成图片匹配异常: story_2724723846_0.png, [] |
| image_fact_audit_4 | audit | 1 | 0.020s (0.00min) | 0.020s (0.00min) | 失败 | 生成图片匹配异常: story_2724723846_3.png, [] |
| story_compliance_audit | audit | 1 | 28.147s (0.47min) | 28.147s (0.47min) | 成功 | - |
| audit_analysis | audit | 1 | 53.426s (0.89min) | 53.426s (0.89min) | 成功 | - |
### SM_006

- 结论：**生成执行失败**
- 生成总耗时：**1807.152s (30.12min)**
- 审核总耗时：未执行或无阶段记录

#### 生成节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| ensure_content_hub_auth | content_hub_request | 1 | 1.311s (0.02min) | 1.311s (0.02min) | 成功 | - |
| presign_upload | content_hub_request | 14 | 0.976s (0.02min) | 0.070s (0.00min) | 成功 | - |
| upload_case_image | content_hub_request | 14 | 4.656s (0.08min) | 0.333s (0.01min) | 成功 | - |
| create_agent_task | content_hub_request | 1 | 0.203s (0.00min) | 0.203s (0.00min) | 成功 | - |
| stream_agent_task | content_hub_request | 1 | 387.681s (6.46min) | 387.681s (6.46min) | 失败 | Response ended prematurely |
| history_polling | content_hub_request | 1 | 1412.335s (23.54min) | 1412.335s (23.54min) | 失败 | Agent 任务超过 30 分钟总时限: task_id=2079148230902214657 |

#### 审核节点

未执行审核：生成执行阶段已失败。
### SM_007

- 结论：**审核执行失败**
- 生成总耗时：**592.202s (9.87min)**
- 审核总耗时：**0.220s (0.00min)**

#### 生成节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| ensure_content_hub_auth | content_hub_request | 1 | 0.446s (0.01min) | 0.446s (0.01min) | 成功 | - |
| presign_upload | content_hub_request | 35 | 2.743s (0.05min) | 0.078s (0.00min) | 成功 | - |
| upload_case_image | content_hub_request | 35 | 6.431s (0.11min) | 0.184s (0.00min) | 成功 | - |
| create_agent_task | content_hub_request | 1 | 0.393s (0.01min) | 0.393s (0.01min) | 成功 | - |
| stream_agent_task | content_hub_request | 1 | 578.348s (9.64min) | 578.348s (9.64min) | 成功 | - |
| 制定计划 | agent_node | 1 | 4.718s (0.08min) | 4.718s (0.08min) | 成功 | - |
| 解析病例文件 | agent_node | 1 | 45.923s (0.77min) | 45.923s (0.77min) | 成功 | - |
| 生成大纲 | agent_node | 1 | 69.294s (1.15min) | 69.294s (1.15min) | 成功 | - |
| 生成故事正文 | agent_node | 1 | 42.828s (0.71min) | 42.828s (0.71min) | 成功 | - |
| 生成配图 | agent_node | 1 | 265.920s (4.43min) | 265.920s (4.43min) | 成功 | - |
| 生成html页面 | agent_node | 1 | 148.883s (2.48min) | 148.883s (2.48min) | 成功 | - |
| history_polling | content_hub_request | 1 | 0.163s (0.00min) | 0.163s (0.00min) | 成功 | - |
| write_case_parse | content_hub_request | 1 | 0.006s (0.00min) | 0.006s (0.00min) | 成功 | - |
| presign_download | content_hub_request | 11 | 0.764s (0.01min) | 0.069s (0.00min) | 成功 | - |
| download_artifact | content_hub_request | 11 | 2.751s (0.05min) | 0.250s (0.00min) | 成功 | - |

#### 审核节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| image_design_audit | audit | 1 | 0.176s (0.00min) | 0.176s (0.00min) | 失败 | 429 Client Error: Too Many Requests for url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions |
| outline_fact_extraction | audit | 1 | 0.183s (0.00min) | 0.183s (0.00min) | 失败 | 429 Client Error: Too Many Requests for url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions |
| story_compliance_audit | audit | 1 | 0.198s (0.00min) | 0.198s (0.00min) | 失败 | 429 Client Error: Too Many Requests for url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions |
| story_fact_extraction | audit | 1 | 0.212s (0.00min) | 0.212s (0.00min) | 失败 | 429 Client Error: Too Many Requests for url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions |
### SM_008

- 结论：**生成执行失败**
- 生成总耗时：**214.760s (3.58min)**
- 审核总耗时：未执行或无阶段记录

#### 生成节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| ensure_content_hub_auth | content_hub_request | 1 | 0.254s (0.00min) | 0.254s (0.00min) | 成功 | - |
| presign_upload | content_hub_request | 4 | 0.274s (0.00min) | 0.069s (0.00min) | 成功 | - |
| upload_case_image | content_hub_request | 4 | 0.711s (0.01min) | 0.178s (0.00min) | 成功 | - |
| create_agent_task | content_hub_request | 1 | 0.197s (0.00min) | 0.197s (0.00min) | 成功 | - |
| stream_agent_task | content_hub_request | 1 | 213.144s (3.55min) | 213.144s (3.55min) | 成功 | - |
| 制定计划 | agent_node | 1 | 5.200s (0.09min) | 5.200s (0.09min) | 成功 | - |
| 解析病例文件 | agent_node | 1 | 20.843s (0.35min) | 20.843s (0.35min) | 成功 | - |
| 生成大纲 | agent_node | 1 | 145.004s (2.42min) | 145.004s (2.42min) | 成功 | - |
| 生成故事正文 | agent_node | 1 | 41.444s (0.69min) | 41.444s (0.69min) | 成功 | - |
| 生成配图 | agent_node | 1 | 0.057s (0.00min) | 0.057s (0.00min) | 失败 | [Errno 2] No such file or directory: '/app/workspaces/5d6b9492-cc8a-43b5-818f-ede6c8b0c4ca/story.md' |
| history_polling | content_hub_request | 1 | 0.139s (0.00min) | 0.139s (0.00min) | 成功 | - |

#### 审核节点

未执行审核：生成执行阶段已失败。
### SM_009

- 结论：**审核执行失败**
- 生成总耗时：**560.418s (9.34min)**
- 审核总耗时：**75.271s (1.25min)**

#### 生成节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| ensure_content_hub_auth | content_hub_request | 1 | 0.318s (0.01min) | 0.318s (0.01min) | 成功 | - |
| presign_upload | content_hub_request | 35 | 2.593s (0.04min) | 0.074s (0.00min) | 成功 | - |
| upload_case_image | content_hub_request | 35 | 5.222s (0.09min) | 0.149s (0.00min) | 成功 | - |
| create_agent_task | content_hub_request | 1 | 0.197s (0.00min) | 0.197s (0.00min) | 成功 | - |
| stream_agent_task | content_hub_request | 1 | 549.233s (9.15min) | 549.233s (9.15min) | 成功 | - |
| 制定计划 | agent_node | 1 | 8.190s (0.14min) | 8.190s (0.14min) | 成功 | - |
| 解析病例文件 | agent_node | 1 | 49.948s (0.83min) | 49.948s (0.83min) | 成功 | - |
| 生成大纲 | agent_node | 1 | 61.441s (1.02min) | 61.441s (1.02min) | 成功 | - |
| 生成故事正文 | agent_node | 1 | 40.334s (0.67min) | 40.334s (0.67min) | 成功 | - |
| 生成配图 | agent_node | 1 | 243.013s (4.05min) | 243.013s (4.05min) | 成功 | - |
| 生成html页面 | agent_node | 1 | 145.660s (2.43min) | 145.660s (2.43min) | 成功 | - |
| history_polling | content_hub_request | 1 | 0.132s (0.00min) | 0.132s (0.00min) | 成功 | - |
| write_case_parse | content_hub_request | 1 | 0.002s (0.00min) | 0.002s (0.00min) | 成功 | - |
| presign_download | content_hub_request | 11 | 0.765s (0.01min) | 0.070s (0.00min) | 成功 | - |
| download_artifact | content_hub_request | 11 | 1.933s (0.03min) | 0.176s (0.00min) | 成功 | - |

#### 审核节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| final_image_fact_audit | audit | 1 | 56.016s (0.93min) | 56.016s (0.93min) | 成功 | - |
| final_image_layout_audit | audit | 1 | 60.816s (1.01min) | 60.816s (1.01min) | 成功 | - |
| image_design_audit | audit | 1 | 11.959s (0.20min) | 11.959s (0.20min) | 成功 | - |
| image_fact_audit_1 | audit | 1 | 0.004s (0.00min) | 0.004s (0.00min) | 失败 | 生成图片匹配异常: story_4029188875_0.png, [] |
| image_fact_audit_2 | audit | 1 | 0.020s (0.00min) | 0.020s (0.00min) | 失败 | 生成图片匹配异常: story_4029188875_1.png, [] |
| image_fact_audit_3 | audit | 1 | 0.006s (0.00min) | 0.006s (0.00min) | 失败 | 生成图片匹配异常: story_4029188875_2.png, [] |
| image_fact_audit_4 | audit | 1 | 0.015s (0.00min) | 0.015s (0.00min) | 失败 | 生成图片匹配异常: story_4029188875_3.png, [] |
| image_fact_audit_5 | audit | 1 | 0.019s (0.00min) | 0.019s (0.00min) | 失败 | 生成图片匹配异常: story_4029188875_4.png, [] |
| outline_fact_extraction | audit | 1 | 7.540s (0.13min) | 7.540s (0.13min) | 失败 | 429 Client Error: Too Many Requests for url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions |
| story_compliance_audit | audit | 1 | 7.154s (0.12min) | 7.154s (0.12min) | 失败 | 429 Client Error: Too Many Requests for url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions |
| story_fact_compare | audit | 1 | 27.779s (0.46min) | 27.779s (0.46min) | 成功 | - |
| story_fact_extraction | audit | 1 | 47.489s (0.79min) | 47.489s (0.79min) | 成功 | - |
### SM_010

- 结论：**业务审核失败**
- 生成总耗时：**540.310s (9.01min)**
- 审核总耗时：**189.185s (3.15min)**

#### 生成节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| ensure_content_hub_auth | content_hub_request | 1 | 0.299s (0.00min) | 0.299s (0.00min) | 成功 | - |
| presign_upload | content_hub_request | 35 | 2.566s (0.04min) | 0.073s (0.00min) | 成功 | - |
| upload_case_image | content_hub_request | 35 | 4.728s (0.08min) | 0.135s (0.00min) | 成功 | - |
| create_agent_task | content_hub_request | 1 | 0.230s (0.00min) | 0.230s (0.00min) | 成功 | - |
| stream_agent_task | content_hub_request | 1 | 530.096s (8.83min) | 530.096s (8.83min) | 成功 | - |
| 制定计划 | agent_node | 1 | 9.007s (0.15min) | 9.007s (0.15min) | 成功 | - |
| 解析病例文件 | agent_node | 1 | 49.484s (0.82min) | 49.484s (0.82min) | 成功 | - |
| 生成大纲 | agent_node | 1 | 67.849s (1.13min) | 67.849s (1.13min) | 成功 | - |
| 生成故事正文 | agent_node | 1 | 47.171s (0.79min) | 47.171s (0.79min) | 成功 | - |
| 生成配图 | agent_node | 1 | 193.917s (3.23min) | 193.917s (3.23min) | 成功 | - |
| 生成html页面 | agent_node | 1 | 162.047s (2.70min) | 162.047s (2.70min) | 成功 | - |
| history_polling | content_hub_request | 1 | 0.203s (0.00min) | 0.203s (0.00min) | 成功 | - |
| write_case_parse | content_hub_request | 1 | 0.005s (0.00min) | 0.005s (0.00min) | 成功 | - |
| presign_download | content_hub_request | 10 | 0.732s (0.01min) | 0.073s (0.00min) | 成功 | - |
| download_artifact | content_hub_request | 10 | 1.405s (0.02min) | 0.141s (0.00min) | 成功 | - |

#### 审核节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| outline_fact_extraction | audit | 1 | 74.505s (1.24min) | 74.505s (1.24min) | 成功 | - |
| story_fact_extraction | audit | 1 | 41.397s (0.69min) | 41.397s (0.69min) | 成功 | - |
| story_fact_compare | audit | 1 | 17.475s (0.29min) | 17.475s (0.29min) | 成功 | - |
| outline_fact_compare | audit | 1 | 30.021s (0.50min) | 30.021s (0.50min) | 成功 | - |
| image_design_audit | audit | 1 | 32.307s (0.54min) | 32.307s (0.54min) | 成功 | - |
| final_image_fact_audit | audit | 1 | 62.027s (1.03min) | 62.027s (1.03min) | 成功 | - |
| final_image_layout_audit | audit | 1 | 128.207s (2.14min) | 128.207s (2.14min) | 成功 | - |
| image_fact_audit_1 | audit | 1 | 0.066s (0.00min) | 0.066s (0.00min) | 失败 | 生成图片匹配异常: story_477092379_0.png, [] |
| image_fact_audit_2 | audit | 1 | 0.060s (0.00min) | 0.060s (0.00min) | 失败 | 生成图片匹配异常: story_477092379_1.png, [] |
| image_fact_audit_3 | audit | 1 | 0.068s (0.00min) | 0.068s (0.00min) | 失败 | 生成图片匹配异常: story_477092379_2.png, [] |
| image_fact_audit_4 | audit | 1 | 0.019s (0.00min) | 0.019s (0.00min) | 失败 | 生成图片匹配异常: story_477092379_3.png, [] |
| story_compliance_audit | audit | 1 | 26.636s (0.44min) | 26.636s (0.44min) | 成功 | - |
| audit_analysis | audit | 1 | 28.556s (0.48min) | 28.556s (0.48min) | 成功 | - |

## 4. 业务审核失败详情

### SM_004

- 综合分：`48.0/100`
- 故事合规：`不通过`；实际使用的PD-1单药术后辅助治疗超适应症，且文本未标注探索性治疗；推荐联合方案描述存在医学常识错误。
- 图片设计：`不通过`；替雷利珠单抗作为注射剂，以口服药盒形式呈现，易误导观众认为其可口服。
- 图片事实审核：`阻断`；5个图片事实匹配节点未获得匹配结果。

### SM_005

- 综合分：`46.67/100`
- 故事合规：`不通过`；四药联合方案属于超适应症探索性治疗，但文本未明确标注，且缺少知情同意、风险获益说明及MDT记录。
- 图片设计：`不通过`；患者年龄与案例不符（52岁 vs 69岁），图1的prompt背景与composition描述矛盾。
- 图片事实审核：`阻断`；4个图片事实匹配节点未获得匹配结果。

### SM_010

- 综合分：`52.5/100`
- 故事合规：`不通过`；仑伐替尼联合信迪利单抗用于肝内胆管癌属于超适应症，且未明确标注，缺少知情同意及风险获益说明。
- 图片设计：`不通过`；图2/第二幕存在年龄不一致。
- 图片事实审核：`阻断`；4个图片事实匹配节点未获得匹配结果。

## 5. 结论口径

- “生成执行失败”表示中台任务或本地生成执行没有完成，不能归因于业务审核规则。
- “审核执行失败”表示生成产物已经存在，但审核模型/审核节点调用失败，例如 DashScope 返回 429；该类不能判定为业务审核不通过。
- “业务审核失败”表示审核节点正常返回结果，并明确指出故事合规、图片设计或事实一致性问题。
- 生成节点和审核节点分别列出，阶段累计耗时不作为任务总耗时直接相加。

