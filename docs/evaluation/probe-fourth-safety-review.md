# 第四次两步模型诊断独立安全审查

结论：**可以执行一次隔离的两步开发诊断**。本次审查没有发现阻断诊断的机械约束或运行隔离问题；它不代表语义合格、前提完整或允许模型内容进入生产。只有真实远程运行才能确认两次推理的耗时、内存与效果。

冻结脚本 SHA256：`8d1a5d0c1d2f4aae51815216cb876cf7ab37300154cf902d2b0d77989e2a3ede`。固定模型 pins 未变，仍为官方 Qwen3-4B Q5_K_M 与 llama.cpp b11756；输入仍为同六项已见开发案例，fixture SHA256 `96978ccade1edc8841ad23d7aef2676734157c6b2826a6707d5dbcabe64917bf`。未访问私有未见/反例目录，没有下载权重、执行模型、改动脚本或正式数据。

## 已独立确认的边界

- `paragraphPacket()` 核对冻结来源 hash，并按原空行分配稳定段落 ID；六案例逐字重建检查通过。标题、代码、限制、否定及原分隔字符保留。这里“完整”只指全部冻结的 source_quote，不表示读完完整 README 或发现了所有前提。
- 发给两个阶段的 `promptPacket()` 保留每个 ref、段落 ID 与 text，省去机器生成的段落 SHA256；本地 packet、selected_evidence 与报告仍保留 hash。独立比较两个请求中的所有原文片段均未丢失；正文自己写的 checksum 不属于被删除的机器字段。
- stage1 只能生成八字段的 ref_id、paragraph_id、relation，来源及段落 ID 受当前输入 enum 限制。运行时拒绝跨 ref 的段落组合、非法/缺失字段、额外自由 quote，以及非法空值组合。relation 属于模型判断，合法 project 标签并不证明真实主语正确。
- stage2 接收全部原始段落和 stage1 选择。每个非空字段必须使用该字段选择的 project 来源；非 project 的非空断言、换来源、无效 null 配对均拒绝。path 另须为所选段落里的完整 HTTPS URL token，不能借同 ref 的另一个依赖段落补地址。
- 两阶段原文、可解析 raw、错误与状态分别保存。独立合成的非法输出均保持 raw 原样，bound 为 null；没有把失败内容改成 null 后计作合格。stage1 无效或截断不执行 stage2，stage2 失败不绑定。
- 绑定继续由程序复制完整冻结 ref 原文，unknowns 由合法 null 配对计算。所选段落另存在 selected_evidence，不能把程序复制包装成模型引用准确率。

## 独立机械反例与测试

以下检查使用内存合成资料与 mocked loopback 响应，没有调用真实模型：

| 合成输入/输出 | 独立观察 |
| --- | --- |
| ref_id 为 r1、paragraph_id 却属于 r2 | stage1 raw 保留，stage2 未调用 |
| relation 为 dependency、third_party 或 unknown，却生成非空项目断言 | 三种均拒绝，raw 保留，bound=null |
| stage2 改用另一个真实但未选择的 ref | 拒绝字段来源替换，raw 保留 |
| path 借用同 ref 另一个未选择段落的依赖 URL | `path_not_in_selected_paragraph`，bound=null |
| stage2 prompt 3690 tokens，再预留 400+8 | 推理前阻断，已完成 stage1 raw 保留 |
| 无来源 case 的 stage2 猜用途并带 null ref | 两阶段均实际调用，猜测保留，7/8 null 配对只作描述，bound=null |
| 父环境带三个合成 Token 变量 | server 子进程仅四个允许环境键，退出调用 terminate |

最终独立运行 `python3 -m unittest tests.test_model_probe tests.test_model_probe_contract tests.test_model_probe_v3 tests.test_model_probe_v4`：**41 项通过**。测试覆盖阶段 token 用量与请求预留一致、截断/超限、全局截止保留当前 case、失败 canary 停止主样本及显式诊断入口。`git diff --check` 通过。未在本次审查中重跑整仓测试或使用网络。

## 没有被机械解决的事情

独立故意把 “does not support Windows” 写成肯定断言，或从同 ref 的未选择段落取非 path 事实，仍能通过字段/来源机械检查；报告继续保持 `human_review_required`。非 path 字段没有可自动证明中文蕴含的段落约束。即使两个阶段都选择并复制一致，也可能一致地理解错误。

无来源阶段2的 value 仍允许 string/null，schema 只把 ref_id 限成 null；因此猜测并未被 schema 预先隐藏。`no_source_unknown_rate` 只能描述这一受约束控制的实际 null 配对，不能叫模型总体拒答准确率。关系、来源选择、语义与语义拒答准确率全部为 null，等待独立评分。格式有效、全答未知、真实主语正确和有用中文介绍是不同结论。

每字段只选一段、翻译单条事实，不能证明运行条件或限制完整。费用/许可未知、第三方主语、依赖路径与否定句仍须原文审阅；此次没有引入关键词“语义合格”打分。

## 预算与隔离

每项固定 stage1 300、stage2 400，合计最多 700 生成 tokens，不借用另一阶段剩余额度；每阶段独立实际模板/tokenizer 预检，context 4096，余量 8。实际返回 usage 超阶段预算或缺失会失败。canary 为独立的 128-token 基础设施检查，不进入六项内容质量分母。

CPU-only、4 个推理与 prefill 线程、单 slot、关闭思考、loopback、禁用代理、无 Authorization、含下载的 900 秒全局截止保持不变。诊断入口要求公开 Linux x86_64 Actions 与独占显式 model_probe_only；workflow 不持久化 checkout 凭据，跳过采集、promote、commit 和发布。二进制与模型仍先验 size+SHA256，artifact 只保存小型诊断文本，不上传权重。

后续仅执行这一次固定开发组，并独立评 stage1 的主语/证据与 stage2 的忠实度。若仍有重大主语、否定、费用或前提错误，保留结果，停止围绕这六项继续调 prompt；不得把反复开发复测称作新盲评，也不自动扩大试验或上线内容。
