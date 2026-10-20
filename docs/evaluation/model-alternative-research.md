# 免费开放权重模型备选研究

核对时间：2026-10-20 16:42 UTC。范围仅为官方资料与小型元数据；没有下载权重、执行推理或改动生产代码。此文不构成模型质量、CPU 性能或 V4 效果验收。

目前只建议保留一个备用实验组合：**Qwen 官方 `Qwen3-4B-GGUF` 的 `Q5_K_M`，显式关闭思考**。它是经过后训练的 4.0B 文本模型，官方提供现成 GGUF，并沿用当前实验的 `qwen3` 架构。选它是为了减少模型来源、格式转换与架构变化带来的额外变量；中文证据抽取是否优于 1.7B 仍须实测。[固定版本官方模型卡](https://huggingface.co/Qwen/Qwen3-4B-GGUF/blob/bc640142c66e1fdd12af0bd68f40445458f3869b/README.md)

## 可复现的唯一备用组合

| 项目 | 固定值 |
| --- | --- |
| 官方仓库 | `Qwen/Qwen3-4B-GGUF` |
| 模型 revision | `bc640142c66e1fdd12af0bd68f40445458f3869b` |
| 文件 | `Qwen3-4B-Q5_K_M.gguf` |
| 实际文件大小（官方元数据） | `2,889,513,184` 字节，约 `2.69 GiB` |
| LFS SHA256（官方元数据） | `aca596860e8cb40af6539e3f2ea40df305f42515deac56d49c08d39a02e6533f` |
| 下载地址 | `https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/bc640142c66e1fdd12af0bd68f40445458f3869b/Qwen3-4B-Q5_K_M.gguf` |
| 模型许可 | Apache-2.0 |
| 推理引擎 | 当前实验固定的官方 llama.cpp `b11756` CPU 二进制 |
| 后续实验约束 | CPU-only、4 线程、单 slot、context 4096、关闭思考、原有来源验证与隔离预算 |

大小、revision 与摘要已同时核对 [Hugging Face 固定 revision API](https://huggingface.co/api/models/Qwen/Qwen3-4B-GGUF/revision/bc640142c66e1fdd12af0bd68f40445458f3869b?blobs=true) 和 [固定文件页面](https://huggingface.co/Qwen/Qwen3-4B-GGUF/blob/bc640142c66e1fdd12af0bd68f40445458f3869b/Qwen3-4B-Q5_K_M.gguf)。**尚未下载文件重新计算摘要**；真正运行前必须沿用现有 size + SHA256 校验，不能仅信任 URL。

[同 revision 的 LICENSE](https://huggingface.co/Qwen/Qwen3-4B-GGUF/blob/bc640142c66e1fdd12af0bd68f40445458f3869b/LICENSE) 内容为 Apache License 2.0。此次小文件 GET 得到 11,544 字节，内容 SHA256 为 `5de36594c10839788a8c589443a8ef9d8b8d17c65a1b5807206ae037fc36c6bd`。本地临时推理不要求调用付费模型 API；若未来分发权重或其修改版，应保留适用的许可与声明。

`Q5_K_M` 是此次有限 CPU 实验的取舍：文件比同仓库 `Q8_0` 小，又不选择最低位数。它是否具有足够精度、是否比其他量化更快，**本研究没有实测证据**。2.69 GiB 是权重文件体积，不能当作进程峰值 RAM；KV cache、计算缓冲、服务进程和系统均需内存。它可以进入 16 GiB runner 的受限试验清单，但只有实际加载和完整样本运行才能确认内存与总时限达标。

## 与 `b11756` 的兼容证据

固定 tag 源码中，`src/llama-arch.cpp:36` 将 `LLM_ARCH_QWEN3` 映射为 `qwen3`；`src/models/qwen3.cpp:8` 明确包含 36 层、embedding 2560 对应 4B 的分支。`src/CMakeLists.txt` 将 `models/*.cpp` 纳入编译。因此存在该模型架构与 4B 规格的实现支持；这仍不能替代本次官方二进制对选定 GGUF 的实际加载验证。[架构注册](https://github.com/ggml-org/llama.cpp/blob/b11756/src/llama-arch.cpp#L36)、[Qwen3 实现](https://github.com/ggml-org/llama.cpp/blob/b11756/src/models/qwen3.cpp#L3-L12)、[编译目标](https://github.com/ggml-org/llama.cpp/blob/b11756/src/CMakeLists.txt#L9)

本次读取原始源码的小文件内容摘要：

- `src/llama-arch.cpp`：`1170b4b3b2c99642b4b6b65f245b56e3f9d5a1fb58d8c8dad1fabea52f29fc50`。
- `src/models/qwen3.cpp`：`6018840e2d7e23340e2404aceb216e6afcedbd8ae24977a0df0eb878be9d0107`。
- `src/CMakeLists.txt`：`802f9f3eced47f2396f2e8b7534050361e72882cffe2619fed6653d11b1f474d`。

官方模型卡支持非思考模式，但该模型也能进行思考；后续实验需沿用模板参数关闭思考并检查实际输出，不能因为名称含 Qwen3 就假定不会生成思考内容。现有 1.7B 的 JSON Schema 请求适配错误应先修复，并通过实际二进制 canary；更换模型无法验证或修复错误的请求契约。

## 为什么没有直接采用 `Qwen3-4B-Instruct-2507`

官方 `Qwen/Qwen3-4B-Instruct-2507` 确实存在，核对到 revision `cdbee75f17c01a7cc42f958dc650907174af0554`。模型卡明确其只支持非思考模式，因此从任务形态看值得关注；但本次 [官方模型文件 API](https://huggingface.co/api/models/Qwen/Qwen3-4B-Instruct-2507/revision/cdbee75f17c01a7cc42f958dc650907174af0554?blobs=true) 没有 `.gguf` 文件。[官方模型卡](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/blob/cdbee75f17c01a7cc42f958dc650907174af0554/README.md)

本次 [Qwen 官方公开 4B 模型清单](https://huggingface.co/api/models?author=Qwen&search=4B&limit=100) 返回 41 项，没有 `Qwen3-4B-Instruct-2507-GGUF`。猜测的同名 GGUF API 路径返回 HTTP 401；401 本身不能证明仓库不存在，但结合公开清单与本体文件列表，当前没有可核实的官方公开现成 GGUF，故不引入第三方权重冒充官方版本。较新的 `Qwen3.5-4B` 同样出现在官方清单中，本次未找到其官方公开 GGUF，不能把新名称直接当成可复现实验依赖。

## 进入实验的条件

先完成现有 1.7B 嵌套 schema 契约与 canary 实测，再决定是否需要该备用。若需要，只替换隔离实验的固定模型 pins，完整记录下载、载入、每项耗时、tokens/s、峰值 RAM、截断与退出状态；采用相同六项已见开发样本作对照，独立检查否定句、他者主语、未知信息和字段证据。**不把参数数量、文件大小或旧模型吞吐量按比例换算成新模型的实测速度，也不将六项开发对照称作新盲评。**

本研究没有给出 4B 速度、RAM 或中文语义准确率数值，也没有证明其达到生产门槛。若实际 CPU 成本或语义质量不合格，应保持生产数据与推荐链路原状。
