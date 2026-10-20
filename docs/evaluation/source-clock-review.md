# 来源刷新与采集时钟独立复审

结论：本轮发现的两个问题均已修复，独立复测通过；在审查的来源映射、缓存白名单、全文上下文保护及采集 cutoff 范围内，没有剩余阻断问题。此结论不涉及模型语义评分、生产上线或长期运行效果。

审查只读检查 `gitradar/content.py`、`evidence.py`、`github_client.py`、`pipeline.py`、`sources.py` 及对应测试，未修改代码、正式数据或暂存区。本文是唯一新增文件。没有下载模型或访问私有评测目录。

## 首次发现与修复后的结果

1. **身份冲突响应绕过缓存白名单。** 首次合成一个带 ETag、`node_id` 已更换的仓库响应，`readProjectEvidence()` 虽返回身份错误，cache 中仍保留 `temp_clone_token`、`permissions`、`stargazers_count`；原因是检查身份先抛错，清洗没有执行。修复将元数据白名单清洗置于身份检查前。独立重跑 HTTP 200，以及带正确认证范围的历史 ETag cache + HTTP 304 两条路径，均确认身份仍被拒绝、三个多余字段不再进入返回缓存、旧证据没有被刷新日期。只使用合成字段值，未打印实际凭据。
2. **显式带时区 asOf 的 UTC 日期错误。** 首次 `2026-10-21T01:00:00+08:00` 离线运行被允许，却把 `utc_date` 写成 21 日；此为原有字符串取日前缀的输入限制。修复在 run 入口及完成 cutoff 统一转换 UTC/Z。独立重跑该输入，得到 `2026-10-20T17:00:00Z`；反向跨日输入 `2026-10-19T23:00:00-02:00` 得到 `2026-10-20T01:00:00Z`，报告日期均为 20 日，原仓库 history 字节保持不变。

## 时钟及来源边界

独立运行：

```text
PYTHONPATH=.:tests python3 -m unittest test_v4_client test_v4_content test_v4_evidence test_v4_pipeline test_v4_sources
Ran 110 tests ... OK
```

这包含首次审查的 108 项及新增两项回归。live 生成时间包含采集中完成的来源/路径检查；显式 asOf 与 offline 的 cutoff 保持固定，未来来源不会因此被接受。跨 UTC 午夜会阻断，不以本地日期替代。额外直接检查带 offset 的完成时刻：当地日期已变但 UTC 同日可正常规范化；UTC 跨日、早于开始及无时区时间均拒绝。

旧 `source_kind=repository` 的 `/license` 按真实文档读取，不再冒充仓库根元数据；仓库 API 的 `html_url` 事实与证据请求 URL 分开保存。文档片段不变可保留已审核内容 hash，但全文 hash 变化仍触发 context guard；根元数据按绑定字段比较，Star 等无关字段不再造成内容变更。现有回归均通过。

`git diff --check` 通过。上述额外复现均使用临时目录或内存合成响应，没有改写正式 `data/history.json`。

最终复审源码 SHA256：

- `gitradar/content.py`：`634acd7d24f1c66f6b7ac9116c393807e1ca6fbed2e0d7a2b33dc4b08878dd41`
- `gitradar/evidence.py`：`1d6760509be3c14045e03167287baca459bf97f5b5e53d96f596ae3b3d17dc29`
- `gitradar/github_client.py`：`af8c92341c5d26c1c309e03232a416c1acd868d1dd1de9f76bcc0f1f2000ffde`
- `gitradar/pipeline.py`：`01e230901704e7d4b0c9163875079fc068f8022298b33f3b137f95e9f7c7e123`
- `gitradar/sources.py`：`eeafcfe77d7246c4afabb89a8a9fccc749c75d1abe90a267a0aa18c454d6e093`
