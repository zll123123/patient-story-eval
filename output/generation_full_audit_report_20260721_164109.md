# 患者故事生成链路全量审核详细测试报告

- 报告生成时间：2026-07-21 16:41:09 +0800
- 数据来源：`story_med/results/generation_runs/*/*.json`、`story_med/results/story_audits/*/summary.json`及各审核节点阶段记录
- 统计范围：当前已有的 `SM_001` 至 `SM_010` 最新生成记录及本轮全量审核记录
- 总耗时口径：每个任务按阶段最早开始到最后结束计算墙钟时间；节点表按节点名称汇总，不将并行节点重复累加

## 1. 总体汇总

- 总任务数：**10**
- 生成执行成功：**10**
- 生成执行失败：**0**
- 审核整体执行失败：**1**
- 审核部分节点执行失败且业务结果不通过：**1**
- 业务审核失败（审核执行完成）：**8**
- 生成与审核全链路通过：**0**

### 失败类型汇总

| 类型 | Case | 判断口径 |
|---|---|---|
| 生成执行失败 | - | Agent 未生成完成，无法进入审核 |
| 审核整体执行失败 | SM_010 | 审核主流程因模型超时/调用错误中断，不能作为业务不通过结论 |
| 审核部分节点执行失败 | SM_001 | 其他审核结果已返回，但存在节点调用失败，结论需要结合节点状态理解 |
| 业务审核失败 | SM_002, SM_003, SM_004, SM_005, SM_006, SM_007, SM_008, SM_009 | 审核正常返回具体事实、合规或视觉问题 |
| 全链路通过 | - | 生成成功且所有审核维度通过 |

## 2. Case 结果总览

| Case | 结论类型 | 生成状态 | 生成耗时 | 审核耗时 | Task ID | Session ID | 具体问题 |
|---|---|---|---:|---:|---|---|---|
| SM_001 | 业务审核失败（含审核节点执行问题） | 成功 | 648.131s (10.80min) | 164.223s (2.74min) | `2079457939265142785` | `6586b54f-c261-4735-b3a9-207130b47e58` | 429 Client Error: Too Many Requests for url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions |
| SM_002 | 业务审核失败 | 成功 | 603.121s (10.05min) | 263.489s (4.39min) | `2079133526523834370` | `b1077769-9b97-4b13-97de-1f343386b583` | 故事合规：故事中齐倍安（艾帕洛利托沃瑞利单抗）用于肝细胞癌（HCC）后线治疗，属于超适应症用药，且未标注探索性治疗、未提及MDT及患者知情同意，存在合规风险。；图片设计：发现1处严重事实错误：患者年龄在病历中为57岁，但图片大纲中所有角色描述均写为69岁，违背医学记录一致性。 |
| SM_003 | 业务审核失败 | 成功 | 589.178s (9.82min) | 254.845s (4.25min) | `2079136645605421057` | `ac3aa205-ccb3-4b79-bbe7-9aaf8e7ee281` | 故事合规：奥希替尼术后辅助治疗时间点可能早于中国获批日期，且文本未标注超适应症/探索性治疗，缺少MDT及知情同意记录，存在合规风险。；图片设计：发现1处系统性医学与常识错误：所有图片中的人物性别与病例患者性别不符，且多处年龄不一致，可能造成严重误导。；图片事实：未通过，失败图片 [1] |
| SM_004 | 业务审核失败 | 成功 | 680.490s (11.34min) | 276.011s (4.60min) | `2079139707384426497` | `af879f0e-d948-4a50-b782-2f99c5e20a08` | 故事合规：故事中存在实际使用的PD-1单药辅助治疗未标注超适应症/探索性治疗，以及推荐方案描述为“标准方案”的医学常识错误和违规宣传；图片设计：发现1处医学事实错误：图2的prompt中错误地将肝掌红斑描述在指关节（knuckles），而实际应为手掌大小鱼际部位。；图片事实：未通过，失败图片 [3] |
| SM_005 | 业务审核失败 | 成功 | 879.133s (14.65min) | 231.173s (3.85min) | `2079143613980143617` | `b2222e17-0466-4fce-a014-b12c0daa3f2a` | 故事合规：四药联合方案（度伐利尤单抗+贝伐珠单抗+吉西他滨+顺铂）为超适应症探索性治疗，文本未标注，且存在医学常识错误和违规宣传倾向。；图片设计：发现2处画面描述与医学事实/临床逻辑不符，以及1处prompt与composition不一致的问题。；图片事实：未通过，失败图片 [1] |
| SM_006 | 业务审核失败 | 成功 | 738.426s (12.31min) | 209.215s (3.49min) | `2079460676727980034` | `a86250a9-855a-44b6-a1f5-e552ac59d514` | 图片设计：发现1处医学事实错误（图4输液部位不符合R-CHOP临床规范）和1处源数据一致性错误（患者年龄矛盾）。 |
| SM_007 | 业务审核失败 | 成功 | 592.202s (9.87min) | 296.763s (4.95min) | `2079155824600793089` | `c496d77d-c175-4642-afab-efbf4bd9ed9b` | 故事合规：联合方案（仑伐替尼+信迪利单抗+化疗）用于肝内胆管癌（ICC）属超适应症探索性治疗，但文本未标注“超适应症/探索性治疗”，且缺少患者知情同意及风险获益说明。 |
| SM_008 | 业务审核失败 | 成功 | 575.167s (9.59min) | 247.898s (4.13min) | `2079463753904275457` | `6f309939-79ec-4102-a5fe-8168212edfc8` | 图片事实：未通过，失败图片 [3] |
| SM_009 | 业务审核失败 | 成功 | 560.418s (9.34min) | 191.025s (3.18min) | `2079159205553750017` | `163f25aa-3ddc-4004-875f-464d8b05c874` | 审核维度未通过：image_consistency_passed、final_image_layout_passed |
| SM_010 | 审核执行失败 | 成功 | 540.310s (9.01min) | 349.686s (5.83min) | `2079161870396407809` | `6be09caf-6ef9-46cc-b6e7-6e7d2d7d430e` | HTTPSConnectionPool(host='dashscope.aliyuncs.com', port=443): Read timed out. (read timeout=300) |

## 3. 每个 Case 节点运行时间

### SM_001

- 结论：**业务审核失败（含审核节点执行问题）**
- 生成总耗时：**648.131s (10.80min)**
- 审核总耗时：**164.223s (2.74min)**

#### 生成节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| ensure_content_hub_auth | content_hub_request | 1 | 0.313s (0.01min) | 0.313s (0.01min) | 成功 | - |
| presign_upload | content_hub_request | 4 | 0.334s (0.01min) | 0.084s (0.00min) | 成功 | - |
| upload_case_image | content_hub_request | 4 | 1.118s (0.02min) | 0.280s (0.00min) | 成功 | - |
| create_agent_task | content_hub_request | 1 | 0.214s (0.00min) | 0.214s (0.00min) | 成功 | - |
| stream_agent_task | content_hub_request | 1 | 642.603s (10.71min) | 642.603s (10.71min) | 成功 | - |
| 制定计划 | agent_node | 1 | 7.194s (0.12min) | 7.194s (0.12min) | 成功 | - |
| 解析病例文件 | agent_node | 1 | 24.507s (0.41min) | 24.507s (0.41min) | 成功 | - |
| 生成大纲 | agent_node | 1 | 101.629s (1.69min) | 101.629s (1.69min) | 成功 | - |
| 生成故事正文 | agent_node | 1 | 124.078s (2.07min) | 124.078s (2.07min) | 成功 | - |
| 生成配图 | agent_node | 1 | 216.608s (3.61min) | 216.608s (3.61min) | 成功 | - |
| 生成html页面 | agent_node | 1 | 167.934s (2.80min) | 167.934s (2.80min) | 成功 | - |
| history_polling | content_hub_request | 1 | 0.283s (0.00min) | 0.283s (0.00min) | 成功 | - |
| write_case_parse | content_hub_request | 1 | 0.002s (0.00min) | 0.002s (0.00min) | 成功 | - |
| presign_download | content_hub_request | 10 | 0.745s (0.01min) | 0.074s (0.00min) | 成功 | - |
| download_artifact | content_hub_request | 10 | 2.558s (0.04min) | 0.256s (0.00min) | 成功 | - |

#### 审核节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| outline_fact_extraction | audit | 1 | 66.019s (1.10min) | 66.019s (1.10min) | 成功 | - |
| story_fact_extraction | audit | 1 | 90.582s (1.51min) | 90.582s (1.51min) | 成功 | - |
| outline_fact_compare | audit | 1 | 39.555s (0.66min) | 39.555s (0.66min) | 成功 | - |
| story_fact_compare | audit | 1 | 57.914s (0.97min) | 57.914s (0.97min) | 成功 | - |
| image_design_audit | audit | 1 | 5.656s (0.09min) | 5.656s (0.09min) | 失败 | 429 Client Error: Too Many Requests for url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions |
| story_compliance_audit | audit | 1 | 16.617s (0.28min) | 16.617s (0.28min) | 成功 | - |
| audit_analysis | audit | 1 | 15.646s (0.26min) | 15.646s (0.26min) | 成功 | - |
### SM_002

- 结论：**业务审核失败**
- 生成总耗时：**603.121s (10.05min)**
- 审核总耗时：**263.489s (4.39min)**

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
| outline_fact_extraction | audit | 1 | 123.626s (2.06min) | 123.626s (2.06min) | 成功 | - |
| story_fact_extraction | audit | 1 | 102.306s (1.71min) | 102.306s (1.71min) | 成功 | - |
| story_fact_compare | audit | 1 | 61.748s (1.03min) | 61.748s (1.03min) | 成功 | - |
| outline_fact_compare | audit | 1 | 59.181s (0.99min) | 59.181s (0.99min) | 成功 | - |
| image_design_audit | audit | 1 | 15.012s (0.25min) | 15.012s (0.25min) | 成功 | - |
| image_fact_audit_1 | audit | 1 | 30.042s (0.50min) | 30.042s (0.50min) | 成功 | - |
| final_image_fact_audit | audit | 1 | 53.733s (0.90min) | 53.733s (0.90min) | 成功 | - |
| final_image_layout_audit | audit | 1 | 96.752s (1.61min) | 96.752s (1.61min) | 成功 | - |
| image_fact_audit_2 | audit | 1 | 39.379s (0.66min) | 39.379s (0.66min) | 成功 | - |
| image_fact_audit_3 | audit | 1 | 69.559s (1.16min) | 69.559s (1.16min) | 成功 | - |
| image_consistency_audit | audit | 1 | 80.501s (1.34min) | 80.501s (1.34min) | 成功 | - |
| image_fact_audit_4 | audit | 1 | 50.602s (0.84min) | 50.602s (0.84min) | 成功 | - |
| story_compliance_audit | audit | 1 | 25.045s (0.42min) | 25.045s (0.42min) | 成功 | - |
| audit_analysis | audit | 1 | 80.599s (1.34min) | 80.599s (1.34min) | 成功 | - |
### SM_003

- 结论：**业务审核失败**
- 生成总耗时：**589.178s (9.82min)**
- 审核总耗时：**254.845s (4.25min)**

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
| outline_fact_extraction | audit | 1 | 43.343s (0.72min) | 43.343s (0.72min) | 成功 | - |
| story_fact_extraction | audit | 1 | 65.715s (1.10min) | 65.715s (1.10min) | 成功 | - |
| outline_fact_compare | audit | 1 | 40.588s (0.68min) | 40.588s (0.68min) | 成功 | - |
| story_fact_compare | audit | 1 | 34.449s (0.57min) | 34.449s (0.57min) | 成功 | - |
| image_design_audit | audit | 1 | 22.896s (0.38min) | 22.896s (0.38min) | 成功 | - |
| final_image_fact_audit | audit | 1 | 143.242s (2.39min) | 143.242s (2.39min) | 成功 | - |
| final_image_layout_audit | audit | 1 | 109.677s (1.83min) | 109.677s (1.83min) | 成功 | - |
| image_fact_audit_1 | audit | 1 | 34.254s (0.57min) | 34.254s (0.57min) | 成功 | - |
| image_fact_audit_2 | audit | 1 | 146.208s (2.44min) | 146.208s (2.44min) | 成功 | - |
| image_fact_audit_3 | audit | 1 | 51.859s (0.86min) | 51.859s (0.86min) | 成功 | - |
| image_consistency_audit | audit | 1 | 125.331s (2.09min) | 125.331s (2.09min) | 成功 | - |
| image_fact_audit_4 | audit | 1 | 39.547s (0.66min) | 39.547s (0.66min) | 成功 | - |
| image_fact_audit_5 | audit | 1 | 29.717s (0.50min) | 29.717s (0.50min) | 成功 | - |
| story_compliance_audit | audit | 1 | 36.585s (0.61min) | 36.585s (0.61min) | 成功 | - |
| audit_analysis | audit | 1 | 85.646s (1.43min) | 85.646s (1.43min) | 成功 | - |
### SM_004

- 结论：**业务审核失败**
- 生成总耗时：**680.490s (11.34min)**
- 审核总耗时：**276.011s (4.60min)**

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
| outline_fact_extraction | audit | 1 | 62.303s (1.04min) | 62.303s (1.04min) | 成功 | - |
| story_fact_extraction | audit | 1 | 51.512s (0.86min) | 51.512s (0.86min) | 成功 | - |
| story_fact_compare | audit | 1 | 56.557s (0.94min) | 56.557s (0.94min) | 成功 | - |
| outline_fact_compare | audit | 1 | 45.278s (0.75min) | 45.278s (0.75min) | 成功 | - |
| image_design_audit | audit | 1 | 54.725s (0.91min) | 54.725s (0.91min) | 成功 | - |
| final_image_fact_audit | audit | 1 | 110.647s (1.84min) | 110.647s (1.84min) | 成功 | - |
| image_fact_audit_2 | audit | 1 | 62.833s (1.05min) | 62.833s (1.05min) | 成功 | - |
| image_fact_audit_1 | audit | 1 | 73.602s (1.23min) | 73.602s (1.23min) | 成功 | - |
| image_consistency_audit | audit | 1 | 156.956s (2.62min) | 156.956s (2.62min) | 成功 | - |
| image_fact_audit_3 | audit | 1 | 50.054s (0.83min) | 50.054s (0.83min) | 成功 | - |
| final_image_layout_audit | audit | 1 | 139.468s (2.32min) | 139.468s (2.32min) | 成功 | - |
| image_fact_audit_4 | audit | 1 | 69.424s (1.16min) | 69.424s (1.16min) | 成功 | - |
| image_fact_audit_5 | audit | 1 | 97.938s (1.63min) | 97.938s (1.63min) | 成功 | - |
| story_compliance_audit | audit | 1 | 51.434s (0.86min) | 51.434s (0.86min) | 成功 | - |
| audit_analysis | audit | 1 | 60.409s (1.01min) | 60.409s (1.01min) | 成功 | - |
### SM_005

- 结论：**业务审核失败**
- 生成总耗时：**879.133s (14.65min)**
- 审核总耗时：**231.173s (3.85min)**

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
| outline_fact_extraction | audit | 1 | 66.708s (1.11min) | 66.708s (1.11min) | 成功 | - |
| story_fact_extraction | audit | 1 | 58.584s (0.98min) | 58.584s (0.98min) | 成功 | - |
| story_fact_compare | audit | 1 | 58.061s (0.97min) | 58.061s (0.97min) | 成功 | - |
| outline_fact_compare | audit | 1 | 36.418s (0.61min) | 36.418s (0.61min) | 成功 | - |
| image_design_audit | audit | 1 | 22.120s (0.37min) | 22.120s (0.37min) | 成功 | - |
| final_image_fact_audit | audit | 1 | 95.849s (1.60min) | 95.849s (1.60min) | 成功 | - |
| final_image_layout_audit | audit | 1 | 77.988s (1.30min) | 77.988s (1.30min) | 成功 | - |
| image_fact_audit_3 | audit | 1 | 43.831s (0.73min) | 43.831s (0.73min) | 成功 | - |
| image_fact_audit_1 | audit | 1 | 65.629s (1.09min) | 65.629s (1.09min) | 成功 | - |
| image_fact_audit_2 | audit | 1 | 52.080s (0.87min) | 52.080s (0.87min) | 成功 | - |
| image_consistency_audit | audit | 1 | 119.275s (1.99min) | 119.275s (1.99min) | 成功 | - |
| image_fact_audit_4 | audit | 1 | 74.371s (1.24min) | 74.371s (1.24min) | 成功 | - |
| story_compliance_audit | audit | 1 | 37.016s (0.62min) | 37.016s (0.62min) | 成功 | - |
| audit_analysis | audit | 1 | 89.727s (1.50min) | 89.727s (1.50min) | 成功 | - |
### SM_006

- 结论：**业务审核失败**
- 生成总耗时：**738.426s (12.31min)**
- 审核总耗时：**209.215s (3.49min)**

#### 生成节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| ensure_content_hub_auth | content_hub_request | 1 | 0.187s (0.00min) | 0.187s (0.00min) | 成功 | - |
| presign_upload | content_hub_request | 14 | 1.104s (0.02min) | 0.079s (0.00min) | 成功 | - |
| upload_case_image | content_hub_request | 14 | 4.948s (0.08min) | 0.353s (0.01min) | 成功 | - |
| create_agent_task | content_hub_request | 1 | 0.228s (0.00min) | 0.228s (0.00min) | 成功 | - |
| stream_agent_task | content_hub_request | 1 | 728.389s (12.14min) | 728.389s (12.14min) | 成功 | - |
| 制定计划 | agent_node | 1 | 6.939s (0.12min) | 6.939s (0.12min) | 成功 | - |
| 解析病例文件 | agent_node | 1 | 33.312s (0.56min) | 33.312s (0.56min) | 成功 | - |
| 生成大纲 | agent_node | 1 | 63.670s (1.06min) | 63.670s (1.06min) | 成功 | - |
| 生成故事正文 | agent_node | 1 | 199.450s (3.32min) | 199.450s (3.32min) | 成功 | - |
| 生成配图 | agent_node | 1 | 286.977s (4.78min) | 286.977s (4.78min) | 成功 | - |
| 生成html页面 | agent_node | 1 | 137.271s (2.29min) | 137.271s (2.29min) | 成功 | - |
| history_polling | content_hub_request | 1 | 0.230s (0.00min) | 0.230s (0.00min) | 成功 | - |
| write_case_parse | content_hub_request | 1 | 0.003s (0.00min) | 0.003s (0.00min) | 成功 | - |
| presign_download | content_hub_request | 11 | 0.823s (0.01min) | 0.075s (0.00min) | 成功 | - |
| download_artifact | content_hub_request | 11 | 2.581s (0.04min) | 0.235s (0.00min) | 成功 | - |

#### 审核节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| outline_fact_extraction | audit | 1 | 50.132s (0.84min) | 50.132s (0.84min) | 成功 | - |
| story_fact_extraction | audit | 1 | 82.186s (1.37min) | 82.186s (1.37min) | 成功 | - |
| outline_fact_compare | audit | 1 | 44.046s (0.73min) | 44.046s (0.73min) | 成功 | - |
| story_fact_compare | audit | 1 | 43.091s (0.72min) | 43.091s (0.72min) | 成功 | - |
| image_design_audit | audit | 1 | 31.588s (0.53min) | 31.588s (0.53min) | 成功 | - |
| final_image_fact_audit | audit | 1 | 96.140s (1.60min) | 96.140s (1.60min) | 成功 | - |
| image_fact_audit_3 | audit | 1 | 45.103s (0.75min) | 45.103s (0.75min) | 成功 | - |
| image_fact_audit_1 | audit | 1 | 41.964s (0.70min) | 41.964s (0.70min) | 成功 | - |
| final_image_layout_audit | audit | 1 | 98.090s (1.63min) | 98.090s (1.63min) | 成功 | - |
| image_fact_audit_2 | audit | 1 | 62.960s (1.05min) | 62.960s (1.05min) | 成功 | - |
| image_consistency_audit | audit | 1 | 91.047s (1.52min) | 91.047s (1.52min) | 成功 | - |
| image_fact_audit_4 | audit | 1 | 69.193s (1.15min) | 69.193s (1.15min) | 成功 | - |
| image_fact_audit_5 | audit | 1 | 37.748s (0.63min) | 37.748s (0.63min) | 成功 | - |
| story_compliance_audit | audit | 1 | 9.935s (0.17min) | 9.935s (0.17min) | 成功 | - |
| audit_analysis | audit | 1 | 66.363s (1.11min) | 66.363s (1.11min) | 成功 | - |
### SM_007

- 结论：**业务审核失败**
- 生成总耗时：**592.202s (9.87min)**
- 审核总耗时：**296.763s (4.95min)**

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
| outline_fact_extraction | audit | 1 | 95.183s (1.59min) | 95.183s (1.59min) | 成功 | - |
| story_fact_extraction | audit | 1 | 96.355s (1.61min) | 96.355s (1.61min) | 成功 | - |
| outline_fact_compare | audit | 1 | 24.382s (0.41min) | 24.382s (0.41min) | 成功 | - |
| story_fact_compare | audit | 1 | 27.305s (0.46min) | 27.305s (0.46min) | 成功 | - |
| image_design_audit | audit | 1 | 24.718s (0.41min) | 24.718s (0.41min) | 成功 | - |
| final_image_fact_audit | audit | 1 | 64.084s (1.07min) | 64.084s (1.07min) | 成功 | - |
| image_fact_audit_1 | audit | 1 | 48.761s (0.81min) | 48.761s (0.81min) | 成功 | - |
| final_image_layout_audit | audit | 1 | 101.694s (1.69min) | 101.694s (1.69min) | 成功 | - |
| image_fact_audit_2 | audit | 1 | 222.446s (3.71min) | 222.446s (3.71min) | 成功 | - |
| image_fact_audit_3 | audit | 1 | 27.981s (0.47min) | 27.981s (0.47min) | 成功 | - |
| image_consistency_audit | audit | 1 | 82.158s (1.37min) | 82.158s (1.37min) | 成功 | - |
| image_fact_audit_4 | audit | 1 | 37.220s (0.62min) | 37.220s (0.62min) | 成功 | - |
| image_fact_audit_5 | audit | 1 | 66.725s (1.11min) | 66.725s (1.11min) | 成功 | - |
| story_compliance_audit | audit | 1 | 23.000s (0.38min) | 23.000s (0.38min) | 成功 | - |
| audit_analysis | audit | 1 | 49.498s (0.82min) | 49.498s (0.82min) | 成功 | - |
### SM_008

- 结论：**业务审核失败**
- 生成总耗时：**575.167s (9.59min)**
- 审核总耗时：**247.898s (4.13min)**

#### 生成节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| ensure_content_hub_auth | content_hub_request | 1 | 0.166s (0.00min) | 0.166s (0.00min) | 成功 | - |
| presign_upload | content_hub_request | 4 | 0.381s (0.01min) | 0.095s (0.00min) | 成功 | - |
| upload_case_image | content_hub_request | 4 | 0.835s (0.01min) | 0.209s (0.00min) | 成功 | - |
| create_agent_task | content_hub_request | 1 | 0.206s (0.00min) | 0.206s (0.00min) | 成功 | - |
| stream_agent_task | content_hub_request | 1 | 569.778s (9.50min) | 569.778s (9.50min) | 成功 | - |
| 制定计划 | agent_node | 1 | 6.331s (0.11min) | 6.331s (0.11min) | 成功 | - |
| 解析病例文件 | agent_node | 1 | 23.180s (0.39min) | 23.180s (0.39min) | 成功 | - |
| 生成大纲 | agent_node | 1 | 67.165s (1.12min) | 67.165s (1.12min) | 成功 | - |
| 生成故事正文 | agent_node | 1 | 86.025s (1.43min) | 86.025s (1.43min) | 成功 | - |
| 生成配图 | agent_node | 1 | 230.049s (3.83min) | 230.049s (3.83min) | 成功 | - |
| 生成html页面 | agent_node | 1 | 156.236s (2.60min) | 156.236s (2.60min) | 成功 | - |
| history_polling | content_hub_request | 1 | 0.345s (0.01min) | 0.345s (0.01min) | 成功 | - |
| write_case_parse | content_hub_request | 1 | 0.006s (0.00min) | 0.006s (0.00min) | 成功 | - |
| presign_download | content_hub_request | 10 | 0.978s (0.02min) | 0.098s (0.00min) | 成功 | - |
| download_artifact | content_hub_request | 10 | 2.451s (0.04min) | 0.245s (0.00min) | 成功 | - |

#### 审核节点

| 节点 | 类型 | 次数 | 累计耗时 | 平均耗时 | 状态 | 错误 |
|---|---|---:|---:|---:|---|---|
| outline_fact_extraction | audit | 1 | 58.610s (0.98min) | 58.610s (0.98min) | 成功 | - |
| story_fact_extraction | audit | 1 | 74.486s (1.24min) | 74.486s (1.24min) | 成功 | - |
| outline_fact_compare | audit | 1 | 40.151s (0.67min) | 40.151s (0.67min) | 成功 | - |
| story_fact_compare | audit | 1 | 51.769s (0.86min) | 51.769s (0.86min) | 成功 | - |
| image_design_audit | audit | 1 | 13.728s (0.23min) | 13.728s (0.23min) | 成功 | - |
| final_image_fact_audit | audit | 1 | 58.464s (0.97min) | 58.464s (0.97min) | 成功 | - |
| image_fact_audit_1 | audit | 1 | 110.616s (1.84min) | 110.616s (1.84min) | 成功 | - |
| final_image_layout_audit | audit | 1 | 60.415s (1.01min) | 60.415s (1.01min) | 成功 | - |
| image_consistency_audit | audit | 1 | 77.244s (1.29min) | 77.244s (1.29min) | 成功 | - |
| image_fact_audit_2 | audit | 1 | 37.282s (0.62min) | 37.282s (0.62min) | 成功 | - |
| image_fact_audit_3 | audit | 1 | 69.818s (1.16min) | 69.818s (1.16min) | 成功 | - |
| image_fact_audit_4 | audit | 1 | 118.093s (1.97min) | 118.093s (1.97min) | 成功 | - |
| story_compliance_audit | audit | 1 | 4.840s (0.08min) | 4.840s (0.08min) | 成功 | - |
| audit_analysis | audit | 1 | 78.690s (1.31min) | 78.690s (1.31min) | 成功 | - |
### SM_009

- 结论：**业务审核失败**
- 生成总耗时：**560.418s (9.34min)**
- 审核总耗时：**191.025s (3.18min)**

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
| outline_fact_extraction | audit | 1 | 32.552s (0.54min) | 32.552s (0.54min) | 成功 | - |
| story_fact_extraction | audit | 1 | 49.397s (0.82min) | 49.397s (0.82min) | 成功 | - |
| outline_fact_compare | audit | 1 | 23.573s (0.39min) | 23.573s (0.39min) | 成功 | - |
| story_fact_compare | audit | 1 | 19.413s (0.32min) | 19.413s (0.32min) | 成功 | - |
| image_design_audit | audit | 1 | 17.204s (0.29min) | 17.204s (0.29min) | 成功 | - |
| final_image_fact_audit | audit | 1 | 45.407s (0.76min) | 45.407s (0.76min) | 成功 | - |
| final_image_layout_audit | audit | 1 | 119.316s (1.99min) | 119.316s (1.99min) | 成功 | - |
| image_fact_audit_1 | audit | 1 | 23.782s (0.40min) | 23.782s (0.40min) | 成功 | - |
| image_consistency_audit | audit | 1 | 109.053s (1.82min) | 109.053s (1.82min) | 成功 | - |
| image_fact_audit_3 | audit | 1 | 65.808s (1.10min) | 65.808s (1.10min) | 成功 | - |
| image_fact_audit_2 | audit | 1 | 28.762s (0.48min) | 28.762s (0.48min) | 成功 | - |
| image_fact_audit_4 | audit | 1 | 30.621s (0.51min) | 30.621s (0.51min) | 成功 | - |
| image_fact_audit_5 | audit | 1 | 30.915s (0.52min) | 30.915s (0.52min) | 成功 | - |
| story_compliance_audit | audit | 1 | 13.400s (0.22min) | 13.400s (0.22min) | 成功 | - |
| audit_analysis | audit | 1 | 54.416s (0.91min) | 54.416s (0.91min) | 成功 | - |
### SM_010

- 结论：**审核执行失败**
- 生成总耗时：**540.310s (9.01min)**
- 审核总耗时：**349.686s (5.83min)**

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
| final_image_fact_audit | audit | 1 | 63.998s (1.07min) | 63.998s (1.07min) | 成功 | - |
| final_image_layout_audit | audit | 1 | 181.779s (3.03min) | 181.779s (3.03min) | 成功 | - |
| image_consistency_audit | audit | 1 | 105.813s (1.76min) | 105.813s (1.76min) | 成功 | - |
| image_design_audit | audit | 1 | 14.144s (0.24min) | 14.144s (0.24min) | 成功 | - |
| image_fact_audit_1 | audit | 1 | 115.616s (1.93min) | 115.616s (1.93min) | 成功 | - |
| image_fact_audit_2 | audit | 1 | 38.911s (0.65min) | 38.911s (0.65min) | 成功 | - |
| image_fact_audit_3 | audit | 1 | 22.732s (0.38min) | 22.732s (0.38min) | 成功 | - |
| image_fact_audit_4 | audit | 1 | 78.862s (1.31min) | 78.862s (1.31min) | 成功 | - |
| outline_fact_compare | audit | 1 | 39.297s (0.65min) | 39.297s (0.65min) | 成功 | - |
| outline_fact_extraction | audit | 1 | 50.549s (0.84min) | 50.549s (0.84min) | 成功 | - |
| story_compliance_audit | audit | 1 | 24.182s (0.40min) | 24.182s (0.40min) | 成功 | - |
| story_fact_compare | audit | 1 | 300.104s (5.00min) | 300.104s (5.00min) | 失败 | HTTPSConnectionPool(host='dashscope.aliyuncs.com', port=443): Read timed out. (read timeout=300) |
| story_fact_extraction | audit | 1 | 49.577s (0.83min) | 49.577s (0.83min) | 成功 | - |

## 4. 业务审核问题明细

### SM_001

- 综合分：`46.67/100`
- 审核维度：outline_passed=通过；story_passed=不通过；story_compliance_passed=通过；image_fact_passed=不通过
- 故事合规：`通过`；文本未发现超适应症、违规宣传或医学常识错误，合规性良好。
- 图片事实：`blocked`；通过 0/0，失败图片：-
- 审核执行问题：429 Client Error: Too Many Requests for url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions

### SM_002

- 综合分：`61.67/100`
- 审核维度：outline_passed=不通过；story_passed=通过；story_compliance_passed=不通过；image_design_passed=不通过；image_consistency_passed=不通过；image_fact_passed=通过；final_image_layout_passed=不通过
- 故事合规：`不通过`；故事中齐倍安（艾帕洛利托沃瑞利单抗）用于肝细胞癌（HCC）后线治疗，属于超适应症用药，且未标注探索性治疗、未提及MDT及患者知情同意，存在合规风险。
- 图片设计：`不通过`；发现1处严重事实错误：患者年龄在病历中为57岁，但图片大纲中所有角色描述均写为69岁，违背医学记录一致性。
- 图片事实：`success`；通过 4/4，失败图片：-

### SM_003

- 综合分：`56.34/100`
- 审核维度：outline_passed=不通过；story_passed=不通过；story_compliance_passed=不通过；image_design_passed=不通过；image_consistency_passed=不通过；image_fact_passed=不通过；final_image_layout_passed=不通过
- 故事合规：`不通过`；奥希替尼术后辅助治疗时间点可能早于中国获批日期，且文本未标注超适应症/探索性治疗，缺少MDT及知情同意记录，存在合规风险。
- 图片设计：`不通过`；发现1处系统性医学与常识错误：所有图片中的人物性别与病例患者性别不符，且多处年龄不一致，可能造成严重误导。
- 图片事实：`success`；通过 4/5，失败图片：[1]

### SM_004

- 综合分：`66.0/100`
- 审核维度：outline_passed=通过；story_passed=通过；story_compliance_passed=不通过；image_design_passed=不通过；image_consistency_passed=不通过；image_fact_passed=不通过；final_image_layout_passed=不通过
- 故事合规：`不通过`；故事中存在实际使用的PD-1单药辅助治疗未标注超适应症/探索性治疗，以及推荐方案描述为“标准方案”的医学常识错误和违规宣传
- 图片设计：`不通过`；发现1处医学事实错误：图2的prompt中错误地将肝掌红斑描述在指关节（knuckles），而实际应为手掌大小鱼际部位。
- 图片事实：`success`；通过 4/5，失败图片：[3]

### SM_005

- 综合分：`66.67/100`
- 审核维度：outline_passed=不通过；story_passed=通过；story_compliance_passed=不通过；image_design_passed=不通过；image_consistency_passed=不通过；image_fact_passed=不通过；final_image_layout_passed=不通过
- 故事合规：`不通过`；四药联合方案（度伐利尤单抗+贝伐珠单抗+吉西他滨+顺铂）为超适应症探索性治疗，文本未标注，且存在医学常识错误和违规宣传倾向。
- 图片设计：`不通过`；发现2处画面描述与医学事实/临床逻辑不符，以及1处prompt与composition不一致的问题。
- 图片事实：`success`；通过 3/4，失败图片：[1]

### SM_006

- 综合分：`71.34/100`
- 审核维度：outline_passed=不通过；story_passed=不通过；story_compliance_passed=通过；image_design_passed=不通过；image_consistency_passed=不通过；image_fact_passed=通过；final_image_layout_passed=不通过
- 故事合规：`通过`；患者故事文本符合医学合规要求，未发现超适应症、医学常识错误、违规营销或隐私泄露问题。
- 图片设计：`不通过`；发现1处医学事实错误（图4输液部位不符合R-CHOP临床规范）和1处源数据一致性错误（患者年龄矛盾）。
- 图片事实：`success`；通过 5/5，失败图片：-

### SM_007

- 综合分：`75.0/100`
- 审核维度：outline_passed=通过；story_passed=通过；story_compliance_passed=不通过；image_design_passed=通过；image_consistency_passed=不通过；image_fact_passed=通过；final_image_layout_passed=不通过
- 故事合规：`不通过`；联合方案（仑伐替尼+信迪利单抗+化疗）用于肝内胆管癌（ICC）属超适应症探索性治疗，但文本未标注“超适应症/探索性治疗”，且缺少患者知情同意及风险获益说明。
- 图片设计：`通过`；审查通过：该图片大纲未发现违背医学事实或临床实际情况的视觉设定。
- 图片事实：`success`；通过 5/5，失败图片：-

### SM_008

- 综合分：`82.5/100`
- 审核维度：outline_passed=通过；story_passed=通过；story_compliance_passed=通过；image_design_passed=通过；image_consistency_passed=不通过；image_fact_passed=不通过；final_image_layout_passed=不通过
- 故事合规：`通过`；该患者故事文本涉及的疾病和用药方案均为常规治疗，无超适应症、医学常识错误或违规营销内容，且包含必要的合规声明，审核通过。
- 图片设计：`通过`；审查通过：该图片大纲未发现违背医学事实或临床实际情况的视觉设定。
- 图片事实：`success`；通过 3/4，失败图片：[3]

### SM_009

- 综合分：`80.0/100`
- 审核维度：outline_passed=通过；story_passed=通过；story_compliance_passed=通过；image_design_passed=通过；image_consistency_passed=不通过；image_fact_passed=通过；final_image_layout_passed=不通过
- 故事合规：`通过`；文本已明确标注超适应症/探索性治疗，包含知情同意、风险获益说明及免责声明，无医学常识错误、违规宣传或隐私泄露，整体合规。
- 图片设计：`通过`；审查通过：该图片大纲未发现违背医学事实或临床实际情况的视觉设定。
- 图片事实：`success`；通过 5/5，失败图片：-


## 5. 结论口径

- 生成执行成功只表示 Agent 生成产物已成功落盘，不代表故事内容通过审核。
- 审核执行失败表示模型调用、超时或本地审核节点执行异常，不能直接归因为业务问题。
- 业务审核失败表示审核节点正常返回，并明确指出病例事实、治疗合规或图片设计问题。
- `SM_001` 同时存在业务审核未通过和图片设计审核 429，属于“审核部分节点执行失败且业务结果不通过”，不应只按业务问题归因。
- `SM_010` 的生成已成功，但审核因硬规则节点读取超时中断，当前不能判断其业务审核是否通过。

