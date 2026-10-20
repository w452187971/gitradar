# 首次真实 CPU 模型输出：独立语义复核

评阅者：独立 AI 代理，**不是人工或真人审核**。日期：2026-10-21（Asia/Shanghai）。运行 [39457606306](https://github.com/w452187971/gitradar/actions/runs/39457606306)，代码 `9878366f4dd78e441e001fe27caf1d34ad51c16e`。只评阅首次原始结果，不改探针、输入、代码或首次 40 项盲评。

## 结论与分母

本次输出不能进入生产：6/6 可解析 JSON，但规定的字段对象、证据 quote/ref 和 unknowns 契约通过 0/6。无论格式原因最终如何，固定输入已足以确认第三方主语错归、字段错位与无来源猜测。`response_format` 是否实际启用 grammar 正另行核对，本报告不把格式失败直接归因为模型能力，也不据一次运行断言该模型不可用。

六个样本是首次盲评之后选出的**已见开发样本**，不是第二次盲评。按每样本 8 字段计，共 48 个字段位置：34 个非空输出、14 个 null。对非空值进行独立语义诊断，得到 **支持 16、错误 3、来源不足 15**；null 统一列作 **未输出 14**，既不奖励为正确，也不自动判为错误。这些分类不恢复其已失败的证据契约。

| 维度 | 字段位置 | 非空断言 | 支持 | 错误 | 不足 | 未输出 |
|---|---:|---:|---:|---:|---:|---:|
| 用途 | 6 | 6 | 5 | 0 | 1 | 0 |
| 受众 | 6 | 6 | 0 | 0 | 6 | 0 |
| 平台 | 6 | 6 | 2 | 2 | 2 | 0 |
| 交付形态 | 6 | 6 | 3 | 0 | 3 | 0 |
| 关键前提与限制 | 6 | 1 | 1 | 0 | 0 | 5 |
| 官方获取路径 | 6 | 5 | 2 | 1 | 2 | 1 |
| 费用 | 6 | 1 | 1 | 0 | 0 | 5 |
| 许可 | 6 | 3 | 2 | 0 | 1 | 3 |
| 合计 | 48 | 34 | 16 | 3 | 15 | 14 |

用途、平台、路径的有断言样本分别只有 6、6、5，均远少于每维 30 条门槛；**完整效果准确率未验证，不计算或宣称验收通过率**。平台数组作为一个字段断言评价，没有将多个系统拆开扩大分母。

## 口径

仅依据 [固定输入](../../tests/fixtures/model_probe/cases.json) 实际传给模型的 `refs[].source_quote`。不为模型补读完整 README、外链或外部知识。每个非空字段的所有实质部分均获直接文字支持，才记“支持”；部分正确而额外延伸无依据，记“不足”。“错误”限于输入能证明的主语错归或产品字段语义错位。“不足”不等于现实中必定为假；URL 未出现不能据此宣称 URL 实际不可达。

任务明确要求受众不能凭用途臆测。因此诸如“Windows 用户”“英语学习者”等即便合理，也不能据平台或用途自动视为直接受众证据。Transformers 原文明确出现 researchers，但输出额外包含开发人员、开发者，整字段仍记不足。fd 原文将自身比作 find，但固定片段没有明确说命令行形态；按本轮直接证据要求记不足，不用外部常识补齐。此保守口径不代表这些现实描述一定错误。

## 逐字段核对

### 1. TranslucentTB/TranslucentTB

原始输出：[case-01.txt](model-first-39457606306/case-01.txt)。r1 为用途和 Windows 支持，r2 为下载与便携版限制，r3 为 GPLv3。

| 字段 | 输出概要 | 判定与理由 |
|---|---|---|
| purpose | 使 Windows 任务栏透明/透明 | 支持：r1 明确半透明/透明；中文重复用词影响表达，不构成功能编造。 |
| audience | Windows 10/11 用户 | 不足：从兼容平台推导受众，片段没有直接受众声明。 |
| platforms | Windows 10、11 | 支持：r1 直接列明。 |
| form | 桌面应用程序 | 支持：Windows 任务栏工具，r2 明确 app、appinstaller 与安装路径。未声称 GUI 或已试用。 |
| requirements | null | 未输出：r2 有便携包仅 Windows 11 的明确限制；虽然所选路径是 Store，包特定限制仍未被提取。 |
| path | Microsoft Store 的 9PF4KZ2VN4W9 地址 | 支持：与 r2 内实际 URL 一致。 |
| fees | null | 未输出：r2 明确可免费从 Store 下载，有可提取事实被遗漏。 |
| license | GPLv3 | 支持：r3 直接声明。 |

### 2. AdguardTeam/AdGuardHome

原始输出：[case-02.txt](model-first-39457606306/case-02.txt)。r1/r2 是 DNS 层过滤；r3 是安装及配置设备；r4 列明不能过滤的广告。

| 字段 | 输出概要 | 判定与理由 |
|---|---|---|
| purpose | 阻止网络范围广告和跟踪 | 支持：r1/r2 直接描述；没有在此字段声称所有广告都可拦。 |
| audience | 网络用户，特别需要全面阻断的用户 | 不足：没有直接受众依据；“全面”容易误导，r4 已明确部分广告无法拦截。 |
| platforms | Linux、Windows、macOS、Android、iOS | 不足：片段没有服务端支持系统列表。“覆盖家中所有设备”不是各系统可安装此服务器的证据。 |
| form | DNS 服务器软件 | 支持：r1/r2 直接说明。 |
| requirements | 安装 DNS 服务器和网络配置 | 支持：r2 定义软件本身为 DNS server，r3 要求安装并配置设备使用它；理解为安装本软件，而非额外安装另一个 DNS 产品。 |
| path | https://wiki.adguard.com/AdGuard-Home | 不足：r3 只有未展开的 `[wiki-start]` 引用，没有这个具体 URL。 |
| fees | 免费 | 支持：r1 明确 Free，不是从 open source 推断。 |
| license | 开源（GPLv3） | 不足：开源获 r1 支持，但输入没有 GPLv3 许可标识。 |

该输出还遗漏 r4 中 DNS 级过滤对同域广告的限制。由于每字段最多一个简短断言，以上 requirements 的已述事实仍记支持；“支持”不等于内容完整或足以让用户决定安装。

### 3. sharkdp/fd

原始输出：[case-03.txt](model-first-39457606306/case-03.txt)。r1 用途，r2 二进制平台与 releases，r3 许可。

| 字段 | 输出概要 | 判定与理由 |
|---|---|---|
| purpose | 查找文件系统条目 | 支持：r1 直接说明。 |
| audience | 用户 | 不足：没有具体受众证据，且泛称不提供用户决策信息。 |
| platforms | Linux、macOS、Windows | 支持：r2 明确三平台预编译二进制。 |
| form | 命令行工具 | 不足：固定片段没有直接 CLI 形态声明，不补用对 find 的外部知识。 |
| requirements | null | 未输出：片段未给出必须满足的运行前提；提及 musl 资产不等于所有用户必须使用 musl。 |
| path | https://github.com/sharkdp/fd/releases | 支持：r2 直接给出。 |
| fees | null | 未输出：固定片段没有费用声明。 |
| license | MIT 和 Apache 2.0 | 支持：r3 直接写 both，对原文本身的转述成立；未进一步解释法律适用方式。 |

### 4. huggingface/transformers

原始输出：[case-04.txt](model-first-39457606306/case-04.txt)。r1 是模型定义框架，r2 是依赖和安装命令，r3 明确讨论 researchers。

| 字段 | 输出概要 | 判定与理由 |
|---|---|---|
| purpose | 文本/视觉/音视频/多模态模型定义框架，用于推理训练 | 支持：r1 直接覆盖，中文“用于构建”按定义模型理解。 |
| audience | 研究人员、开发人员和开发者 | 不足：r3 支持研究人员，额外开发者群体没有直接声明。 |
| platforms | Python 3.10+、PyTorch 2.6+ | 错误：r2 给的是运行依赖版本，不能替代产品平台字段；应进入关键前提。数字本身没有编造。 |
| form | Python 包 | 支持：r2 在 Python 虚拟环境通过 pip/uv 安装，直接支持该形态。 |
| requirements | null | 未输出：r2 明确依赖与虚拟环境说明，却被错放在 platforms。 |
| path | https://huggingface.co/huggingface/transformers | 不足：三个输入片段均没有该 URL；r2 实际提供 pip/uv 命令。不能仅因形似品牌域名认为是官方获取入口。 |
| fees | null | 未输出：没有费用证据。 |
| license | null | 未输出：没有许可证据。 |

### 5. hehonghui/awesome-english-ebooks

原始输出：[case-05.txt](model-first-39457606306/case-05.txt)。唯一 r1 的标题是英语外刊杂志下载，随后是“优质 App 推荐”，具体介绍第三方英阅阅读器。

| 字段 | 输出概要 | 判定与理由 |
|---|---|---|
| purpose | 提供英语外刊杂志下载 | 支持：仓库标题直接支持这一用途。 |
| audience | 英语学习者、外刊杂志读者 | 不足：由用途推测受众；不能借第三方 App 的“AI 学英语”补仓库受众。 |
| platforms | iOS、Android | 错误：这两个版本明确属于被推荐的英阅阅读器，不属于资料仓库自身的支持平台。 |
| form | 下载链接 | 不足：标题支持下载用途，但所示链接属于第三方 App，未充分确定仓库本身的交付形态；不得将其当作已确认应用。 |
| requirements | null | 未输出：输入没有仓库自身前提。 |
| path | https://ereader.link | 错误：输入明确将其作为第三方阅读器 Android 下载入口，不能变成此仓库的官方获取入口。 |
| fees | null | 未输出：没有仓库费用证据。 |
| license | null | 未输出：没有仓库许可证据。 |

### 6. squoosh/squoosh（无来源控制）

原始输出：[case-06.txt](model-first-39457606306/case-06.txt)。`refs=[]`，控制条件要求八字段均 unknown。

| 字段 | 输出概要 | 判定与理由 |
|---|---|---|
| purpose | 图像压缩和编辑 | 不足：没有任何来源，名称或模型记忆不能作为证据。 |
| audience | 开发者和图像处理爱好者 | 不足：没有任何来源。 |
| platforms | Linux、macOS、Windows | 不足：没有任何来源。 |
| form | 命令行工具 | 不足：没有任何来源，属于不应产生的形态断言。空输入不足以独立证明现实中的 CLI 分类真伪，故不混记为已证事实错误。 |
| requirements | null | 未输出：符合本字段应弃答的方向，但结构无效。 |
| path | null | 未输出：同上。 |
| fees | null | 未输出：同上。 |
| license | null | 未输出：同上。 |

原始报告的 `unknown_control=0/8` 是**严格结构控制得分**：结构不合法导致 0，并不意味着八个值全部非空。独立查看原文实际是四个 null、四个无来源断言；两者不能混报成语义拒答率。

## 格式、运行与证据边界

所有 6 份 raw JSON 均缺少每字段的 `{value, source_quote, ref_id}`，也没有任何可归属的引文。13 个非空字段同时被列入 unknowns，另有空值未列入 unknowns；该列表不能当作可靠的拒答标记。即使未来 grammar 约束修复了形状，仍须重新核对主语、蕴含、字段类别及不足时弃答。

原始 report 记录 runtime/model 文件大小与 hash 校验通过；6 个请求均 fit token budget、finish_reason=stop。全程 126.068 秒；采样的 server VmHWM 峰值 2,740,900 KiB（约 2.61 GiB）。这是一次固定 runner、固定 6 样本的测量，不代表完整采集耗时、整机峰值或长期运行表现。schema 0/6 与 semantic_accuracy=null 原样保留。

可据此继续做**隔离格式协议验证**，再用相同开发样本检查修复差异；任何后续修复结果均是新运行，不覆盖本次首结果。生产启用还需字段证据、独立语义评估和足量未见样本，不能靠本报告的 AI 分类替代真人审核。

## 不可变关联

已核对六个 case 原文解析值与 report 中 output 相同，固定输入 SHA256 与 report 的 fixture_sha256 相同。协调者归档：[首次原始附件](model-first-39457606306/manifest.json)。

- 输入 SHA256：`96978ccade1edc8841ad23d7aef2676734157c6b2826a6707d5dbcabe64917bf`
- report.json SHA256：`24aafac4b237fb75270170601784c48ecec178d5846b7f65648ece6856b76ef5`
- case-01：`d49be4b488e7ba2be954619f2c2085684134af4c9b7dc7261dd024df116a2a0d`
- case-02：`0334eb708774afceff3bc77d3e92884b3931a6e32975020be2266106353ced3e`
- case-03：`c6aec071e9576452c11c681dedfcd7e9e093611743473f943025e9462419c366`
- case-04：`60a47e4161d83473ceabce0a8085c7dc91f293e348f23fca40edebcfea86de2c`
- case-05：`c44fe247f30ee7c4623713cf4add240b4cd5600381b19af205456f8b39d67efd`
- case-06：`24713c176f198650811fdcd6cbba2551edaa6e25bfcbf62c43a1970da564e37d`

## 追加：首次格式失败的协议根因已确认

独立读取已保存的官方固定 `b11756/tools/server/server-common.cpp`，SHA256 为 `b4f4aae7eed919f914d132ae64416a0e7cfb23442161af6f63ba8d902954d442`。`oaicompat_chat_params_parse` 在 `type=json_schema` 分支只读取 `response_format.json_schema.schema`；首次请求使用扁平 `response_format.schema`，被解析为空 schema，再转成任意 JSON object 约束。这确认探针适配错误，首次未实际检验预定嵌套 schema 的模型遵循能力。

第二版改为嵌套请求，加入字段模板和官方 server 上的前置对抗 canary；独立审查见 [probe-second-safety-review.md](probe-second-safety-review.md)。离线 HTTP 协议模拟没有执行上游 C++，真实 grammar 行为仍需第二次远程 canary。此补充不改变原始附件、逐字段判定或计数，不能免除无来源猜测、他者主语错归和字段错位。第二次须另存运行结果。
