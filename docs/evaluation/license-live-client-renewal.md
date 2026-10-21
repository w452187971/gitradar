# 六项目许可证真实生产客户端续期验证

结论：六份 `/license` 均真实返回 200，并由当前生产 `GitHubClient.readProjectEvidence` → `mergeEvidence` 在隔离副本中成功续期。原许可证片段、`content_hash` 和完整许可证 `source_hash` 均保持一致。六项目合并结果中，FreeTube 的发布页上下文哈希发生变化，生产规则保留 `context_changed:path` 并撤回其推荐资格；其余五项目资格计算通过。**没有将隔离结果写回生产数据。**

本报告由独立 AI 代理执行与审核，不是真人读者评估。代码基线为 `2129ce7b17105c85584436ac34bef7bccf158ff4`；输入数据与四个相关生产模块的逐文件 SHA256 见 [核验 JSON](license-live-client-renewal-checks.json)。

## 实际请求与隔离边界

- 实际 UTC 时间：`2026-10-21T01:22:31.601534Z` 至 `2026-10-21T01:23:06.724896Z`。没有伪造检查时间。
- 发请求前离线枚举 `boundSourceRequests + defaultSources`：共 25 个端点，分别为六份 README、六份仓库 metadata、六份 `/license`、六个官方网页，以及 WinMerge 的 `Src/Merge.cpp`。本次没有需要补齐的默认来源。
- `Budget` 中 REST/content 均为 25，`max_retries=0`，Search、GraphQL、HEAD/path、identity 预算均为零。最终 REST/content 各记 25，实际 HTTP 打开次数 25；全部返回 200，无重试、304、限流或未完成端点。余量 4973。
- 通过现有 ignored helper 在内存取得认证，仅生产客户端向 `api.github.com` 附带认证。六个官方网页均使用生产无认证请求。未输出请求头、凭据或凭据派生的 `auth_scope`，归档副本移除了后者。
- 使用未修改的生产 HTTP 解析与同源重定向策略；只在当前审查进程外包记录器，额外限制实际 HTTP 打开总数为 25，若重定向发生也计入。此次没有重定向或额外网络补取。旁路保存解析前的完整响应体，不改变返回值和事实解释。
- 完整输入在内存深拷贝，持久化隔离副本仅保留六项目相关 evidence。生产 evidence、seed、curation、history、projects 与相关代码执行前后哈希一致。原 facts 与编辑结论未修改，未提交。

## 许可证与绑定核验

| 项目 | `/license` 续期后的 `checked_at`（UTC） | 该项目核验的绑定数 | 合并后资格 |
|---|---|---:|---|
| FreeTubeApp/FreeTube | 2026-10-21T01:22:37.818249Z | 6 | 撤回：发布页上下文变化 |
| KDE/kdenlive | 2026-10-21T01:22:43.384903Z | 6 | 通过 |
| WinMerge/winmerge | 2026-10-21T01:22:49.016663Z | 8 | 通过 |
| Zettlr/Zettlr | 2026-10-21T01:22:55.887167Z | 5 | 通过 |
| arsenetar/dupeguru | 2026-10-21T01:23:00.884657Z | 6 | 通过 |
| bleachbit/bleachbit | 2026-10-21T01:23:06.701915Z | 7 | 通过 |

逐条独立核验了 facts/curation 引用的 38 个绑定，其中包含此前八项目恢复取证的 31 个绑定在本次六项目中的全部 **25 个**。其余两个项目的六个绑定不在本次续期范围内。

38 个绑定的原文片段仍在完整来源中，仓库 metadata 则逐字段验证原 JSON 子集；绑定文本、`content_hash` 与 curation 哈希均未变。所有 `source_hash` 都从此次完整响应独立重算一致；每条新的 `checked_at` 晚于该源响应接收时间、晚于旧检查时间，且不晚于实验结束。六份许可证及其他七份文件的 base64 解码全文、Git blob SHA 和 SHA256 均校验通过。所有 facts、critical unknowns 和路径检查字段保持原值。

FreeTube 的 `path` 是唯一发生全文 `source_hash` 变化的绑定。其旧片段仍存在，`content_hash` 未变，但不能据此认为上下文未变；生产合并设置 `context_changed=true`、保留 `previous_source_hash`，资格原因包含 `context_changed:path` 和 `not_published`。本轮未判断网页变化是否具有语义实质，也未清除保护或重新编辑断言。未发现六份许可证正文变化。

网页正文检查时间与下载入口 HEAD 检查时间分开：此次虽然读了网页，仍未发 HEAD，所有 `path_checked_at`、`path_checks`、`path_status` 保持原值。其余五项目的资格通过也依赖此前仍有效的路径检查，不能表述为本轮重新验证了下载入口。

## 原始资料与指纹

完整资料已逐文件核验并持久封存为 [原始资料压缩包](license-live-client-renewal-20261021.tar.gz)（1,044,879 字节，SHA256 `15e6b385730befab162652837afcba6812304a293296d0fa9177068a795f3cfd`），解压后文件字节与原 MANIFEST 一致。工作副本保存在 `/tmp/gitradar-license-live-renewal-xpq6zrtb`，含 25 份完整 HTTP 响应体、13 份解码全文、计划、逐端点时间与状态、前后副本、逐绑定 before/after、核验结果及两份执行脚本。MANIFEST 固定 45 个文件；没有保存授权请求头。HTTP 响应体为生产解析器实际收到的原始字节，不含 HTTP 响应头或 TLS 报文。

采集最初使用系统临时目录 `/var/folders/72/pf18q9rs6x5_gpg6pw6kcqkc0000gn/T/gitradar-license-live-renewal-xpq6zrtb`，结束后逐字节复制到上述 `/tmp` 目录；原报告中的采集路径保留，未改写。

| 文件 | SHA256 |
|---|---|
| 隔离 `report.json` | `9c070892f2ffc70df5298b93640e729d854c481614a584197da8ba08374fe213` |
| 隔离 `before.json` | `fdf10983e25927945b387551a88696721857b8b7fe17100b4260cde52ce72598` |
| 隔离 `after.json` | `bcada5fc99848481be742b419375d92551bc0bfc1b7cb90038f2b00dbcee713b` |
| 隔离 `MANIFEST.json` | `f8cea60fc054e5f3c8c1105c325c87b7bce7d64d98518afcfdc10f2cc6d6d97c` |
| 本报告附带核验 JSON | `41a50a7ec042265af7c85202fd49de0f5fe779eec9bc4341396f566d515b6202` |

这只是人工指定六项目的真实生产客户端续期。它不是正常调度批次、14 天长期采样、全池刷新、安装实测、许可证法律判断或模型效果验收。未读取私有盲组或模型输出，也没有扩大网络范围。
