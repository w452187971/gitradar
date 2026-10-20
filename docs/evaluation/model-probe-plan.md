# 免费公开 CPU runner：开放权重模型隔离实验

状态：代码与离线边界验证已准备；尚未运行远程模型，不能据此声称 CPU 可行、内容正确或 V4 验收通过。

用户授权的研究问题：在现有公开 GitHub 仓库的标准托管 Actions runner 上，临时运行无需个人密钥的开放权重模型，能否在有限时间内把官方资料转换为有逐字来源的中文事实？本实验不接入 collector、content、推荐、正式 JSON 或 Pages，不使用付费 AI/翻译 API，不要求个人电脑常驻或新增硬件。

## 冻结输入与依赖

依赖只使用 Python 3.12 标准库，以及下载后校验的官方 llama.cpp CPU 二进制和 Qwen GGUF；无 pip 安装、`curl | sh`、HF Token 或自动选择 latest。完整 URL、字节大小、校验和与出处保存在 `scripts/model_probe_pins.json`。

- [llama.cpp b11756 官方 release](https://github.com/ggml-org/llama.cpp/releases/tag/b11756)：`llama-b11756-bin-ubuntu-x64.tar.gz`，22,240,705 字节，SHA256 `9def57d9e9b0149979a9ceba40896a4e2bf88c94734069a5567d2f487ceab551`。摘要来自官方 GitHub release asset API 的 `digest`，开发机匿名 API 限流时由协调者用已有凭据只读获取；凭据不进入脚本、日志或模型请求。
- [Qwen3-1.7B-GGUF 固定版本](https://huggingface.co/Qwen/Qwen3-1.7B-GGUF/tree/90862c4b9d2787eaed51d12237eafdfe7c5f6077)：revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`，`Qwen3-1.7B-Q8_0.gguf`，1,834,426,016 字节，LFS SHA256 `061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a`，官方模型卡标 Apache-2.0。该官方仓库此次元数据只有 Q8_0，不冒称 Q4。
- [固定版 server 接口说明](https://github.com/ggml-org/llama.cpp/blob/b11756/tools/server/README.md)：CPU 参数、JSON Schema、`chat_template_kwargs`、`timings_per_token`、`/apply-template` 与 `/tokenize` 均按该版核对。Qwen [官方模型卡](https://huggingface.co/Qwen/Qwen3-1.7B-GGUF)说明 `/no_think`；本实验另显式关闭 thinking，temperature 固定 0 是实验约束，不是官方最优采样推荐。

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

仅允许 `workflow_dispatch` 的 `model_probe_only=true`，默认 false，与原 `probe_only` 互斥；两者同时 true 立即失败。所有采集、提升、提交、发布和采集失败归档步骤均排除模型模式。模型模式 checkout 不持久化 GitHub 凭据。模型 Python 入口再次检查 GitHub Actions、Linux x86_64 和公开仓库 event，个人电脑调用只写失败诊断，不下载或推理。

命令入口为 `bash scripts/model_probe.sh`。该入口由协调者在代码审核、提交后通过现有 `update.yml` dispatch，本文件不代替实际运行记录。脚本不接受外部模型服务地址：llama-server 只监听 `127.0.0.1` 的临时端口；HTTP 客户端禁用代理，且不加任何 Authorization。server 子进程只继承 PATH、LANG、LD_LIBRARY_PATH 和 OMP_NUM_THREADS；不会接收 GitHub/HF/付费服务 Token。

固定 CPU-only `-ngl 0`、推理及 prefill 线程各 4、单 slot、context 4096、temperature 0、每项最多生成 700 tokens、thinking 关闭。全实验含下载限制 900 秒；独立截止异常不会被单项网络错误重试捕获。单项 completion 超时 120 秒，载入等待最多 120 秒；workflow 诊断模式上限 17 分钟为失败报告和 artifact 预留收尾时间，默认生产任务超时保持 GitHub 原有 360 分钟。

每项先 `/apply-template` 形成完整 system+user prompt，再 `/tokenize`，记录实际输入 token，预留 700 输出与 8 个 special token 余量；超过 4096 不推理、不自动删片段。该检查不保证 700 tokens 足够完整输出；若被截断，保留原文并记失败。模型和二进制放系统临时目录，按 size+SHA256 两项验证后才启用，退出清理；下载/校验/启动失败均保留报告并退出非 0，不自动降级成“成功”。

## 输出、指标与人工判断

每项严格 JSON：`purpose`、`audience`、`platforms`、`form`、`requirements`、`path`、`fees`、`license` 分别表示中文用途、受众、平台、形态、关键前提与限制、路径、费用、许可。每字段结构为 `{value, source_quote, ref_id}`；未知则三个值全为 null，并列入 `unknowns`。不接受额外属性、markdown 围栏、重复键、缺字段或空证据。JSON Schema 限制格式，逐字校验将引用限定在相同 ref_id 对应片段。

`.model-probe/report.json` 保存固定 pins、fixture hash、提交 SHA、runner/CPU 信息、下载耗时与实际摘要、加载到 health-ready 墙钟耗时、每项 prefill/generate 时间及 token/用量、每项墙钟耗时、server `/proc/PID/status` VmHWM 采样峰值 RAM（KiB），以及每项格式和引用匹配结果。单次无 warmup，加载时间不包括第一次推理的全部运行成本；prefill/generate 采用 server 返回的 timings。无法取得这些计时也不宣称完整成功。

机器指标分别报告：6 项请求分母、已尝试数、成功 JSON 数、schema 合格数、所有已输出字段引用可逐字匹配的项目数、引用字段分子/分母。无来源控制另报 8 字段中明确返回未知的数量与 `no_source_unknown_rate`，这是一个缺来源控制的自动拒答率，不能外推成模型总体拒绝编造率。未执行的项目和失败不会从请求分母消失。

**逐字匹配不等于语义支持。** 例如从 “cannot block YouTube ads” 截取 “block YouTube ads” 能通过字面检查，却把否定翻成肯定；第三方 App 的真引用也可能错误归给本项目。所以所有产物始终标 `human_review_required`，`semantic_accuracy`、`semantic_refusal_rate` 保持 null。原始小文本与报告交给独立人工核对用途、受众、否定、主语、关键条件、官方路径与费用后再评分；不得把模型 confidence 作为核实证据。

仅当六项都正常停止、JSON/引用校验均通过、thinking 未产生且计时完整，进程才能以 0 返回 `runtime_complete_semantics_unverified`；该状态只表示运行/格式边界完成。其他情况为非 0 的 `failed_unverified`。任一状态都不改变任何正式 JSON。

Actions artifact 只收 `.model-probe/report.json`、六个 `case-*.txt` 和小型 `server.log`，保留 7 天，不上传 GGUF、二进制、临时目录或凭据。`.model-probe/` 已加入 gitignore。

## 离线验证与下一道门槛

`python3 -m unittest tests.test_model_probe` 验证引用归属、未知字段一致性、严格 JSON、校验失败不启用下载、输入片段 hash、deadline 不被吞掉、超长输入不推理、个人电脑拒绝执行并保留报告、CPU/loopback/生成上限，以及模型模式跳过正式采集发布。`bash -n scripts/model_probe.sh` 和 `git diff --check` 作为脚本及补丁基本检查。

当前没有远程模型输出，因此可行性结论仍待运行。若公开 runner 的下载/内存/耗时失败，如实记录对应阶段；若技术运行通过但中文语义不够，仍不接入生产。只有在六项开发材料经过独立语义审查之后，才考虑更大固定评测；再次声称未见效果必须使用新的独立未见输入，不复用这六项或首次已归档的 40 项。
