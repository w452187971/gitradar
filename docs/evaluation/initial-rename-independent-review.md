# 首次无稳定 ID 改名的独立限定审查

审查日期：2026-10-21（Asia/Shanghai）。只读检查客户端请求关联、观测合并、历史别名与发布校验；未改实现、未发网络请求、未提交，也未改首次盲评或 CPU 探针结论。范围为末尾六个文件及 [实现报告](initial-rename-review.md)。

## 结论

**限定审查通过，无未关闭阻断。** 核心双候选修复及历史只读约束通过。首次审查发现的 P2（目标已有确认历史别名时，合法合并被校验器误拒绝）已由协调者修复，独立重跑原始反例通过。未发现修复放宽同名重建或创建时间不符的隔离。

## 通过

独立执行 `PYTHONPATH=tests:. python3 -m unittest test_v4_observations test_v4_validation -q`，首轮 33 项通过，补充修复后 34 项通过（观测 16、校验 18）。另在临时目录写最小跨组件回放，使用真实 `GitHubClient.fetchObservations → applyObservations → validateBatch`，仅传输响应为离线夹具，不将其计作真实 GitHub 成功。

- `parseNode` 始终记录输入 ref 的原追踪键，缺省采用请求时的 full_name；当前显示名仍来自响应。应用先按原主历史键关联，再验证稳定 ID 与 created_at。
- 无 ID 旧候选与已有稳定 ID 新候选，必须有同批两端成功响应，node ID、created_at 和当前名称相符后才归并。目标唯一性和争抢计数保守拒绝歧义，记录顺序与请求顺序的四个组合均通过。
- 合并输出保留旧主 history_key、保存新记录的冗余历史键、维持旧收藏到新名称的关联；原输入不变。冗余历史不拼接或覆盖到主系列。
- 独立修改旧响应 created_at、新响应 created_at 或新响应 node_id：三种反例均保留两候选，旧主历史原样，无新收藏别名。现有测试还覆盖新目标未成功、同描述不同创建时间。
- 正常合并进入 `validateBatch` 得到 allowed=true。分别对冗余历史新增当日值、改写旧值、删除日期、删除整个历史键，四种反例全部拒绝：新增报 `unobserved_history`，其余报 `history_changed`。
- alias 只参与候选连续性与合法来源核对。fresh 可写集合仍仅使用主 history_key；alias 不成为可写端点。不存在的别名、重复别名、占另一主键、创建时间或 ID 不符的声明均被拒绝。

## 已关闭 P2：反例、根因与复核

在正常双记录输入基础上，令已绑定稳定 ID 的新候选额外持有 `history_aliases=['ancestor/tool']`，并保留该键旧历史 `{'2026-10-19': 8}`。这表达该候选在之前批次已经确认的冗余历史。

本批旧入口、新入口响应均成功且返回相同 ID、相同 created_at 和新名称。`mergeInitialRename` 正确保留 `ancestor/tool` 历史，并输出 `[新候选原主键, 'ancestor/tool']`；随后 `validateBatch` 返回：

```json
{"allowed": false, "errors": ["invalid_history_alias:ancestor/tool"]}
```

`_validHistoryAlias` 只允许旧主候选本身已有的别名，或某个旧候选的直接主历史键；它未接受从本次被合并的同 ID、同创建时间目标继承的已确认别名。因此实现层承诺保留的传递别名被验证层误拒绝。

协调者已限定兼容此前同 ID、同 created_at 目标持有的确认别名，保持历史存在、唯一性、主键冲突检查及只允许主键 fresh 写入的边界。独立重跑同一反例得到 allowed=true，冗余历史完全保留。另对继承别名分别新增今日值、删整个系列、改变其原持有者 node_id、改变其原持有者 created_at，四种反例仍全部拒绝。审查者未实施生产修改。临时复现脚本为 `/tmp/gitradar-initial-rename-independent.py`，结果为 `/tmp/gitradar-initial-rename-independent-results.json`；本报告已记录完整触发条件，不依赖临时文件永久存在。

## 未验证与范围

审查者未进行真实 GitHub 采集。已阅读协调者的 `/tmp/gitradar-initial-rename-network-check/report.json`：时间 `2026-10-20T16:29:46Z`，单次 GraphQL 请求遇到 SSL EOF，两条观测均 failed，保留两记录、全部历史不变、收藏别名为空。该失败回放通过发布校验，只证明失败不破坏旧数据，不能证明真实迁移。真实旧入口是否仍能成功解析，必须由后续 Actions 响应与产物证明；不能凭名称、描述或创建时间相似认定转移。未重新评价模型探针或首页请求大小优化，也未重新评分首次 40 个未见样本。

## 首次审查文件快照

```text
ece6ae3d970e4bf57f593964b88b563812855eea53dba7ef4e965c0241352a8d  gitradar/github_client.py
97b15fa07cc5c8970d3fa5bd267dae1475f48a1f9f2d81564af0ca26431c5a5d  gitradar/observations.py
31073f2136ded4789e5b743bb7a2dcc62801fa7f6590770ba8145cb15433595b  gitradar/models.py
4728613d67a0aa37f2f804e13363587bf9eda50a4282260715a1fdee30098da7  gitradar/validation.py
4c313ce3b75b4f2fc6645a4ac389bb125df528993eab49b98f78f06d85ac6800  tests/test_v4_observations.py
cea70ce59762684a8d2da018ff9d6f592f24148067c73170cfbb3a1b935e6302  tests/test_v4_validation.py
```

## P2 修复后最终审查文件快照

```text
ece6ae3d970e4bf57f593964b88b563812855eea53dba7ef4e965c0241352a8d  gitradar/github_client.py
97b15fa07cc5c8970d3fa5bd267dae1475f48a1f9f2d81564af0ca26431c5a5d  gitradar/observations.py
31073f2136ded4789e5b743bb7a2dcc62801fa7f6590770ba8145cb15433595b  gitradar/models.py
4728613d67a0aa37f2f804e13363587bf9eda50a4282260715a1fdee30098da7  gitradar/validation.py
4c313ce3b75b4f2fc6645a4ac389bb125df528993eab49b98f78f06d85ac6800  tests/test_v4_observations.py
cea70ce59762684a8d2da018ff9d6f592f24148067c73170cfbb3a1b935e6302  tests/test_v4_validation.py
```
