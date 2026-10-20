# Normalizer 与 CPU 模型探针限定安全复核

审查日期：2026-10-21（Asia/Shanghai）。审查对象为冻结提交 `03895d38972d617d4698edbc446d5774f3401342` 之后、提交前的指定文件，精确 SHA256 见末尾。独立审查者没有修改生产实现，没有启动模型下载或推理，没有提交或推送。

## 结论

**通过：可以 dispatch `model_probe_only=true`、`probe_only=false` 的隔离诊断实验。** 指定范围未发现阻断。此结论只确认实验执行边界，不代表模型可用于生产，不代表 V4 产品验收或新盲评通过。

**通过：本次 normalizer 修复关闭首次工程审查中已复现的 seed_v1 内联 HTML 不兼容问题。** 全文 `source_hash` 与 `context_changed` 保护保留。首次盲评与原工程报告保持原样，不追改首评分。

## Normalizer 核对

`visibleSourceText` 的默认与显式 `seed_v1` 均与原种子采集脚本规则一致：保留文本节点空白，在既有块标签开始处换行，最终按行整理；未知版本拒绝处理。没有改证据结构，也没有清除历史 `context_changed`。兼容规则只排除 script/style；noscript/template 沿用旧规则，因此不能将此函数称为浏览器可见性判断器。

独立运行 8 项 `SourceNormalizationTests` 全部通过。跨组件用例实际覆盖读取正文、合并证据和推荐资格：同正文保留资格；同片段的完整正文新增付费或账号前提时仍撤销资格。

独立重放 [normalization-review.md](normalization-review.md) 所存的真实 KeePassXC HTTP 200 HTML，而非重新发起网络请求。原始缓存 HTML SHA256 为 `cf2c3e70a2f9a0100a43a7a06aa9b1a11f8dc370ea95afa0233f98a8ccf50ce5`；重新调用生产归一化得到 3531 字符，与所存 txt 逐字相同，SHA256 为 `7aba283ab2d3f84619cf6d61a1323405aa8bfc56b83fb3c721fdad93c10e7f34`，匹配 seed。该真实 GET 记录时间是 `2026-10-20T16:14:50.933824Z`。这只验证该页面及受测兼容规则，不证明所有官网均未变化。

独立逐字节比较确认 `data/seed-evidence.json`、`data/curation.json` 相对冻结提交未改。

## 探针边界核对

- **来源固定和校验通过。** runtime 固定为官方 `ggml-org/llama.cpp` 的 `b11756` Ubuntu x64 CPU 压缩包；模型固定为官方 `Qwen/Qwen3-1.7B-GGUF` 的 revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`、`Qwen3-1.7B-Q8_0.gguf`。下载流同时检查精确字节数与 SHA256，全部吻合才启用文件；临时文件随后清理。解包拒绝危险路径、特殊文件和越界链接。
- **官方 pin 证据已核对。** 审查者的匿名 GitHub 请求受 403 限制、HF 请求未成功；协调者只读获取的精简官方元数据现归档为 [runtime.json](model-pin-provenance/runtime.json) 与 [model.json](model-pin-provenance/model.json)，时间为 `2026-10-20T16:22:37Z` / `16:22:36Z`。逐字段独立比较确认 URL、版本、文件名、大小和 hash 与 pins 一致。runtime asset id 为 `659461707`；模型 hash 使用 LFS SHA256，不使用 Git blobId。未声称审查者独立重下载过二进制。
- **CPU 和资源边界通过。** 固定 `-ngl 0`、4 线程、单并发、4096 上下文、700 输出 token。对实际 chat template 先本地 tokenize，预留 700+8 token，超预算直接记失败，不截断输入后冒充完整输入。启动 120 秒、每案例请求 120 秒；总计时器 900 秒触发不可被单案例异常处理吞掉的截止，随后进程收尾最多约 15 秒；workflow 17 分钟为外层兜底。900 秒不是包含所有清理在内的绝对完成承诺。
- **凭据与推理隔离通过。** 下载请求不带 Authorization。模型进程环境只含 PATH、LANG、LD_LIBRARY_PATH、OMP_NUM_THREADS；推理只访问固定 loopback，禁代理，不带认证头，不提供外部推理服务入口。仅发送已归档的公开开发样本。workflow 模型步骤不注入 GitHub token，checkout 在模型模式不持久化凭据。job 原有 `contents: write` 权限仍在，不能将其描述为整个 job 的只读权限；代码和步骤隔离使本次模型路径没有写仓库动作。
- **生产路径隔离通过。** 模型模式与其他 probe 模式互斥。collect、promote、commit、常规测试和其他 probe 步骤均有排除模型模式的条件；Python 探针不导入或调用生产采集/推荐模块。只写 `.model-probe/`，该目录被 gitignore。上传的诊断附件仅 report.json、case 文本和 server.log，保留 7 天，不上传模型或 runtime。
- **失败与结果口径通过。** 固定 6 个已见开发样本，不是新的未见盲评。请求失败、来源不足、格式错误及超预算保留请求分母。严格 JSON、指定 ref 的连续 quote 匹配仅支持格式与溯源检查；即使所有 quote 匹配也始终保留 `human_review_required` / `semantics_unverified`，不生成语义准确率。否定句截取为肯定断言的反例证明 quote 匹配不能替代语义审核。

## 验证与未验证

独立执行：

```text
PYTHONPATH=tests:. python3 -m unittest test_v4_sources.SourceNormalizationTests test_model_probe.ModelProbeTests -v
Ran 19 tests — OK（normalizer 8，probe 11）
```

通过项目包括 hash 不匹配不启用、loopback/CPU/预算固定、本机在下载前拒绝运行、workflow 所有生产步骤 guard、全局截止不被吞、token 超预算不推理、严格 JSON 与 quote 边界。

**失败：** 此限定代码审查没有发现阻断性失败；匿名元数据网络获取失败已如上披露，以协调者保存的官方只读响应补充核对。

**未验证：** 尚未实际下载并运行固定 CPU 二进制和模型；真实启动兼容性、峰值内存、耗时、运行成功率、中文语义准确性及拒答质量均待 Actions 诊断附件和独立人工核对。6 个已见样本不能替代原 40 个未见首盲，更不能声称完成 120 样本计划。

首次盲评 sampling / inputs / labels 的 SHA256 与首次归档记录一致。本轮未改首盲档案。另行进行的仓库改名身份处理及首页小流量修复不在本报告范围。

## 审查文件快照

```text
58e87c9b78287db7823425bf6717de680083c258e97a448170c41ed34e988ce5  gitradar/sources.py
757ff7435b78b89c273c861456515f911018a1e4e13fc459ce67370e3b6a44a7  tests/test_v4_sources.py
f58a4d521cbe821cfe561092c1c91d3408363e1b6dbea099b8c0bbfa4d9e90e6  scripts/probe_local_model.py
5035f1bd105cbdfc3e703a2b12a482066f7e7aea5711003a09cf50954a9febbf  scripts/model_probe.sh
403f5122925632dfc3360683c5e83a4a0c24830dec8d261fa8f5e29cc0b4dd78  scripts/model_probe_pins.json
6311907c44e28b0f9e32d7c2e7f2a72d814a3970fd0ced183329471ec261aef1  tests/test_model_probe.py
96978ccade1edc8841ad23d7aef2676734157c6b2826a6707d5dbcabe64917bf  tests/fixtures/model_probe/cases.json
3be870c51e0b1496592dab5ee35428ead140fdd67554e56913ab2d38f71210f4  .github/workflows/update.yml
8f51cd68b1d1bfbc40a3582b13607765c40c74c8ddfe5e248fc9c7ef8add5257  .gitignore
```
