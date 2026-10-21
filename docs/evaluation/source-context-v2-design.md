# GitHub Release 上下文 v2：设计提案，尚未实施

建议前瞻增加可选的、有版本的断言上下文，不全量迁移 seed。`seed_v1`、片段 `content_hash`、完整可见文本 `source_hash` 及原文审计均保持原义。当前 FreeTube 仍待独立 re-review，已有 sticky 不自动清除。本设计只读本地真实响应与代码，无网络、无生产修改。

**范围比“只保留 Release 正文”更窄。** 真实 `03.body` 有唯一仓库 `nav[aria-label="Repository"]`，其中 `a[data-tab-item="pull-requests"]` 指向同仓 `/FreeTubeApp/FreeTube/pulls`，计数位于 `span[data-component="counter"]`，包括可见12和隐藏的(12)。拟定 `github_release_context_v2`：先验证 HTTPS github.com、仓库身份、精确 releases URL（首版仅无 query 的列表页）、唯一 repo-content 容器、Release 标题/section/tag 身份一致；再仅从该已确认导航链接中排除格式与双份数值一致的计数子树。保留链接标题、其余全文、所有数字和任意正文里的 Pull requests。唯一性、栈闭合、结构或数值不符即解析失败；不能静默回退成“v2未变化”。这是站点结构适配器，不是全局 canonicalization；其他来源完全沿用旧规则。

**上下文必须覆盖文本以外的入口。** v2 的固定序列化输入为：按原 seed_v1 规则提取的上述全文（不裁长度）＋文档顺序的链接目标/文字、表单 action、`include-fragment src` 与 Release section/tag 身份，URL只解析为绝对地址，不删查询或改大小写。版本名、Beta/Pre-release、费用/许可/条件、分页与资产数量都保留。真实页资产为 lazy `expanded_assets/v0.25.3-beta`；仅哈希 src 不能证明资产清单未变。首版遇未完整获取的资产片段应令 v2 不可用于放行；若要支持本页，必须在既有预算内同源获取完整片段并纳入hash，失败/超额则待复核，不能降低为仅凭入口200。独立路径HEAD和身份/许可检查仍分别保留。该额外请求与原始片段的归档是本方案主要成本，不能声称一处计数修复已覆盖资产保护。

**最小字段和链路。** `EvidenceRef` 仅加可选 `source_context={scheme,hash,text}`（text为可重算的完整规范化上下文，只在完整来源ref保存，片段ref携带scheme/hash）；`ContentRecord` 加可选 `evidence_context_bindings={refId:{scheme,hash}}`。旧 `evidence_context_hashes` 仍指旧全文，不重解释。影响范围：sources新增纯解析器；github_client在raw HTML仍可用时生成上下文、webEvidence传给完整及已绑定片段；evidence匹配/刷新保留全文hash审计，只有两端有效同版本v2才比较v2；content资格检查严格校验binding与当前上下文，缺失、错版、畸形hash或无完整来源对应均拒绝；models补可选类型。pipeline快照/事实拷贝须确认不丢字段，validation仍经资格检查拒绝异常绑定；页面来源日期/版本/入口失效逻辑不变，新增字段不直接展示，也不改变公共事实字段。REST cache/304不能凭旧缓存制造v2；需要完整原始输入，或已验证且完整保存的同版上下文及原有身份绑定。

**建立基线与迁移。** 新采集可附待审v2，只有新编辑审核显式绑定后才参与发布。旧片段没有v2时继续旧全文保护：首次接纳v2只允许当前完整 seed_v1 哈希与旧绑定 `source_hash` 完全相同，或有独立审核记录逐项核对当前正文/链接/资产后显式重绑；前者只证明文本基线连续，不把原本未审核的链接/资产宣称已审核。两者都不能自动清sticky、替旧curation改状态或改历史hash。FreeTube现存只有旧规范化全文，缺旧HTML/资产，不能由11→12文本diff推导旧v2，更不能自动迁移；单项re-review当前完整来源即可，无需其余seed迁移。旧ref/新source混合、解析歧义和不支持版本均维持待复核。

**最小离线验收。** 固定真实HTML及其hash，结构化改导航12→11：全文hash不同、v2相同；原片段不动而分别新增费用/系统条件/许可限制、改Beta/Pre-release、tag/title、href、资产src/完整清单：v2必须变化并撤回。正文出现Pull requests或数字变化必须保留。另测计数结构伪造/重复nav/身份不符/空正文/未闭合DOM/资产抓取失败、旧无v2与错版绑定、首次全文不一致、sticky二次刷新、旧seed全部回归、snapshot/页面不错误放行。验收只能证明边界机制，不能估计全站误撤率；若暂不承担资产获取与归档，最安全的简化方案是保持全文规则，只对FreeTube做独立重审，不先发布半套v2。

当前决策：本轮先保留已核实的误撤回和完整审计，维持保护；该提案仍需完整结构、资产、迁移与独立评审后才能实现，不作为既有开发授权之外的额外用户审批要求。
