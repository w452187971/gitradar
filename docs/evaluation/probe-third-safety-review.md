# v3 隔离模型探针独立安全审查

审查范围：`scripts/probe_local_model.py`、`scripts/model_probe_pins.json`、`scripts/model_probe.sh`、三个 `test_model_probe*` 测试文件、`docs/evaluation/model-probe-plan.md`，并只读核对现有 `update.yml` 的隔离条件。没有读取私有盲测或反例目录，没有下载权重、调用推理、改动代码或生产数据。本文使用的路径反例为审查者当场构造的公开形式字符串。

**最终结论：可以执行本次隔离诊断 dispatch。** 首次发现的 URL 前缀问题经协调者最小修复后，独立复测通过；未发现其他削弱 CPU、时间、入口或凭据隔离的阻断问题。此结论仅适用于固定六项开发资料的诊断，不能解释为语义、生产准入或 V4 效果达标。流水线正在单独修正的问题不属于此次模型探针审查。

## 首次独立复现：URL 前缀会被误当作原文明示路径

首次审查时 `pathSourceValid()` 使用 `value in source`。合成输入仅为：

```text
Get [fd releases](https://github.com/sharkdp/fd/releases).
```

结果如下，完整 raw 对象的其他七个字段均为合法 null 配对：

| 模型 `path.value` | 首次 `path_source_valid` | 首次 `raw_valid` | 首次可生成 bound |
| --- | --- | --- | --- |
| `https://github.com` | true | true | 是 |
| `https://github.com/sharkdp` | true | true | 是 |
| `https://github.com/sharkdp/fd/releases` | true | true | 是 |
| `https://example.com/invented` | false | false | 否 |

前两个地址只是完整 URL 的前缀，资料没有将其单独列为获取路径。现有测试只验证了完整地址、完全陌生的地址及 HTTP，没有覆盖这个边界。建议先从所选 ref 原文按明确边界提取完整 HTTPS URL token，再作精确相等比较，覆盖 Markdown 链接与句末标点；禁止用子串或 `startswith` 替代。拒绝时继续保留 raw，`runtime_bound_output=null`，不能改写为未知后计合格。这个修复只证明地址被原文完整写出，不证明网址官方身份、可访问性或实际安装用途。

协调者已收到复现，并承担该项最小 TDD 修复；首次结果在本文保留，不因后续修复覆盖。

## 其余协议与隔离边界

- raw 严格包含八个字段，每字段只允许 `value/ref_id`。运行时拒绝重复键、额外字段、空字符串、外来来源 ID 与不完整 null 配对。`ref_id.enum` 逐 case 构造；无来源 case 的 enum 仅含 null，但 value 仍可为字符串，因此不会通过 schema 提前把所有猜测强制成未知。
- 原始文本与解析后的 raw 分别保留。无效 null 配对拒绝绑定，不修补、不偷偷置空。有效输出按选中的 ref_id 绑定完整冻结原文，并再次核对片段 SHA256；`unknowns` 完全由程序依据合法 null 配对计算。
- 源文绑定按构造精确成立，不代表模型引用能力或语义正确。代码与文档明确保留 `human_review_required`，三项语义/来源选择准确率均为 null，不再用 `quotes_match` 包装程序复制。测试故意把“不能屏蔽 YouTube 广告”解释成肯定句，仍要求其语义待审，从而区分协议通过与断言正确。
- schema canary 仍在六个开发项目之前执行，使用固定嵌套对象与故意冲突的 prompt；失败即停主样本。它只验证实际二进制 schema 约束，不进入六项质量分母。HTTP 契约模拟器测试明确没有执行上游 C++，远程 canary 仍不可省略。
- 模型 pins 与前次官方元数据研究一致：Qwen3-4B Q5_K_M，revision `bc640142c66e1fdd12af0bd68f40445458f3869b`，2,889,513,184 字节，SHA256 `aca596860e8cb40af6539e3f2ea40df305f42515deac56d49c08d39a02e6533f`。官方 llama.cpp `b11756` 的 URL、大小及摘要未改变。下载仍先验大小及 SHA256，再启用文件；不使用 latest 或第三方权重。
- `requirePublicRunner()` 在下载前检查 Linux x86_64、GitHub Actions、公开仓库 event、显式 `workflow_dispatch` 和独占 `model_probe_only=true`；普通采集、schedule、错误输入和冲突诊断模式不允许进入下载。workflow 继续使用 `ubuntu-latest`，模型模式 checkout 不持久化凭据，采集、promote、commit 和其他 probe 均排除模型模式。
- 服务绑定 `127.0.0.1`，本地客户端禁用代理且不添加 Authorization。server 子进程环境仅包含 PATH、LANG、LD_LIBRARY_PATH、OMP_NUM_THREADS；没有继承 GH、HF 或付费服务 Token。源文本只作为 JSON 输入，不构成命令执行入口。
- CPU-only `-ngl 0`、4 个推理及 prefill 线程、单 slot、4096 context、700 输出 tokens 和关闭思考保持不变。输入先经过实际模板/tokenizer 预算检查，不自动删来源。900 秒全局截止包含下载，特殊截止异常不会被单项网络错误捕获；退出时终止子进程并清理临时模型。
- 模型诊断不导入生产采集器，不提升正式 JSON，不提交或发布。artifact 只保存 report、原始小文本及 server.log，不上传权重、二进制或临时目录。每次结果应按新的 run ID 独立封存。

## 本次独立验证

初次命令 `python3 -m unittest tests.test_model_probe tests.test_model_probe_contract tests.test_model_probe_v3`：**28 项通过**。这不包含整仓作者报告的 283 项，也不代替协调者重新运行完整测试。

额外以 mocked `Popen` 调用 `runServer()`，在父环境含三个合成 Token 变量的情况下检查子进程环境，确认仅四个允许键且退出调用 terminate。该检查没有执行二进制或请求推理。

上述 URL 四例为独立的直接函数调用，已复现首次漏洞。首次结果保持原样；修复后的独立复测见下节。当前没有任何 4B 远程性能或语义结果可用于验收。

## 最小修复后的独立复测

协调者增加前缀回归测试后，将原文按空白、Markdown 括号、引号等明确边界提取的 HTTPS URL token 作精确相等匹配，不做域名相似、路径前缀或 URL 归一化兜底。此为当前固定输入形态的词法边界，并非通用 Markdown 或全部 URL 语法解析器；更复杂的原文格式仍需后续单独处理，不能凭此声明所有 URL 已获官方身份或语义验证。

独立复测没有只调用 `pathSourceValid()`，还通过 mocked completion 执行完整 `runCase()`，结果如下：

| `path.value` | 修复后 `raw_valid` | raw 原样保留 | bound |
| --- | --- | --- | --- |
| `https://github.com` | false | 是 | null |
| `https://github.com/sharkdp` | false | 是 | null |
| `https://github.com/sharkdp/fd` | false | 是 | null |
| `https://github.com/sharkdp/fd/releases` | true | 是 | 可绑定，语义仍待审 |
| `https://example.com/invented` | false | 是 | null |

另外构造原文 `https://example.com/get?version=1&checksum=abcd.`，完整去句末点号的地址通过；去掉 query、截断 query 参数及截断参数值三个前缀均拒绝。上述输入不属于私有评测数据。所有拒绝项目的 status 均为 failed，没有将路径置 null 后转为合格。

再次独立运行相同三个测试模块：**29 项通过**。再次以合成父环境 Token 变量检查 `runServer()`，子进程仍只有四个允许环境键，退出仍调用 terminate。`git diff --check` 通过。没有执行模型推理或下载文件。

本次最终复审读取的 SHA256：

- `scripts/probe_local_model.py`：`0871654d0a1f0731daa75133c46ab632332bcd9fabde8719f0e44be49e1b74ae`。
- `scripts/model_probe_pins.json`：`f549fdefd504a7c0c7b2049766820174dacf1cab36ef2a8c9cfbb2e2fc258971`。
- `tests/test_model_probe_v3.py`：`335e3ccccbf7f770cf50a6c2d4174c665c607e54252783b0698ad27d4acba518`。
- `.github/workflows/update.yml`：`3be870c51e0b1496592dab5ee35428ead140fdd67554e56913ab2d38f71210f4`。

可以在这些边界保持不变、协调者完成提交和完整回归后执行显式 `model_probe_only=true`。远程 canary、下载摘要、CPU/RAM/900 秒预算以及实际输出仍须按本次运行结果核验；即使诊断退出 0，六项语义也仍需要独立评分，不能进入正式内容或推荐链路。
