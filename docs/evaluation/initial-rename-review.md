# 无稳定 ID 的首次改名迁移复核

限定修复及离线贯通回放通过；尚未用修复后的代码完成下一轮真实 GitHub 观测。本报告不把测试中的传输夹具计作真实 API 成功，也不改写首次 Actions 运行的记录。

## 问题与证据边界

首次真实运行 [39454254516](https://github.com/w452187971/gitradar/actions/runs/39454254516) 的自动提交为 `1c815e6e5d1a77449cdda3b5f383d5d8bd3fe24f`。冻结产物同时存在：

- `JeroenCorthout/TheMachine`：无 `node_id`，创建时间 `2026-10-15T20:40:05Z`，原历史保留，但为 deferred。
- `Salesflare/TheMachine`：`node_id=R_kgDOVLdUZA`，同创建时间，fresh Star=10，另建历史键。

原始 GraphQL 响应没有归档，不能仅根据名称、描述或创建时间相似就断言转移关系。缺陷复现使用明确的请求关联：真正的 `GitHubClient.fetchObservations` 查询旧入口，传输夹具按 GitHub GraphQL 结构返回新名称，再调用真正的 `applyObservations`。修复前，旧记录保留，另新建一条候选；提供显式原 `history_key` 时也无法迁移。

## 关联契约

不引入 `requested_full_name`。客户端始终将 `Observation.history_key` 初始化为输入 `ref.history_key`，缺省时为本次请求的 `ref.full_name`。它继续表示原追踪键；`Observation.full_name` 仍表示 GitHub 返回的当前显示名，含义不变。

观测应用先按原追踪键寻找既有记录，再验证稳定 ID。旧记录首次绑定 ID 时，必须有相同的已保存 `created_at`；缺失或不一致进入 `identity_conflict`，不追加旧历史、不比较增量、不建立收藏别名。描述相同不参与判断。

主要消费者仍为观测应用、首次新候选建档及兼容导出。没有新增请求数，没有为了该修复引入身份 REST 补查。

## 已有双记录的消解条件

只有同时满足以下条件，才合并显示记录：

1. 旧记录尚无稳定 ID；同批对其原追踪键的成功请求返回新名称、稳定 ID，创建时间与旧记录一致。
2. 已有新名称记录保存同一稳定 ID、同一创建时间。
3. 同批针对新记录自身追踪键的成功请求，也返回相同稳定 ID、创建时间及当前名称。
4. 对应身份没有多个无 ID 旧记录争抢，也没有矛盾的成功结果。

归并在应用当日观测之前完成，候选记录顺序和请求顺序均不影响结果。任何时间不匹配、目标请求失败或身份矛盾均不合并；不能靠名称、描述或创建时间的相似性消解。

输出保持原历史为主键：

```json
{
  "full_name": "Salesflare/TheMachine",
  "node_id": "R_kgDOVLdUZA",
  "history_key": "JeroenCorthout/TheMachine",
  "history_aliases": ["Salesflare/TheMachine"],
  "observation_status": "fresh"
}
```

`saved_aliases` 增加 `JeroenCorthout/TheMachine → Salesflare/TheMachine`。`history_aliases` 仅记录保留下来的冗余历史键：两个系列及其全部原日期、数值均保留，绝不把冗余系列搬入、覆盖或拼接到主系列；本轮 fresh 只写原主键，冗余历史键不成为当日写入端点。

验证层单独核对归并声明：主键必须对应原候选且创建时间一致、原稳定 ID 缺失或相同；冗余键必须已有历史，其原候选的稳定 ID、创建时间必须一致。后续批次可延续已确认的同主键、同 ID 别名。未知键、重复别名、占用另一主键、身份或创建时间不符均拒绝；历史保留校验不因归并放松。

## TDD 与冻结输入回放

先观察失败，再实施最小修复：初始迁移三个贯通用例失败；已有双记录的两种记录顺序与两种请求顺序组合共四个子例失败。修复后上述用例通过，时间不符及目标未成功的反例仍保持隔离。

从 `git show 1c815e6:data/projects.json`、`history.json` 只读抽取实际双记录，以冻结新记录的元数据构造**明确标注的离线响应夹具**，经过真实客户端解析与观测应用，两种请求顺序均得到：

- 输入 2 条候选，输出 1 条，主历史键为旧入口，冗余键列入 `history_aliases`。
- 两个原历史系列的每个原日期和数值均保留；冗余系列没有新增模拟当日端点。
- 旧收藏别名恢复；输入对象不被修改。
- 不访问网络、不获取凭据、不写生产数据。

冻结 `projects.json` SHA256：`a5dd5b7bea91ec326af1c94a0cad9239d1c6fecf94e691d7ea5aadb4116aa5e5`。

## 验证命令

- `python3 -m unittest discover -s tests -p test_v4_observations.py`：16 项通过。
- `python3 -m unittest discover -s tests -p test_v4_client.py`：34 项通过。
- `python3 -m unittest discover -s tests`：265 项通过（含验证层 17 项）。
- `node --test tests/*.cjs`：75 项通过。

此前并发中的验证层新增用例曾按预期因 `candidate_lost:new/tool` 失败；验证层完成严格归并兼容后，以上完整回归通过。

真实迁移成功仍须由后续 Actions 产物证明：只有实际响应再次满足上述身份条件，才会消解既有双记录；旧入口不存在或身份不符时应保留隔离，不能伪造网络成功。

## 后续独立复核与网络检查

独立审查发现目标持有的已确认历史别名在归并后被校验误拒绝；已保留首次发现并按同 ID、同创建时间限定兼容其继承。补回归先失败后通过。最终完整 Python 266 项、Node 75 项通过；独立跨组件复验见 [独立审查](initial-rename-independent-review.md)。

2026-10-20 16:29 UTC，本机真实 GraphQL 尝试遇 SSL EOF，两项均失败，旧记录及历史保持不变；这不是迁移成功。随后 16:31 UTC 独立只读 REST 检查旧、新两个入口，均返回 `Salesflare/TheMachine`、相同 `R_kgDOVLdUZA` 和创建时间 `2026-10-15T20:40:05Z`，证实这两个公开入口目前解析到同一仓库。原始精简结果保存在 [网络检查](initial-rename-network-check/rest-identity.json)，失败观测保存在 [失败回放](initial-rename-network-check/report.json)。该 REST 旁证没有写入正式快照，也不替代修复后完整 Actions 采集。
