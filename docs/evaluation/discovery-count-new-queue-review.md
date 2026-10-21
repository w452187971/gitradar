# 第三批新增计数与新内容队列修正

固定快照离线回放确认：本批新增候选为 **890**，原按名称计数的 892 包含 2 次同身份改名。生产 `data` 保留第三批原始结果；新口径在后续正式批次生成时生效。本次没有网络请求、重新采集或修改历史数据。

## 计数边界

- 基线：`fc7436b18e9f0a8310fb0776da1ef7dd19f9e7cf`，2561 个候选。
- 第三批：`83ba30c12ae7dbea095af7a25c8fa3c21283db65`，3451 个候选。
- 执行代码父提交：`61aca582ba85e3b5e2711e770beb376139d6b9c8`；其 `projects.json` 与上述基线逐字节相同。
- `AvengeMedia/DankMaterialShell → duxlabs-dev/dux-shell`，稳定 ID `R_kgDOPKVP_Q`。
- `Timeregainedme/ChangeAT → Timeregainedme/DyeingTime`，稳定 ID `R_kgDOVHfbwQ`。

`collectionStats` 保留四参数签名及输出字段，仅用观测层已经核对的主 `history_key` 做大小写归一后的集合差；旧格式回退 `full_name`。V4 pipeline 和 legacyMain 的 previous 集合同步采用该规则。不自行凭名称相似、描述或创建时间归并；不把 `history_aliases` 冗余历史键算作候选。`retained_count` 原本按显式观测状态计数，与名称无关，保持原义。前端继续读取同一 `newly_discovered_count`，无需接口或文案迁移。

## 仅 new 池排序

排序键为 `(last_attempt_at, -discovery_score, first_observed_at, full_name)`；只接受 int 与有限 float，缺失、None、NaN、无穷、字符串、bool 明确回退 0。不转换字符串，不吞异常；不修改输入和既有分数算法。尝试时间保持第一优先级，避免高分重试插队；同分使用首次观测时间与名称保证确定顺序。

以固定批次起点 `2026-10-21T00:54:51.434047Z`、第三批候选和执行前 evidence/feed 调用真实 `scheduleContent`：旧函数的完整计划与第三批保存计划一致；新函数实际配额仍为 due 0 / recommended 8 / new 6 / review 4 / rotation 2 / refill 0，前 8 个推荐槽顺序不变。new 的 6 个槽变为：

| 候选 | 既有发现分 |
| --- | ---: |
| dominikmartn/harp | 448.6 |
| zhuyansen/new-term-radar | 423.9 |
| withmarbleapp/os-taxonomy | 322.1 |
| mw00/project-maya | 321.8 |
| UniXNU/UniXNU | 306.0 |
| AjncSystem/ShadowOfTheColossus-PC | 288.6 |

这些仅获得资料核对优先级，未因此获得推荐资格。其余池仍沿用原排序；轮换/补位可能因已选集合不同而自然避开新池已选项目。

## 验证证据

先 RED：统计文件 13 项中出现 3 个预期失败子例（改名分别误计 1、主键去重误计 5）；pipeline 文件 28 项中 3 个排序回归失败。最小实现后分别 13/13、28/28 通过。

- `python3 -m unittest discover -s tests`：325 项通过。
- `node --test tests/*.test.cjs`：75 项通过。
- 固定快照回放：名称差 892、主历史键差 890；新队列结果与上表一致；实际配额与原批次一致。结构化结果见同目录 `discovery-count-new-queue-replay.json`。

可用以下纯离线调用复核关键结果（在仓库根目录）：

```python
import json, subprocess
from discovery_stats import collectionStats
from gitradar.pipeline import scheduleContent

def read(commit, path):
    return json.loads(subprocess.check_output(['git', 'show', f'{commit}:{path}']))

old = read('fc7436b', 'data/projects.json')
new = read('83ba30c', 'data/projects.json')
known = {(p.get('history_key') or p['full_name']).lower() for p in old['projects']}
assert collectionStats(new['projects'], {}, known, [])['newly_discovered_count'] == 890
selected, report = scheduleContent(
    new['projects'], read('61aca58', 'data/evidence.json'),
    read('61aca58', 'data/recommendations.json'), '2026-10-21T00:54:51.434047Z')
assert report['actual'] == {'due': 0, 'recommended': 8, 'new': 6,
                            'review': 4, 'rotation': 2, 'refill': 0}
print([(p['full_name'], p['discovery_score']) for p in selected[8:14]])
```
