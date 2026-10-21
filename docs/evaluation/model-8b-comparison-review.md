# 8B 受控对照差异独立审查

结论：**本次冻结差异没有阻止一次隔离诊断的问题。** 仅扩充两个固定模型资产之间的选择，原 v3 引擎安全审查继续适用。实际速度、内存和语义质量仍未实测；本报告没有发起调度或下载权重。

这是独立 AI 的限定代码/来源审查，不是真人用户验证。审查时 HEAD 为 `8344180d0bcdd4a2bd2de2dc7d68619a33ad02fb`，未读取私有组，未改生产代码、数据或旧实验档案。

| 冻结文件 | SHA256 |
| --- | --- |
| `scripts/probe_model_comparison.py` | `c1b061587e8fdf29d578501d65c4c20c7a6b4772ab0e40fcbe3a5a0da4b94eda` |
| `.github/workflows/model-comparison-8b.yml` | `2d4628876ac19924c6313ea78d8e09eb2d1a66ea7a35e534d3da1ab69ea938f6` |
| `scripts/model_comparison_8b.json` | `2ac76850f9afa2f1f44050bad3e65f374d8f5acff775236b283dbaf00cf8b191` |

## 新差异的边界

`--model-key` 的 CLI choices 与程序内固定映射均只接受 `14b`、`8b`，默认仍是 `14b`。资产路径来自代码映射，不能由输入拼成任意路径或 URL；两份配置分别检查固定文件 SHA256，之后才解析 JSON。新增 provenance 的 `model_key` 与 `model_pins_sha256` 可追踪本次选择。

独立比较默认与显式 `14b` 的返回值完全相等。合成 14B pins 的字节 SHA256 仍为旧实验的 `3c28a9749d6833dfcd36c22cd4c948308c1951f0dedef56b93e304e29678e0e5`；原 14B workflow SHA256 `20b9f2c022a94e1179e685958cce5afcd4d70b4777267ff991e58de540f194f7` 与模型配置 SHA256 `d1ff6d33271fa0e8e8f7ba32302845fe04ec6ea8b6ff57aa915e5ca168b68ef4` 均未变。

8B 与 14B 的 source、fixture 字节相同；去掉 `model` 节点后，合成 pins 完全相同。基线仍为 `980b7657415796f9d9c67181dac69365a22e2838` 的原 v3，源码 SHA256 `0871654d0a1f0731daa75133c46ab632332bcd9fabde8719f0e44be49e1b74ae`、fixture SHA256 `96978ccade1edc8841ad23d7aef2676734157c6b2826a6707d5dbcabe64917bf` 及原 runtime/prompt 均未变。当前 v4 脚本、既有 pins、正式 `update.yml` 也未改。8B 合成 harness pins 预期字节 SHA256 为 `2f347d10232e979d578621042e9083badf546143f11edc002abc550acdaf02d5`。

新 workflow 与已审 14B workflow 的完整文本差异仅为模型显示名称、独立 artifact 前缀和命令增加 `--model-key 8b`。手动独占输入及公开仓库 guard、`contents: read`、不保存 checkout 凭据、4 CPU/0 GPU、4096 context、700 tokens、900 秒/17 分钟以及输出小文件白名单沿用原约束。磁盘门槛随模型大小得到 **7,197,507,841 字节**；没有放宽原校验或截止。

## 官方来源与独立反例

通过 [固定 revision 官方 API](https://huggingface.co/api/models/Qwen/Qwen3-8B-GGUF/revision/7c41481f57cb95916b40956ab2f0b139b296d974?blobs=true) 与 [同 revision LICENSE 全文](https://huggingface.co/Qwen/Qwen3-8B-GGUF/raw/7c41481f57cb95916b40956ab2f0b139b296d974/LICENSE) 两次小 GET 独立复核：author 为 `Qwen`，revision 为 `7c41481f57cb95916b40956ab2f0b139b296d974`，许可声明 `apache-2.0`；`Qwen3-8B-Q4_K_M.gguf` 大小 **5,027,783,488 字节**，LFS SHA256 为 `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`，确为 64 位十六进制，与 pins/source.json 完全一致。LICENSE 正文 11,544 字节，SHA256 `5de36594c10839788a8c589443a8ef9d8b8d17c65a1b5807206ae037fc36c6bd`，包括 Apache 2.0 完整条款及条款结尾。没有请求 GGUF 权重。

- 独立复跑 **12 项 comparison 测试通过**，包含本次新增五项。
- 额外用空字符串、大小写/空白变体、相对/绝对路径、外部 URL、shell 文本、换行和 NUL 共 **9 个非法 modelKey** 调用真实 wrapper 入口，全部失败并保存失败报告；引擎加载与网络调用均未发生。
- 两份模型配置各自仅多一个换行的字节篡改均被拒绝，不能借合法 JSON 或默认分支绕过摘要校验。默认 14B 与新增 8B 的来源/fixture/runtime 等价性及新增 provenance 也独立核对通过。
- 冻结摘要重算匹配，`git diff --check` 通过；未重复运行或修改未变的 llama.cpp 引擎函数。

可由 root 在专用 `codex/gitradar-v4-model-8b-comparison` ref 将这份已审 workflow 逐字复制至已注册 `update.yml`，与旧 14B 诊断 ref 隔离。实际调度前保留两个 workflow 同字节摘要与真实诊断 commit，运行后用 `checkout_head` 和 source/fixture/pins 再核对。这个后续分支操作尚不由本次静态报告证明已发生。

允许的是一次固定方法资产对照，不能用 4B 与 14B 的端点插值宣布 8B 会按期完成或语义更准。原始超时、错误、未完成与 null 控制仍保留六项分母；引用绑定与 schema 合法仍不代表语义正确。
