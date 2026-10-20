# 官网正文归一化修复复核

本报告追加复核冻结实现 `03895d38972d617d4698edbc446d5774f3401342` 的官网正文抽取 P1；不覆盖 [首次独立审查](final-review.md)，也不改变首次盲评结论。

## 结论与实现边界

官网正文统一使用 `gitradar.sources.visibleSourceText`，默认规范版本为 `SOURCE_TEXT_NORMALIZATION = 'seed_v1'`。函数接受显式版本参数，未知版本拒绝处理，避免悄悄用另一套规则更新已审核上下文。原有双参数调用保持兼容；没有新增或改变证据 JSON 字段。

规则与原 seed 采集脚本 `/tmp/gitradar-seed-review/extra.py` 一致：保留文本节点原始空白；仅在 `p/h1/h2/h3/li/tr/div` 开始标签处加入换行；拼接后按原有行去除行首尾空白和空行。内联链接、强调及 span 不再拆断句子。HTML 字符实体正常解码，UTF-8 保持原文，script/style 内容不进入正文，解析过程不执行脚本。兼容旧 seed 的规则只排除 script/style，noscript/template 的处理沿用 seed；该规范不是浏览器布局或可见性判定器。普通文本不重新归一化。

没有修改 `github_client.py`、`evidence.py`、完整 source_hash 比较或 `context_changed` 保护。既有片段和全文哈希实际相同才保留原审核；未来规范升级必须明确迁移并重新审核。已被旧流程标记 `context_changed` 的历史证据不会自动清除标记。

## TDD 与离线验证

新增 `tests/test_v4_sources.py`。修复前先执行原始七项用例，观察内联拆行、实体、原始换行和“同文仍被撤资格”的断言失败；添加显式版本用例后再次执行，确认旧接口不支持版本参数。然后只修改 `sources.py`，八项全部通过。

跨组件测试经过 `readEvidenceSource → webEvidence → mergeEvidence → deriveFacts → resolveContent`，传输边界返回合成 HTML，并要求实际调用 GET、目标官网 URL 且无 Authorization：

- 同一正文仅含内联 HTML：片段 hash 和全文 hash 不变，推荐资格保留。
- 原片段不变但新增必需付费或账号句：片段 hash 保留、全文 hash 改变，触发 `context_changed` 并撤销资格。
- UTF-8、HTML 实体、script/style 排除、块级分隔及原始文本空白均有回归。

完整检查：

```text
python3 -m unittest discover -s tests
Ran 250 tests — OK

node --test tests/*.test.cjs
tests 74 / pass 74 / fail 0
```

250 项含冻结版 236 项、本次 8 项，以及并行模型探针工作新增的 6 项。本次未改探针相关文件。

## 单页真实 GET 复核

请求 URL：`https://keepassxc.org/download/`。记录时间：`2026-10-20T16:14:50.933824Z`。生产 `httpTransport` 返回 HTTP 200，Content-Type 为 `text/html; charset=utf-8`。只发公开 GET，不使用令牌，不安装软件，也没有用 HEAD 更新正文时间。

原 seed 缓存 `/tmp/gitradar-seed-review/keepassxc-path.extra.json` 记录时间为 `2026-10-20T15:26:47Z`；没有旧 raw HTML，未重造历史 HTML。本次保存的 HTML 来自本次真实响应。

| 对比项 | 原 seed | 本次生产归一化 |
|---|---|---|
| 正文字符数 | 3531 | 3531 |
| SHA256 | `7aba283ab2d3f84619cf6d61a1323405aa8bfc56b83fb3c721fdad93c10e7f34` | `7aba283ab2d3f84619cf6d61a1323405aa8bfc56b83fb3c721fdad93c10e7f34` |
| 全文逐字比较 | — | 相同 |
| 推荐资格 | true | true |

生产 GET 结果经 `mergeEvidence → deriveFacts → resolveContent`，`invalidation_reasons=[]`。`requirements_1` 与 `path` 均保留原片段、content_hash、source_hash，无 `context_changed`：

- requirements_1 content_hash：`771c1c78354d1b7fe30dbf305881f72b644c3f357222c13d27925b4bdd464369`
- path content_hash：`0c13c22191c99c7a9ba784078f35c44a7bad8a7ccf2a23ba66ec76e362f21e77`

另在本次已获取 HTML 后分别合成追加 `Requires a paid subscription.` 与 `Requires an account.`（明确为反例，非官网实际声明），沿用生产抽取、webEvidence 和合并流程。两次均 `eligible=false`，原因为 `context_changed:path`、`context_changed:requirements_1`。

本地复核原始输出保存在 `/tmp/gitradar-normalization-review/`：`keepassxc-current.html`、`keepassxc-current.txt`、`result.json`。本次已解码 HTML 文件 SHA256 为 `cf2c3e70a2f9a0100a43a7a06aa9b1a11f8dc370ea95afa0233f98a8ccf50ce5`。临时目录不是永久归档承诺；上方固定记录本次结果与哈希。

## 保留范围

与冻结提交逐字节比较确认：

- `data/seed-evidence.json` 未改，188 refs 保留；文件 SHA256 `9581bd8036eaf2ce780b2eed696c40d10c81298cfd566ab49b307ecdcc259a64`。
- `data/curation.json` 未改；文件 SHA256 `f0c871b5b9e708cefb8051d47cb97f30188626a45f6e590025696e4a98204389`。

这次真实网络验证只覆盖 KeePassXC 下载页。其余官网真实变化、完整采集批次及推荐数量仍须由后续采集验证；未据单页成功宣称全部官网无变化，也未宣称 V4 产品完整验收通过。
