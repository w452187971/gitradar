# 第二版模型探针：接口与入口限定安全复核

日期：2026-10-21（Asia/Shanghai）。独立 AI 代理只读审查请求协议、canary、运行入口及测试隔离；未修改实现、未下载或推理。本结论只覆盖第二版差异。

## 结论

**限定审查通过，可进行第二次独占模型诊断 dispatch，未发现本次范围的阻断。** 18 项相关离线测试通过；另在父进程 `GITHUB_ACTIONS=true`、`GITHUB_EVENT_NAME=schedule` 条件下独立执行原失败测试，通过且无下载。官方二进制上的 canary 与第二轮语义表现仍未验证。

## 请求契约

已读取协调者保存的固定官方 `b11756/tools/server/server-common.cpp`，完整 SHA256 为 `b4f4aae7eed919f914d132ae64416a0e7cfb23442161af6f63ba8d902954d442`。实际 parser 在 `json_schema` 类型分支读取 `response_format.json_schema.schema`；为空时转为任意 object。第二版 `responseFormat()` 正确使用此嵌套位置；主样本和 canary 共用该构造函数。首次扁平请求不符合实际契约，不能将格式失败直接归罪模型。

新增 HTTP 测试经过真实 loopback 请求序列化，再由冻结协议模拟器读取，验证 nested 得到完整 schema、旧 flat 得到 object。模拟器没有执行上游 C++ 或加载官方 runtime；文档已正确披露。主 prompt 新增八字段对象模板，六样本及片段 hash 未改。第二轮同时改变协议和提示，不能将全部效果差异仅归于 grammar。

## Canary 拦截

经过既有 hash 校验的官方 CPU server 启动后，先执行 canary。对抗 prompt 要求 `purpose` 为字符串 `SHAPE_BYPASS`，schema 要求三成员对象及固定常量；常量期望值未放进 prompt。只有输出精确匹配 `CANARY_OUTPUT`、正常 stop、无 thinking、timing 完整才通过。原文与完整请求存入报告，原文另写 `case-00-schema-canary.txt`，既有 `case-*.txt` 附件模式覆盖它。

canary 失败设置 `failure_kind=schema_canary_infrastructure` 并抛出异常，六项主样本调用次数为 0，最终非零退出。它不占六项质量分母。通过后全部六项运行，包括无来源控制，没有提前跳过空 refs；报告完成条件也要求 canary 通过。相关测试分别验证失败时零主样本、通过时六项执行。

canary 最多生成 128 token，完成请求限时 30 秒，沿用总 900 秒计时及清理兜底。上下文预检仍按 700+8 余量保守预留，比其实际输出上限更严格。单次 canary 通过只是该固定请求的运行证据，不证明所有 schema 构造或中文语义都正确。

## 入口与普通 CI 隔离

`executeProbe` 在读取 pins 和下载前调用 `requirePublicRunner`。除原 Linux/x64、Actions、公有仓库条件外，现要求 `workflow_dispatch`，且 event inputs 中 model_probe_only 显式 true（布尔 true 或字符串 `true`）、probe_only 未启用。schedule、普通 dispatch、false、数字 1、普通 batch probe、双模式冲突均在下载前拒绝；独占诊断两种 true 编码均允许。

原“本机拒绝运行”测试子进程现显式传 `GITHUB_ACTIONS=false`，不再依赖 Mac 环境天然不能推理。独立以 CI 风格父环境执行，仍在入口拒绝，报告无 downloads、attempted 为 0。本次修复没有增加生产采集、提升或提交路径。

已读取普通 collector CI [39458715810](https://github.com/w452187971/gitradar/actions/runs/39458715810) 的本地原日志：旧测试继承 Actions 环境，真实下载并执行首版六样本，诊断 total_wall_seconds=101.31，随后 `assertNotIn('downloads', report)` 失败。这是错误触发的旧版推理，不是第二版实验。协调者确认流程止于测试、未采集/提升/commit；本限定检查独立核对了日志中的失败和诊断输出，没有另行请求远程 job 状态。该缺陷说明首次本机测试不足以证明 CI 环境隔离，第二版增加环境显式化和入口双重检查。

## 验证与封存

```text
PYTHONPATH=tests:. python3 -m unittest test_model_probe test_model_probe_contract -v
Ran 18 tests — OK

GITHUB_ACTIONS=true GITHUB_EVENT_NAME=schedule PYTHONPATH=tests:. python3 -m unittest test_model_probe.ModelProbeTests.test_local_execution_fails_before_any_download_and_preserves_report -v
Ran 1 test — OK
```

独立重算首次 manifest 所列八个文件，hash 全部相同；输入 SHA256 仍为 `96978ccade1edc8841ad23d7aef2676734157c6b2826a6707d5dbcabe64917bf`。只在首次语义报告末尾追加根因说明，原输出、48 字段分类与首轮盲评均未改。未重复全库测试，未声称新远程 canary 或内容效果通过。

## 审查快照

```text
16dbda47dc2602b02eee97028c7fbf37ae16fa961887372d4b43ce831b6ebf41  scripts/probe_local_model.py
9948db5a076fe836b13128a0c7762262b666b0082b7c9d4c60007b22d8bfc6c7  tests/test_model_probe.py
33c33e04fac9f1a1acadf6a1f707ab4f648bf1953dd26cfe697b655251019fe9  tests/test_model_probe_contract.py
22f95681ccf9168fc450f4444697647133c03c38be0ac45d2baf053127bc7dad  docs/evaluation/model-probe-plan.md
```
