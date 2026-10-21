# 新增计数与新内容池优先级独立复核

结论：本次限定改动通过，未发现阻断问题。独立 AI 只读审查；未修改生产代码、data、seed、curation 或第三次工程运行原报告，未联网，未读取私有盲组或新模型输出。

## 计数口径

`collectionStats` 保留四参数签名和 `newly_discovered_count` 输出字段。当前项目使用 `(history_key or full_name).lower()`，两个正式调用方也向第三参数传同口径的旧集合。旧格式缺少或为空的主键回退到名称；大小写重复只计一次，不因名称相近而合并。

兼容边界需要明确：第三参数仍名为 `previousNames`，但有主历史键的调用方必须传主键，不能继续传改名后的显示名。仓内全部正式调用方（V4 `_prepare` 与 legacyMain）已同步。该统计函数信任观测层已验证的主键，不自行验证 stable ID、不使用 `history_aliases` 推断身份，也不把保留观测误当新增。

独立从 Git 对象读取 `fc7436b` 与 `83ba30c` 回放：名称差为 892，主历史键差为 **890**。两个差额均是已验证的改名。原 `83ba30c` 产物仍记录 892；本次没有改写它或历史运行报告。首次初始化、已知改名、空/缺失主键、大小写重复及相似名称保持独立的反例均通过。

## 排序范围与公平性

改动仅作用于 automatic 且没有已有 refs 的 new 池，排序依次为尝试时间、既有发现分倒序、首次观测时间、名称。没有新增评分算法。只接受原生 int 和有限 float；缺失、None、bool、字符串、NaN、正负无穷及其他类型回退为 0，不尝试转换字符串。超大整数安全排序，负有限分保持其原值。

尝试时间仍是第一优先级，因此高分重试不会越过从未尝试或更早尝试的候选；同分再以首次观测和名称确定顺序。这里没有新增“所有低分候选在固定周期内一定轮到”的保证：持续出现未尝试的高分候选仍可能延后低分项目，这与指定排序一致。

due、recommended、review、rotation、refill 的原排序和额度未改，总计划上限仍为 20，内容/REST 预算执行处未改。新池选择变化后，其他池通过原去重规则避开已选项目，不能要求有交集时它们的最终名单绝对不变。

固定第三批候选、运行前 evidence/feed 及批次起点离线回放时，旧函数完整计划与 `83ba30c` 保存的计划一致。新函数仍为 due 0 / recommended 8 / new 6 / review 4 / rotation 2 / refill 0，前 8 个推荐槽顺序不变，new 六个既有分数依次为 448.6、423.9、322.1、321.8、306.0、288.6。没有 new 候选的独立构造中，新旧函数所有池的完整结果一致。提高资料核对优先级不会赋予推荐资格。

## 验证与指纹

- 本评审重跑 `test_discovery_stats.py`：13 项通过；`test_v4_pipeline.py`：28 项通过，没有重复全套测试。
- 额外独立反例覆盖数值异常、安全整数范围、尝试优先于分数、同分首次观测/名称、输入顺序反转及输入对象序列化字节不变。
- 独立脚本与结果保留在 `/tmp/gitradar-discovery-priority-independent.py`、`/tmp/gitradar-discovery-priority-independent-result.json`；只读 Git 对象与本地数据，不运行采集网络路径。

| 审查文件 | SHA256 |
|---|---|
| `discovery_stats.py` | `27c07ce85603b452b47e7aaffc19901c75a82f7c926f0d7e144880f2b851b95c` |
| `collect.py` | `7ffd7121d9a964ffc8f1ceacdba195f32b93906ea2f488777e2a55534e44ed52` |
| `gitradar/pipeline.py` | `4393e50fce6a92ef29eabcc1ad1edb777fc5b0470c13fa3abcb91d5da4182f50` |
| `tests/test_discovery_stats.py` | `5e1a7638d52e5df01a30e99ac5020e92b93a417c6ebd5059c91ce9a049c73944` |
| `tests/test_v4_pipeline.py` | `53e18d28ec9c113bb65f4e17ea12922bb2632a328b66eb6e4ac8a978104018cf` |
