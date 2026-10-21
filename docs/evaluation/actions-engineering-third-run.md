# 第三次真实工程运行独立核验

[Actions 39524153820](https://github.com/w452187971/gitradar/actions/runs/39524153820) 在开发分支 `codex/gitradar-v4` 手动运行成功。输入代码为 `61aca582ba85e3b5e2711e770beb376139d6b9c8`，普通 bot 提交为 `83ba30c12ae7dbea095af7a25c8fa3c21283db65`，其唯一父提交与输入代码一致。测试、隔离采集校验、提升和提交步骤均成功；模型诊断步骤跳过。本报告为独立 AI 只读工程核验，不是模型语义或真人读者评估。

运行于 UTC 2026-10-21 00:54:40 开始，最终批次时间 `2026-10-21T01:00:28.698358Z`，bot 于 01:00:32 提交，任务于 01:00:40 完成。批次 ID 为 `217947df35da48d29457f9938c5434cc`。

## 通过的工程检查

- 以 `fc7436b18e9f0a8310fb0776da1ef7dd19f9e7cf` 为旧数据基线，2,562 个历史键及其 2,562 个点全部保留，旧值无任何改写。该基线实际只有 10 月 20 日数据，没有更早日期；核验遍历了全部旧键/日期，而非只抽查当日。
- 当前 3,451 个候选中，3,449 个取得本批成功观测，2 个为 NOT_FOUND/REST 404。新增的 3,449 个历史点全部在 10 月 21 日，逐点对应 fresh 候选主历史键与本批 Star 数；所有 fresh 的 `last_observed_at` 均在 21 日且不晚于最终批次时间。两条 404 的旧历史原样保留，没有新增当日点。
- 现有 3,452 个历史键。按主历史键独立计算新增候选 890；`collection_stats.newly_discovered_count=892` 使用名称口径，包含两次改名，不能当作 892 个新身份或合格发现。
- 独立重算得到 28 个 eligible 内容，20 个推荐均来自本批 fresh 候选，且通过当前全部资格门槛。推荐统计为 20 次轮换、0 个 `automatic_new`，没有把新增候选数当作自动新增推荐数。
- 遍历 evidence 与推荐中的来源检查时间共 1,959 处（包括重复引用），没有未来或无效时间。最晚检查时间 `2026-10-21T01:00:28.697277Z` 早于最终批次时间。此前将开始时间当成最终验收时间的问题在本次产物中未重现。
- 42 个 manifest 产物全部从固定 bot Git 对象提取至 `/tmp/gitradar-engineering-third-review/snapshot`，逐文件 SHA256 一致。用旧批次与新快照重跑 `validateBatch`，`allowed=true`，errors/warnings 均为空。bot 改动 39 个文件，均在 manifest 或 manifest 本身范围内。
- seed-evidence、curation 与运行输入提交逐字节一致；本评审未更改它们、history 或生产数据，也未 pull。fetch 后由主代理自行快进工作树，不影响此处固定 Git 对象的核验。

## 改名与历史连续性

| 显示名称 | 保留的主历史键 | 本轮核验 |
|---|---|---|
| `Salesflare/TheMachine` | `JeroenCorthout/TheMachine` | 既有迁移保持稳定；主键追加 21 日点，冗余 `Salesflare/TheMachine` 历史只有原 20 日点，完全未改 |
| `duxlabs-dev/dux-shell` | `AvengeMedia/DankMaterialShell` | 本轮新改名；stable node ID、created_at 与旧候选相同，保留旧主键和收藏别名；未创建新名字历史 |
| `Timeregainedme/DyeingTime` | `Timeregainedme/ChangeAT` | 本轮新改名；stable node ID、created_at 与旧候选相同，保留旧主键和收藏别名；未创建新名字历史 |

两条 NOT_FOUND 分别为 `AndreSzymanski15/ai-jailbreaks`、`YuJunZhiXue/dsh-purge`，产物同时保留 GraphQL NOT_FOUND 与 REST 404 诊断。没有把身份检查失败转换成零 Star 或旧值的新日期观测。

## 修复绑定与仍未验证的部分

八个受损种子项目的 14 个修复绑定，其 text、content_hash 均继续与原 seed 一致，身份不变，source_hash 与修复后输入一致；八个项目当前均满足资格门槛。

但这 14 条的 `checked_at` 全部仍为 10 月 20 日独立取证时间，本轮内容分配没有选择这些项目。**本次证明修复绑定未被破坏，不能证明真实 collector 已重新请求并正确处理这六个 `/license` 端点。** 本轮新日期仅有 Star 观测成功，不意味着所有内容来源都刷新过。该真实来源刷新路径仍需后续覆盖，不能用绿色 Actions 或 28 个 eligible 抹平这个限制。

内容预算计划选择 20 个项目，实际尝试 18 个，使用全部 60 次内容请求，10 个完整成功、8 个部分成功、0 个完全失败；其余候选继续等待内容复核，pending 新候选队列本轮为 0。这不证明全部候选已得到用途、平台或安装路径解释。

API 实际消耗为：搜索 20 次，REST 82 次（内容 60、路径 20、身份补查 2），GraphQL 70 点/70 批；未计量 GraphQL 请求 0、重试 0、304 为 0，未触发限流。各项均在固定预算内。本次是手动开发分支工程运行，不计为连续定时运行验收，也没有完成自动中文解读、未见盲评、真人任务或持续发现效果验收。

## 可复核指纹

小型逐项核验结果见 [actions-engineering-third-run-checks.json](actions-engineering-third-run-checks.json)，SHA256：`72f9c8224a7121fbc6c4cdb29af76406cd18f7873c4aceda36fac0f3521ef92b`。

| 产物 | SHA256 |
|---|---|
| `build-manifest.json` | `787725a8e9349c4c415d3d87f0cfc8bcc576683ed9cd90b43592e7c6bab409b4` |
| `data/history.json` | `46a46d699014def7286a38bda729500dc70dde38463212771226aa68f18b8f31` |
| `data/projects.json` | `3fe79549262b1aed381ccc8986df50f5b30531814e5358d71c7dceec1ecee361` |
| `data/evidence.json` | `3d77dde26795ac7488c830dfb862a4e1fb7ff144c1ddfbf4b012f4198c10f990` |
| `data/recommendations.json` | `7be33a1694334d59f880dcbd8f17c5391c092ee4525cee5d3234a2320a21187d` |

本次未读取第二盲组 inputs/labels，未读取新模型输出。所有运行状态请求只输出公开的 compact 字段；凭据仅由既有授权 helper 在内存中使用。
