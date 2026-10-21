# 14B 固定方法对照独立审查

结论：未发现阻止这一次隔离诊断的代码或来源问题。可以按已授权的专用诊断分支方式调度一次；运行结果仍须另行封存和逐字段审查，不能直接成为生产内容或泛化验收结论。

本次为独立 AI 代码与官方来源核对，不是人工用户验证。未读取隐藏盲组，未下载或运行权重，未修改生产代码、正式数据、提示词或首次结果。审查时工作树 HEAD 为 `634cbbb7cd1f135165636f31f611a2d07e040aaa`；以下新增文件按字节摘要冻结。

| 对象 | SHA256 |
| --- | --- |
| `scripts/probe_model_comparison.py` | `cdcc6124f7e3b658c96f679a67279c8f8daaf21914537aaa0b1e7b603954d915` |
| `.github/workflows/model-comparison.yml` | `20b9f2c022a94e1179e685958cce5afcd4d70b4777267ff991e58de540f194f7` |
| `scripts/model_comparison_14b.json` | `d1ff6d33271fa0e8e8f7ba32302845fe04ec6ea8b6ff57aa915e5ca168b68ef4` |
| `tests/test_model_comparison.py` | `3099238a9908e42d2547fb54dad07a160a36eea6ece208ffbde5073c2f9238d3` |
| `docs/evaluation/model-14b-source.json` | `3b5749b0cf206fddaad729e25208bb3c3f2c883e40931e57b460df1746bd5f72` |

## 固定方法与来源

wrapper 从 Git 对象 `980b7657415796f9d9c67181dac69365a22e2838` 读取原 v3 源码，读取后和执行前分别检查 SHA256 `0871654d0a1f0731daa75133c46ab632332bcd9fabde8719f0e44be49e1b74ae`。独立 `git show` 得到相同的 26,678 字节；运行模块未替换任何函数、提示词或协议，仅将 `ROOT` 指向临时 harness。

六项已见 fixture 从同一 Git 对象读取，SHA256 为 `96978ccade1edc8841ad23d7aef2676734157c6b2826a6707d5dbcabe64917bf`，还要求与当前工作树文件逐字节相同。原 pins 也取自该提交，只替换 `model` 节点，llama.cpp b11756 的 URL、22,240,705 字节、SHA256 `9def57d9e9b0149979a9ceba40896a4e2bf88c94734069a5567d2f487ceab551` 及其他 runtime 属性均保持相同。

独立读取了 [Qwen 固定 revision 官方 API](https://huggingface.co/api/models/Qwen/Qwen3-14B-GGUF/revision/530227a7d994db8eca5ab5ced2fb692b614357fd?blobs=true) 与 [同 revision 的 LICENSE 正文](https://huggingface.co/Qwen/Qwen3-14B-GGUF/raw/530227a7d994db8eca5ab5ced2fb692b614357fd/LICENSE)。API 返回 author 为 `Qwen`，revision 为 `530227a7d994db8eca5ab5ced2fb692b614357fd`，许可声明为 `apache-2.0`。其中 `Qwen3-14B-Q4_K_M.gguf` 的文件大小为 **9,001,752,960 字节**，LFS SHA256 为 `500a8806e85ee9c83f3ae08420295592451379b4f8cf2d0f41c15dffeb6b81f0`，与配置及来源记录一致。许可证正文为 11,544 字节、SHA256 `5de36594c10839788a8c589443a8ef9d8b8d17c65a1b5807206ae037fc36c6bd`，包含 Apache 2.0 正文及条款结尾。许可和官方权重来源有据，不代表模型输出或 CPU 适配已验证。

## 隔离与预算

- 原 v3 的公开 Linux x86_64 Actions 校验仍实际执行，要求 `workflow_dispatch`、`model_probe_only=true`、`probe_only` 不为 true、`repository.private` 严格为 false。wrapper 没有重写事件或绕过该函数。
- workflow 只有手动入口，`contents: read`、`persist-credentials: false`、完整历史 checkout；没有采集、提升、正式数据写入或提交步骤，也没有传入 secrets。
- 原 canary、单项 120 秒、加载 120 秒、canary 30 秒、总计 900 秒均保留。外层 `timeout` 同为 900 秒，TERM 后最多 15 秒清理，job 上限 17 分钟。4 CPU 线程、0 GPU 层、4096 context、每项 700 生成 tokens 与原非思考设置不变。
- server 仍只监听 `127.0.0.1`。独立调用原 v3 `runServer` 并拦截进程创建，确认环境仅有 `PATH`、`LANG`、`LD_LIBRARY_PATH`、`OMP_NUM_THREADS`；加入的 `GH_API_TOKEN`、`GITHUB_TOKEN`、`HF_TOKEN` 标记均未进入子进程。未真实启动模型。
- 下载前临时磁盘门槛为模型与 runtime 大小加 2 GiB，即 **11,171,477,313 字节**。临界值可通过，少 1 字节拒绝。原下载函数仍逐块检查大小、最终核对 SHA256，并清理失败的 `.part` 文件。
- 临时 harness 只包含固定 fixture 和合成 pins，退出后删除。附件只含报告、provenance、原始文本和 server 日志；权重与 harness 不上传。

`comparison-provenance.json` 分开记录 `checkout_head`（实际 `git rev-parse HEAD`）与 `event_github_sha`（事件变量），并保存 baseline commit、实际源码/fixture 与合成 pins 摘要。原 v3 报告中的事件 SHA 不再被单独拿来证明 checkout。

## 独立验证与调度边界

复跑 `test_model_comparison`、`test_model_probe_v3`、`test_model_probe_v4` 共 **30 项测试通过**。另外针对固定原 v3 模块独立执行：1 项合法 runner 组合与 8 项非法环境/事件/输入/可见性/架构组合、源码字节篡改、模型配置字节篡改、基线 fixture 字节篡改、磁盘门槛两侧及四键环境隔离，结果符合预期；所有反例均未下载权重。

新 workflow 的注册限制由专用 `codex/gitradar-v4-model-comparison` 诊断分支处理：仅在该分支将已审 `model-comparison.yml` 逐字复制至已注册的 `update.yml`，通过该诊断 ref 手动调度。此等价路径保留真实公开 Actions 事件和独占输入校验，没有扩大生产权限。实际 dispatch 前仍需记录两个 workflow 的字节 SHA256 相同，以及诊断分支实际 commit；本次静态审查不声称该后续分支复制已发生。dev/main 的原 `update.yml` 保持原状。

本次对照比较的是固定的 **14B Q4_K_M 与既有 4B Q5_K_M** 两个模型资产；量化精度也不同，结果不能单独证明参数数量的因果作用。16 GB runner 的实际峰值内存、速度、900 秒完成情况及语义改善均未实测，不能据文件大小或算术预测宣布通过。超时、未尝试、截断和错误仍留在固定六项分母；程序绑定原文不代表模型引用或语义正确。
