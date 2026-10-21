# 一次14B容量对照

本实验仅回答：保持原 v3 抽取协议不变时，增加模型容量是否值得继续评测。仍使用六个已见开发样本，不使用隐藏组，不按项目名调整提示词，不导入生产模块或写入正式数据。4B 两步诊断不再调参。

`scripts/probe_model_comparison.py` 从 Git 对象读取基线 `980b7657415796f9d9c67181dac69365a22e2838` 的 `scripts/probe_local_model.py`，执行前两次核对 SHA256 `0871654d0a1f0731daa75133c46ab632332bcd9fabde8719f0e44be49e1b74ae`。六项 fixture 必须与基线及当前文件逐字节相同，SHA256 为 `96978ccade1edc8841ad23d7aef2676734157c6b2826a6707d5dbcabe64917bf`。临时 harness 仅包含该 fixture 和由基线 pins 替换 model 节点得到的配置；动态模块仅更换 ROOT，提示词、函数、运行时和协议均不修改。当前 v4 脚本及4B配置保持原样。

唯一模型变量为官方 `Qwen/Qwen3-14B-GGUF` 的 `Qwen3-14B-Q4_K_M.gguf`：revision `530227a7d994db8eca5ab5ced2fb692b614357fd`，9,001,752,960 bytes，SHA256 `500a8806e85ee9c83f3ae08420295592451379b4f8cf2d0f41c15dffeb6b81f0`。独立配置在 `scripts/model_comparison_14b.json`。固定 revision 的官方元数据和 Apache-2.0 LICENSE 正文经两次小 GET 核对，精简证据在 `docs/evaluation/model-14b-source.json`；未下载权重。llama.cpp 仍由基线固定为 b11756，下载时继续验证精确长度和 SHA256。

执行仍要求公开 Linux x86_64 Actions 的手动事件，`model_probe_only=true` 且 `probe_only` 不为 true。CPU 线程4、GPU层0、context4096、每样本最多700生成 tokens、temperature0、非思考和原始 canary 均沿用基线。无来源控制仍真实推理。单请求120秒、canary30秒、加载120秒等原有上限也不放宽；因此14B可能在单项或整批截止前失败，失败和未尝试项仍保留在六项分母。

下载前要求临时磁盘至少容纳模型、runtime及2 GiB余量；16 GB runner 的实际峰值内存、吞吐和成功完成能力尚未验证。整批外层 `timeout` 900秒（终止后最多15秒清理），基线内部仍有900秒截止，job最多17分钟。server继续仅监听127.0.0.1，环境仅保留原四键白名单，不继承 GitHub Token。

独立 `.github/workflows/model-comparison.yml` 只有手动入口、contents只读、checkout不留凭据，无采集、提升或提交步骤。新 workflow 的可调度注册由 root 处理；如需经已注册路径运行，只在专用诊断分支逐字复制已审 workflow，并记录等价文件 SHA256 和诊断 commit，dev/main 的 update.yml 不改。不得为触发诊断切换 main 或增加额外试跑。

附件只包括 report.json、comparison-provenance.json、case-*.txt 和 server.log，临时 harness/权重不上传。provenance在执行前保存基线commit、实际源码hash、harness fixture/pins hash；`checkout_head` 来自本地 `git rev-parse HEAD`，`event_github_sha` 只表示事件变量，二者不能混用。成功也只标记语义未核实。绑定原文是程序按ref复制，不能当作模型引用或蕴含关系准确的证明。现有首次、v2、v3、v4结果档案保持原样；这一次结果需另行封存并独立逐字段核对，不能直接接入生产。
