# GitRadar — 中文精选 + 自动发现候选

帮助中文用户发现还不了解、但可能喜欢的开源项目。

- **中文精选**：依据官方资料编辑整理用途、设备、前提和入口，方便判断是否适合自己。
- **自动发现候选**：持续搜索和观察 GitHub 项目，保留原简介、真实 Star 快照及已有规则能提取的资料线索；资料不足，不编写中文完整解读。
- **生产零模型、零 AI API**：使用 Python 标准库、静态网页和 GitHub Actions，无需本地电脑常驻或额外硬件。GitHub API 用于读取公开项目资料。

[访问网站](https://w452187971.github.io/gitradar/) · [项目记录](docs/CHAT_HISTORY.md)

## 如何使用

首页先看6项中文精选，可继续展开；按场景探索、搜索、设备筛选和浏览器本地收藏帮助缩小范围。完整候选页提供原项目入口、分类/安装线索及1日、7日快照净变化。

中文精选不是全自动中文解读，也不代表实际试用。费用、依赖和许可证以官方说明为准；来源变化、失效或资料到期会暂停推荐和相关入口，保留原核对日期。候选池是有限搜索结果，不是 GitHub 全站榜单。

## 运行与检查

环境：Python 3.12、Node.js 22，无第三方依赖。

```sh
python3 -m unittest discover -s tests
node --test tests/*.test.cjs
python3 collect.py --offline --output-dir .v4-preview
python3 -m http.server 8000 --directory .v4-preview
```

真实采集使用环境变量 `GH_API_TOKEN`（Actions使用内置 `GITHUB_TOKEN`），先写隔离目录，再验证并提升：

```sh
python3 collect.py --output-dir .v4-output
python3 collect.py --output-dir .v4-output --promote-only --publish-to .
```

离线预览不能发布。提升会重验历史与产物哈希；正式文件已变化时拒绝覆盖。`data/curation.json` 和 `data/seed-evidence.json` 不由采集器改写。

## 自动更新与发布

每日计划 UTC 02:23（北京时间10:23），也可手动运行，调度可能延迟。正常链路为离线测试→隔离采集/校验→提升→普通提交推送；main随后显式请求 Pages 构建并有限核对同一提交，实际上线验证以运行记录为准。非main分支与诊断不发布，失败保留附件；不会force push。

`probe_only` 保留为轻量 GitHub API 访问诊断，不采集或发布。生产流程不含模型入口；两个历史模型对照workflow已禁用，脚本与原始报告仅保留研究出处。

**必须保留 `data/history.json`**，部署或恢复时不可用空文件/旧包覆盖。快照按UTC日期保存；缺基准显示未知，负增长照实保留，失败不冒充新观测。来源资料14天、入口7天后需复核，失败不刷新原日期。完整候选页可查看评分、覆盖范围与刷新状态。

## 文件与历史边界

`gitradar/` 处理采集、证据、内容资格和静态生成；`web/templates/`、`web/assets/` 是页面源；根HTML及 `projects/` 是生成产物。`build-manifest.json` 记录同批产物哈希，`tests/` 保存离线回归。

[V4范围](docs/V4_PRODUCT_DESIGN.md) · [证据记录](docs/evaluation/seed-review.md) · [历史评估](docs/evaluation/)

历史模型、独立样本、真实读者和持续运行评估仍按原记录保留未验证边界，不作为本次“中文精选 + 自动候选”上线的新增前置条件。
