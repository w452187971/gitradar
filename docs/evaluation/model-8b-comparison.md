# 一次8B资源折中对照：设计冻结与实测

以下方案冻结于 `401dd4b`，当时尚未运行。执行后记：[39533359976](https://github.com/w452187971/gitradar/actions/runs/39533359976) 实际完成六例，用时474.099秒、server峰值约9.14 GiB，6项解析、4项raw有效；仍有严重语义错误，独立核对见 [model-sixth-8b-review.md](model-sixth-8b-review.md)。此次之后停止旧六例选型及提示调试，未接入生产。

14B真实运行 `39527528160` 用时749.187秒，前五个有来源样本均在原120秒单请求截止前未返回；仅无来源控制完成。其下载、加载与canary成功，server峰值RSS15,161,836 KiB。该结果只能说明现有资源/时限下无法完成这些输入，不能评价14B语义质量，也不能把未完成项排除分母。因此仅准备一次8B对照，不继续调整六例提示词，不消耗隐藏组；若这次仍无效，停止围绕该开发组选择模型或调提示词。

官方固定 `Qwen/Qwen3-8B-GGUF` revision `7c41481f57cb95916b40956ab2f0b139b296d974` 的 `Qwen3-8B-Q4_K_M.gguf` 为5,027,783,488 bytes，LFS SHA256 `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`（64位）。固定revision API与完整Apache-2.0 LICENSE经两次primary小GET核对；精简证据为 `model-8b-source.json`，权重未下载。LICENSE正文11,544 bytes，SHA256 `5de36594c10839788a8c589443a8ef9d8b8d17c65a1b5807206ae037fc36c6bd`。只用资源和输入不等于证明模型更准确，实测前不承诺可完成或内存足够。

现有 `scripts/probe_model_comparison.py` 仅增加白名单枚举 `--model-key {14b,8b}`，默认14b；每份模型配置均有代码中固定的文件SHA256，未知选项与篡改均拒绝。8B配置为 `scripts/model_comparison_8b.json`，文件SHA256 `2ac76850f9afa2f1f44050bad3e65f374d8f5acff775236b283dbaf00cf8b191`。新增provenance的model_key和model_pins_sha256明确选择。wrapper自身已改变，因此不能沿用14B旧wrapper冻结SHA `cdcc6124…` 来证明新版本；实际源码hash须重新冻结，14B旧运行与review不改写。

基线仍为 `980b7657415796f9d9c67181dac69365a22e2838` 原v3源码，SHA256 `0871654d0a1f0731daa75133c46ab632332bcd9fabde8719f0e44be49e1b74ae`；fixture字节及SHA `96978ccade1edc8841ad23d7aef2676734157c6b2826a6707d5dbcabe64917bf`、prompt、runtime b11756及原hash全部不变。固定CPU4、GPU0、4096上下文、700生成tokens、非思考、temperature0、单项120秒、canary30秒、加载120秒、整批900秒；不裁上下文或跳过无来源真实推理。仍仅动态模块ROOT指临时harness，下载前检查权重+runtime+2GiB磁盘，大小/hash验证后才执行；原环境白名单与loopback不变。

新增独立 `.github/workflows/model-comparison-8b.yml` 与原14B workflow仅模型名称、artifact前缀和命令 `--model-key 8b` 不同：手动互斥公开runner guard、contents只读、不保存checkout凭据、900秒外层截止/17分钟job和报告小文件白名单均相同。原14B workflow和配置不修改。root将在独立 `codex/gitradar-v4-model-8b-comparison` 诊断分支处理已注册workflow路径的逐字等价调度，记录实际checkout_head与工作流hash；不覆盖14B冻结ref、不改main/dev正式workflow。

离线回归覆盖8B篡改、未知modelKey、14B默认等价、8B与14B只有model节点不同、原harness/身份/预算/磁盘/Token/数据隔离及两工作流严格差异。没有模型运行或语义结论。实际结果仍需独立逐字段评分，raw/ref绑定不证明语义蕴含；基础设施超时和失败保留原始报告及六项分母。
