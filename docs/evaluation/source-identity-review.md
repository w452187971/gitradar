# 已确认来源身份冲突独立复审

结论：**来源 API 明确返回另一稳定身份时，现在会立即阻止旧内容进入推荐；普通网络失败的保守沿用保持不变。** 身份标记、证据保留、缓存认证范围与输入不可变性均已独立复测，没有剩余阻断项。本报告不代表观察到真实仓库发生换主，只记录基于真实 seed 的合成竞态。

## 首次根因复现

复制现有 HandBrake seed 与 curation，在 `2026-10-20T16:00:00Z` 原内容为 published、eligible=true。令已绑定的元数据请求首先执行，再合成 HTTP 200 返回另一 `node_id`。此前虽然记录 identity changed，错误只作为普通 ValueError 处理；旧证据保持 200 和旧日期，fetched/merged/facts 都没有 identity_conflict，旧内容仍 eligible=true。

这与超时不同：超时只意味着本次没核实，明确的另一稳定 ID 则已经否定来源身份一致性。不能在已有反证后继续把旧内容当作同一项目推荐。

## 修复后独立复测

| 合成情形 | 最终观察 |
| --- | --- |
| 预期和实际均为非空字符串 ID，且明确不同 | typed EvidenceIdentityError 传播 identity_conflict，内容 blocked，eligible=false |
| OSError 网络失败 | 不新造身份冲突，旧有效期内内容可沿用 |
| 普通 ValueError 的文字恰好为 identity changed | 不按错误文本判定冲突 |
| 元数据缺少 ID、空 ID 或非字符串 ID | 未确认为另一身份，不新造 identity_conflict |
| 同批先明确冲突、稍后又成功 | 冲突仍优先，整批不刷新旧内容证据 |
| 冲突后只遇到 timeout 或后续同 ID 成功 | 标记保持 sticky，不自动恢复推荐 |
| 冲突响应带 ETag | 返回缓存保留实际 ID，并只存公开产品事实白名单 |
| 对旧预期 ID 再请求，服务却返回 304 | 不发送错误 identity 的 If-None-Match，拒绝复用不匹配缓存 |

独立复现确认：原输入未被修改，旧 refs 的 checked_at 与 content_hash 保持，历史正文没有被另一仓库响应覆盖。merge 将已有 unknowns 与新冲突取并集；编辑资料中的空 unknowns 不能抹掉机器确认的冲突。既有 context_changed 保护也不因身份标记而消失。

另发现并关闭缓存浅复制问题：认证范围正确的同身份 HTTP 304 会返回旧 cache body，随后白名单处理原先会修改调用者 previous.cache 的共享 entry。最小修复改为 deep copy。最终独立复测确认 previous 与调用前完全相同，返回缓存已清洗，嵌套 entry 不再共享。

## 验证与保留限制

来源/内容/证据/流水线/来源归一化的 **117 项重点测试独立通过**。缓存不可变性修复后，新增认证 304 回归与四项身份边界测试再次独立通过；合成复现同时确认返回缓存清洗及 previous 不变。`git diff --check` 通过。整仓完整测试由协调者另行运行，本报告不把作者或协调者的测试数量算作独立执行结果。

没有调用网络、修改生产代码、正式 data 或暂存区。此审查仅新增报告。冲突解除仍要求独立复核；后续同 ID 成功暂不会自动清除 sticky 标记，这是保守恢复边界，不能描述成已经实现自动恢复。

最终复审 SHA256：

- `gitradar/github_client.py`：`82ab2d76f2069d752ded011986a0910904e77653cc361008df897a0c919f73d4`
- `gitradar/evidence.py`：`d4f2f6911dfb2d912802afdcb0d488829c25189a2175b09834ffefb2efc2667f`
- `gitradar/content.py`：`91291a1cc51263640dd9a0cbbcb27688673eca74a0a512839b6c6dc596825385`
