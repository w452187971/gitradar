# 八项目证据恢复独立复核

复核日期：2026-10-20 UTC。独立 AI 代理审查，不是人工读者评估。

结论：允许应用 SHA256 `41f912ae55435f712a1b8102fdd9ba023c5735b57024e20b7241e293a07d94b2` 对应的精确修复提案，仅校正下表 14 个受损引用。不直接恢复项目资格标记，不刷新未检查来源的时间，不改 seed、curation 或 history。本评审没有应用提案；实际执行与后续 collector 回归由主代理负责。

审查基线为 `40d972921ffadedc646e3296a8f77d08d0b91d97`。审查时工作树 HEAD 已是 `cfe0bd9e6fd0f92b63e5b27440d443268a0aa433`，但 evidence、seed-evidence、curation 三个数据文件均与基线逐字节一致。

## 核验结果

- 49 个取证归档文件与 `/tmp/gitradar-v4-source-recovery-m29zw740` 逐字节一致。MANIFEST 内列出的 48 个文件逐项哈希通过，MANIFEST 自身另算。原材料见 [取证归档](source-recovery-40d9729/README.md)。
- 22 份成功响应均为 200：8 份 metadata、8 份 README、6 份 `/license`。本评审未发网络请求，不能独立证明响应发生过程；依据是归档请求、响应、时间、版本与内容。
- 8 个项目的 `node_id`、`created_at`、名称与 seed、生产 evidence 一致。原 `repository.text` JSON 的全部字段，包括完整嵌套 license，在新取公开事实白名单响应中深相等；新增 `fork` 不被冒充原断言。
- 14 份 README/许可证从原响应 base64 独立重新解码，字节大小、Git blob SHA、完整 SHA256 与归档全文一致。原 span 仍在原行区间，原 `content_hash` 与 curation 绑定相同，`source_length` 与完整文本字符数相同，全文 `source_hash` 与 seed 一致。没有用“旧句仍在”替代全文上下文校验。
- 共支持 31 个原绑定：14 个受损绑定需要校正，17 个 README 绑定当前已一致。本次 22 份来源未发现真实内容或身份变化；不能据此推断未请求来源没有变化。

## 精确允许范围

| 项目 | 允许校正的 ref ID | 已核对但无需改绑定 | 本轮未复核，保持原状态及日期 |
|---|---|---|---|
| Flow-Launcher/Flow.Launcher | `repository` | `intro`、`install` | `path` |
| FreeTubeApp/FreeTube | `repository`、`license_document_review` | `intro`、`install`、`license_grant_review` | `path` |
| Zettlr/Zettlr | `repository`、`license_document_review` | `intro`、`install` | `path` |
| KDE/kdenlive | `repository`、`license_document_review` | `intro`、`install` | `requirements_1`、`path` |
| bleachbit/bleachbit | `repository`、`license_document_review` | `intro`、`install` | `requirements_1`、`requirements_2`、`path` |
| HandBrake/HandBrake | `repository` | `intro`、`install` | `license`、`requirements_1`、`path` |
| WinMerge/winmerge | `repository`、`license_document_review` | `intro`、`install` | `requirements_1`、`requirements_2`、`path`、`license_grant_review` |
| arsenetar/dupeguru | `repository`、`license_document_review` | `intro`、`install` | `requirements_1`、`path` |

每条只允许提案中的五个字段变化：

1. `text`、`content_hash`：恢复原 seed 的确切 span/事实子集及哈希，仍与未修改的 `curation.evidence_hashes[ref_id]` 相同，不能重写 curation 来接受损坏文本。
2. `source_hash`：6 个 `license_document_review` 使用新取完整解码许可证的 SHA256，等于 seed 全文哈希；8 个 `repository` 使用新取公开事实白名单完整序列化文本的 SHA256。后者与原事实子集的 `content_hash` 不同是合理的，不是整个 GitHub HTTP body 的字节哈希。
3. `checked_at`：只使用对应归档响应的 `received_at` / report `checked_at`，不能统一设为修复执行时间。
4. `status`：设为此次对应成功响应的数值 `200`。

14 条 `before` 均与当前 evidence 完全相等；项目/ref 集合恰好等于独立确认的受损集合，没有额外项、重复项或漏项。所有实际 diff 均恰好是上述五字段。`id`、URL、`source_kind`、section、原行范围、`source_length`、`text_extraction`、`previous_hash` 等均不变。目标原本没有 `context_changed`、`previous_source_hash` 或 `error`，提案没有删除这些保护。实施前若 evidence 哈希或任意 before 条目不符，应终止，而非重新套用本许可。

`repository` 参与原用途/受众绑定，Flow Launcher 的许可也绑定它；`license_document_review` 参与各项目许可。README 的 intro/install 参与用途、平台、形态与前提等，本轮不重新编辑对应中文断言。WinMerge 的许可仍依赖本轮未复核的独立 `license_grant_review`；单个许可证标题不能替代完整许可授予证据。所有下载入口都在此次新请求范围外。

## 必须保留的边界

- `unchecked_other_sources` 共 17 个引用未由此次 22 GET 刷新，可以沿用此前有效检查和既有失效规则，但不能增加本轮 `checked_at`、`path_checked_at`、`path_checks` 或清除失效状态。HandBrake 的独立 LICENSE、WinMerge 源码许可授予条款也在此列。
- 真正变化或身份不一致的来源必须保持撤回/待复核，不能用旧 seed 覆盖。其他来源已有的上下文变化、404/410、过期、身份冲突或缺证据不获豁免。是否重新可推荐只能由现有校验器读取全部当前证据计算，不能直接设置发布/资格状态为通过。
- 当前提案不修改 history。实施应保留修复前 evidence 哈希、提案哈希与审计报告。后续 collector 产生的是新证据，本次离线复核不冒充实际采集回归。
- 本轮不是模型盲测、完整种子准确率重评、安装实测或真人可理解性验收。第二盲组保持私有，未读取其模型输出。

## 输入指纹

| 文件 | SHA256 |
|---|---|
| `data/seed-evidence.json` | `9581bd8036eaf2ce780b2eed696c40d10c81298cfd566ab49b307ecdcc259a64` |
| `data/evidence.json` | `60946d9de629efb65e54d971c289c6f46f059b5a8c1d63b71a72e41c410f1b6e` |
| `data/curation.json` | `f0c871b5b9e708cefb8051d47cb97f30188626a45f6e590025696e4a98204389` |
| 取证 `report.json` | `49051b6d779311de92b6a36215c7cbb21350b351248be862575a1e39055b370e` |
| 取证 `MANIFEST.json` | `aefd7e2e8879cffce3dd0abe22a84718c596a1ab9292e6422cf7d896882f0232` |
| 取证 `README.md` | `ef9dc744a2865acd25b7c3bb230ad04a53fad8fc361b5ed8055730f5c3459b9e` |
| `/tmp/gitradar-evidence-repair-proposal.json` | `41f912ae55435f712a1b8102fdd9ba023c5735b57024e20b7241e293a07d94b2` |

逐源 URL、实际接收时间、全文哈希和 ref 清单位于 [取证报告](source-recovery-40d9729/report.json)，由以上指纹固定。独立核验脚本与逐 ref 结果暂存 `/tmp/gitradar-evidence-recovery-independent.py`、`/tmp/gitradar-evidence-repair-proposal-independent.py`、`/tmp/gitradar-evidence-recovery-independent-result.json`。脚本从基线 Git 对象与原归档读取，没有调用生产修复函数或网络来产生“通过”。
