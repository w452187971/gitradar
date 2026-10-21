# 第四次两步模型真实诊断独立评分

结论：**尚无进入未见验收组的依据，应按预定停止围绕这六例继续调 prompt。** 两步诊断在预算内跑完，失败来自来源关系、空值配对、入口对象与中文交付，而非超时、截断或上下文耗尽。只有两个项目通过 raw 协议：一个是无来源全未知，另一个只有整句英文用途；没有可交付中文介绍的完整有效项目。

本次是独立 AI 依据冻结原文的开发评分，不是真人标注、真实读者测试或未见盲评。评分包含全部六项目；不能把同项目的多个字段当成多个独立项目。没有改 prompt、代码或原始结果，也没有读私有新样本/反例。

## 运行与可复现证据

- [Actions 39524320125](https://github.com/w452187971/gitradar/actions/runs/39524320125)：conclusion=failure，report.status=failed_unverified；canary 通过。唯一诊断 artifact 用已有 ignored 安全工具一次下载成功，未关闭 TLS、未重试模型。原始档案由协调者封存。
- 6/6 都执行 stage1、stage2，12/12 正常 stop；未执行 0、截断 0、阶段超时 0。stage1 结构合法 6/6，stage2 null 配对及最终 raw 合法仅 2/6，程序绑定 2/6。所有失败 raw 均保留，未改写为未知后计合格。
- 总墙钟 593.480 秒，低于 900 秒；server VmHWM 峰值 3,966,472 KiB，约 3.78 GiB，只是该服务进程峰值。六项目两阶段合计生成 1595 tokens；固定上限仍是每项 300+400=700。最大输入分别 957/1301 tokens，最大阶段输出分别 149/156，没有触及 4096 context 或阶段输出上限。
- 下载大小与 SHA256 校验通过：runtime 22,240,705 字节；模型 2,889,513,184 字节，实际 SHA256 与固定 pins 一致。没有付费 AI API 调用。
- run.head_sha 与 report.git_sha 都是 `61aca582ba85e3b5e2711e770beb376139d6b9c8`。report.git_sha 来自 GITHUB_SHA，没有另记 checkout HEAD，因此不能仅据该字段断言实际 checkout。另一个已知候选为正常采集 bot 子提交 `83ba30c12ae7dbea095af7a25c8fa3c21283db65`；对两个 commit 分别 git show 核对，脚本、pins、fixture 三项摘要完全相同。
- 脚本 SHA256：`8d1a5d0c1d2f4aae51815216cb876cf7ab37300154cf902d2b0d77989e2a3ede`；fixture SHA256：`96978ccade1edc8841ad23d7aef2676734157c6b2826a6707d5dbcabe64917bf`。
- 原 report SHA256：`411a5a5ce018c98870da0828ad0e783e8d2a5ab4342990f303836a390c9a6c30`。十二份阶段文本均与 report 中的原始文本、解析 raw 一致。逐字段机器可读记录见 [model-fourth-scores.json](model-fourth-scores.json)。

## 严格分母与口径

阶段1有 48 个字段槽位：选择来源的 15 个、真实未选择的 33 个。按对象关系单独核对，15 个非空选择中 10 个归属正确、4 个把本项目事实错分为 dependency、1 个“项目的依赖要求”存在分类语义歧义；归属正确的 10 个里，另有一个 path 段只有安装命令、没有协议要求的 HTTPS URL。故阶段1综合判断为支持 9、错误 4、不足 2、未知 33。这里的支持包含正确识别第三方，**不等于支持了 9 个项目事实**。

阶段2同样保留 48 槽位：**非空 15、真实 null 配对 33**。严格按原文、字段角色与可用来源判定：**支持 6、错误 4、不足 5、未知 33**。不足的五个值在原文可找到依据，但 raw 的 ref_id 为 null，不能擅自补来源使其变成有效输出。只看字面事实而忽略引用协议，可以说 11/15 有原文依据、4/15 错主语或错入口；这不能当成可用内容准确率。

8 个非空字段违反 null 配对，另有 1 个路径跳出所选段落。四个项目整例被正确拦截。唯一成功绑定的非空项目只有 1 个英文用途；另一个绑定项目八字段全未知。因此“2/6 raw 有效”“程序绑定成功”“有证中文项目可交付”是不同结论。

33 个未知只是实际模型输出，并不自动计为正确。部分字段被阶段1的关系与来源选择限制，不能据此报模型总体拒答准确率；八字段无来源控制另列 8/8，semantic_refusal_rate 仍为 null。

| 阶段2维度 | 项目槽位 | 非空 | 支持 | 错误 | 不足 | 未知 | 准确率门槛 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| purpose | 6 | 5 | 4 | 1 | 0 | 1 | 未验证，独立项目少于30 |
| audience | 6 | 0 | 0 | 0 | 0 | 6 | 未验证，独立项目少于30 |
| platforms | 6 | 3 | 1 | 1 | 1 | 3 | 未验证，独立项目少于30 |
| form | 6 | 0 | 0 | 0 | 0 | 6 | 未验证，独立项目少于30 |
| requirements | 6 | 1 | 0 | 0 | 1 | 5 | 未验证，独立项目少于30 |
| path | 6 | 4 | 0 | 2 | 2 | 2 | 未验证，独立项目少于30 |
| fees | 6 | 0 | 0 | 0 | 0 | 6 | 未验证，独立项目少于30 |
| license | 6 | 2 | 1 | 0 | 1 | 4 | 未验证，独立项目少于30 |

## 全部六案例逐字段判断

表中的“阶段1支持”判断所选段落与对象分类；第三方可以被正确识别，但不因此成为本项目事实。阶段2“支持”仅指断言及来源有依据；如果本项目整体 raw 失败，不能从中自动拼出生产结果。

### 1. TranslucentTB/TranslucentTB

raw_valid=false；bound=null。阶段1/2 都正常完成。

| 字段 | 阶段1段落/关系 → 判断 | 阶段2原值/来源 → 判断 | 理由 |
| --- | --- | --- | --- |
| purpose | r1:p1/project → 支持 | 使Windows任务栏半透明/透明 / r1 → 支持 | r1:p1为本项目用途，中文断言忠实。 |
| audience | null/unknown → 未知 | null / null → 未知 | 未选受众，两个阶段都未作受众断言。 |
| platforms | r1:p1/project → 支持 | Windows 10 和 Windows 11 / r1 → 支持 | r1:p1直接支持Windows 10/11。 |
| form | null/unknown → 未知 | null / null → 未知 | 未选形态；r2已有app/appinstaller文字，仍未形成覆盖。 |
| requirements | null/unknown → 未知 | null / null → 未知 | 未选运行限制，r2:p5便携包仅Windows 11条件没有呈现。 |
| path | r2:p3/dependency → 错误 | https://www.microsoft.com/store/apps/9PF4KZ2VN4W9 / null → 不足 | r2:p3是本程序Store入口却误标dependency；地址本身有证，但stage2 ref为null，不能补成有效绑定。 |
| fees | null/unknown → 未知 | null / null → 未知 | r2:p3明示免费，但两阶段均未提取。 |
| license | r3:p1/project → 支持 | GPLv3 / r3 → 支持 | r3:p1直接支持GPLv3；名称保留英文可接受。 |

### 2. AdguardTeam/AdGuardHome

raw_valid=true；bound=存在。阶段1/2 都正常完成。

| 字段 | 阶段1段落/关系 → 判断 | 阶段2原值/来源 → 判断 | 理由 |
| --- | --- | --- | --- |
| purpose | r1:p1/project → 支持 | Free and open source, powerful network-wide ads & trackers blocking DNS server. / r1 → 支持 | r1:p1为本项目用途；stage2原样英文，事实有证但没有完成中文交付。 |
| audience | null/unknown → 未知 | null / null → 未知 | r2:p1家庭设备已有受众线索，仍未选择。 |
| platforms | null/unknown → 未知 | null / null → 未知 | 冻结文字未明确操作系统，未知可以保留。 |
| form | null/unknown → 未知 | null / null → 未知 | r1:p1/r2:p2的DNS服务器形态未提取。 |
| requirements | null/unknown → 未知 | null / null → 未知 | 设备配置及DNS无法屏蔽同域广告限制均遗漏。 |
| path | null/unknown → 未知 | null / null → 未知 | 安装Wiki引用没有展开成HTTPS URL，未知可保留。 |
| fees | null/unknown → 未知 | null / null → 未知 | r1:p1明确Free，但费用被遗漏。 |
| license | null/unknown → 未知 | null / null → 未知 | 只有开源属性，没有具体许可，未知可保留。 |

### 3. sharkdp/fd

raw_valid=false；bound=null。阶段1/2 都正常完成。

| 字段 | 阶段1段落/关系 → 判断 | 阶段2原值/来源 → 判断 | 理由 |
| --- | --- | --- | --- |
| purpose | r1:p1/project → 支持 | 寻找文件系统中的条目 / r1 → 支持 | r1:p1为本项目文件查找用途，未移植find全部能力。 |
| audience | null/unknown → 未知 | null / null → 未知 | 无明确目标人群，未知可保留。 |
| platforms | r2:p2/dependency → 不足 | Linux, macOS and Windows / null → 不足 | r2:p2是本项目二进制平台，误标dependency；stage2系统值有证但ref为null。 |
| form | null/unknown → 未知 | null / null → 未知 | 当前片段没有直接写CLI，不用常识替它补证。 |
| requirements | null/unknown → 未知 | null / null → 未知 | 没有明确权限或运行前提，不新增访问权限断言。 |
| path | r2:p2/dependency → 不足 | https://github.com/sharkdp/fd/releases / null → 不足 | 本项目release入口误标dependency；正确URL以null ref输出，协议失败。 |
| fees | null/unknown → 未知 | null / null → 未知 | 没有直接费用文字，不再猜免费。 |
| license | r3:p2/dependency → 错误 | MIT License and Apache License 2.0 / null → 不足 | r3:p2是fd自身许可，误标dependency；两个名称有证但ref为null。 |

### 4. huggingface/transformers

raw_valid=false；bound=null。阶段1/2 都正常完成。

| 字段 | 阶段1段落/关系 → 判断 | 阶段2原值/来源 → 判断 | 理由 |
| --- | --- | --- | --- |
| purpose | r1:p1/project → 支持 | 提供最先进的机器学习模型定义框架 / r1 → 支持 | r1:p1为项目模型定义框架，中文用途支持。 |
| audience | null/unknown → 未知 | null / null → 未知 | 未选择受众，不能算受众正确覆盖。 |
| platforms | null/unknown → 未知 | null / null → 未知 | Python/PyTorch没有再错填操作系统，保持未知。 |
| form | null/unknown → 未知 | null / null → 未知 | r3:p2明示library却未选，形态仍无覆盖。 |
| requirements | r2:p2/dependency → 不足 | 支持Python 3.10+和PyTorch 2.6+ / null → 不足 | r2:p2是项目的依赖要求，project/dependency划分有歧义；当前只接收project使其不可用，不能无条件判模型关系错误。stage2版本值有证但ref为null。 |
| path | r2:p6/project → 不足 | https://pytorch.org/get-started/locally/ / r2 → 错误 | r2:p6确为本项目pip安装命令但无HTTPS URL；stage2转而给PyTorch依赖页，且该URL不在所选段。 |
| fees | null/unknown → 未知 | null / null → 未知 | 冻结输入没有价格，未知可保留。 |
| license | null/unknown → 未知 | null / null → 未知 | 冻结输入没有具体许可，未知可保留。 |

### 5. hehonghui/awesome-english-ebooks

raw_valid=false；bound=null。阶段1/2 都正常完成。

| 字段 | 阶段1段落/关系 → 判断 | 阶段2原值/来源 → 判断 | 理由 |
| --- | --- | --- | --- |
| purpose | r1:p3/third_party → 支持 | 提供英语阅读工具 / null → 错误 | stage1正确识别r1:p3为third_party；stage2仍把英阅App工具用途归给资料仓库。 |
| audience | null/unknown → 未知 | null / null → 未知 | 未对仓库目标人群作无证推断。 |
| platforms | r1:p3/third_party → 支持 | iOS和Android / null → 错误 | stage1正确识别第三方App；stage2仍把iOS/Android归给仓库且ref为null。 |
| form | null/unknown → 未知 | null / null → 未知 | 未再直接把仓库形态填成App，保持未知。 |
| requirements | null/unknown → 未知 | null / null → 未知 | 未再编造必须安装App/联网的仓库前提。 |
| path | r1:p3/third_party → 支持 | 英阅 App Store 地址（id1558805880；完整值见评分JSON） / null → 错误 | stage1正确识别第三方商店链接；stage2仍作为仓库获取地址输出且ref为null。 |
| fees | null/unknown → 未知 | null / null → 未知 | 原文没有价格，未再猜付费。 |
| license | null/unknown → 未知 | null / null → 未知 | 原文无具体许可，保持真实null而非字符串未提及。 |

### 6. squoosh/squoosh

raw_valid=true；bound=存在。阶段1/2 都正常完成。

| 字段 | 阶段1段落/关系 → 判断 | 阶段2原值/来源 → 判断 | 理由 |
| --- | --- | --- | --- |
| purpose | null/unknown → 未知 | null / null → 未知 | 无来源控制，两个阶段均保持未知；只描述本控制，不外推语义拒答率。 |
| audience | null/unknown → 未知 | null / null → 未知 | 无来源控制，两个阶段均保持未知；只描述本控制，不外推语义拒答率。 |
| platforms | null/unknown → 未知 | null / null → 未知 | 无来源控制，两个阶段均保持未知；只描述本控制，不外推语义拒答率。 |
| form | null/unknown → 未知 | null / null → 未知 | 无来源控制，两个阶段均保持未知；只描述本控制，不外推语义拒答率。 |
| requirements | null/unknown → 未知 | null / null → 未知 | 无来源控制，两个阶段均保持未知；只描述本控制，不外推语义拒答率。 |
| path | null/unknown → 未知 | null / null → 未知 | 无来源控制，两个阶段均保持未知；只描述本控制，不外推语义拒答率。 |
| fees | null/unknown → 未知 | null / null → 未知 | 无来源控制，两个阶段均保持未知；只描述本控制，不外推语义拒答率。 |
| license | null/unknown → 未知 | null / null → 未知 | 无来源控制，两个阶段均保持未知；只描述本控制，不外推语义拒答率。 |

## 重大错误、遗漏与中文效果

- 英语资料仓库：stage1 正确把 App 段落标成 third_party，但 stage2 仍输出该 App 的用途、iOS/Android 与商店入口，三项都错归到仓库。程序因 ref=null 和非 project 越权拒绝它，不能说模型已经解决主语识别。
- Transformers：stage1 选中的是本项目 pip 安装命令；stage2 仍给出 PyTorch 依赖安装页。该 URL 虽在同 ref 的另一段，却不在所选段落，获取对象也错误，安全检查正确拦截。
- TranslucentTB 的 Store 下载、fd 的平台/发行页/许可均被错标 dependency。Transformers 兼容 Python/PyTorch 的项目要求也被该关系挡住；它确实涉及依赖，说明“项目自身要求”和“所谈依赖对象”的分类还存在语义边界，不能仅靠枚举标签冒充正确归属。
- 本轮没有新增错误收费断言，也没有输出明显否定翻转，但六项目的 fees 均未知、两个已有明确免费证据的项目也未提取；AdGuard 的设备配置与同域广告限制没有呈现。这是覆盖不足，不能记成费用100%准确或限制完整。
- 没有一条 requirements 输出具备合法非空来源配对。单段选择本就不证明前提完整，本次也没有提供足够结果支持完整性。
- language_review_fields 共八项，完整 URL、系统与许可证专名可以保留英文；真正影响中文交付的是 AdGuard 唯一绑定的用途完全照抄英文。不能把其原文一致性当成中文解读完成。

## 是否继续未见验收

当前没有足够依据。六项目仍是开发中反复使用的同一组，且每维非空独立项目最多五个，所有统计门槛保持未验证；这次不能重新命名为新盲评。

安全管线按设计保留失败并阻止绑定，工程隔离有效；自动中文理解与可用覆盖仍不满足产品目标。按已定停止条件，**保留此次结果，停止围绕这六例追加 prompt 调整，不自动运行私有未见组或发布模型内容**。后续若另立研究，应先明确如何同时处理项目/依赖关系、结构化来源和完整获取方式，并重新冻结开发与验收边界；不能把事后补引用、强制置空或只输出少数用途句当成通过。
