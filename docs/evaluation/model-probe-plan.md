# 免费公开 CPU runner：开放权重模型隔离实验

状态：前三次运行 39457606306、39460331994、39463843672 已独立封存。v3 的 4B 运行耗时 171.215 秒、canary 通过、5/6 raw 合格，但已暴露主语、依赖入口、平台与费用错误，不能接入生产。当前只准备一次 v4 受控两步开发诊断；沿用同 4B、runtime 和六项已见输入，尚待远程执行。旧档案及首次分数不覆盖。

用户授权的研究问题：在现有公开 GitHub 仓库的标准托管 Actions runner 上，临时运行无需个人密钥的开放权重模型，能否在有限时间内把官方资料转换为有逐字来源的中文事实？本实验不接入 collector、content、推荐、正式 JSON 或 Pages，不使用付费 AI/翻译 API，不要求个人电脑常驻或新增硬件。

## 冻结输入与依赖

依赖只使用 Python 3.12 标准库，以及下载后校验的官方 llama.cpp CPU 二进制和 Qwen GGUF；无 pip 安装、`curl | sh`、HF Token 或自动选择 latest。完整 URL、字节大小、校验和与出处保存在 `scripts/model_probe_pins.json`。

- [llama.cpp b11756 官方 release](https://github.com/ggml-org/llama.cpp/releases/tag/b11756)：`llama-b11756-bin-ubuntu-x64.tar.gz`，22,240,705 字节，SHA256 `9def57d9e9b0149979a9ceba40896a4e2bf88c94734069a5567d2f487ceab551`。摘要来自官方 GitHub release asset API 的 `digest`，开发机匿名 API 限流时由协调者用已有凭据只读获取；凭据不进入脚本、日志或模型请求。
- v1/v2 使用的 [Qwen3-1.7B-GGUF 固定版本](https://huggingface.co/Qwen/Qwen3-1.7B-GGUF/tree/90862c4b9d2787eaed51d12237eafdfe7c5f6077)：revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`，`Qwen3-1.7B-Q8_0.gguf`，1,834,426,016 字节，LFS SHA256 `061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a`，官方模型卡标 Apache-2.0。该官方仓库此次元数据只有 Q8_0，不冒称 Q4。
- v3 使用 [官方 Qwen3-4B-GGUF 固定版本](https://huggingface.co/Qwen/Qwen3-4B-GGUF/tree/bc640142c66e1fdd12af0bd68f40445458f3869b)：revision `bc640142c66e1fdd12af0bd68f40445458f3869b`，`Qwen3-4B-Q5_K_M.gguf`，2,889,513,184 字节，LFS SHA256 `aca596860e8cb40af6539e3f2ea40df305f42515deac56d49c08d39a02e6533f`，Apache-2.0。来源、兼容依据与未实测限制见 [模型备选研究](model-alternative-research.md)。下载时仍同时核对字节大小与摘要，不在个人电脑下载推理。
- [固定版 server 接口说明](https://github.com/ggml-org/llama.cpp/blob/b11756/tools/server/README.md)：CPU 参数、`chat_template_kwargs`、`timings_per_token`、`/apply-template` 与 `/tokenize` 按该版核对。JSON Schema 请求结构经首次失败后按实际 parser 再核对，见下节；README 中扁平 `schema` 示例不符合本次 JSON Schema 解析分支。Qwen [官方模型卡](https://huggingface.co/Qwen/Qwen3-1.7B-GGUF)说明 `/no_think`；本实验另显式关闭 thinking，temperature 固定 0 是实验约束，不是官方最优采样推荐。

开发资料固定于 `tests/fixtures/model_probe/cases.json`，来源是首次评分已经归档的 `blind-first-03895d3/inputs.json` 中的公开官方文字，保留 URL、行号、核对时间及片段 SHA256。未导入标签，也未读取任何未评分私有输入。这六项从此属于**已见开发回归**，以后不能重新声称盲评。

| 项目 | 固定覆盖点 |
| --- | --- |
| TranslucentTB/TranslucentTB | 桌面用途、Windows 10/11 与仅限 Windows 11 的便携包区别、费用与许可区别 |
| AdguardTeam/AdGuardHome | 自部署 DNS 服务、设备配置，以及不能屏蔽 YouTube/Twitch 广告的否定句 |
| sharkdp/fd | CLI 文件查找、官方二进制入口、不能把 find 全部能力归给 fd |
| huggingface/transformers | 开发库/模型定义框架、Python/PyTorch 前提、不能把神经网络积木工具箱作为用途 |
| hehonghui/awesome-english-ebooks | 中文资料集合；推荐的英阅 App 功能、iOS/Android 链接属于他者，不能移植给仓库 |
| squoosh/squoosh | 本次归档官方资料获取失败；不给模型任何有效片段，检查是否用记忆编造 |

此样本覆盖六种资料/形态边界，不代表六大产品场景的统计覆盖，也不是 40 或 120 项效果验收。

## 运行隔离与预算

仅允许 `workflow_dispatch` 的 `model_probe_only=true`，默认 false，与原 `probe_only` 互斥；两者同时 true 立即失败。所有采集、提升、提交、发布和采集失败归档步骤均排除模型模式。模型模式 checkout 不持久化 GitHub 凭据。模型 Python 入口再次检查 GitHub Actions、Linux x86_64、公开仓库 event、`GITHUB_EVENT_NAME=workflow_dispatch`，且 event inputs 明确为独占 `model_probe_only=true`（布尔 true 或字符串 `"true"`），个人电脑调用只写失败诊断，不下载或推理。

命令入口为 `bash scripts/model_probe.sh`。该入口由协调者在代码审核、提交后通过现有 `update.yml` dispatch，本文件不代替实际运行记录。脚本不接受外部模型服务地址：llama-server 只监听 `127.0.0.1` 的临时端口；HTTP 客户端禁用代理，且不加任何 Authorization。server 子进程只继承 PATH、LANG、LD_LIBRARY_PATH 和 OMP_NUM_THREADS；不会接收 GitHub/HF/付费服务 Token。

固定 CPU-only `-ngl 0`、推理及 prefill 线程各 4、单 slot、context 4096、temperature 0、每项最多生成 700 tokens、thinking 关闭。全实验含下载限制 900 秒；独立截止异常不会被单项网络错误重试捕获。单项 completion 超时 120 秒，载入等待最多 120 秒；workflow 诊断模式上限 17 分钟为失败报告和 artifact 预留收尾时间，默认生产任务超时保持 GitHub 原有 360 分钟。

每项先 `/apply-template` 形成完整 system+user prompt，再 `/tokenize`，记录实际输入 token，预留 700 输出与 8 个 special token 余量；超过 4096 不推理、不自动删片段。该检查不保证 700 tokens 足够完整输出；若被截断，保留原文并记失败。模型和二进制放系统临时目录，按 size+SHA256 两项验证后才启用，退出清理；下载/校验/启动失败均保留报告并退出非 0，不自动降级成“成功”。

## v3 输出、指标与人工判断（历史协议）

模型 raw JSON 严格包含八个字段：`purpose`、`audience`、`platforms`、`form`、`requirements`、`path`、`fees`、`license`。每字段只有 `{value, ref_id}`，不输出 `source_quote` 或 `unknowns`。`value` 是简短中文断言或 null；`ref_id` 只能选当前 case 的输入 ID 或 null。两者必须同时有效或同时为 null，禁止把无效配对转换成未知凑合格率。raw JSON 保留到 `raw_model_output`，原始文本另存 `raw_model_text` 和 `case-*.txt`。

schema 的 `ref_id.enum` 每 case 单独生成；无来源时 enum 仅有 null，但 **value 仍允许 string 或 null**，且实际调用模型，因此仍可观察“凭记忆给 value 却没有来源”的失败。程序不预填全 null，也不隐藏无来源控制。重复键、缺字段、额外 `unknowns/source_quote`、空字符串、外来 ref_id 或 partial null 均判无效；`validation_errors` 留下原因，`runtime_bound_output` 为 null，raw 原样保留。

仅 `raw_valid` 的输出才由程序构建 `runtime_bound_output`：按模型选的 ref_id 取完整冻结片段，核对 SHA256 后原样复制为 `source_quote`，再依据 null 配对计算 `unknowns`。此绑定与未知列表**是程序生成，按构造成立**，不能拿它计算“模型逐字引用准确率”。例如模型把否定句翻成肯定，即使选中该否定句的 ref_id、程序成功绑定原文，语义仍错误。来源选对、主语属于本项目、原文蕴含断言、否定与费用边界都继续交独立人工评测。

path 有一个明确的机械边界：非空 `path.value` 必须是所选 ref 原文逐字包含的 HTTPS URL，不能凭记忆拼官网、wiki 或应用商店路径。不符合时记录 `invalid_path_source`，保留 raw、禁止绑定，不能改成 null。该检查不证明链接当前可访问、URL 官方身份或页面支持该使用路径。其他字段不增加关键词语义打分。非空 value 没有中文字符时保留原值并列入 `language_review_fields`；程序不假装完成翻译，URL、系统名或许可证标识也可进入这份待审列表。

`.model-probe/report.json` 保存固定 pins、fixture hash、提交 SHA、runner/CPU 信息、下载耗时与实际摘要、加载到 health-ready 墙钟耗时、每项 prefill/generate 时间及 token/用量、每项墙钟耗时、server `/proc/PID/status` VmHWM 峰值 RAM（KiB）。canary 仍单独验证实际二进制约束，不计入六项内容样本。单次无 warmup，加载时间不包括第一次推理的全部运行成本；prefill/generate 采用 server 返回 timings。

机器指标分别报告：固定六项请求分母、已尝试数、JSON 可解析数、schema 有效数、nullpair 有效数、raw 协议有效数、程序成功绑定数、非空字段数及有非空断言的项目数。空值协议合格不代表产生了有用介绍；无来源控制另报八字段的真实 null 配对率。`model_source_selection_accuracy`、`semantic_accuracy`、`semantic_refusal_rate` 均为 null，待独立原文核对。v3 不再输出 `quotes_match` 等容易被误解成模型引用正确性的指标。

只有 canary 通过、六项均正常 stop、raw 协议与 path 边界通过、thinking 未产生且计时齐全，进程才返回 0 和 `runtime_complete_semantics_unverified`。所有语义始终 `human_review_required`；任一协议/运行失败为非 0 的 `failed_unverified`。任何状态都不改变正式 JSON 或公共 ProjectFacts API。

Actions artifact 只收 `.model-probe/report.json`、`case-*.txt`（含 canary）和小型 `server.log`，保留 7 天，不上传权重、二进制、临时目录或凭据。`.model-probe/` 已加入 gitignore。

## 离线验证与下一道门槛

`python3 -m unittest tests.test_model_probe` 验证引用归属、未知字段一致性、严格 JSON、校验失败不启用下载、输入片段 hash、deadline 不被吞掉、超长输入不推理、个人电脑拒绝执行并保留报告、CPU/loopback/生成上限，以及模型模式跳过正式采集发布。`bash -n scripts/model_probe.sh` 和 `git diff --check` 作为脚本及补丁基本检查。

首次远程输出已经封存于 `docs/evaluation/model-first-39457606306/`，它保留原始失败结果；第二版输出已独立封存于 `docs/evaluation/model-second-39460331994/`。首次约 126 秒完成并录得约 2.61 GiB server RSS 峰值，但由于请求适配错误，不能把该次格式失败解释成模型无法遵守本 schema，也不能当作内容验收。若公开 runner 的下载/内存/耗时失败，如实记录对应阶段；若技术运行通过但中文语义不够，仍不接入生产。只有在六项开发材料经过独立语义审查之后，才考虑更大固定评测；再次声称未见效果必须使用新的独立未见输入，不复用这六项或首次已归档的 40 项。


## 首次失败根因与第二版验证边界

首次 [Actions 39457606306](https://github.com/w452187971/gitradar/actions/runs/39457606306) 的六项均正常 stop、均可解析为 JSON，但没有字段级 `{value, source_quote, ref_id}` 对象。固定版本 [server-common.cpp](https://github.com/ggml-org/llama.cpp/blob/b11756/tools/server/server-common.cpp#L1357-L1382) 的 `oaicompat_chat_params_parse` 在 `response_format.type=json_schema` 时，只读取 `response_format.json_schema.schema`；首次代码按同版 README 示例传 `response_format.schema`，实际被读成空 schema，再归一化为 `{"type":"object"}`。因此服务端约束实际只是任意 JSON 对象。另一个缺口是 system prompt 没有明确展示八字段的嵌套结构。

本次读取的完整官方 `server-common.cpp` SHA256 为 `b4f4aae7eed919f914d132ae64416a0e7cfb23442161af6f63ba8d902954d442`，关键解析分支在 1357–1382 行，`inputs.json_schema` 传入 chat 模板在 1423 行。此处以固定版本实际实现作为请求契约依据，不将 README 的不一致直接归因模型。

第二版 `responseFormat()` 统一生成 `response_format={type:"json_schema",json_schema:{name,strict:true,schema}}`。主样本 prompt 明确八个字段均为嵌套对象，并序列化完整 `OUTPUT_TEMPLATE`，要求按资料填写而非机械全答 null。主样本、样本片段与证据 hash 不变；原无来源控制仍实际调用模型，诊断不会通过提前拒答遮住幻觉。

在六项样本前新增独立基础设施 canary：prompt 故意要求错误的 `{"purpose":"SHAPE_BYPASS"}`，schema 则强制 `purpose` 是带 `value/source_quote/ref_id` 的对象，且各值为固定常量。只接受与预定对象精确相同、正常 stop、无 thinking 且 timing 完整的返回。该项最多 128 生成 tokens，沿用 CPU、loopback、总 900 秒与上下文预检约束。canary 失败写 `failure_kind=schema_canary_infrastructure`、保留原文、停止所有六项主样本并返回非 0；它不进入六项内容质量分母。只有 canary 通过才测模型对六项官方资料的实际行为。canary 通过本身不证明中文语义准确。

第二版报告 `version=2`、`request_contract=b11756-nested-json-schema-v2`，完整保留 canary 请求、token 预算、原文、解析输出与计时。原文文件 `case-00-schema-canary.txt` 由现有 `case-*.txt` 附件规则保存，不上传模型权重。首次八个文件及 manifest hash 保持原样，新的远程结果另按新 run ID 封存。

`tests/test_model_probe_contract.py` 以真实 loopback HTTP 序列化请求，对**冻结的 b11756 解析协议模拟器**验证新 nested schema 被读取、旧 flat schema 退化为任意对象，并验证 canary 前置关卡。该测试在修复前实际失败、修复后通过，不是 grep 源码；但它不执行完整上游 C++，不能代替对官方二进制的远程 canary。后者才验证实际解析及约束行为。第二版提交前的 18 项离线测试通过，命令为 `python3 -m unittest tests.test_model_probe tests.test_model_probe_contract`；现第二次远程结果已封存，canary 通过但旧字段协议及语义未达标。


另修复普通 CI 测试继承 runner 环境的问题：原“个人电脑拒绝执行”子进程继承 `GITHUB_ACTIONS=true` 和公开仓库事件，在 Linux 常规 collector CI 中会误触发真实模型下载与推理；Mac 本地通过不足以发现这一点。该测试现显式传 `GITHUB_ACTIONS=false`，不再依赖宿主环境。脚本入口同时要求显式 `workflow_dispatch` 与互斥的模型诊断输入；模拟 Linux/public Actions 的 schedule、无输入、false 输入、普通 batch probe、冲突模式与非布尔值均须在下载前拒绝。常规测试仍完全离线，不靠模型探针入口兜底以外的宿主默认值。


## v3 的对照范围与结果门槛

v2 实测证实 canary 与嵌套 schema 有效，但出现未知列表与已填值矛盾、翻译/编造原文、把 r1 当引用文字、凭记忆猜平台和 URL 等问题；仅两个全未知项目通过旧格式检查。v3 把逐字原文复制与未知列表计算交给确定性代码，模型只承担中文断言与选择现有来源，缩小本次需要评估的输入输出边界。

v3 同时改用固定官方 4B Q5_K_M 和简化协议，因而即使结果变好，也不能把提升单独归因于参数量或量化方式。六项仍是原有已见开发样本，整体 fixture SHA256 保持 `96978ccade1edc8841ad23d7aef2676734157c6b2826a6707d5dbcabe64917bf`；不增加答案、不借助付费模型翻译、不把复测重新称为盲评。v3 已实测完整运行 171.215 秒、峰值 RSS 4,286,684 KiB；这些只描述本次六项的运行情况，语义不达标，不能按比例推算更大样本或下一协议。

v3 的独立 schema canary 保持旧固定 quote 对象测试，仅用于基础设施约束证明；它不代表主样本仍要求模型生成 quote。主样本原文 hash、raw/bound 分离、nullpair、逐字路径、无来源真实推理、非中文待审与语义 pending 边界由离线测试覆盖。当前命令为 `python3 -m unittest tests.test_model_probe tests.test_model_probe_contract tests.test_model_probe_v3`，共 28 项；未下载或运行本机模型。首次与 v2 结果档案保持不变，v3 结果已按 run 39463843672 独立封存。


## 当前 v4：一次受控选择与翻译开发诊断

本次只改变抽取协议，固定使用现有 4B/Q5_K_M 与 llama.cpp b11756 pins，固定同六项已见开发资料。没有读取私有未见输入、反例名单或标签，也没有按仓库名分支。复用原下载、size+SHA256、服务、loopback、凭据白名单、显式诊断入口和 canary；不导入生产模块或写正式数据，不修改公共 ProjectFacts。

### 完整上下文与 stage1 契约

`paragraphPacket()` 按原空行分配 `r1:p1` 之类的确定性段落 ID，保留原分隔字符。所有段落顺序拼接必须逐字重建原 `source_quote`，并先核对原来源 SHA256；代码块、标题、否定句、限制段和空白都不裁剪。段落 hash 留在本地 packet/报告用于审计；发给模型的 `promptPacket()` 只含 `ref_id`、`paragraph_id`、`text`，不携带这些机器 hash。若原文本身写了 checksum，原文内容仍完整保留。

stage1 接收所有原段落，只输出八个字段，每字段结构固定为：

```json
{"ref_id":"r1","paragraph_id":"r1:p2","relation":"project"}
```

这里只示例单个字段值；实际八字段全部必需。ref 与段落 ID 均限定在当前 case 输入 enum，不允许 `value`、`quote`、概括或额外键。运行时还验证段落确属所选 ref，不能跨来源拼接。无选择时两个 ID 同时 null，relation 必须 unknown。选择了有效段落时 relation 可以是 `project`、`dependency`、`third_party` 或 `unknown`。这些关系**全部是模型判断，尚未核实**，不能把选择了 project 算成真实主语正确。

每字段只选一个完整段落，是一次有限的单断言实验；它不能证明已找到全部前置条件。stage1 的 JSON、原始文本、协议结果，以及程序取出的 `selected_evidence` 原段落和 hash，均保存给独立评审。

### stage2 契约与机械边界

stage2 仍接收**全部原始段落**及 stage1 选择，不是只看摘出来的一句话。模型输出沿用 v3 八个 `{value, ref_id}`，要求忠实中文、保留否定和条件，不新增来源或推断事实。每字段 ref enum 只允许该字段 stage1 所选且标 project 的 ref，或 null；未选择及非 project 字段 ref enum 只有 null，但 value 仍允许字符串，程序不会预填未知以隐藏猜测。

运行时保留 raw，拒绝无效 null 配对、外来/未选择的来源、非 project 字段的非空断言。path 另要求完整 HTTPS URL token 出现在所选段落，不能跳到同 ref 的其他依赖段。非 path 字段的机械检查**只能约束同 ref 和模型所报 relation**；它无法判断中文是否出自所选 paragraph，更不能证明主语、蕴含关系或前提完整性。即便两阶段完全一致，也可能一致地理解错误，必须独立语义评分。没有新增关键词语义评分或自动纠正。

只在两阶段均正常完成、stage1 选择合法、stage2 raw 及上述机械边界通过后，才调用原有绑定函数。`runtime_bound_output` 继续复制完整冻结 ref 原文并程序计算 unknowns；`selected_evidence` 另列所选段落供核对。模型没有自由生成 quote，程序复制不计作模型引用准确率。非中文原值仍保留并标待审；不得伪造翻译完成。

### 固定预算、失败与无来源控制

所有项目统一 stage1 **300**、stage2 **400** 最大生成 tokens，合计最多 **700**，不按案例调配、不把 stage1 剩余额度加到 stage2。两阶段要求紧凑 JSON。每阶段报告的 `max_tokens`、HTTP 请求值、实际 tokenizer 预算中的 `reserved_output_tokens` 必须一致；还核对返回 usage 未超阶段上限。

每阶段独立 `/apply-template` + `/tokenize`，保留 8 个 special token 余量，完整 prompt 加本阶段预留超过 4096 就失败，不删来源。stage1 截断、超限、无效选择时不继续 stage2；stage2 截断、超限或无效输出时不绑定。各阶段保留原始文本、可解析的 raw、finish_reason、usage、prefill/generate、墙钟时间与错误。当前 case 在执行前就加入报告，因此全局截止发生在第二阶段时，仍保留第一阶段已完成结果和第二阶段失败状态。

无来源 case 没有程序提前拒答：合法 stage1 后，stage2 仍实际推理；它若凭记忆返回非空 value，raw 留下并计失败。若 stage1 自身给出非法选择，则该 case 已是可见失败，stage2 标 not_attempted，不能当作两步拒答成功。无来源控制只检查该例的缺证据行为，不证明一般语义可靠性。

CPU-only、4 线程、单 slot、非思考、每阶段 completion HTTP 最多 120 秒，以及含下载的全实验 **900 秒**硬截止不变。canary 另有 job 级 128-token 上限，不计入每个内容项目的 700。两次推理与更完整 prompt 会改变成本，不能把上一轮 171 秒乘二当作实际耗时保证；真实耗时、RAM 和能否在预算内完成六项，只有本次远程运行才能确认。未运行项目继续保留在固定六项分母，报告分别记录 stage1 解析/选择有效数、stage2 实际调用数、总生成 tokens 与最终非空覆盖。

报告 `version=4`、`request_contract=b11756-controlled-select-translate-v4`。每项有 `stage1`、`stage2`、`selected_evidence`、stage2 的 `raw_model_output` 和 `runtime_bound_output`；原文文件为 `case-NN-stage1.txt` 与 `case-NN-stage2.txt`，由现有 artifact 通配规则保存。`model_relation_accuracy`、`model_source_selection_accuracy`、`semantic_accuracy` 与 `semantic_refusal_rate` 均保持 null，关系/语义始终待独立审核。

### 验证与停止条件

`tests/test_model_probe_v4.py` 覆盖完整原文重建、CRLF/空白/代码块与 hash、prompt 不携带机器 hash 但不删除正文 checksum、严格选择契约、关系与来源约束、两阶段实际调用、阶段上限/预留一致、截断不继续、同 ref 其他段落路径拒绝、无来源幻觉保留，以及全局截止保留当前阶段。原 v3 的 raw/bound 与路径边界测试继续保留，改用两阶段 mocked completion。

此次只运行固定六项开发组一次。由独立评审分别检查 stage1 是否选对对象与证据、stage2 是否忠实翻译，以及最终正确覆盖是否改善；格式合格或全答未知不能替代效果。若仍有重大主语、否定、费用或前提错误，停止按这六项调 prompt，不自动增加试验。只有实测值得继续时再冻结实现、由独立评测者开展新的未见组；本实验不宣称已泛化，不直接发布模型内容。
