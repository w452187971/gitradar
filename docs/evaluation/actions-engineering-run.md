# 开发分支真实 Actions 工程验收

本次真实“采集→隔离校验→提升→自动提交”链路通过；历史、预算、推荐刷新和产物哈希符合本报告检查项。另发现旧仓库转移后的身份关联缺口，以及首页为核对批次而下载完整候选文件的性能问题。**这不是 V4 整体验收通过，也不是 main / GitHub Pages 发布验收。**

本报告只新增文档，未修改生产代码、数据或生成产物，未提交或推送。核验以固定提交的 Git 对象为准，不把工作区后续修复计入首次运行。

## 运行身份与真实执行

- 运行：[39454254516](https://github.com/w452187971/gitradar/actions/runs/39454254516)，开发分支 `codex/gitradar-v4`。
- 事件：`workflow_dispatch`，状态 `completed / success`。
- 执行代码：`03895d38972d617d4698edbc446d5774f3401342`。
- 自动数据提交：`1c815e6e5d1a77449cdda3b5f383d5d8bd3fe24f`，作者 `github-actions[bot]`。
- 运行时间：2026-10-20 16:04:51–16:10:37 UTC；数据批次起点 `2026-10-20T16:05:01.116030Z`。
- 批次：`f98d7f0f85ec4292921dfa7c9fe1a081`。

认证只读导出的 run/jobs 元数据显示：Python 测试、前端测试、隔离采集与校验、提升、提交推送步骤均 `success`。采集步骤为 16:05:00–16:10:29 UTC，提升 16:10:29–16:10:30，提交推送 16:10:30–16:10:34。探测专用步骤和失败附件步骤正确跳过。成功运行没有触发失败附件，因此此次不能证明真实失败附件上传路径已经执行。

本次没有逐条 HTTP 原始响应归档；“成功观测”依据真实 Actions 提交的观测时间、稳定身份、状态、Star 与历史端点一致性、请求用量及冻结代码校验复算，不声称重新独立访问了全部 GitHub 仓库。

## 历史与观测

以执行代码提交 `03895d3` 为输入基线，与自动提交 `1c815e6` 逐键逐日期比较。输入 history SHA256 为 `f4551e8d51a3db71410f54a35ceea007dcb8f39121df927b270d244901e7a8cc`，与冻结基线记录一致。

| 检查 | 实测结果 |
|---|---:|
| 原历史项目键 | 1,970，全部保留 |
| 原日期键丢失 | 0 |
| 已有数值变化 | 855，全部为 2026-10-20 UTC 当日 |
| 变化未对应当日 fresh / Star / 观测日期 | 0 |
| 新增历史端点 | 374，全部为 2026-10-20 |
| 当前历史键 / 正式候选 | 2,344 / 2,344 |
| 本轮 fresh | 2,343 / 2,344，99.9573% |
| 固定原池 fresh | 1,969 / 1,970，99.9492% |
| fresh 缺稳定 ID、当日观测时间或匹配 Star 端点 | 0 |
| 当前推荐 fresh | 20 / 20 |
| 待观测新候选队列 | 0 |

855 处同日数值更新属于允许的当日重跑，不是改写非当日历史。本轮历史仍只有一个 UTC 日期，全部 1 日 / 7 日增量为空；不能据本轮 Star 变化宣称已验证日增长或周增长。

### 唯一 deferred 项与身份连续性缺口

`JeroenCorthout/TheMachine` 保留原 Star=10、原 `2026-10-20` 历史，状态为 `deferred`，错误为 `No successful observation in this batch.`；没有新 `last_observed_at`，不在首页推荐。

产物同时新增 `Salesflare/TheMachine`，稳定 ID `R_kgDOVLdUZA`，创建时间与旧项目同为 `2026-10-15T20:40:05Z`，描述相同，实际观测时间 `2026-10-20T16:08:21.736434Z`，fresh Star=10。旧项没有稳定 ID。全批 `observation_errors=[]`、身份 REST 补查=0，不能将旧项 deferred 解释成已证实的 API 失败。

使用自动提交归档的冻结 `applyObservations`，以旧项目记录和该新名称成功观测作最小回放，结果是两个项目、两个 history 键、空 `saved_aliases`：关联只尝试稳定 ID 和返回名称，旧项无 ID 时无法把返回的新名称关联回原入口。**这确认了迁移关联边界的缺口**；同创建时间和描述支持仓库发生转移的推断，但原始 GraphQL 响应没有保存，本报告不把具体转移过程当作独立核实事实。旧历史未丢失，但用户旧收藏别名及连续观测尚未正确合并，需另行修复后验证。

## 搜索、预算与内容工作量

搜索 20 次，成功 20 次；其中 18 次受查询结果上限限制，0 次 `incomplete_results`。成功率不等于 GitHub 全站覆盖。

| 用量 | 实际 / 上限 |
|---|---:|
| 搜索 | 20 / 20 |
| 非搜索 REST 合计 | 80 / 100 |
| 内容 REST | 60 / 60 |
| 路径检查 | 20 / 20 |
| 身份补查 | 0 / 20 |
| GraphQL 批次 | 47 / 100 |
| GraphQL 点数 | 47 / 600 |
| 重试 / 未计量 GraphQL | 0 / 0 |
| 限流标志 | false |

结束记录的 REST 余量 4,960，GraphQL 余量 4,957，搜索余量 10。内容队列尝试 20 项，实际使用 60 次请求；16 项完整成功、4 项部分成功、0 项完全失败，另有 2,324 项等待，不能把 20 次尝试说成 20 项完整复核。

## 批次、文件与提交边界

直接从 Git 对象抽取 `1c815e6` 的完整归档，在临时目录运行该冻结版本 `validateBatch`，结果 `allowed=true`、错误与警告均为空；同版本 `collect.loadState` 能读取全部 2,344 项。没有用当前工作区修改后的代码替代冻结实现复算。

- manifest 列出的 42 个产物逐项重算 SHA256，匹配 42/42；产物总字节为 18,142,801。
- projects、evidence、recommendations、pending-candidates、observation-reports 和 manifest 的 schema、规则、推荐版本、批次、生成时间与 source_commit 全部一致，分别为 `4.0 / v3.3 / v4.0` 及上方运行身份。
- site-state 保持其精简契约，仅承载 `schema_version`、`batch_id`、收藏别名；schema / batch 与页面一致。history、summaries 和 detail-index 保持字典结构，内容由 manifest 哈希绑定，不宣称它们自行携带所有版本字段。
- 首页、场景和抽查的 LocalSend 详情 HTML 内批次一致；全部生成文件的字节均已经过上面的哈希验证。
- 自动提交没有修改 `data/curation.json` 或 `data/seed-evidence.json`，与输入提交字节相同。
- summaries 文件发生了格式变化，但解析后的字典与输入完全相等，未把本轮网络采集替换成人工摘要改写。

## 产物大小与静态页面性能

以下大小从固定 Git blob 计数；gzip 为本地标准 gzip 结果，不是实际服务器传输量。Node 测量在本机进程对相同 UTF-8 文本执行 9 次 `JSON.parse`，取中位数，不能替代移动浏览器或受限网络测试。

| 产物 | 原始字节 | 本地 gzip 字节 |
|---|---:|---:|
| index.html | 52,609 | 10,100 |
| scenes.html | 70,508 | 12,258 |
| LocalSend 详情 HTML | 5,838 | 2,796 |
| site.js | 8,974 | 2,858 |
| site.css | 16,963 | 4,592 |
| data/site-state.json | 103 | 109 |
| data/projects.json | 11,986,812 | 1,350,785 |
| data/evidence.json | 2,895,823 | 654,501 |
| data/recommendations.json | 1,702,591 | 107,834 |
| data/detail-index.json | 532,774 | 117,906 |
| data/observation-reports.json | 468,956 | 110,225 |

冻结 `assets/site.js:42` 的批次检查会下载并解析整个 projects.json；页面筛选与收藏实际基于静态卡片和内嵌状态，不消费这份候选内容。测得本机 Node 解析候选文件中位数 13.19ms、最大 16.18ms，site-state 中位数约 0.00042ms。网络额外流量和移动设备解析成本未做浏览器实测，不能从本机解析时间推断真实首屏时长。

静态 HTML 已预渲染，异步批次检查不是阅读正文的前置依赖，因此**本次没有证据证明静态首屏被阻断**；但为一条状态提示强制下载近 12MB 原始 JSON 是明确且可避免的资源浪费。最小修法是该检查只读取既有 site-state.json，并把文案改成“发布状态批次”，不能继续声称验证了 projects 文件的实际批次或字节。完整 explore 页面仍需 candidates 数据，近 12MB 文件是另一个仍保留的体验限制。

核验报告时，工作区 `web/assets/site.js` 已出现上述最小修复和“发布状态”文案；它没有进入被冻结的 `1c815e6`，生成目录 `assets/site.js` 与 manifest 保留原批次。因此首次运行的性能问题仍如上记录，修复的实际部署效果须由下一批生成产物验证。此报告未修改实现或旧批次哈希。

## 验收边界与证据记录

- 本次仅是开发分支一次真实工程运行成功；名称迁移关联问题尚未通过，不能表述为全部工程边界无缺陷。
- 本次为手动触发，观察报告也记录 `run_kind=workflow_dispatch`、`planned_run=false`。它对“14 天至少 13 天计划任务成功”贡献 **0 天**，不替代未来独立参考集、48 小时发现窗口或真实 Pages 发布后的观察起点。
- [首次冻结盲评](final-review.md)中六类内有明确用途资料的 28 项全部未知，范围内未知率 100%，仍然失败；工程运行成功、20 个 fresh 推荐不能抵销该失败。
- 未完成真实读者任务和规定持续发现观察，不能宣称 V4 整体通过。未在本报告中评价 main 线上发布效果。

只读 API 导出证据位于本次本地临时目录 `/tmp/gitradar-v4-actions-engineering`，报告保存关键身份与以下摘要以便核对；临时文件本身没有加入仓库，也没有记录凭据。

| 证据 | SHA256 |
|---|---|
| run.json | `04a5934cfdb588da8cd5a3e408cb5246890485933193f1fde33b0da5c36267b0` |
| jobs.json | `e8cb7ee3fbaa129ae4d37421e7926342fe69da115ba790205abb065369404a09` |
| 冻结校验与迁移回放 frozen-validation.json | `b7843d86c8b9d9bdac31c9cc24ccf4905bf165984508be30bd03bf3be5848641` |

复核方法：`git show 03895d3:data/history.json` 与 `git show 1c815e6:data/history.json` 做逐键比较；对 `git archive 1c815e6` 临时归档执行其自带 `validateBatch`；对 manifest 每项使用 `sha256(git show 1c815e6:<path>)` 验证；对相同 Git blob 执行本地字节计数、gzip 和 JSON.parse 测量。以上过程只读取正式产物。
