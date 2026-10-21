# FreeTube 发布页上下文变化的离线分析

结论：**本例有可复现的误撤回证据。** 与旧绑定哈希完全匹配的完整规范化文本已找到；前后 34,226 字符、967 行，唯一变化是 GitHub 仓库导航中 Pull requests 数量从 11 变为 12。其余规范化文本逐字一致，包括发布列表、版本、Beta/Pre-release 标识、发布说明与限制。此处“误撤回”指无关导航计数使既有推荐断言失效，不代表当前保护规则执行错误，也不授权清除已经产生的 sticky 标志。

本分析仅使用本地已知归档，无新网络、无私有盲组或模型输出访问，不修改生产代码、data、seed、curation 或上下文保护。

## 原文与差异

旧全文就在 `/tmp/gitradar-license-live-renewal-xpq6zrtb/before.json` 的 FreeTube `official_site:source:af2104…` 引用中，不必另行搜索临时目录。它的 UTF-8 SHA256 同时匹配该完整引用的 `content_hash`、旧 `path.source_hash`，也匹配原 seed 的 `path.source_hash`。原 seed 检查时间为 `2026-10-20T15:26:56Z`，旧完整引用后续检查时间为 `2026-10-20T16:54:25.698349Z`。

新全文取自同目录 `after.json`，并以生产 `visibleSourceText` 对真实响应 `responses/03.body` 独立重算，结果逐字相同；新完整引用检查时间为 `2026-10-21T01:22:36.903398Z`。前后 URL 均为 `https://github.com/FreeTubeApp/FreeTube/releases`。

完整 diff 只有第 100 行：

```diff
 Repository navigation
 Code
 Issues284 (284)
-Pull requests11 (11)
+Pull requests12 (12)
 Discussions
 Actions
 Projects
```

数量与括号之间均为同一个 U+00A0 空格；不存在隐藏的空白改写。完整页第 108 行起的原 `path` 片段保持相同，原片段哈希 `138bb8b363e8af9f2d01d28a9547198b70c2ce1cebc0c94f01686dd182cf4cd8` 仍有效。

该导航计数不是 FreeTube 发布、平台、费用或安装条件。当前编辑中 `path` 参与 platforms、prerequisites、usage_paths 和 cost 的引用，尤其支持“v0.25.3 Beta / Pre-release，不能称为稳定正式版”。本次变化没有改变这些已保存断言的原文依据。

## 为何仍须保留当前撤回结果

当前规则按完整规范化来源保护上下文：旧片段仍存在不足以证明页面没有新加限制，所以 `_refreshRef` 在全文哈希变化时设置 `context_changed` 和 `previous_source_hash`，后续资格检查撤回内容。这个原则能够防止“老句没删，但页面另一处新增付费、平台或许可限制”继续被当作已审核结论。

独立离线回放把此次真实新完整来源交给未修改的 `mergeEvidence`，旧输入资格为 true，合并后为 false，原因为 `context_changed:path`、`not_published`。因此，已经定位本例因无关计数触发保护，不能把它写成规则失效或悄悄豁免。生产数据本轮仍未写回，隔离归档中的撤回记录保持原样。

边界：旧材料是完整**规范化文本**，并非旧原始 HTML；本轮未找到或声称比较过旧 HTML、链接属性或安装资产。故能够证明的是“触发本次哈希变化的全部文本差异只有导航计数”，不能据此宣布下载链接、资产或整个网站的所有语义都未变化。此前来源恢复归档也将该发布页列为未检查来源，不能拿它补证旧 HTML。

## 后续改进必须守住的边界

1. 可以提出 GitHub 发布页专用的、有版本的正文范围提取：明确识别仓库导航区域，再排除导航计数；不能对任意正文做全局数字清洗或简单删除包含 `Pull requests` 的行。未知 DOM、解析歧义、空正文或来源身份不符应继续待复核。
2. 仍保留完整原文及全文哈希用于审计，另以明确的“断言上下文范围”检测内容变化。发布标题、版本、预发布状态、正文的许可/付费/系统限制、获取入口与资产变化都必须进入相关保护，不能只保留已选旧片段或交给模型判断“差不多”。
3. 若改用官方 Release API，需绑定稳定 release 身份与选择规则。本项目选择 Beta，不能直接使用可能排除预发布的 `releases/latest` 来替代当前入口；还必须保留页面链接与下载路径的独立复核。API 不自动覆盖所有网页限制。
4. 不静默改写已有 `seed_v1` 规范化规则。新提取版本需要明确迁移和重新审核；只有保存的旧完整来源能够重算并精确匹配旧绑定哈希时，才可作为迁移的比较依据，缺旧全文则证据不足。旧全文哈希、首次变化记录与 sticky 状态保留；不能借提取规则变更自动洗掉既有冲突。
5. 本例可成为真实回归样本，但只证明一例误撤回。验收还应覆盖“仅导航计数变化”以及“原片段不变但发布正文新增限制”等正反例，并确认链接、许可、预发布与身份变化仍会阻断。没有这些证据前不宜降低全局保护强度。

本轮只给设计边界，不实施这些改进。

## 可复现资料与指纹

离线脚本、结果、唯一差异和摘要已封存于 [freetube-context-change/](freetube-context-change/manifest.json)，原工作副本脚本为 `/tmp/gitradar-freetube-context-analysis.py`，输出位于 `/tmp/gitradar-freetube-context-analysis/`。原始前后全文及 HTTP 字节可从 [完整续期归档](license-live-client-renewal-20261021.tar.gz) 取出。脚本校验完整前后哈希、原响应规范化结果、全部 967 行差异及现有合并/资格规则，不调用网络。

| 材料 | SHA256 |
|---|---|
| 原归档 `before.json` | `fdf10983e25927945b387551a88696721857b8b7fe17100b4260cde52ce72598` |
| 原归档 `after.json` | `bcada5fc99848481be742b419375d92551bc0bfc1b7cb90038f2b00dbcee713b` |
| 新原始响应 `responses/03.body` | `38d83daf821b056f0f7d99b049d38c44319936f96c26cecc168df56722c24cde` |
| 旧完整规范化文本 | `af2104e7ed60b10555e3d697a49b5980c33aa7fbe2b01303ef04e033d2e71665` |
| 新完整规范化文本 | `29dacbde5baf766d956bf6632b92ccc095fa3052a2a7c706dbd5f80daad4d3d4` |
| 离线核验 `result.json` | `c3a5122a148e0863eee61106e7bd35126f7a29da8ff2387b601f6deef10bca94` |

本结论是独立 AI 代理对实际文本差异的审核，不是人工读者测试、模型准确率结论或全池误报率估计。
